"""
Watch live lens events from the command line.

Joins a Sense Relay room, publishes a camera feed (a still image or a video file),
subscribes to the room's lens channel on Sense Wire, and prints the vision events
that the AI agent's lenses produce. Handy for trying the platform without a browser.

Prerequisites:
    - The platform is running (docker compose up)
    - An agent with lenses is running in the room, e.g.
        curl -X POST localhost:3000/agents/start -H "X-API-Key: $SENSE_API_KEY" \
             -H "Content-Type: application/json" \
             -d '{"room_id": "demo", "lenses": ["MoodLens", "FaceLens"]}'
    - pip install ./sdks/sense-py livekit websockets httpx pillow numpy

Usage:
    SENSE_API_KEY=sk_live_... python watch_lens_events.py demo --image photo.jpg
"""

import argparse
import asyncio
import json
import os

import httpx
import numpy as np
import websockets
from livekit import rtc
from PIL import Image

GATE_URL = os.environ.get("SENSE_GATE_URL", "http://localhost:3000")
WIRE_URL = os.environ.get("SENSE_WIRE_URL", "ws://localhost:3001")


async def main(room_id: str, image: str, max_events: int, timeout: float) -> None:
    key = os.environ["SENSE_API_KEY"]
    headers = {"X-API-Key": key}
    async with httpx.AsyncClient(timeout=30) as http:
        join = (await http.post(f"{GATE_URL}/rooms/{room_id}/join", headers=headers,
                                json={"user_id": "watcher"})).json()
        token = (await http.post(f"{GATE_URL}/auth/token", headers=headers,
                                 json={"user_id": "watcher"})).json()["access_token"]

    events: list[dict] = []

    async def listen() -> None:
        async with websockets.connect(f"{WIRE_URL}/ws/connect?token={token}") as ws:
            await ws.recv()  # connection ack
            await ws.send(json.dumps({"type": "channel.subscribe",
                                      "channel_type": "lens", "channel_id": room_id}))
            async for raw in ws:
                event = json.loads(raw)
                if event.get("type") == "lens.event":
                    data = event["data"]
                    events.append(data)
                    print(f'[{data["lens_name"]}] {data.get("confidence", 0):.0%}  '
                          f'{data["context_text"]}', flush=True)

    listener = asyncio.create_task(listen())

    pixels = np.array(Image.open(image).convert("RGBA").resize((640, 480)))
    frame = rtc.VideoFrame(640, 480, rtc.VideoBufferType.RGBA, pixels.tobytes())
    room = rtc.Room()
    await room.connect(join["relay_url"], join["relay_token"])
    source = rtc.VideoSource(640, 480)
    track = rtc.LocalVideoTrack.create_video_track("camera", source)
    await room.local_participant.publish_track(
        track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_CAMERA))

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while len(events) < max_events and loop.time() < deadline:
        source.capture_frame(frame)
        await asyncio.sleep(0.1)

    await room.disconnect()
    listener.cancel()
    if not events:
        print("No lens events received — is an agent with lenses running in this room?")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("room", help="room id (as used with /agents/start)")
    parser.add_argument("--image", required=True, help="image to publish as the camera feed")
    parser.add_argument("--events", type=int, default=4, help="stop after this many events")
    parser.add_argument("--timeout", type=float, default=30, help="give up after N seconds")
    args = parser.parse_args()
    asyncio.run(main(args.room, args.image, args.events, args.timeout))
