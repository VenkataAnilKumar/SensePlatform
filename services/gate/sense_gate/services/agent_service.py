"""
Sense Gate — Agent Service
Start and stop Sense Mind agent instances via HTTP.
"""

import logging
from typing import Any

import httpx

from sense_gate.config import get_settings
from sense_gate.services.relay_service import build_room_name

settings = get_settings()
logger = logging.getLogger(__name__)


class AgentServiceError(Exception):
    """Sense Mind rejected a request or could not be reached."""

    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


class AgentService:
    """
    Orchestrates Sense Mind agent instances.
    Communicates with the Sense Mind HTTP control API.
    """

    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=settings.mind_url,
            timeout=10.0,
        )

    async def start_agent(
        self,
        tenant_slug: str,
        room_id: str,
        instructions: str | None = None,
        lenses: list[str] | None = None,
        llm: str = "claude-sonnet-4-6",
        tenant_id: str | None = None,
        stt: str | None = None,
        tts: str | None = None,
    ) -> dict[str, Any]:
        """
        Launch a Sense Mind agent into a tenant room.

        Args:
            tenant_slug: Tenant identifier.
            room_id:     User-facing room ID.
            instructions: Override system prompt.
            lenses:      Vision lenses to enable (e.g. ["MoodLens", "FaceLens"]).
            llm:         LLM model name.

        Returns:
            Agent status dict from Sense Mind API.
        """
        room_name = build_room_name(tenant_slug, room_id)
        payload = {
            "room": room_name,
            "llm": llm,
            "lenses": lenses or [],
            # Lets Sense Mind stream lens events to this tenant's Wire channel
            "tenant_id": tenant_id,
            "room_id": room_id,
            "stt": stt,
            "tts": tts,
        }
        if instructions:
            payload["instructions"] = instructions

        result = await self._request("POST", "/agents/start", json=payload)
        logger.info("Agent %s — tenant=%s room=%s", result.get("status"), tenant_slug, room_id)
        return result

    async def stop_agent(self, tenant_slug: str, room_id: str) -> dict[str, Any]:
        """Stop a running agent in a room."""
        room_name = build_room_name(tenant_slug, room_id)
        result = await self._request("POST", "/agents/stop", json={"room": room_name})
        logger.info("Agent stopped — tenant=%s room=%s", tenant_slug, room_id)
        return result

    async def get_agent_status(self, tenant_slug: str, room_id: str) -> dict[str, Any]:
        """Get the status of an agent in a room."""
        room_name = build_room_name(tenant_slug, room_id)
        return await self._request("GET", "/agents/status", params={"room": room_name})

    async def get_lenses(self, tenant_slug: str, room_id: str) -> dict[str, Any]:
        """List lenses on the agent in a room."""
        room_name = build_room_name(tenant_slug, room_id)
        return await self._request("GET", f"/agents/{room_name}/lenses")

    async def configure_lens(
        self,
        tenant_slug: str,
        room_id: str,
        lens_name: str,
        throttle_seconds: float | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        """Update a lens at runtime."""
        room_name = build_room_name(tenant_slug, room_id)
        return await self._request(
            "POST",
            f"/agents/{room_name}/lenses/{lens_name}/configure",
            json={"throttle_seconds": throttle_seconds, "enabled": enabled},
        )

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Call Sense Mind; map failures to AgentServiceError (never fake success)."""
        try:
            resp = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            logger.error("Sense Mind unreachable (%s %s): %s", method, path, e)
            raise AgentServiceError(503, "Sense Mind is unavailable") from e
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise AgentServiceError(resp.status_code, detail)
        return resp.json()

    async def close(self):
        await self._client.aclose()


# Module-level singleton
_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
