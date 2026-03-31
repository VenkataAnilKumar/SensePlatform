# Sense Platform — Claude Instructions

> This file gives Claude persistent memory, long context, and project rules for the SensePlatform codebase.
> All instructions here OVERRIDE default behavior. Follow them exactly.

---

## Project Identity

**Name**: Sense Platform
**Tagline**: "Build AI-powered video, voice, and chat applications with real-time intelligence in hours, not weeks."
**GitHub**: https://github.com/VenkataAnilKumar/SensePlatform
**License**: Apache 2.0
**Owner**: VenkataAnilKumar
**Local path**: `V:/AI Engineer/GitHub/SensePlatform/`

---

## What This Project Is

Sense Platform is a **self-hosted, open-source developer platform** for building vision-AI products.

It is a **direct competitor to GetStream** — we recreate all of Stream's infrastructure from scratch with original names so developers have zero cloud dependency. Everything runs on their own servers.

### Products developers can build with it:
1. **AI Contact Center** — emotion-aware agent adapts to customer mood in real time
2. **Sales Coach** — AI coaching whispers during live sales calls
3. **Fitness Coach** — real-time body form correction with YOLO
4. **Telehealth** — patient presence, identity, and posture monitoring
5. **Security SOC** — occupancy tracking and content moderation

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                         Sense Platform                             │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │ Sense Relay  │  │  Sense Mind  │  │      Sense Gate        │   │
│  │  WebRTC SFU  │◄─│  AI Agents   │  │  API + Auth + Tenants  │   │
│  │  (LiveKit)   │  │  + Lenses    │  │                        │   │
│  └──────────────┘  └──────────────┘  └────────────────────────┘   │
│         ▲                 ▲                      ▲                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │    Redis     │  │  Sense Wire  │  │    Sense Console       │   │
│  │  Room State  │  │  Real-time   │  │  Developer Dashboard   │   │
│  │   Pub/Sub    │  │  Messaging   │  │                        │   │
│  └──────────────┘  └──────────────┘  └────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

---

## Services — Names, Ports, Status

| Service | Original Name | Description | Port | Status |
|---------|--------------|-------------|------|--------|
| **Sense Relay** | Replaces Stream Video (WebRTC cloud) | Self-hosted WebRTC SFU (LiveKit engine) | 7880 | ✅ Phase 1 |
| **Sense Mind** | Replaces Vision-Agents + Stream transport | AI agent engine, LLM + STT + TTS + Lenses | 8080 | ✅ Phase 1 |
| **Sense Gate** | Replaces Stream API gateway | REST API, JWT auth, multi-tenancy | 3000 | ✅ Phase 2 |
| **Sense Wire** | Replaces Stream Chat | Real-time WebSocket messaging | 3001 | ✅ Phase 3 |
| **Sense Console** | Replaces Stream Dashboard | Developer dashboard UI | 4000 | ✅ Phase 5 |

---

## Directory Structure

```
SensePlatform/
├── services/
│   ├── relay/                          # Sense Relay — WebRTC media server
│   │   └── sense-relay.yaml            # LiveKit config with Sense API keys
│   ├── mind/                           # Sense Mind — AI agent engine
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── sense_mind/
│   │       ├── __init__.py             # exports SenseMind, SenseRunner
│   │       ├── mind.py                 # SenseMind agent class
│   │       ├── runner.py               # SenseRunner lifecycle manager
│   │       ├── transport/
│   │       │   └── relay_transport.py  # ⚡ CRITICAL: EdgeTransport via LiveKit
│   │       ├── lenses/                 # Vision processors
│   │       │   ├── base_lens.py        # BaseLens ABC + LensEvent
│   │       │   ├── mood_lens.py        # Customer emotion detection
│   │       │   ├── pose_lens.py        # Body pose + form analysis
│   │       │   ├── guard_lens.py       # Content moderation
│   │       │   └── face_lens.py        # Face detection + occupancy
│   │       ├── core/                   # Agent core (adapted from Vision-Agents)
│   │       └── plugins/                # 17 AI plugins (LLM/STT/TTS)
│   ├── gate/                           # Sense Gate (Phase 2)
│   └── wire/                           # Sense Wire (Phase 3)
├── sdks/
│   ├── sense-py/                       # Python developer SDK (Phase 7)
│   └── sense-js/                       # JavaScript SDK (Phase 4)
├── examples/
│   └── contact_center/agent.py         # Phase 1 validation example
├── docker-compose.yml                  # One-command startup
├── .env.example
├── CLAUDE.md                           # This file
└── README.md
```

