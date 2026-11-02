"""
Sense Gate — Agents Router
POST /agents/start  — launch a Sense Mind agent into a room
POST /agents/stop   — stop a running agent
GET  /agents/status — get agent status in a room
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sense_gate.deps import TenantDep
from sense_gate.services.agent_service import AgentServiceError, get_agent_service

router = APIRouter(prefix="/agents", tags=["Agents"])


class StartAgentRequest(BaseModel):
    room_id: str
    instructions: str | None = None
    lenses: list[str] = []
    llm: str = "claude-sonnet-4-6"
    stt: str | None = None  # e.g. "deepgram"; default: auto-detect from Mind's API keys
    tts: str | None = None  # e.g. "elevenlabs"


class StopAgentRequest(BaseModel):
    room_id: str


class LensConfigRequest(BaseModel):
    throttle_seconds: float | None = None
    enabled: bool | None = None


async def _call(coro):
    """Run an AgentService call and translate Mind errors to HTTP errors."""
    try:
        return await coro
    except AgentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


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
    return await _call(service.start_agent(
        tenant_slug=tenant.slug,
        room_id=body.room_id,
        instructions=body.instructions,
        lenses=body.lenses,
        llm=body.llm,
        tenant_id=str(tenant.id),
        stt=body.stt,
        tts=body.tts,
    ))


@router.post("/stop")
async def stop_agent(body: StopAgentRequest, tenant: TenantDep):
    """
    Stop a running Sense Mind agent in a room.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    service = get_agent_service()
    return await _call(service.stop_agent(tenant_slug=tenant.slug, room_id=body.room_id))


@router.get("/status")
async def get_agent_status(room_id: str, tenant: TenantDep):
    """
    Get the current status of an agent in a room.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    service = get_agent_service()
    return await _call(service.get_agent_status(tenant_slug=tenant.slug, room_id=room_id))


@router.get("/lenses")
async def get_agent_lenses(room_id: str, tenant: TenantDep):
    """List the vision lenses attached to the agent in a room."""
    service = get_agent_service()
    return await _call(service.get_lenses(tenant_slug=tenant.slug, room_id=room_id))


@router.post("/lenses/{lens_name}/configure")
async def configure_agent_lens(
    lens_name: str, room_id: str, body: LensConfigRequest, tenant: TenantDep
):
    """Change a lens's throttle or enabled state at runtime."""
    service = get_agent_service()
    return await _call(service.configure_lens(
        tenant_slug=tenant.slug,
        room_id=room_id,
        lens_name=lens_name,
        throttle_seconds=body.throttle_seconds,
        enabled=body.enabled,
    ))
