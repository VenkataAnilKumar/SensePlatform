# Quick Start

Get Sense Platform running locally in under 5 minutes.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- An API key from at least one LLM provider — Anthropic is recommended

## 1. Clone and configure

```bash
git clone https://github.com/VenkataAnilKumar/SensePlatform
cd SensePlatform
cp .env.example .env
```

Open `.env` and add your keys:

```env
ANTHROPIC_API_KEY=sk-ant-...      # required for default LLM
DEEPGRAM_API_KEY=...              # optional — Deepgram STT
ELEVENLABS_API_KEY=...            # optional — ElevenLabs TTS
```

Change the secrets before deploying to production:

```env
SENSE_JWT_SECRET=your-secret-here
```

## 2. Start the platform

```bash
docker compose up
```

First run downloads images and builds services (~2 minutes). Subsequent starts take ~10 seconds.

After startup, all 5 services are available:

| Service | URL | Purpose |
|---------|-----|---------|
| Sense Console | http://localhost:4000 | Developer dashboard |
| Sense Gate | http://localhost:3000 | REST API |
| Sense Wire | ws://localhost:3001 | WebSocket messaging |
| Sense Mind | http://localhost:8080 | AI agent API |
| Sense Relay | ws://localhost:7880 | WebRTC server |

## 3. Open the developer dashboard

Navigate to http://localhost:4000.

Enter any API key to sign in. To create your first tenant and key via the API:

```bash
# Register a new account
curl -s -X POST http://localhost:3000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "email": "dev@acme.com", "password": "changeme"}' \
  | jq .

# Note the api_key in the response — use it for all further requests
```

## 4. Start an AI agent

```bash
# Start a MoodLens-enabled agent in a room
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

The agent joins the room, connects to Sense Relay, and starts listening for participants.

## 5. Check service health

```bash
curl http://localhost:3000/health     # Gate
curl http://localhost:8080/health     # Mind (shows agent count)
curl http://localhost:3001/health     # Wire
```

## Python SDK Quickstart

```bash
pip install sense-platform
```

```python
import asyncio
from sense import SenseClient, SenseWire, LensStream

async def main():
    # Connect to Sense Gate
    async with SenseClient(api_key="sk_live_your_key") as client:
        await client.connect()
        print(f"Connected as: {client.tenant.name}")

        # Start an emotion-aware agent
        await client.agents.start(
            "demo",
            lenses=["MoodLens"],
            instructions="You are a supportive contact center agent.",
        )

        # Join the messaging channel
        async with SenseWire(client, "messaging", "demo") as wire:

            # Subscribe to vision lens events
            stream = LensStream(wire)

            @stream.on_mood
            def on_mood(event):
                print(f"Mood: {event.mood} ({event.confidence:.0%})")
                print(f"  {event.context_text}")

            # Send a message
            wire.on_message(lambda msg: print(f"  [{msg.user_id}] {msg.text}"))
            await wire.send("Hello from Python!")

            # Block until disconnected
            await wire.wait()

asyncio.run(main())
```

## JavaScript SDK Quickstart

```bash
npm install @sense/core @sense/vision @sense/chat @sense/lens
```

```typescript
import { SenseClient } from "@sense/core";
import { SenseRoom }   from "@sense/vision";
import { Channel }     from "@sense/chat";
import { LensStream }  from "@sense/lens";

const client = new SenseClient({
  apiKey: "sk_live_your_key",
  gateUrl: "http://localhost:3000",
});
await client.connect();

// Join the WebRTC room (publishes webcam + mic)
const room = new SenseRoom(client);
await room.join({ roomId: "demo", autoPublish: true });

room.on("participant_joined", (p) => {
  console.log(`${p.identity} joined (agent: ${p.isAgent})`);
});

// Chat
const channel = new Channel(client.wire, "messaging", "demo");
channel.on("message.new", (msg) => console.log(msg.text));
await channel.sendMessage("Hello from the browser!");

// Lens events
const lenses = new LensStream(client.wire, "demo");
lenses.onMood((e) => console.log(`Mood: ${e.mood} — ${e.contextText}`));
```

## Next steps

- [Architecture overview](architecture.md)
- [Python SDK reference](python-sdk.md)
- [Building a Contact Center](products/contact-center.md)
- [Self-hosting in production](self-hosting.md)