---

## Key Technical Decisions

### Why relay_transport.py is the most important file
Vision-Agents core is built on `getstream[webrtc]` for all WebRTC primitives.
`relay_transport.py` implements the `EdgeTransport` ABC using `livekit.api` and `livekit.rtc` instead.
This **single file** makes ALL 35+ existing Vision-Agents plugins work on self-hosted infrastructure without any GetStream account or cloud dependency.

### Lens throttle system
`BaseLens._emit()` enforces `throttle_seconds` between events.
This is critical — without it, 30fps video = 30 LLM context updates/second = broken agent.
Default throttles: MoodLens=3s, PoseLens=2s, GuardLens=2s, FaceLens=5s.
GuardLens bypasses throttle on violations (auto_action=True) for safety.

### LensEvent.context_text
This is the string that gets injected into the LLM's system context.
It must be human-readable, actionable, and concise (1-2 sentences max).
The LLM reads this mid-conversation to adapt its response in real time.

### Plugin system
Keep the Vision-Agents plugin-per-package model.
Each plugin is a separate directory under `sense_mind/plugins/`.
Import them by name: `from sense_mind.plugins import anthropic, deepgram`.
**Never import the getstream plugin** — it does not exist in this codebase.

---

## Naming Rules — ALWAYS Follow These

These names are final. Never rename them to match source repos.

| Our Name | DO NOT use |
|----------|-----------|
| Sense Relay | LiveKit Server, Stream Video |
| Sense Mind | Vision Agents, Stream AI |
| Sense Gate | Stream API |
| Sense Wire | Stream Chat |
| Sense Console | Stream Dashboard |
| SenseMind | VisionAgent, StreamAgent |
| SenseRunner | AgentRunner |
| RelayTransport | GetStreamTransport |
| MoodLens | EmotionProcessor |
| PoseLens | PoseProcessor |
| GuardLens | ModerationProcessor |
| FaceLens | SecurityProcessor |
| LensEvent | ProcessorEvent |
| BaseLens | BaseProcessor |

---

## Hard Rules

1. **NO GetStream dependencies** — never add `getstream`, `stream-chat`, `stream-video`, or `getstream[webrtc]` to any requirements file.
2. **NO cloud-mandatory services** — all services must be runnable 100% self-hosted with `docker compose up`.
3. **Keep original Sense names** — all service/class/module names follow the table above.
4. **Lenses use ultralytics** — all vision processing is via YOLO (ultralytics package), never OpenCV-only.
5. **Plugins stay modular** — don't merge plugins into core. Each LLM/STT/TTS is its own plugin directory.
6. **Never commit model weights** — `.pt`, `.onnx`, `.engine` files are in `.gitignore`. Users download them.
7. **Never commit `.env`** — only `.env.example` is committed.
8. **Relay config key** — the default key is `sense_gateway: secret_change_in_production`. Always remind users to change this in production.

---

## Build Phases

| Phase | What | Status |
|-------|------|--------|
| 1 | Sense Relay + Sense Mind + Lenses + docker-compose | ✅ Done (2026-03-30) |
| 2 | Sense Gate — FastAPI, JWT auth, tenant management, REST API | ✅ Done (2026-03-30) |
| 3 | Sense Wire — WebSocket chat, Postgres persistence, Redis pub/sub | ✅ Done (2026-03-30) |
| 4 | sense-js SDK — `@sense/core`, `@sense/vision`, `@sense/chat`, `@sense/lens` | ✅ Done (2026-03-30) |
| 5 | Sense Console — developer dashboard (shadcn/ui + Next.js) | ✅ Done (2026-03-30) |
| 6 | Vision pipeline hardening — Processor Config API, Vision Event Stream | 🔲 Next |
| 7 | sense-py SDK + full developer documentation | 🔲 |
| 8 | 5 product examples — contact-center, sales-coach, fitness-coach, telehealth, security-soc | 🔲 |

