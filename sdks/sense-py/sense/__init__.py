"""
Sense Platform — Python SDK
=============================
Build AI-powered video, voice, and vision applications with zero cloud dependency.

Quick Start:
    pip install sense-platform

    import asyncio
    from sense import SenseClient, SenseWire, LensStream

    async def main():
        async with SenseClient(api_key="sk_live_...") as client:
            await client.connect()

            # Start an AI agent with emotion detection
            await client.agents.start("my-room", lenses=["MoodLens"])

            # Subscribe to real-time messages
            async with SenseWire(client, "messaging", "my-room") as wire:
                wire.on_message(lambda msg: print(f"{msg.user_id}: {msg.text}"))
                await wire.send("Hello from Python!")
                await wire.wait()

    asyncio.run(main())

Modules:
    sense.client     — SenseClient: HTTP client for Sense Gate
    sense.wire       — SenseWire: real-time WebSocket messaging
    sense.lens       — LensStream: vision lens event subscriber
    sense.models     — typed data models for all API responses
"""

from sense.client import SenseClient
from sense.lens import LensStream
from sense.models import (
    AgentStatus,
    ApiKey,
    FaceEvent,
    GuardEvent,
    LensEvent,
    LensInfo,
    Message,
    MoodEvent,
    PoseEvent,
    Reaction,
    RelayToken,
    Room,
    Tenant,
    TypingEvent,
    UsageSummary,
    Webhook,
)
from sense.wire import SenseWire

__version__ = "0.1.0"

__all__ = [
    # Clients
    "SenseClient",
    "SenseWire",
    "LensStream",
    # Models
    "Tenant",
    "Room",
    "RelayToken",
    "AgentStatus",
    "LensInfo",
    "ApiKey",
    "Webhook",
    "UsageSummary",
    "Message",
    "Reaction",
    "TypingEvent",
    "LensEvent",
    "MoodEvent",
    "PoseEvent",
    "GuardEvent",
    "FaceEvent",
]
