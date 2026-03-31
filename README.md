<div align="center">

<img src="https://img.shields.io/badge/Sense-Platform-4F46E5?style=for-the-badge&logoColor=white" alt="Sense Platform" height="40"/>

### Self-hosted developer platform for AI-powered video, voice, and vision apps

*Build products that see, hear, and understand — with zero cloud lock-in*

<br/>

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-4F46E5.svg?style=flat-square)](LICENSE)
[![Docker Compose](https://img.shields.io/badge/docker_compose_up-ready-22C55E?style=flat-square&logo=docker&logoColor=white)](docker-compose.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3B82F6?style=flat-square&logo=python&logoColor=white)](sdks/sense-py)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3B82F6?style=flat-square&logo=typescript&logoColor=white)](sdks/sense-js)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-22C55E?style=flat-square)](https://github.com/VenkataAnilKumar/SensePlatform/pulls)

<br/>

[**Quick Start**](#-quick-start) &nbsp;·&nbsp;
[**Demo**](#-demo) &nbsp;·&nbsp;
[**Architecture**](#-architecture) &nbsp;·&nbsp;
[**SDKs**](#-sdks) &nbsp;·&nbsp;
[**Examples**](#-examples) &nbsp;·&nbsp;
[**Docs**](docs/quickstart.md)

</div>

<br/>

---

## What is Sense Platform?

Sense Platform is a **complete, self-hosted alternative to GetStream** — rebuilt from scratch for AI-first products. Every component runs on your own servers with a single `docker compose up`.

<table>
<tr>
<td width="50%">

**What you replace**
- ❌ Stream Video (cloud WebRTC)
- ❌ Stream Chat (cloud messaging)
- ❌ Vendor AI add-ons
- ❌ Per-seat / per-minute billing

</td>
<td width="50%">

**What you get instead**
- ✅ Self-hosted WebRTC SFU (LiveKit engine)
- ✅ Real-time WebSocket messaging
- ✅ Native vision AI — MoodLens, PoseLens, GuardLens, FaceLens
- ✅ Full ownership, no limits

</td>
</tr>
</table>

---

## 🧪 Demo

Run the interactive demo against your local stack — or in simulated mode without any services running:

```bash
# With the platform running
docker compose up -d
python demo.py

# Without the platform (simulated output)
python demo.py
```

**What the demo walks through:**

```
Step 1  Health-check all 5 services
Step 2  Authenticate with Sense Gate (API key → JWT)
Step 3  Create a demo room
Step 4  Start an AI agent with MoodLens + FaceLens
Step 5  Send real-time messages via Sense Wire
Step 6  Stream live vision lens events
Step 7  Reconfigure MoodLens throttle at runtime
Step 8  Stop the agent and clean up
```

**Sample output:**

```
  ███████╗███████╗███╗   ██╗███████╗███████╗
  ██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝
  ███████╗█████╗  ██╔██╗ ██║███████╗█████╗
  ╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝
  ███████║███████╗██║ ╚████║███████║███████╗
  ╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝

  AI-powered video · voice · vision — self-hosted

Step 1  Health-checking all services
  Sense Gate   :3000   [LIVE]       status=ok
  Sense Wire   :3001   [LIVE]       status=ok
  Sense Mind   :8080   [LIVE]       status=ok
  Sense Relay  :7880   [LIVE]       status=ok

Step 2  Authenticating with Sense Gate
  ✓  Authenticated  [real JWT]

Step 4  Starting AI agent  (MoodLens + FaceLens)
  ✓  Agent started  [live]
     room   = acme__demo-room
     llm    = claude-sonnet-4-6
     lenses = ['MoodLens', 'FaceLens']

Step 6  Streaming vision lens events
  [14:03:01] MOOD: NEUTRAL    conf=91%
             context → Participant appears calm and attentive.

  [14:03:01] FACE: 1 detected conf=98%
             context → 1 face detected in frame.

  [14:03:02] MOOD: CURIOUS    conf=83%
             context → Participant is engaged and leaning forward.

  [14:03:03] MOOD: SATISFIED  conf=87%
             context → Participant appears satisfied with the response.
```

---

## 🏗 Architecture

```
                     ┌──────────────────────────────────────┐
  Browser / SDK ────►│           Sense Gate  :3000           │◄──── Sense Console :4000
  Client        ◄────│      REST · Auth · Multi-tenancy      │      Developer Dashboard
                     └─────────────┬──────────────┬──────────┘
                                   │              │
              ┌────────────────────┘              └────────────────────┐
              │                                                         │
   ┌──────────▼──────────┐                              ┌──────────────▼──────────┐
   │    Sense Mind :8080  │                              │    Sense Wire  :3001     │
   │  ┌────────────────┐  │  ── LensEventBridge ────────►│  WebSocket Messaging     │
   │  │  AI Agents     │  │                              │  Redis pub/sub fan-out   │
   │  │  + AgentPool   │  │                              └─────────────────────────┘
   │  └────────────────┘  │
   │  ┌────────────────┐  │
   │  │ MoodLens       │  │
   │  │ PoseLens       │  │
   │  │ GuardLens      │  │
   │  │ FaceLens       │  │
   │  └────────────────┘  │
   └──────────┬───────────┘
              │
   ┌──────────▼──────────┐         ┌──────────────────────────┐
   │  Sense Relay  :7880  │         │  Postgres  +  Redis       │
   │  WebRTC SFU           │         │  data · state · pub/sub   │
   │  (LiveKit engine)     │         └──────────────────────────┘
   └─────────────────────┘
```

<details>
<summary><strong>Services at a glance</strong></summary>
<br/>

| Service | Role | Port |
|---------|------|-----:|
| **Sense Relay** | Self-hosted WebRTC SFU — audio/video routing, no cloud | 7880 |
| **Sense Mind** | AI agent engine — LLM · STT · TTS · Vision Lenses · AgentPool | 8080 |
| **Sense Gate** | REST API gateway — JWT auth, multi-tenancy, webhooks, usage metering | 3000 |
| **Sense Wire** | Real-time WebSocket messaging — Redis pub/sub cross-instance fan-out | 3001 |
| **Sense Console** | Next.js developer dashboard — rooms, agents, keys, webhooks, usage | 4000 |

</details>

<details>
<summary><strong>Vision Lenses</strong></summary>
<br/>

Lenses are throttled vision processors that **inject context directly into the agent's LLM prompt** mid-conversation — no prompt engineering required.

| Lens | What it detects | Throttle |
|------|----------------|:--------:|
| **MoodLens** | Emotion — frustrated · confused · satisfied · happy | 3 s |
| **PoseLens** | Body keypoints — posture, form faults, gestures | 2 s |
| **GuardLens** | Safety — weapons, explicit content, fire/smoke, tailgating | 2 s |
| **FaceLens** | Presence — face count, occupancy, identity continuity | 5 s |

</details>

---

## 🚀 Quick Start

> **Prerequisites:** Docker Desktop · one LLM API key (Anthropic recommended)

### 1 · Clone and configure

```bash
git clone https://github.com/VenkataAnilKumar/SensePlatform
cd SensePlatform
cp .env.example .env
```

Add your key to `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### 2 · Start the platform

```bash
docker compose up
```

All five services start automatically. First run pulls images (~2 min). After ~30 s:

| URL | Service |
|-----|---------|
| **http://localhost:4000** | Sense Console — developer dashboard |
| http://localhost:3000 | Sense Gate — REST API |
| ws://localhost:3001 | Sense Wire — WebSocket |
| http://localhost:8080 | Sense Mind — agent control |
| ws://localhost:7880 | Sense Relay — WebRTC |

### 3 · Run the demo

```bash
python demo.py
```

### 4 · Start your first AI agent

```bash
curl -s -X POST http://localhost:3000/agents/start \
  -H "X-API-Key: sk_live_your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": "demo",
    "lenses": ["MoodLens"],
    "llm":    "claude-sonnet-4-6",
    "instructions": "You are a helpful assistant. Adapt to the user emotional state."
  }' | jq .
```

---

## 🛠 SDKs

### Python SDK

```bash
pip install sense-platform
```

```python
import asyncio
from sense import SenseClient, SenseWire, LensStream

async def main():
    async with SenseClient(api_key="sk_live_...") as client:
        await client.connect()

        # Launch AI agent with emotion detection
        await client.agents.start("demo", lenses=["MoodLens"])

        # Subscribe to messages + live lens events
        async with SenseWire(client, "messaging", "demo") as wire:
            stream = LensStream(wire)

            @stream.on_mood
            def on_mood(event):
                print(f"[{event.mood}] {event.context_text}")

            wire.on_message(lambda msg: print(f"{msg.user_id}: {msg.text}"))
            await wire.send("Hello from Python!")
            await wire.wait()

asyncio.run(main())
```

### TypeScript / JavaScript SDK

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

// Join WebRTC room (publishes webcam + mic)
const room = new SenseRoom(client);
await room.join({ roomId: "demo", autoPublish: true });

// Chat
const channel = new Channel(client.wire, "messaging", "demo");
await channel.sendMessage("Hello from the browser!");

// Live vision events
const lenses = new LensStream(client.wire, "demo");
lenses.onMood((e) => console.log(`${e.mood} — ${e.contextText}`));
lenses.onGuard((e) => { if (e.violation) alert(`⚠ ${e.violationType}`); });
```

<details>
<summary><strong>Sense Mind Agent SDK — build custom agents</strong></summary>
<br/>

```python
from sense_mind import SenseMind, SenseRunner
from sense_mind.plugins import anthropic, deepgram, elevenlabs
from sense_mind.lenses import MoodLens, PoseLens

agent = SenseMind(
    instructions="""
        You are a supportive contact center agent.
        When the customer is frustrated, acknowledge it first.
        When confused, slow down and use plain language.
    """,
    llm=anthropic.LLM("claude-sonnet-4-6"),
    stt=deepgram.STT(),
    tts=elevenlabs.TTS(),
    lenses=[MoodLens(throttle_seconds=3), PoseLens()],
)

SenseRunner(agent, room="support-room-1").serve()
```

**Supported plugins**

| Category | Options |
|----------|---------|
| **LLM** | `anthropic` · `openai` · `gemini` · `mistral` · `openrouter` · `xai` |
| **STT** | `deepgram` · `assemblyai` · `fast_whisper` |
| **TTS** | `elevenlabs` · `cartesia` · `kokoro` · `fish` · `pocket` |
| **Vision** | `ultralytics` (YOLO) · `moondream` · `roboflow` · `nvidia` |

</details>

---

## ⚡ Multi-Agent API

Sense Mind manages multiple agents concurrently — one per room, controlled via REST:

```bash
# Launch an agent
curl -X POST http://localhost:8080/agents/start \
  -H "Content-Type: application/json" \
  -d '{"room": "acme__room-1", "lenses": ["MoodLens"], "llm": "claude-sonnet-4-6"}'

# Check all running agents
curl http://localhost:8080/agents/status

# Tune lens throttle at runtime — zero downtime
curl -X POST http://localhost:8080/agents/acme__room-1/lenses/mood_lens/configure \
  -d '{"throttle_seconds": 5.0, "enabled": true}'

# Stop an agent
curl -X POST http://localhost:8080/agents/stop \
  -d '{"room": "acme__room-1"}'
```

---

## 📦 Examples

Five production-grade examples in [`examples/`](examples/):

| Example | Lenses | What it does |
|---------|--------|-------------|
| [`contact-center/`](examples/contact-center/agent.py) | MoodLens · FaceLens | Adapts tone to frustration; escalates to human on trigger |
| [`sales-coach/`](examples/sales-coach/agent.py) | MoodLens · PoseLens | Silent whisper coach — spots buying signals, flags objections |
| [`fitness-coach/`](examples/fitness-coach/agent.py) | PoseLens · FaceLens | Real-time form cues; rep counting; rest detection |
| [`telehealth/`](examples/telehealth/agent.py) | FaceLens · PoseLens · MoodLens | Clinical assistant — logs observations, flags distress |
| [`security-soc/`](examples/security-soc/agent.py) | FaceLens · GuardLens | Zone monitoring; weapon/threat detection; auto-incident |

**Run any example:**

```bash
# Contact center
ANTHROPIC_API_KEY=sk-ant-... SENSE_ROOM=support python examples/contact-center/agent.py

# Fitness coach (squats)
EXERCISE=squat SENSE_ROOM=gym-alice python examples/fitness-coach/agent.py

# Security SOC — restricted zone
ZONE_TYPE=restricted ZONE_ID=server-room-a python examples/security-soc/agent.py
```

---

## 📖 Documentation

| | |
|--|--|
| [**Quick Start**](docs/quickstart.md) | Up and running in 5 minutes |
| [**Architecture**](docs/architecture.md) | How the five services connect, data flow, multi-tenancy |
| [**Self-Hosting Guide**](docs/self-hosting.md) | TLS, backups, horizontal scaling, production checklist |
| [**Python SDK Reference**](docs/python-sdk.md) | Full API reference for every class and method |
| [**Contact Center Tutorial**](docs/products/contact-center.md) | End-to-end product guide with React frontend + Python supervisor |

---

## ✅ Project Status

All eight phases shipped.

| | Phase | What shipped |
|-|-------|-------------|
| ✅ | **1 — Core** | Sense Relay · Sense Mind · Vision Lenses · Docker Compose |
| ✅ | **2 — Gate** | FastAPI gateway · JWT auth · multi-tenancy · webhooks · usage metering |
| ✅ | **3 — Wire** | WebSocket messaging · Postgres persistence · Redis pub/sub fan-out |
| ✅ | **4 — JS SDK** | `@sense/core` · `@sense/vision` · `@sense/chat` · `@sense/lens` |
| ✅ | **5 — Console** | Next.js developer dashboard — rooms, agents, keys, webhooks, usage |
| ✅ | **6 — Agent Pool** | Multi-agent pool · LensEventBridge · Vision Event Stream · `/agents` API |
| ✅ | **7 — Py SDK + Docs** | `sense-platform` Python SDK · quickstart · architecture · self-hosting guide |
| ✅ | **8 — Examples** | Contact center · sales coach · fitness coach · telehealth · security SOC |

---

<div align="center">

**[Apache 2.0](LICENSE)** · Built with [LiveKit](https://livekit.io), [FastAPI](https://fastapi.tiangolo.com), [Next.js](https://nextjs.org), and [Claude](https://anthropic.com)

</div>
