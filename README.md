# Sense Platform

> **Build AI-powered video, voice, and vision applications with real-time intelligence in hours, not weeks.**

Sense Platform is a self-hosted, open-source developer platform for building vision-AI products.
Zero cloud dependencies. Run everything on your own infrastructure.

---

## What you can build

| Product | Lenses Used | Description |
|---------|-------------|-------------|
| AI Contact Center | MoodLens | Agent adapts to customer emotion in real time |
| Sales Coach | MoodLens + PoseLens | Coaching whispers during live sales calls |
| Fitness Coach | PoseLens | Real-time form correction and rep counting |
| Telehealth | FaceLens + PoseLens | Patient presence, identity, and posture monitoring |
| Security SOC | FaceLens + GuardLens | Occupancy tracking and content moderation |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Sense Platform                           │
│                                                                 │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │ Sense Relay │   │  Sense Mind  │   │     Sense Gate       │ │
│  │  WebRTC SFU │◄──│  AI Agents   │   │  API Gateway + Auth  │ │
│  │  (LiveKit)  │   │  + Lenses    │   │  Multi-tenancy       │ │
│  └─────────────┘   └──────────────┘   └──────────────────────┘ │
│         ▲                  │                     ▲              │
│         │         LensEventBridge                │              │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │    Redis    │   │  Sense Wire  │◄──│   Sense Console      │ │
│  │  Room State │   │  Real-time   │   │  Developer Dashboard │ │
│  │   Pub/Sub   │   │  Messaging   │   │     :4000            │ │
│  └─────────────┘   └──────────────┘   └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Services

| Service | Description | Port | Status |
|---------|-------------|------|--------|
| **Sense Relay** | Self-hosted WebRTC SFU (built on LiveKit) | 7880 | ✅ |
| **Sense Mind** | AI agent engine — LLM + STT + TTS + Vision Lenses | 8080 | ✅ |
| **Sense Gate** | REST API gateway, JWT auth, multi-tenancy | 3000 | ✅ |
| **Sense Wire** | Real-time WebSocket messaging | 3001 | ✅ |
| **Sense Console** | Developer dashboard (Next.js) | 4000 | ✅ |

### Vision Lenses

| Lens | Purpose | Default Throttle |
|------|---------|-----------------|
| **MoodLens** | Customer emotion detection (frustrated / confused / satisfied) | 3s |
| **PoseLens** | Body pose tracking + form analysis | 2s |
| **GuardLens** | Content moderation + safety violation detection | 2s |
| **FaceLens** | Face detection + occupancy monitoring | 5s |

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- An API key for at least one LLM (Anthropic, OpenAI, or Gemini)

### 1. Clone and configure

```bash
git clone https://github.com/VenkataAnilKumar/SensePlatform
cd SensePlatform
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY (or OPENAI_API_KEY)
```

### 2. Start the full platform

```bash
docker compose up
```

All 5 services start automatically. After ~30 seconds:

| Service | URL |
|---------|-----|
| Sense Console (dashboard) | http://localhost:4000 |
| Sense Gate (REST API) | http://localhost:3000 |
| Sense Wire (WebSocket) | ws://localhost:3001 |
| Sense Mind (agent API) | http://localhost:8080 |
| Sense Relay (WebRTC) | ws://localhost:7880 |

### 3. Get an API key from the Console

Open http://localhost:4000 → sign in → API Keys → Create key.

Or via API:
```bash
# Create a tenant + API key (first-run setup)
curl -X POST http://localhost:3000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "My Company", "email": "admin@mycompany.com", "password": "secret"}'
```

### 4. Start an AI agent in a room

```bash
curl -X POST http://localhost:3000/agents/start \
  -H "X-API-Key: sk_live_your_key" \
  -H "Content-Type: application/json" \
  -d '{"room_id": "demo-room", "lenses": ["MoodLens"], "llm": "claude-sonnet-4-6"}'
```

---

## SDKs

### Python SDK

```bash
pip install sense-platform
```

