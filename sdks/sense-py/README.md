# sense-platform

Python SDK for [Sense Platform](https://github.com/VenkataAnilKumar/SensePlatform) — build AI-powered video, voice, and vision applications with zero cloud dependency.

## Install

```bash
pip install sense-platform
```

## Quick Start

```python
import asyncio
from sense import SenseClient, SenseWire, LensStream

async def main():
    async with SenseClient(api_key="sk_live_your_key") as client:
        await client.connect()

        # Start an emotion-aware AI agent in a room
        await client.agents.start(
            "support-room-1",
            instructions="You are a supportive contact center agent. Adapt your tone to the customer's emotional state.",
            lenses=["MoodLens"],
        )

        # Subscribe to real-time messages
        async with SenseWire(client, "messaging", "support-room-1") as wire:
            wire.on_message(lambda msg: print(f"{msg.user_id}: {msg.text}"))

            # Subscribe to vision lens events
            stream = LensStream(wire)

            @stream.on_mood
            def handle_mood(event):
                print(f"Customer mood: {event.mood} ({event.confidence:.0%})")
                if event.mood == "frustrated":
                    print("ALERT: Consider escalating to supervisor")

            await wire.wait()

asyncio.run(main())
```

## Configuration

Set environment variables or pass directly:

| Variable | Description |
|----------|-------------|
| `SENSE_API_KEY` | Your Sense API key (`sk_live_...`) |
| `SENSE_GATE_URL` | Sense Gate URL (default: `http://localhost:3000`) |
| `SENSE_WIRE_URL` | Sense Wire URL (default: `ws://localhost:3001`) |

## API

### SenseClient

```python
client = SenseClient(api_key="sk_live_...", gate_url="http://localhost:3000")
await client.connect()
```

**Rooms**
```python
rooms = await client.rooms.list()
token = await client.rooms.join("room-id", user_id="user_1", user_name="Alice")
# token.relay_url + token.relay_token → pass to LiveKit JS/Python client
```

**Agents**
```python
await client.agents.start("room-id", lenses=["MoodLens", "FaceLens"])
await client.agents.stop("room-id")
status = await client.agents.status("room-id")
lenses = await client.agents.get_lenses("room-id")
await client.agents.configure_lens("room-id", "mood_lens", throttle_seconds=5.0)
```

**Channels**
```python
messages = await client.channels.messages("messaging", "room-id", limit=50)
```

**Usage**
```python
usage = await client.usage.summary(start_date="2026-03-01", end_date="2026-03-31")
print(f"Total calls: {usage.total_calls}, Minutes: {usage.total_minutes:.1f}")
```

### SenseWire

```python
async with SenseWire(client, channel_type="messaging", channel_id="room-id") as wire:
    # Send messages
    await wire.send("Hello!")
    await wire.start_typing()
    await wire.stop_typing()
    await wire.add_reaction(message_id, "👍")

    # Receive events
    wire.on_message(lambda msg: print(msg.text))
    wire.on_typing(lambda e: print(f"{e.user_id} is typing..."))
    wire.on("*", lambda event: print(event))   # catch-all

    await wire.wait()
```

### LensStream

```python
async with SenseWire(client, "lens", room_name) as wire:
    stream = LensStream(wire)

    # Decorator style
    @stream.on_mood
    def handle_mood(event: MoodEvent):
        print(f"Mood: {event.mood}, valence: {event.valence:.2f}")
        print(f"Context: {event.context_text}")

    @stream.on_pose
    def handle_pose(event: PoseEvent):
        print(f"Posture: {event.posture}")

    @stream.on_guard
    async def handle_guard(event: GuardEvent):
        if event.violation:
            await client.rooms.mute_participant(...)

    @stream.on_face
    def handle_face(event: FaceEvent):
        print(f"Faces detected: {event.count}")

    await wire.wait()
```

## Lens Events

| Lens | Event Type | Key Fields |
|------|-----------|------------|
| MoodLens | `MoodEvent` | `mood`, `valence`, `confidence`, `context_text` |
| PoseLens | `PoseEvent` | `posture`, `keypoints`, `confidence` |
| GuardLens | `GuardEvent` | `violation`, `violation_type`, `action_taken` |
| FaceLens | `FaceEvent` | `count`, `identities`, `confidence` |

## Self-hosting

See the [Sense Platform README](../../README.md) for Docker setup.

```bash
git clone https://github.com/VenkataAnilKumar/SensePlatform
cd SensePlatform
cp .env.example .env    # add your LLM/STT/TTS keys
docker compose up
```

## License

Apache 2.0