---

## Sense Gate — Phase 2 Plan (Next)

Build `services/gate/` — FastAPI-based API gateway.

### Responsibilities:
- **Authentication** — JWT token issuance and validation
- **Multi-tenancy** — each product/customer = one tenant, namespaced rooms
- **Relay token vending** — generate LiveKit access tokens for frontend clients
- **Agent orchestration** — start/stop Sense Mind agent instances via REST
- **Webhook delivery** — emit events (call started, mood detected, etc.) to tenant endpoints
- **Usage metering** — track API calls, minutes, participants per tenant

### Key endpoints:
```
POST /auth/token                — issue JWT for a user
POST /rooms/:room_id/join       — get LiveKit token for a room
POST /agents/start              — launch a SenseMind agent in a room
POST /agents/stop               — shut down an agent
GET  /tenants/:id/usage         — usage stats
POST /webhooks/register         — register a tenant webhook
```

### Tech stack:
- FastAPI + Uvicorn
- PostgreSQL (tenant data, API keys)
- Redis (token cache, rate limiting)
- python-jose (JWT)
- Alembic (migrations)

---

## Sense Wire — Phase 3 Plan

Build `services/wire/` — real-time messaging.

### Responsibilities:
- WebSocket server (per-room channels)
- Message persistence in Postgres
- Redis pub/sub for fan-out across instances
- Reaction, thread, and read-receipt support
- Attachments via S3-compatible storage

### API surface (mirrors Stream Chat for drop-in compatibility):
```
WS  /ws/connect                 — establish WebSocket connection
POST /channels/:type/:id/message — send message
GET  /channels/:type/:id/query  — fetch message history
POST /channels/:type/:id/event  — send custom event
```

---

## Sense Mind Plugins — Available

| Category | Plugin | Import |
|----------|--------|--------|
| LLM | Anthropic Claude | `from sense_mind.plugins import anthropic` |
| LLM | OpenAI | `from sense_mind.plugins import openai` |
| LLM | Gemini | `from sense_mind.plugins import gemini` |
| LLM | Mistral | `from sense_mind.plugins import mistral` |
| LLM | OpenRouter | `from sense_mind.plugins import openrouter` |
| LLM | xAI Grok | `from sense_mind.plugins import xai` |
| STT | Deepgram | `from sense_mind.plugins import deepgram` |
| STT | AssemblyAI | `from sense_mind.plugins import assemblyai` |
| STT | faster-whisper | `from sense_mind.plugins import fast_whisper` |
| TTS | ElevenLabs | `from sense_mind.plugins import elevenlabs` |
| TTS | Cartesia | `from sense_mind.plugins import cartesia` |
| TTS | Kokoro | `from sense_mind.plugins import kokoro` |
| Vision | Ultralytics YOLO | `from sense_mind.plugins import ultralytics` |
| Vision | Moondream VLM | `from sense_mind.plugins import moondream` |
| Vision | Roboflow | `from sense_mind.plugins import roboflow` |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SENSE_RELAY_URL` | `ws://localhost:7880` | WebSocket URL of Sense Relay |
| `SENSE_RELAY_API_KEY` | `sense_gateway` | Relay API key |
| `SENSE_RELAY_SECRET` | `secret_change_in_production` | Relay API secret |
| `SENSE_ROOM` | `default` | Default room name for agent to join |
| `ANTHROPIC_API_KEY` | — | Anthropic Claude API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `DEEPGRAM_API_KEY` | — | Deepgram STT key |
| `ELEVENLABS_API_KEY` | — | ElevenLabs TTS key |
| `SENSE_MIND_PORT` | `8080` | HTTP control API port |

---

## Auto-save Rule

After every completed phase or major milestone, save a session summary to:
`C:/Users/venka/.claude/projects/V--AI-Engineer-GitHub/memory/senseplatform_project.md`

Update the Phase Status table to reflect completed work.
