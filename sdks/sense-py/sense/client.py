"""
SenseClient — Sense Gate HTTP Client
======================================
Async HTTP client for all Sense Gate REST operations.
Handles API key auth, JWT token lifecycle, and all resource APIs.

Usage:
    async with SenseClient(api_key="sk_live_...") as client:
        await client.connect()

        # Room management
        rooms = await client.rooms.list()
        token = await client.rooms.join("my-room", user_id="user_1")

        # Agent management
        await client.agents.start("my-room", lenses=["MoodLens"])
        await client.agents.stop("my-room")

        # Messaging
        msgs = await client.channels.messages("messaging", "room1")

        # Usage
        usage = await client.usage.summary()
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from sense.models import (
    AgentStatus,
    ApiKey,
    LensInfo,
    Message,
    RelayToken,
    Room,
    Tenant,
    UsageSummary,
    Webhook,
)

logger = logging.getLogger(__name__)


class SenseClient:
    """
    Async HTTP client for Sense Gate.

    Args:
        api_key:  Sense API key (sk_live_... or sk_test_...).
                  Falls back to SENSE_API_KEY env var.
        gate_url: Sense Gate base URL.
                  Falls back to SENSE_GATE_URL env var or http://localhost:3000.

    Example:
        async with SenseClient(api_key="sk_live_abc123") as client:
            await client.connect()
            rooms = await client.rooms.list()
    """

    def __init__(
        self,
        api_key: str | None = None,
        gate_url: str | None = None,
    ):
        self._api_key = api_key or os.environ.get("SENSE_API_KEY", "")
        self._gate_url = (gate_url or os.environ.get("SENSE_GATE_URL", "http://localhost:3000")).rstrip("/")
        self._jwt: str | None = None
        self._tenant: Tenant | None = None

        self._http = httpx.AsyncClient(
            base_url=self._gate_url,
            headers={"X-API-Key": self._api_key},
            timeout=15.0,
        )

        # Sub-resource APIs (lazy-initialised once connected)
        self.rooms = _RoomsAPI(self)
        self.agents = _AgentsAPI(self)
        self.channels = _ChannelsAPI(self)
        self.webhooks = _WebhooksAPI(self)
        self.usage = _UsageAPI(self)
        self.keys = _ApiKeysAPI(self)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> "SenseClient":
        """
        Authenticate with Sense Gate and fetch tenant info.
        Must be called before using resource APIs.
        """
        data = await self._get("/tenants/me")
        self._tenant = Tenant(
            id=data["id"],
            name=data["name"],
            slug=data["slug"],
            plan=data.get("plan", "free"),
            is_active=data.get("is_active", True),
        )
        logger.info("SenseClient connected — tenant: %s (%s)", self._tenant.name, self._tenant.slug)
        return self

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    # Context manager support
    async def __aenter__(self) -> "SenseClient":
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    @property
    def tenant(self) -> Tenant | None:
        """The authenticated tenant. Available after connect()."""
        return self._tenant

    # ── Health ────────────────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Check Sense Gate + Sense Mind health."""
        return await self._get("/health")

    # ── Internal HTTP helpers ─────────────────────────────────────────────────

    async def _get(self, path: str, **params) -> Any:
        resp = await self._http.get(path, params=params or None)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: Any = None) -> Any:
        resp = await self._http.post(path, json=json)
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, path: str) -> Any:
        resp = await self._http.delete(path)
        resp.raise_for_status()
        return resp.json()


# ── Sub-resource APIs ─────────────────────────────────────────────────────────

