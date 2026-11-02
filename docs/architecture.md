# Sense Platform — Architecture & Code Review

Based on a read-through of the repository (services, SDKs, compose, examples).
Items marked **[verified]** were confirmed by reading the code; nothing here was executed end to end.

## 1. Services

| Service | Port | Stack | Role |
|---|---|---|---|
| Relay | 7880 | LiveKit server | WebRTC SFU. Default key `sense_gateway` / `secret_change_in_production` |
| Mind | 8080 | Python, FastAPI | Agent engine: one `SenseMind` per room, managed by `AgentPool` |
| Gate | 3000 | FastAPI, Postgres, Redis | API keys → tenants, JWT, relay tokens, agent orchestration, webhooks, usage |
| Wire | 3001 | FastAPI, Postgres, Redis | WebSocket chat + REST; Redis pub/sub fan-out |
| Console | 4000 | Next.js | Dashboard (dashboard, rooms, agents, keys, webhooks, usage) |

## 2. Request flows

**Start an agent.** Client → `POST Gate /agents/start` (API key) → `AgentService` namespaces the room per tenant (`<tenant_slug>__<room>`) → `POST Mind /agents/start` → `AgentPool.start()` builds a `SenseMind` and runs `_run_agent_in_room` (`authenticate` → `create_call` → `join`) as an asyncio task.

**Join a room.** Client → `POST Gate /rooms/{id}/join` → Gate mints a LiveKit access token → client connects to Relay directly.

**Vision events.** Lens fires `LensEvent` → `AgentPool` listener → `LensEventBridge.forward()` → `POST Wire /internal/events` (service key; routed by tenant id + room id) → Redis pub/sub → WebSocket clients (`@sense/lens`, `sense.LensStream`).

**Auth.** Gate issues HS256 JWTs; Wire validates them with the same `JWT_SECRET` (shared via compose).

## 3. Sense Mind internals

- `mind.py` — `SenseMind(Agent)`; wires `RelayTransport` and reads `SENSE_RELAY_*` env vars.
- `transport/relay_transport.py` — `RelayTransport(EdgeTransport)` using `livekit.api` / `livekit.rtc`. Subscribed audio tracks become `AudioReceivedEvent`s; `publish_tracks` publishes the agent's audio; `send_custom_event` uses LiveKit data messages.
- `pool.py` — `AgentPool`: one agent per room, idempotent start, lens registry (`MoodLens`, `PoseLens`, `GuardLens`, `FaceLens`), `_resolve_llm` dispatching on model-name substring.
- `runner.py` — `SenseRunner`: FastAPI control API + signal handling; legacy single-agent mode via `SENSE_ROOM`.
- `bridge.py` — `LensEventBridge`: best-effort HTTP forwarder (5 s timeout, errors swallowed at debug level).
- `lenses/` — `BaseLens` (throttle + callbacks) and four YOLO lenses. `LensEvent.context_text` is the string meant for LLM context.
- `core/` — vendored Vision-Agents engine (agents, LLM/STT/TTS/VAD, MCP, observability, events). `plugins/` — 23 provider packages.

Mind control API: `GET /health`, `GET /status`, `GET /agents/status`, `POST /agents/start`, `POST /agents/stop`, `GET /agents/{room}/lenses`, `POST /agents/{room}/lenses/{lens_name}/configure`, `POST /shutdown`.

## 4. Gate / Wire surface

Gate: `/auth/token`, `/rooms/{id}/join`, `/rooms`, `/agents/{start,stop,status}`, `/tenants` (+ `/me`, `/me/api-keys`), `/webhooks` (+ `/{id}/test`), `/usage`, `/health`. There is **no** `/auth/register`.
Wire: `WS /ws/connect?token=<jwt>`, channel CRUD + members, `/channels/{type}/{id}/messages`, pin/delete, `/channels/{type}/{id}/event`. WebSocket events: subscribe/unsubscribe, message.new/delete, reactions, typing, read marks, custom.

## 5. Findings and resolution

All items from the initial code review have been fixed. Tests cover the Mind pipeline
(`services/mind/tests`), Gate (`services/gate/tests`) and Wire (`services/wire/tests`).