```python
import asyncio
from sense import SenseClient, SenseWire, LensStream

async def main():
    async with SenseClient(api_key="sk_live_your_key") as client:
        await client.connect()

        # Launch AI agent with emotion detection
        await client.agents.start("demo-room", lenses=["MoodLens"])

        # Subscribe to real-time messages + lens events
        async with SenseWire(client, "messaging", "demo-room") as wire:
            stream = LensStream(wire)

            @stream.on_mood
            def handle_mood(event):
                print(f"Customer mood: {event.mood} — {event.context_text}")

            wire.on_message(lambda msg: print(f"{msg.user_id}: {msg.text}"))
            await wire.send("Hello from Python!")
            await wire.wait()

asyncio.run(main())
```

### JavaScript SDK

```bash
npm install @sense/core @sense/vision @sense/chat @sense/lens
```

```typescript
import { SenseClient } from "@sense/core";
import { SenseRoom }   from "@sense/vision";
import { Channel }     from "@sense/chat";
import { LensStream }  from "@sense/lens";

const client = new SenseClient({ apiKey: "sk_live_your_key" });
await client.connect();

// Join a WebRTC room
const room = new SenseRoom(client);
await room.join({ roomId: "demo-room", autoPublish: true });

// Real-time chat
const channel = new Channel(client.wire, "messaging", "demo-room");
await channel.sendMessage("Hello from JavaScript!");

// Vision lens events
const stream = new LensStream(client.wire, "demo-room");
stream.onMood((event) => {
  console.log(`Customer mood: ${event.mood} (${event.confidence})`);
});
```

---

## Sense Mind Agent SDK

Build custom AI agents directly with Sense Mind:

```python
from sense_mind import SenseMind, SenseRunner
from sense_mind.plugins import anthropic, deepgram, elevenlabs
from sense_mind.lenses import MoodLens, PoseLens

agent = SenseMind(
    relay_url="ws://localhost:7880",
    instructions="""
        You are a supportive contact center agent.
        When the customer is frustrated, acknowledge their feelings first.
        When confused, slow down and use simpler language.
    """,
    llm=anthropic.LLM("claude-sonnet-4-6"),
    stt=deepgram.STT(),
    tts=elevenlabs.TTS(),
    lenses=[MoodLens(throttle_seconds=3)],
)

SenseRunner(agent, room="support-room-1").serve()
```

### Supported Plugins

| Category | Plugins |
|----------|---------|
| **LLM** | `anthropic`, `openai`, `gemini`, `mistral`, `openrouter`, `xai` |
| **STT** | `deepgram`, `assemblyai`, `fast_whisper` |
| **TTS** | `elevenlabs`, `cartesia`, `kokoro`, `fish`, `pocket` |
| **Vision** | `ultralytics` (YOLO), `moondream`, `roboflow`, `nvidia` |

---

## Multi-agent API

Sense Mind exposes a REST API for managing multiple agents:

```bash
# Start agent in a room
POST http://localhost:8080/agents/start
{"room": "tenant__room-1", "lenses": ["MoodLens", "FaceLens"], "llm": "claude-sonnet-4-6"}

# Stop agent
POST http://localhost:8080/agents/stop
{"room": "tenant__room-1"}

# Status of all agents
GET  http://localhost:8080/agents/status

# Configure lens throttle at runtime (no restart)
POST http://localhost:8080/agents/tenant__room-1/lenses/mood_lens/configure
{"throttle_seconds": 5.0, "enabled": true}
```

---

## Documentation

- [Quick Start](docs/quickstart.md) — up and running in 5 minutes
- [Architecture](docs/architecture.md) — how the services connect
- [Self-hosting Guide](docs/self-hosting.md) — production deployment
- [Python SDK Reference](docs/python-sdk.md) — full API reference
- [Building a Contact Center](docs/products/contact-center.md) — product tutorial

---

## Roadmap

- [x] Phase 1 — Sense Relay + Sense Mind + Vision Lenses
- [x] Phase 2 — Sense Gate (API gateway, auth, multi-tenancy)
- [x] Phase 3 — Sense Wire (real-time messaging)
- [x] Phase 4 — sense-js SDK (@sense/core, @sense/vision, @sense/chat, @sense/lens)
- [x] Phase 5 — Sense Console (developer dashboard)
- [x] Phase 6 — Multi-agent pool + LensEventBridge + Vision Event Stream
- [x] Phase 7 — sense-py SDK + developer docs
- [ ] Phase 8 — 5 product examples (contact-center, sales-coach, fitness-coach, telehealth, security-soc)

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
