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
        }
        if instructions:
            payload["instructions"] = instructions

        try:
            resp = await self._client.post("/agents/start", json=payload)
            resp.raise_for_status()
            logger.info("Agent started — tenant=%s room=%s", tenant_slug, room_id)
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("Failed to start agent: %s", e)
            # Return a local confirmation if Mind is not running yet
            return {"status": "queued", "room": room_name, "error": str(e)}

    async def stop_agent(self, tenant_slug: str, room_id: str) -> dict[str, Any]:
        """Stop a running agent in a room."""
        room_name = build_room_name(tenant_slug, room_id)
        try:
            resp = await self._client.post("/agents/stop", json={"room": room_name})
            resp.raise_for_status()
            logger.info("Agent stopped — tenant=%s room=%s", tenant_slug, room_id)
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("Failed to stop agent: %s", e)
            return {"status": "error", "error": str(e)}

    async def get_agent_status(self, tenant_slug: str, room_id: str) -> dict[str, Any]:
        """Get the status of an agent in a room."""
        try:
            resp = await self._client.get("/status")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            return {"status": "unavailable"}

    async def close(self):
        await self._client.aclose()


# Module-level singleton
_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
