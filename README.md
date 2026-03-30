# Sense Platform

> **Build AI-powered video, voice, and chat applications with real-time intelligence in hours, not weeks.**

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
│         ▲                  ▲                     ▲              │
│         │                  │                     │              │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │    Redis    │   │  Sense Wire  │   │   Sense Console      │ │
│  │  Room State │   │  Real-time   │   │  Developer Dashboard │ │
│  │   Pub/Sub   │   │  Messaging   │   │                      │ │
│  └─────────────┘   └──────────────┘   └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Services

| Service | Description | Port |
|---------|-------------|------|
| **Sense Relay** | Self-hosted WebRTC SFU (built on LiveKit) | 7880 |
| **Sense Mind** | AI agent engine — LLM + STT + TTS + Vision Lenses | 8080 |
| **Sense Gate** | REST API gateway, auth, multi-tenancy *(Phase 2)* | 3000 |
| **Sense Wire** | Real-time WebSocket messaging *(Phase 3)* | 3001 |
| **Sense Console** | Developer dashboard *(Phase 5)* | 4000 |

### Sense Mind — Vision Lenses

| Lens | Purpose | Default Throttle |
|------|---------|-----------------|
| **MoodLens** | Customer emotion detection (frustrated/confused/satisfied) | 3s |
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
# Edit .env — add your ANTHROPIC_API_KEY (or OPENAI_API_KEY)
```

### 2. Start the platform

```bash
docker compose up
```

This starts:
- `sense-relay` on port 7880 (WebRTC media server)
- `redis` on port 6379 (room state)
- `sense-mind` on port 8080 (AI agent — joins room "default")

### 3. Check agent health

```bash
curl http://localhost:8080/health
# {"status": "ok", "room": "default"}

curl http://localhost:8080/status
# {"room": "default", "lenses": [...]}
```

### 4. Connect a client

Point any LiveKit-compatible client (web, iOS, Android) at `ws://localhost:7880`
with API key `sense_gateway` and secret `secret_change_in_production`.

The AI agent will join the room automatically and start interacting.

---

## Python SDK

```python
from sense_mind import SenseMind, SenseRunner
from sense_mind.plugins import anthropic, deepgram, elevenlabs
from sense_mind.lenses import MoodLens, PoseLens

agent = SenseMind(
    relay_url="ws://localhost:7880",
    instructions="You are a helpful contact center agent.",
    llm=anthropic.LLM("claude-sonnet-4-6"),
    stt=deepgram.STT(),
    tts=elevenlabs.TTS(),
    lenses=[MoodLens(), PoseLens(exercise="squat")],
)

SenseRunner(agent, room="my-room").serve()
```

### Supported Plugins

**LLM:** `anthropic`, `openai`, `gemini`, `mistral`, `openrouter`, `xai`

**STT:** `deepgram`, `assemblyai`, `fast_whisper`

**TTS:** `elevenlabs`, `cartesia`, `kokoro`

---

## Development

```bash
cd services/mind
pip install -e ".[all,dev]"
pytest
```

---

## Roadmap

- [x] **Phase 1** — Sense Relay + Sense Mind + Vision Lenses
- [ ] **Phase 2** — Sense Gate (API gateway, auth, multi-tenancy)
- [ ] **Phase 3** — Sense Wire (real-time messaging)
- [ ] **Phase 4** — sense-js SDK
- [ ] **Phase 5** — Sense Console (developer dashboard)
- [ ] **Phase 6** — Vision pipeline hardening
- [ ] **Phase 7** — sense-py SDK + full developer docs
- [ ] **Phase 8** — 5 product examples (contact-center, sales-coach, fitness-coach, telehealth, security-soc)

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