class _RoomsAPI:
    """Room management. Access via client.rooms.*"""

    def __init__(self, client: SenseClient):
        self._c = client

    async def list(self) -> list[Room]:
        """List all rooms for the authenticated tenant."""
        data = await self._c._get("/rooms")
        return [
            Room(
                id=r["id"],
                tenant_id=r["tenant_id"],
                name=r["name"],
                active_participants=r.get("active_participants", 0),
                created_at=r.get("created_at", ""),
            )
            for r in data.get("rooms", [])
        ]

    async def get(self, room_id: str) -> Room:
        """Get a room by ID."""
        data = await self._c._get(f"/rooms/{room_id}")
        return Room(
            id=data["id"],
            tenant_id=data["tenant_id"],
            name=data["name"],
            active_participants=data.get("active_participants", 0),
            created_at=data.get("created_at", ""),
        )

    async def join(
        self,
        room_id: str,
        user_id: str,
        user_name: str = "",
        can_publish: bool = True,
        can_subscribe: bool = True,
    ) -> RelayToken:
        """
        Get a LiveKit access token for a user to join a room.
        Pass the returned relay_url + relay_token to the LiveKit JS/Python client.

        Args:
            room_id:       Room identifier.
            user_id:       Unique user identity.
            user_name:     Display name.
            can_publish:   Allow sending audio/video.
            can_subscribe: Allow receiving audio/video.

        Returns:
            RelayToken with relay_url and relay_token ready for LiveKit.
        """
        data = await self._c._post(f"/rooms/{room_id}/join", json={
            "user_id": user_id,
            "user_name": user_name or user_id,
            "can_publish": can_publish,
            "can_subscribe": can_subscribe,
        })
        return RelayToken(
            relay_url=data["relay_url"],
            relay_token=data["relay_token"],
            room_name=data.get("room_name", ""),
        )

    async def delete(self, room_id: str) -> dict:
        """Delete a room."""
        return await self._c._delete(f"/rooms/{room_id}")


