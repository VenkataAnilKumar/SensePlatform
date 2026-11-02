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

**Vision events.** Lens fires `LensEvent` → `AgentPool` listener → `LensEventBridge.forward()` → `POST Wire /channels/lens/{room}/event` → Redis pub/sub → WebSocket clients (`@sense/lens`, `sense.LensStream`).

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

## 5. Findings

Severity order. All **[verified]** by reading the cited code.

### High

1. **Core still depends on GetStream / vision_agents.** `core/edge/edge_transport.py`, `core/edge/events.py`, `core/agents/agents.py` (`getstream.Edge()` default, `AudioStreamTrack`, `PcmData`), `core/warmup.py`, `session_registry/*`, `agent_launcher.py`, and some plugins import `getstream` or `vision_agents`. `relay_transport.py` itself imports the local `sense_mind.core.edge.*`, which in turn import `vision_agents`. This breaks Hard Rule 1 and, unless `vision_agents` is installed, Mind will not import. Fix: rewrite the imports to `sense_mind.core.*`, and replace `getstream` types (`PcmData`, `AudioStreamTrack`) with local equivalents.
2. **Lenses never receive frames.** `SenseMind.add_processor` appends to `self._processors`, but `Agent` only dispatches video to `self.processors` filtered by `VideoProcessor`. `BaseLens` is not a `VideoProcessor`, and `RelayTransport.add_track_subscriber` returns `None` and never handles video tracks. So `process_frame()` is never called in the running service. Fix: make `BaseLens` implement the processor interface (or adapter), subscribe to video tracks in `RelayTransport`, and register lenses in `Agent.processors`.
3. **Real-time Mind docker image has no vision deps.** `services/mind/Dockerfile` installs `.[anthropic,deepgram,elevenlabs]` only; without `ultralytics` every lens sets `_available=False`.

### Medium

4. **Gate rate limiting is inert.** `app.add_middleware(RateLimitMiddleware, redis_client=None)` runs at construction time; the Redis client created in `lifespan` is never given to it, so the limiter always passes through.
5. **`BaseLens._emit` uses `asyncio.coroutine`**, removed in Python 3.11 (the image's version), so any synchronous callback raises `AttributeError`. It also calls `asyncio.ensure_future` without a running loop when invoked from a worker thread. Fix: wrap sync callbacks in a plain call and use `loop.call_soon_threadsafe`.
6. **`GuardLens` throttle bypass** is documented as intended; ensure violation events cannot flood Wire (the bridge has no rate cap).
7. **`AgentPool.get_lenses` returns `[]` for an unknown room**, so the 404 branch in `runner.py` (`lenses is None`) is unreachable.
8. **`configure_lens` matches on `lens.name`** (e.g. `mood_lens`), while pool start uses class names (`MoodLens`). The API takes inconsistent identifiers; also `enabled=False` only flips `_available` and is not checked by `_emit`.
9. **API keys are stored and compared in plaintext** (`ApiKey.key == raw_key`). Store a hash and look up by prefix.
10. **Agent task failures are invisible to callers**: `_run_agent_in_room` logs and returns, so `POST /agents/start` reports `started` even when the Relay join fails; status then shows `stopped`.
11. **CORS** is `allow_origins=["*"]` with `allow_credentials=True`; tighten for production.

### Low / hygiene

12. Default secrets (`secret_change_in_production`, `sense_jwt_secret_change_in_production`) are hardcoded in `docker-compose.yml`; compose passes the Relay secret literally rather than via env.
13. `api_key.last_used_at` is updated in the dependency without an explicit commit path being obvious.
14. `RelayTransport.create_call` swallows every exception as "already exists".
15. `SenseRunner` docstring says `/agents/{room}/lenses/configure`; the route is `/agents/{room}/lenses/{lens_name}/configure`.
16. `docs/quickstart.md` linked pages that did not exist and `POST /auth/register` that does not exist (fixed in this change).
17. Two divergent files: `examples/contact-center/agent.py` and `examples/contact_center/agent.py`.
18. No automated tests anywhere outside the vendored relay directory.
19. `CLAUDE.md` pointed at an author-local Windows path for memory saves; not applicable in this environment.

## 6. Suggested order of work

1. Remove `getstream` / `vision_agents` imports from `core/` (finding 1) — nothing else can be trusted until Mind imports cleanly.
2. Wire video → lenses (finding 2) and add `ultralytics` to the image (3).
3. Fix `_emit`, the middleware Redis injection, and the lens API identifiers (4, 5, 7, 8).
4. Hash API keys; add tests for Gate auth, Wire fan-out, and lens throttling.
