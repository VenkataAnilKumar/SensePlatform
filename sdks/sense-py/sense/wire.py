"""
SenseWire — Real-time WebSocket Messaging Client
==================================================
Async WebSocket client for Sense Wire.
Auto-reconnects with exponential backoff (up to 5 attempts).
Pending messages are queued and flushed on reconnect.

Usage:
    async with SenseWire(client, channel_type="messaging", channel_id="room1") as wire:
        wire.on("message.new", lambda msg: print(f"{msg.user_id}: {msg.text}"))
        wire.on_typing(lambda e: print(f"{e.user_id} is typing..."))
        await wire.send("Hello, world!")
        await wire.wait()   # keep alive
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Callable, Optional

from sense.models import Message, Reaction, TypingEvent

logger = logging.getLogger(__name__)

_DEFAULT_RECONNECT_DELAYS = [1, 2, 4, 8, 16]  # seconds, exponential backoff


class SenseWire:
    """
    Async WebSocket client for Sense Wire real-time messaging.

    Args:
        client:       Authenticated SenseClient.
        channel_type: Channel type (e.g. "messaging", "livestream").
        channel_id:   Channel identifier.
        wire_url:     Sense Wire WebSocket URL (overrides env var).

    Events you can listen to:
        "message.new"      — new message in the channel
        "message.deleted"  — message was deleted
        "reaction.new"     — reaction added
        "reaction.deleted" — reaction removed
        "typing.start"     — user started typing
        "typing.stop"      — user stopped typing
        "member.added"     — user joined channel
        "member.removed"   — user left channel
        "lens.*"           — vision lens events (use LensStream instead)
        "*"                — catch-all for all events
    """

    def __init__(
        self,
        client,                          # SenseClient
        channel_type: str,
        channel_id: str,
        wire_url: str | None = None,
    ):
        self._client = client
        self._channel_type = channel_type
        self._channel_id = channel_id
        self._wire_ws_url = (
            (wire_url or os.environ.get("SENSE_WIRE_URL", "ws://localhost:3001"))
            .replace("http://", "ws://")
            .replace("https://", "wss://")
            .rstrip("/")
        )
        self._ws = None
        self._connected = asyncio.Event()
        self._handlers: dict[str, list[Callable]] = {}
        self._pending: list[dict] = []    # queued events before connected
        self._reconnect_task: Optional[asyncio.Task] = None
        self._closed = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> "SenseWire":
        """
        Open the WebSocket connection to Sense Wire.
        Subscribes to the channel immediately on connect.
        """
        self._closed = False
        await self._do_connect()
        return self

    async def close(self) -> None:
        """Disconnect and stop all reconnect attempts."""
        self._closed = True
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._ws:
            await self._ws.close()
        self._connected.clear()
        logger.info("SenseWire: disconnected from %s/%s", self._channel_type, self._channel_id)

    # Context manager support
    async def __aenter__(self) -> "SenseWire":
        await self.connect()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    # ── Event listeners ───────────────────────────────────────────────────────

    def on(self, event_type: str, handler: Callable) -> "SenseWire":
        """
        Register an event handler.

        Args:
            event_type: Event name or "*" for all events.
            handler:    Sync or async callable receiving the event payload.

        Returns:
            self (fluent chaining).
        """
        self._handlers.setdefault(event_type, []).append(handler)
        return self

    def off(self, event_type: str, handler: Callable) -> "SenseWire":
        """Remove a previously registered event handler."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
        return self

    def on_message(self, handler: Callable[[Message], Any]) -> "SenseWire":
        """Convenience: listen for new messages."""
        return self.on("message.new", handler)

    def on_typing(self, handler: Callable[[TypingEvent], Any]) -> "SenseWire":
        """Convenience: listen for typing start/stop events."""
        self.on("typing.start", handler)
        self.on("typing.stop", handler)
        return self

    # ── Sending ───────────────────────────────────────────────────────────────

    async def send(self, text: str, user_id: str | None = None) -> None:
        """
        Send a text message to the channel.

        Args:
            text:    Message body.
            user_id: Override sender identity (defaults to connected user).
        """
        await self._send_event({
            "type": "message.new",
            "channel_type": self._channel_type,
            "channel_id": self._channel_id,
            "data": {
                "text": text,
                **({"user_id": user_id} if user_id else {}),
            },
        })

    async def add_reaction(self, message_id: str, emoji: str) -> None:
        """Add a reaction to a message."""
        await self._send_event({
            "type": "reaction.add",
            "channel_type": self._channel_type,
            "channel_id": self._channel_id,
            "data": {"message_id": message_id, "emoji": emoji},
        })

    async def remove_reaction(self, message_id: str, emoji: str) -> None:
        """Remove a reaction from a message."""
        await self._send_event({
            "type": "reaction.remove",
            "channel_type": self._channel_type,
            "channel_id": self._channel_id,
            "data": {"message_id": message_id, "emoji": emoji},
        })

    async def start_typing(self) -> None:
        """Broadcast that the current user started typing."""
        await self._send_event({
            "type": "typing.start",
            "channel_type": self._channel_type,
            "channel_id": self._channel_id,
            "data": {},
        })

    async def stop_typing(self) -> None:
        """Broadcast that the current user stopped typing."""
        await self._send_event({
            "type": "typing.stop",
            "channel_type": self._channel_type,
            "channel_id": self._channel_id,
            "data": {},
        })

    async def mark_read(self) -> None:
        """Mark all messages in the channel as read."""
        await self._send_event({
            "type": "channel.mark_read",
            "channel_type": self._channel_type,
            "channel_id": self._channel_id,
            "data": {},
        })

    async def wait(self) -> None:
        """Block until the connection is closed."""
        if self._ws:
            await self._receive_loop()

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _do_connect(self, attempt: int = 0) -> None:
        try:
            import websockets

            # Gate issues a JWT via X-API-Key; we use the same token for Wire
            wire_url = f"{self._wire_ws_url}/ws/connect?token={self._client._api_key}"
            self._ws = await websockets.connect(wire_url)

            # Subscribe to the channel immediately
            await self._ws.send(json.dumps({
                "type": "channel.subscribe",
                "channel_type": self._channel_type,
                "channel_id": self._channel_id,
                "data": {},
            }))

            self._connected.set()
            logger.info("SenseWire: connected to %s/%s", self._channel_type, self._channel_id)

            # Flush pending events
            for event in self._pending:
                await self._ws.send(json.dumps(event))
            self._pending.clear()

            # Start receive loop in background
            asyncio.ensure_future(self._receive_loop())

        except Exception as e:
            self._connected.clear()
            logger.warning("SenseWire: connect failed (attempt %d): %s", attempt + 1, e)
            if not self._closed and attempt < len(_DEFAULT_RECONNECT_DELAYS):
                delay = _DEFAULT_RECONNECT_DELAYS[attempt]
                logger.info("SenseWire: reconnecting in %ds...", delay)
                await asyncio.sleep(delay)
                await self._do_connect(attempt + 1)

    async def _receive_loop(self) -> None:
        """Receive messages from the WebSocket and dispatch to handlers."""
        try:
            async for raw in self._ws:
                try:
                    event = json.loads(raw)
                    await self._dispatch(event)
                except json.JSONDecodeError:
                    logger.debug("SenseWire: non-JSON message: %s", raw)
        except Exception as e:
            if not self._closed:
                logger.warning("SenseWire: connection dropped: %s", e)
                self._connected.clear()
                await self._do_connect()

    async def _send_event(self, event: dict) -> None:
        """Send an event, queuing it if not yet connected."""
        if self._connected.is_set() and self._ws:
            try:
                await self._ws.send(json.dumps(event))
                return
            except Exception as e:
                logger.warning("SenseWire: send failed: %s", e)
        # Queue for when we reconnect
        self._pending.append(event)

    async def _dispatch(self, event: dict) -> None:
        """Route an incoming event to registered handlers."""
        event_type = event.get("type", "")
        data = event.get("data", event)

        # Build typed objects for known event types
        payload: Any = data
        if event_type == "message.new":
            payload = _parse_message(data)
        elif event_type in ("reaction.new", "reaction.deleted"):
            payload = _parse_reaction(data)
        elif event_type in ("typing.start", "typing.stop"):
            payload = TypingEvent(
                channel_type=event.get("channel_type", self._channel_type),
                channel_id=event.get("channel_id", self._channel_id),
                user_id=data.get("user_id", ""),
                is_typing=(event_type == "typing.start"),
            )

        for handler in [*self._handlers.get(event_type, []), *self._handlers.get("*", [])]:
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning("SenseWire: handler error for %s: %s", event_type, e)


def _parse_message(data: dict) -> Message:
    return Message(
        id=data.get("id", ""),
        channel_id=data.get("channel_id", ""),
        tenant_id=data.get("tenant_id", ""),
        user_id=data.get("user_id", ""),
        text=data.get("text", ""),
        created_at=data.get("created_at", ""),
        is_deleted=data.get("is_deleted", False),
    )


def _parse_reaction(data: dict) -> Reaction:
    return Reaction(
        id=data.get("id", ""),
        message_id=data.get("message_id", ""),
        user_id=data.get("user_id", ""),
        emoji=data.get("emoji", ""),
        created_at=data.get("created_at", ""),
    )