class _AgentsAPI:
    """Agent lifecycle management. Access via client.agents.*"""

    def __init__(self, client: SenseClient):
        self._c = client

    async def start(
        self,
        room_id: str,
        instructions: str | None = None,
        lenses: list[str] | None = None,
        llm: str = "claude-sonnet-4-6",
    ) -> dict[str, Any]:
        """
        Launch a Sense Mind agent into a room.

        Args:
            room_id:      Room to join.
            instructions: Override system prompt.
            lenses:       Vision lenses to enable (e.g. ["MoodLens", "FaceLens"]).
            llm:          LLM model name (e.g. "claude-sonnet-4-6").

        Returns:
            {"status": "started", "room": ...}
        """
        return await self._c._post("/agents/start", json={
            "room_id": room_id,
            "instructions": instructions,
            "lenses": lenses or [],
            "llm": llm,
        })

    async def stop(self, room_id: str) -> dict[str, Any]:
        """Stop the agent running in a room."""
        return await self._c._post("/agents/stop", json={"room_id": room_id})

    async def status(self, room_id: str) -> AgentStatus:
        """Get agent status for a room."""
        data = await self._c._get(f"/agents/{room_id}/status")
        return AgentStatus(
            room=data.get("room", room_id),
            status=data.get("status", "unknown"),
            llm=data.get("llm", ""),
            lenses=data.get("lenses", []),
            uptime_seconds=float(data.get("uptime_seconds", 0)),
        )

    async def get_lenses(self, room_id: str) -> list[LensInfo]:
        """List lenses attached to the agent in a room."""
        data = await self._c._get(f"/agents/{room_id}/lenses")
        return [
            LensInfo(
                name=l["name"],
                throttle_seconds=float(l.get("throttle_seconds", 0)),
                available=bool(l.get("available", True)),
            )
            for l in data.get("lenses", [])
        ]

    async def configure_lens(
        self,
        room_id: str,
        lens_name: str,
        throttle_seconds: float | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        """Update lens configuration for a running agent."""
        return await self._c._post(f"/agents/{room_id}/lenses/{lens_name}/configure", json={
            "throttle_seconds": throttle_seconds,
            "enabled": enabled,
        })


class _ChannelsAPI:
    """Messaging channel operations. Access via client.channels.*"""

    def __init__(self, client: SenseClient):
        self._c = client

    async def messages(
        self,
        channel_type: str,
        channel_id: str,
        limit: int = 50,
        before: str | None = None,
    ) -> list[Message]:
        """
        Fetch message history for a channel.

        Args:
            channel_type: Channel type (e.g. "messaging").
            channel_id:   Channel identifier.
            limit:        Max messages to return (default 50).
            before:       Cursor — return messages before this message ID.

        Returns:
            List of Message objects, newest first.
        """
        params: dict[str, Any] = {"limit": limit}
        if before:
            params["before"] = before

        data = await self._c._get(
            f"/channels/{channel_type}/{channel_id}/query",
            **params,
        )
        return [
            Message(
                id=m["id"],
                channel_id=m["channel_id"],
                tenant_id=m.get("tenant_id", ""),
                user_id=m["user_id"],
                text=m["text"],
                created_at=m.get("created_at", ""),
                is_deleted=m.get("is_deleted", False),
            )
            for m in data.get("messages", [])
        ]

    async def send_message(
        self,
        channel_type: str,
        channel_id: str,
        user_id: str,
        text: str,
    ) -> Message:
        """Send a message to a channel via REST (use SenseWire for real-time)."""
        data = await self._c._post(
            f"/channels/{channel_type}/{channel_id}/message",
            json={"user_id": user_id, "text": text},
        )
        m = data["message"]
        return Message(
            id=m["id"],
            channel_id=m["channel_id"],
            tenant_id=m.get("tenant_id", ""),
            user_id=m["user_id"],
            text=m["text"],
            created_at=m.get("created_at", ""),
        )


class _WebhooksAPI:
    """Webhook management. Access via client.webhooks.*"""

    def __init__(self, client: SenseClient):
        self._c = client

    async def list(self) -> list[Webhook]:
        """List all registered webhooks."""
        data = await self._c._get("/webhooks")
        return [
            Webhook(
                id=w["id"],
                tenant_id=w["tenant_id"],
                url=w["url"],
                events=w.get("events", []),
                is_active=w.get("is_active", True),
                created_at=w.get("created_at", ""),
            )
            for w in data.get("webhooks", [])
        ]

    async def register(
        self,
        url: str,
        events: list[str] | None = None,
    ) -> Webhook:
        """Register a new webhook endpoint."""
        data = await self._c._post("/webhooks/register", json={
            "url": url,
            "events": events or [],
        })
        w = data.get("webhook", data)
        return Webhook(
            id=w["id"],
            tenant_id=w["tenant_id"],
            url=w["url"],
            events=w.get("events", []),
        )

    async def delete(self, webhook_id: str) -> dict:
        """Delete a webhook."""
        return await self._c._delete(f"/webhooks/{webhook_id}")


class _UsageAPI:
    """Usage metrics. Access via client.usage.*"""

    def __init__(self, client: SenseClient):
        self._c = client

    async def summary(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> UsageSummary:
        """
        Fetch usage summary.

        Args:
            start_date: ISO date string (e.g. "2026-03-01").
            end_date:   ISO date string (e.g. "2026-03-31").
        """
        params: dict[str, Any] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data = await self._c._get("/usage/summary", **params)
        return UsageSummary(
            tenant_id=data.get("tenant_id", ""),
            period_start=data.get("period_start", ""),
            period_end=data.get("period_end", ""),
            total_calls=int(data.get("total_calls", 0)),
            total_minutes=float(data.get("total_minutes", 0)),
            total_participants=int(data.get("total_participants", 0)),
            by_type=data.get("by_type", {}),
        )


class _ApiKeysAPI:
    """API key management. Access via client.keys.*"""

    def __init__(self, client: SenseClient):
        self._c = client

    async def list(self) -> list[ApiKey]:
        """List all API keys for the tenant."""
        data = await self._c._get("/tenants/keys")
        return [
            ApiKey(
                id=k["id"],
                tenant_id=k["tenant_id"],
                name=k["name"],
                key=k.get("key", "sk_live_***"),
                is_test=k.get("is_test", False),
                created_at=k.get("created_at", ""),
            )
            for k in data.get("keys", [])
        ]

    async def create(self, name: str = "Default Key", test: bool = False) -> ApiKey:
        """Create a new API key. The full key is only shown once."""
        data = await self._c._post("/tenants/keys", json={"name": name, "test": test})
        k = data.get("api_key", data)
        return ApiKey(
            id=k["id"],
            tenant_id=k["tenant_id"],
            name=k["name"],
            key=k["key"],
            is_test=k.get("is_test", False),
        )

    async def revoke(self, key_id: str) -> dict:
        """Revoke (delete) an API key."""
        return await self._c._delete(f"/tenants/keys/{key_id}")
