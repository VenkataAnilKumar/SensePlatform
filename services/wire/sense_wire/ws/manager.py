"""
Sense Wire — WebSocket Connection Manager
Manages all active WebSocket connections, grouped by channel.
Handles fan-out to all subscribers of a channel.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from sense_wire.ws.events import ServerEvent, make_event

logger = logging.getLogger(__name__)


class WireConnection:
    """Represents one live WebSocket connection."""

    def __init__(self, websocket: WebSocket, user_id: str, tenant_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.subscribed_channels: set[str] = set()

    async def send(self, event: dict[str, Any]) -> bool:
        """Send an event. Returns False if connection is dead."""
        try:
            await self.websocket.send_json(event)
            return True
        except Exception:
            return False

    def channel_key(self, channel_type: str, channel_id: str) -> str:
        return f"{self.tenant_id}:{channel_type}:{channel_id}"


class ConnectionManager:
    """
    Manages all active WebSocket connections for Sense Wire.

    Connections are indexed by:
        - connection_id → WireConnection  (all connections)
        - channel_key  → set of connection_ids  (per channel)

    Thread-safe via asyncio (single-threaded event loop per process).
    Cross-instance fan-out is handled by RedisPubSub.
    """

    def __init__(self):
        self._connections: dict[str, WireConnection] = {}
        self._channel_connections: dict[str, set[str]] = defaultdict(set)

    def _conn_id(self, websocket: WebSocket) -> str:
        return str(id(websocket))

    async def connect(self, websocket: WebSocket, user_id: str, tenant_id: str) -> WireConnection:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        conn = WireConnection(websocket, user_id, tenant_id)
        self._connections[self._conn_id(websocket)] = conn
        logger.info("WS connected — user=%s tenant=%s total=%d", user_id, tenant_id, len(self._connections))
        return conn

    async def disconnect(self, websocket: WebSocket) -> WireConnection | None:
        """Remove a connection and clean up channel subscriptions."""
        cid = self._conn_id(websocket)
        conn = self._connections.pop(cid, None)
        if conn:
            for ch_key in conn.subscribed_channels:
                self._channel_connections[ch_key].discard(cid)
            logger.info("WS disconnected — user=%s total=%d", conn.user_id, len(self._connections))
        return conn

    def subscribe(self, websocket: WebSocket, channel_type: str, channel_id: str) -> str:
        """Subscribe a connection to a channel. Returns channel key."""
        cid = self._conn_id(websocket)
        conn = self._connections.get(cid)
        if not conn:
            return ""
        ch_key = conn.channel_key(channel_type, channel_id)
        conn.subscribed_channels.add(ch_key)
        self._channel_connections[ch_key].add(cid)
        logger.debug("WS subscribe — user=%s channel=%s", conn.user_id, ch_key)
        return ch_key

    def unsubscribe(self, websocket: WebSocket, channel_type: str, channel_id: str):
        """Unsubscribe a connection from a channel."""
        cid = self._conn_id(websocket)
        conn = self._connections.get(cid)
        if not conn:
            return
        ch_key = conn.channel_key(channel_type, channel_id)
        conn.subscribed_channels.discard(ch_key)
        self._channel_connections[ch_key].discard(cid)

    async def broadcast_to_channel(
        self,
        tenant_id: str,
        channel_type: str,
        channel_id: str,
        event: dict[str, Any],
        exclude_user: str | None = None,
    ) -> int:
        """
        Send an event to all connections subscribed to a channel.

        Returns the number of connections successfully delivered to.
        """
        ch_key = f"{tenant_id}:{channel_type}:{channel_id}"
        cids = list(self._channel_connections.get(ch_key, set()))

        if not cids:
            return 0

        tasks = []
        dead_cids = []

        for cid in cids:
            conn = self._connections.get(cid)
            if not conn:
                dead_cids.append(cid)
                continue
            if exclude_user and conn.user_id == exclude_user:
                continue
            tasks.append(conn.send(event))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Clean up dead connections
        for cid in dead_cids:
            self._channel_connections[ch_key].discard(cid)

        delivered = sum(1 for r in results if r is True)
        return delivered

    async def send_to_user(
        self,
        tenant_id: str,
        user_id: str,
        event: dict[str, Any],
    ) -> int:
        """Send an event directly to all connections for a specific user."""
        delivered = 0
        for conn in self._connections.values():
            if conn.tenant_id == tenant_id and conn.user_id == user_id:
                if await conn.send(event):
                    delivered += 1
        return delivered

    def connection_count(self) -> int:
        return len(self._connections)

    def channel_subscriber_count(self, tenant_id: str, channel_type: str, channel_id: str) -> int:
        ch_key = f"{tenant_id}:{channel_type}:{channel_id}"
        return len(self._channel_connections.get(ch_key, set()))


# Module-level singleton
_manager: ConnectionManager | None = None


def get_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
