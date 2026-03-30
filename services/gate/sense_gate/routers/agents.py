"""
Sense Gate — Agents Router
POST /agents/start  — launch a Sense Mind agent into a room
POST /agents/stop   — stop a running agent
GET  /agents/status — get agent status in a room
"""

from fastapi import APIRouter
from pydantic import BaseModel

from sense_gate.deps import TenantDep
from sense_gate.services.agent_service import get_agent_service

router = APIRouter(prefix="/agents", tags=["Agents"])


class StartAgentRequest(BaseModel):
    room_id: str
    instructions: str | None = None
    lenses: list[str] = []
    llm: str = "claude-sonnet-4-6"


class StopAgentRequest(BaseModel):
    room_id: str


class AgentStatusResponse(BaseModel):
    status: str
    room: str | None = None
    lenses: list[dict] = []


@router.post("/start")
async def start_agent(body: StartAgentRequest, tenant: TenantDep):
    """
    Launch a Sense Mind AI agent into a tenant room.

    The agent will:
    - Join the Sense Relay room automatically
    - Start listening and speaking (if STT/TTS configured)
    - Activate any requested Vision Lenses

    Available lenses: `MoodLens`, `PoseLens`, `GuardLens`, `FaceLens`

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    service = get_agent_service()
    result = await service.start_agent(
        tenant_slug=tenant.slug,
        room_id=body.room_id,
        instructions=body.instructions,
        lenses=body.lenses,
        llm=body.llm,
    )
    return result


@router.post("/stop")
async def stop_agent(body: StopAgentRequest, tenant: TenantDep):
    """
    Stop a running Sense Mind agent in a room.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    service = get_agent_service()
    result = await service.stop_agent(tenant_slug=tenant.slug, room_id=body.room_id)
    return result


@router.get("/status")
async def get_agent_status(room_id: str, tenant: TenantDep):
    """
    Get the current status of an agent in a room.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    service = get_agent_service()
    result = await service.get_agent_status(tenant_slug=tenant.slug, room_id=room_id)
    return result