| # | Finding | Resolution |
|---|---------|-----------|
| 1 | Core imported `getstream` / `vision_agents` | Imports rewritten to `sense_mind.*`; new local `core/utils/pcm.py` (`PcmData`, `AudioFormat`, `AudioStreamTrack`); Twilio bridge re-implemented on LiveKit. `tests/test_no_getstream.py` enforces it. |
| 2 | Lenses never received frames | `BaseLens` is now a `VideoProcessor` registered in `Agent.processors`; `RelayTransport` subscribes to video tracks (`add_track_subscriber`) and `BaseLens` samples frames at `sample_fps`, running YOLO in a worker thread. Lens context is injected into the LLM instructions (`SenseMind._on_lens_event`). |
| 3 | Mind image had no vision deps | Dockerfile installs CPU torch + `.[vision,...]`, copies source before install, runs pool mode by default. |
| 4 | Gate rate limiting inert | Middleware resolves `app.state.redis` per request; unique sorted-set members; `/health` exempt. |
| 5 | `asyncio.coroutine` in `BaseLens._emit` | Replaced; delivery is thread-safe via `call_soon_threadsafe`. |
| 6 | Guard event flood | Guard uses `force=True`; `LensEventBridge` caps each (room, lens) at one event per 0.5 s. |
| 7 | `get_lenses` never 404'd | Returns `None` for unknown rooms. |
| 8 | Lens identifiers / `enabled` | Lenses addressable by class or snake_case name; `enabled` is honoured by `_emit` and frame sampling. |
| 9 | Plaintext API keys | SHA-256 hash + prefix stored (migration `002`); raw key shown once at creation (tenant creation and key creation). Console and Python SDK updated. |
| 10 | Failed joins reported as `started` | `AgentPool.start` waits for the Relay join and returns `failed` (HTTP 502 from Mind); Gate propagates Mind errors (no fake `queued`). |
| 11 | CORS wildcard with credentials | `CORS_ORIGINS` setting; credentials only with explicit origins. |
| 12 | Hardcoded secrets | Relay/service secrets come from env in compose; Gate warns at start when defaults are used outside debug mode. |
| 14 | `create_call` swallowed errors | Errors now raise with context. |
| 15–16 | Stale docstrings/docs | Fixed. |
| 17 | Duplicate example | `examples/contact_center` removed; `contact-center` is canonical. |
| 18 | No tests | Added (see above). |

Additional defects found and fixed along the way:

- `RelayTransport` used `events.emit` (EventManager only has `send`), built `AudioReceivedEvent` with the wrong fields, and `SenseMind` imported `User` from the wrong module.
- The pool/runner called `edge.join()` directly, bypassing the `Agent` pipeline (STT/LLM/TTS never started). They now use `agent.join()` + `agent.finish()`.
- `LensEventBridge` posted to a JWT-protected Wire endpoint with the wrong header and payload shape. It now uses Wire's service-authenticated `POST /internal/events` (`X-Service-Key` = `SENSE_SERVICE_KEY`) and routes by tenant id + room id supplied by Gate.
- The Python SDK called Gate routes that do not exist (`/tenants/keys`, `/webhooks/register`, `/usage/summary`, per-room GET/DELETE). It now matches Gate; Gate gained `GET /agents/lenses` and `POST /agents/lenses/{lens}/configure` proxies.
- `mcp` is pinned `<2` (2.x renamed the client API used by `core/mcp`), and runtime deps missing from `pyproject.toml` were added.

Known remaining limitations:

- Publishing agent *video* to Relay is not supported (audio only).
- The Python SDK's `channels.*` REST helpers still target paths that Wire does not expose; use `SenseWire` (WebSocket) for chat.
- `CLAUDE.md`'s auto-save rule points at an author-local Windows path.

## 6. Next steps

1. Run the full stack (`docker compose up`) with real YOLO weights and verify lens events reach a browser through Wire.
2. Publish agent video to Relay and add integration tests against a live LiveKit server.
3. Bring the Python SDK's channel helpers in line with Wire's REST surface.
