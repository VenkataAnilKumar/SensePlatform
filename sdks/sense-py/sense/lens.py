"""
LensStream — Vision Lens Event Subscriber
==========================================
Subscribe to real-time vision intelligence events pushed by Sense Mind
to browser and Python clients via Sense Wire.

Each running agent with vision lenses fires typed events:
  - MoodEvent   — customer emotion, valence score
  - PoseEvent   — body keypoints, posture classification
  - GuardEvent  — content violations, moderation actions
  - FaceEvent   — face count, identity detection

Events are delivered via Sense Wire's lens channel:
    channel_type="lens", channel_id="{tenant_slug}__{room_id}"

Usage:
    async with SenseWire(client, "lens", room_name) as wire:
        stream = LensStream(wire)

        @stream.on_mood
        def handle_mood(event: MoodEvent):
            print(f"Mood: {event.mood} ({event.confidence:.0%})")
            if event.mood == "frustrated":
                escalate_to_supervisor()

        @stream.on_guard
        async def handle_guard(event: GuardEvent):
            if event.violation:
                await client.rooms.mute_participant(room_id, user_id)

        await wire.wait()

Decorator + callback styles both work:
    # Decorator style
    @stream.on_mood
    def handle(event): ...

    # Callback style
    stream.on_mood(handle)

    # Any event
    @stream.on_any
    def log_all(event): ...
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

from sense.models import FaceEvent, GuardEvent, LensEvent, MoodEvent, PoseEvent

logger = logging.getLogger(__name__)

_LENS_EVENT_PREFIX = "lens."


class LensStream:
    """
    Typed subscriber for Sense Mind vision lens events.

    Wraps a SenseWire connection on a 'lens' channel and routes
    incoming events to type-specific handlers.

    Args:
        wire: A connected SenseWire instance on channel_type="lens".
    """

    def __init__(self, wire):   # wire: SenseWire
        self._wire = wire
        self._handlers: dict[str, list[Callable]] = {
            "mood": [],
            "pose": [],
            "guard": [],
            "face": [],
            "any": [],
        }
        # Register with the wire
        self._wire.on("*", self._route_event)

    # ── Decorator / callback registration ─────────────────────────────────────

    def on_mood(self, fn: Callable[[MoodEvent], Any]) -> Callable:
        """Register a handler for MoodLens events."""
        self._handlers["mood"].append(fn)
        return fn   # supports @stream.on_mood decorator syntax

    def on_pose(self, fn: Callable[[PoseEvent], Any]) -> Callable:
        """Register a handler for PoseLens events."""
        self._handlers["pose"].append(fn)
        return fn

    def on_guard(self, fn: Callable[[GuardEvent], Any]) -> Callable:
        """Register a handler for GuardLens events."""
        self._handlers["guard"].append(fn)
        return fn

    def on_face(self, fn: Callable[[FaceEvent], Any]) -> Callable:
        """Register a handler for FaceLens events."""
        self._handlers["face"].append(fn)
        return fn

    def on_any(self, fn: Callable[[LensEvent], Any]) -> Callable:
        """Register a catch-all handler for all lens events."""
        self._handlers["any"].append(fn)
        return fn

    def off_mood(self, fn: Callable) -> None:
        self._handlers["mood"] = [h for h in self._handlers["mood"] if h is not fn]

    def off_pose(self, fn: Callable) -> None:
        self._handlers["pose"] = [h for h in self._handlers["pose"] if h is not fn]

    def off_guard(self, fn: Callable) -> None:
        self._handlers["guard"] = [h for h in self._handlers["guard"] if h is not fn]

    def off_face(self, fn: Callable) -> None:
        self._handlers["face"] = [h for h in self._handlers["face"] if h is not fn]

    # ── Internal routing ──────────────────────────────────────────────────────

    async def _route_event(self, raw_event: Any) -> None:
        """
        Called by SenseWire for every event on the lens channel.
        Routes lens.* events to the appropriate typed handler.
        """
        # raw_event may be a dict (if not caught by wire's own parsing)
        if isinstance(raw_event, dict):
            event_type = raw_event.get("type", "")
            if not event_type.startswith(_LENS_EVENT_PREFIX):
                return
            data = raw_event.get("data", {})
            lens_event = LensEvent(
                lens_name=data.get("lens_name", event_type[len(_LENS_EVENT_PREFIX):]),
                confidence=float(data.get("confidence", 1.0)),
                context_text=data.get("context_text", ""),
                timestamp=float(data.get("timestamp", 0.0)),
                data={k: v for k, v in data.items()
                      if k not in ("lens_name", "confidence", "context_text", "timestamp")},
            )
            await self._dispatch(lens_event)
        elif isinstance(raw_event, LensEvent):
            await self._dispatch(raw_event)

    async def _dispatch(self, event: LensEvent) -> None:
        """Dispatch a LensEvent to the appropriate typed handlers."""
        lens_name = event.lens_name   # "mood_lens" | "pose_lens" | etc.
        key = lens_name.replace("_lens", "")  # "mood" | "pose" | "guard" | "face"

        # Upcast to typed event model
        typed: Any = event
        if key == "mood":
            typed = MoodEvent.from_lens_event(event)
        elif key == "pose":
            typed = PoseEvent.from_lens_event(event)
        elif key == "guard":
            typed = GuardEvent.from_lens_event(event)
        elif key == "face":
            typed = FaceEvent.from_lens_event(event)

        # Fire key-specific handlers + catch-all
        for handler in [*self._handlers.get(key, []), *self._handlers["any"]]:
            try:
                result = handler(typed)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning("LensStream: handler error for %s: %s", lens_name, e)

        logger.debug(
            "LensStream: %s confidence=%.2f | %s",
            lens_name, event.confidence, event.context_text,
        )
