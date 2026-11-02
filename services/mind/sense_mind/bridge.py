"""
LensEventBridge — Vision Event Stream to Sense Wire
=====================================================
Forwards LensEvents from running Sense Mind agents to Sense Wire in real time,
enabling browser clients to subscribe to vision intelligence over WebSocket.

When a lens fires (MoodLens detects emotion, GuardLens flags content, etc.),
the bridge POSTs the event to:

    POST {SENSE_WIRE_URL}/internal/events   (header X-Service-Key)

Sense Wire fans it out to every WebSocket client subscribed to that channel,
so the @sense/lens SDK receives it immediately.

Configuration (env vars):
    SENSE_WIRE_URL      — Sense Wire HTTP base URL (e.g. http://sense-wire:3001)
    SENSE_WIRE_API_KEY  — shared service key; must equal Wire's SERVICE_KEY

Usage:
    bridge = LensEventBridge()
    bridge.attach_to_pool(pool)   # auto-forward all future events
"""

import asyncio
import logging
import os
import time

logger = logging.getLogger(__name__)


class LensEventBridge:
    """
    Bridges Sense Mind lens events to Sense Wire in real time.

    Attach to an AgentPool to auto-forward every LensEvent from every
    running agent to the correct Wire channel.
    """

    def __init__(
        self,
        wire_url: str | None = None,
        api_key: str | None = None,
    ):
        self._wire_url = (wire_url or os.environ.get("SENSE_WIRE_URL", "")).rstrip("/")
        self._api_key = api_key or os.environ.get("SENSE_WIRE_API_KEY", "")
        self._enabled = bool(self._wire_url)
        self._client = None
        self._pool = None
        self._warned_routing: set[str] = set()
        self._last_sent: dict[tuple[str, str], float] = {}
        self.min_interval = 0.5  # seconds per (room, lens) — caps event floods

        if self._enabled:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=5.0)
                logger.info("LensEventBridge: enabled — wire=%s", self._wire_url)
            except ImportError:
                logger.warning("LensEventBridge: httpx not installed — bridge disabled")
                self._enabled = False
        else:
            logger.info(
                "LensEventBridge: disabled — set SENSE_WIRE_URL to stream lens events to clients"
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def attach_to_pool(self, pool) -> None:
        """
        Register this bridge as a pool-level lens event listener.
        After calling this, every LensEvent from every pool agent is forwarded.
        """
        self._pool = pool
        pool.on_lens_event(self._handle_event)

    async def forward(self, room: str, event) -> bool:
        """
        Forward a single LensEvent to Sense Wire.

        Args:
            room:  The Sense Relay room name the event came from.
            event: A LensEvent instance.

        Returns:
            True if the POST succeeded, False otherwise.
        """
        if not self._enabled or self._client is None:
            return False

        tenant_id, room_id = (None, None)
        if self._pool is not None:
            tenant_id, room_id = self._pool.routing(room)
        if not tenant_id or not room_id:
            if room not in self._warned_routing:
                self._warned_routing.add(room)
                logger.warning(
                    "LensEventBridge: no tenant routing for room %s — start agents "
                    "through Sense Gate (or pass tenant_id/room_id) to stream lens events",
                    room,
                )
            return False

        key = (room, event.lens_name)
        now = time.monotonic()
        if now - self._last_sent.get(key, 0.0) < self.min_interval:
            return False
        self._last_sent[key] = now

        url = f"{self._wire_url}/internal/events"
        payload = {
            "tenant_id": tenant_id,
            "channel_type": "lens",
            "channel_id": room_id,
            "event_type": "lens.event",
            "data": {
                "lens_name": event.lens_name,
                "confidence": getattr(event, "confidence", 1.0),
                "context_text": getattr(event, "context_text", ""),
                "timestamp": getattr(event, "timestamp", 0.0),
                **getattr(event, "data", {}),
            },
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-Service-Key"] = self._api_key

        try:
            resp = await self._client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.warning(
                    "LensEventBridge: Wire rejected event [HTTP %d] room=%s lens=%s",
                    resp.status_code,
                    room,
                    event.lens_name,
                )
                return False
            logger.debug(
                "LensEventBridge: forwarded lens=%s room=%s confidence=%.2f",
                event.lens_name, room, getattr(event, "confidence", 1.0),
            )
            return True
        except Exception as e:
            logger.debug("LensEventBridge: forward error: %s", e)
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _handle_event(self, room: str, event) -> None:
        """Pool listener callback — called for every LensEvent from any agent."""
        await self.forward(room, event)
