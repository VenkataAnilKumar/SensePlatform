<div align="center">

# Sense Platform

**Self-hosted developer platform for AI-powered video, voice, and vision applications.**

Build products that see, hear, and understand — with zero cloud lock-in.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-compose%20up-brightgreen)](docker-compose.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](sdks/sense-py)
[![TypeScript](https://img.shields.io/badge/typescript-5.x-blue)](sdks/sense-js)

[Quick Start](#quick-start) · [Architecture](#architecture) · [SDKs](#sdks) · [Examples](#examples) · [Docs](docs/quickstart.md)

</div>

---

## What is Sense Platform?

Sense Platform is a complete, self-hosted alternative to GetStream — rebuilt from scratch for AI-first products. Every component runs on your own infrastructure: no cloud accounts required, no per-seat pricing, no vendor lock-in.

**Drop it in and get:**
- WebRTC video/voice rooms (self-hosted LiveKit SFU)
- AI agents that join calls, see participants, and speak back
- Real-time vision intelligence — emotion, pose, face, moderation
- REST + WebSocket APIs that mirror Stream's surface area
- A developer dashboard at `localhost:4000`

---

## What you can build

| Product | Vision Lenses | What the AI does |
|---------|--------------|------------------|
| **AI Contact Center** | MoodLens · FaceLens | Adapts tone to customer emotion; escalates frustrated callers |
| **Sales Coach** | MoodLens · PoseLens | Silent whisper coaching — spots buying signals, flags objections |
| **Fitness Coach** | PoseLens · FaceLens | Real-time form corrections; counts reps; detects rest periods |
| **Telehealth** | FaceLens · PoseLens · MoodLens | Logs patient observations; flags distress for the physician |
| **Security SOC** | FaceLens · GuardLens | Zone occupancy; weapon/threat detection; auto-incident creation |

---

## Architecture

```
                          ┌────────────────────────────────────┐
   Browser / Mobile ──────►          Sense Gate  :3000          │
   SDK Client       ◄──────        REST · Auth · Tenants        │
                          └──────────────┬─────────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────┐
              │                          │                      │
   ┌──────────▼─────────┐   ┌────────────▼──────────┐   ┌──────▼──────────────┐
   │   Sense Relay      │   │    Sense Mind  :8080   │   │   Sense Wire :3001  │
   │   WebRTC SFU :7880 │◄──│  AI Agents + Lenses   │──►│   WebSocket Chat    │
   │   (LiveKit engine) │   │  Multi-agent Pool     │   │   Redis Fan-out     │
   └────────────────────┘   └───────────────────────┘   └─────────────────────┘
              ▲                         │  LensEventBridge               ▲
              │                         └────────────────────────────────┘
   ┌──────────┴──────────────────────────────────────────────────────────────┐
   │              Postgres (data)  ·  Redis (state · pub/sub)                │
   └─────────────────────────────────────────────────────────────────────────┘
              ▲
   ┌──────────┴──────────┐
   │  Sense Console :4000 │
   │  Developer Dashboard │
   └─────────────────────┘
```

### Services at a glance

| Service | Role | Port |
|---------|------|-----:|
| **Sense Relay** | Self-hosted WebRTC SFU — media routing, no cloud | 7880 |
| **Sense Mind** | AI agent engine — LLM · STT · TTS · Vision Lenses | 8080 |
| **Sense Gate** | REST API gateway — auth, multi-tenancy, webhooks | 3000 |
| **Sense Wire** | Real-time WebSocket messaging with Redis fan-out | 3001 |
| **Sense Console** | Next.js developer dashboard | 4000 |

### Vision Lenses

Lenses are throttled vision processors that inject context directly into the agent's LLM prompt.

| Lens | Detects | Default throttle |
|------|---------|:----------------:|
| **MoodLens** | Emotion — frustrated · confused · satisfied · happy | 3 s |
| **PoseLens** | Body pose — keypoints, posture, form faults | 2 s |
| **GuardLens** | Safety — weapons, explicit content, fire, tailgating | 2 s |
| **FaceLens** | Presence — face count, occupancy, identity continuity | 5 s |

---

## Quick Start

**Prerequisites:** Docker Desktop · one LLM API key (Anthropic recommended)

### 1 — Clone and configure

```bash
git clone https://github.com/VenkataAnilKumar/SensePlatform
cd SensePlatform
cp .env.example .env
```

Open `.env` and set at minimum:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### 2 — Start the platform

```bash
docker compose up
```

All five services start automatically. First run pulls images (~2 min). After ~30 s everything is ready:

```
http://localhost:4000    Sense Console  — developer dashboard
http://localhost:3000    Sense Gate     — REST API
ws://localhost:3001      Sense Wire     — WebSocket messaging
http://localhost:8080    Sense Mind     — agent control API
ws://localhost:7880      Sense Relay    — WebRTC server
```

### 3 — Open the Console

Navigate to **http://localhost:4000** → API Keys → **Create key**.

### 4 — Start your first AI agent

```bash
curl -X POST http://localhost:3000/agents/start \
  -H "X-API-Key: sk_live_your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": "demo",
    "lenses": ["MoodLens"],
    "llm": "claude-sonnet-4-6",
    "instructions": "You are a helpful assistant. Adapt to the user emotional state."
  }'
```

The agent joins the room, activates MoodLens, and starts listening for participants.

---

## SDKs

### Python

```bash
pip install sense-platform
```

```python
import asyncio
from sense import SenseClient, SenseWire, LensStream

async def main():
    async with SenseClient(api_key="sk_live_...") as client:
        await client.connect()

        await client.agents.start("demo", lenses=["MoodLens"])

        async with SenseWire(client, "messaging", "demo") as wire:
            stream = LensStream(wire)

            @stream.on_mood
            def on_mood(event):
                print(f"{event.mood} ({event.confidence:.0%}) — {event.context_text}")

            wire.on_message(lambda msg: print(f"{msg.user_id}: {msg.text}"))
            await wire.send("Hello from Python!")
            await wire.wait()

asyncio.run(main())
```

### TypeScript / JavaScript

```bash
npm install @sense/core @sense/vision @sense/chat @sense/lens
```

```typescript
import { SenseClient } from "@sense/core";
import { SenseRoom }   from "@sense/vision";
import { Channel }     from "@sense/chat";
import { LensStream }  from "@sense/lens";

const client = new SenseClient({ apiKey: "sk_live_..." });
await client.connect();

const room = new SenseRoom(client);
await room.join({ roomId: "demo", autoPublish: true });

const channel = new Channel(client.wire, "messaging", "demo");
await channel.sendMessage("Hello from the browser!");

const lenses = new LensStream(client.wire, "demo");
lenses.onMood((e) => console.log(`${e.mood} — ${e.contextText}`));
```

### Sense Mind Agent SDK

Build custom AI agents that join rooms, speak, and see:

```python
from sense_mind import SenseMind, SenseRunner
from sense_mind.plugins import anthropic, deepgram, elevenlabs
from sense_mind.lenses import MoodLens, PoseLens

agent = SenseMind(
    instructions="""
        You are a supportive contact center agent.
        When the customer is frustrated, acknowledge it first.
        When confused, slow down and speak in plain language.
    """,
    llm=anthropic.LLM("claude-sonnet-4-6"),
    stt=deepgram.STT(),
    tts=elevenlabs.TTS(),
    lenses=[MoodLens(throttle_seconds=3), PoseLens()],
)

SenseRunner(agent, room="support-room-1").serve()
```

#### Supported plugins

| Category | Options |
|----------|---------|
| **LLM** | `anthropic` · `openai` · `gemini` · `mistral` · `openrouter` · `xai` |
| **STT** | `deepgram` · `assemblyai` · `fast_whisper` |
| **TTS** | `elevenlabs` · `cartesia` · `kokoro` · `fish` · `pocket` |
| **Vision** | `ultralytics` (YOLO) · `moondream` · `roboflow` · `nvidia` |

---

## Multi-Agent API

Sense Mind manages multiple agents concurrently — one per room:

```bash
# Launch an agent
curl -X POST http://localhost:8080/agents/start \
  -d '{"room": "acme__room-1", "lenses": ["MoodLens"], "llm": "claude-sonnet-4-6"}'

# Stop an agent
curl -X POST http://localhost:8080/agents/stop \
  -d '{"room": "acme__room-1"}'

# Live status of all agents
curl http://localhost:8080/agents/status

# Tune lens throttle at runtime — no restart needed
curl -X POST http://localhost:8080/agents/acme__room-1/lenses/mood_lens/configure \
  -d '{"throttle_seconds": 5.0, "enabled": true}'
```

---

## Examples

Ready-to-run examples in [`examples/`](examples/):

```
examples/
├── contact-center/   # Emotion-aware support agent (MoodLens + FaceLens)
├── sales-coach/      # Silent rep coach — spots buying signals (MoodLens + PoseLens)
├── fitness-coach/    # Real-time form correction + rep counting (PoseLens)
├── telehealth/       # Clinical session assistant (FaceLens + PoseLens + MoodLens)
└── security-soc/     # Zone monitoring + threat detection (FaceLens + GuardLens)
```

Run any example:

```bash
# Contact center agent
ANTHROPIC_API_KEY=sk-ant-... \
SENSE_ROOM=support-demo \
python examples/contact-center/agent.py

# Security SOC — restricted zone
ZONE_TYPE=restricted \
ZONE_ID=server-room-a \
python examples/security-soc/agent.py
```

---

## Documentation

| Doc | Description |
|-----|-------------|
| [Quick Start](docs/quickstart.md) | Up and running in 5 minutes |
| [Architecture](docs/architecture.md) | How the five services connect |
| [Self-Hosting Guide](docs/self-hosting.md) | TLS, backups, scaling, production checklist |
| [Python SDK Reference](docs/python-sdk.md) | Full API reference for `sense-platform` |
| [Building a Contact Center](docs/products/contact-center.md) | End-to-end product tutorial |

---

## Project Status

All eight phases complete.

| Phase | What shipped |
|-------|-------------|
| ✅ 1 | Sense Relay · Sense Mind · Vision Lenses · Docker Compose |
| ✅ 2 | Sense Gate — FastAPI, JWT auth, multi-tenancy, webhooks, usage metering |
| ✅ 3 | Sense Wire — WebSocket messaging, Postgres persistence, Redis pub/sub |
| ✅ 4 | sense-js SDK — `@sense/core` · `@sense/vision` · `@sense/chat` · `@sense/lens` |
| ✅ 5 | Sense Console — Next.js developer dashboard |
| ✅ 6 | Multi-agent pool · LensEventBridge · Vision Event Stream · `/agents` API |
| ✅ 7 | sense-py SDK · developer documentation |
| ✅ 8 | 5 product examples — contact-center · sales-coach · fitness-coach · telehealth · security-soc |

---

## License

Apache 2.0 — see [LICENSE](LICENSE)