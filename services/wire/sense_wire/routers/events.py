"""
Sense Wire — Events Router
POST /channels/:type/:id/event — emit a custom event to channel subscribers.
Used by Sense Mind to push Lens events (mood, pose, guard, face) to the UI.
"""

import hmac

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from sense_wire.config import get_settings
from sense_wire.deps import DBDep, UserDep
from sense_wire.models.channel import Channel
from sense_wire.pubsub.redis_pubsub import get_pubsub
from sense_wire.ws.events import ServerEvent, make_event
from sense_wire.ws.manager import get_manager

router = APIRouter(prefix="/channels", tags=["Events"])


class EmitEventRequest(BaseModel):
    event_type: str = "custom"
    data: dict = {}


@router.post("/{channel_type}/{channel_id}/event")
async def emit_event(
    channel_type: str,
    channel_id: str,
    body: EmitEventRequest,
    user: UserDep,
    db: DBDep,
):
    """
    Emit a custom event to all subscribers of a channel.

    This is the primary way Sense Mind pushes Vision Lens events to the frontend:
    - `lens.event` with MoodLens data → UI shows emotion badge
    - `lens.event` with PoseLens data → UI shows form feedback overlay
    - `agent.message` → UI shows agent coaching whisper

    **Auth**: Sense Gate JWT
    """
    tenant_id = user.get("tenant_id", "")

    channel_result = await db.execute(
        select(Channel).where(
            Channel.tenant_id == tenant_id,
            Channel.channel_type == channel_type,
            Channel.channel_id == channel_id,
        )
    )
    channel = channel_result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    event_payload = make_event(
        body.event_type,
        user_id=user.get("sub"),
        channel_id=channel_id,
        channel_type=channel_type,
        data=body.data,
    )

    manager = get_manager()
    pubsub = get_pubsub()

    # Fan-out to local WebSocket connections
    delivered = await manager.broadcast_to_channel(
        tenant_id, channel_type, channel_id, event_payload
    )

    # Fan-out to other Wire instances via Redis
    await pubsub.publish(tenant_id, channel_type, channel_id, event_payload)

    return {
        "status": "emitted",
        "event_type": body.event_type,
        "delivered_local": delivered,
    }


# ── Trusted internal endpoint (service-to-service) ────────────────────────────

internal_router = APIRouter(prefix="/internal", tags=["Internal"])


class InternalEventRequest(BaseModel):
    tenant_id: str
    channel_type: str = "lens"
    channel_id: str
    event_type: str = "lens.event"
    data: dict = {}


@internal_router.post("/events")
async def internal_emit_event(
    body: InternalEventRequest,
    x_service_key: str | None = Header(default=None, alias="X-Service-Key"),
):
    """
    Push an event to a channel on behalf of a trusted service (Sense Mind).

    Unlike the public endpoint this needs no end-user JWT and does not require
    the channel to exist in the database — vision events are ephemeral.

    **Auth**: `X-Service-Key` header matching Wire's `SERVICE_KEY` setting.
    """
    expected = get_settings().service_key
    if not expected:
        raise HTTPException(status_code=503, detail="Internal events are disabled (SERVICE_KEY unset)")
    if not x_service_key or not hmac.compare_digest(x_service_key, expected):
        raise HTTPException(status_code=401, detail="Invalid service key")

    payload = make_event(
        body.event_type,
        channel_id=body.channel_id,
        channel_type=body.channel_type,
        data=body.data,
    )
    delivered = await get_manager().broadcast_to_channel(
        body.tenant_id, body.channel_type, body.channel_id, payload
    )
    await get_pubsub().publish(body.tenant_id, body.channel_type, body.channel_id, payload)
    return {"status": "emitted", "delivered_local": delivered}
