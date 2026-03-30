"""
Sense Gate — Rooms Router
POST /rooms/:room_id/join  — get a LiveKit token to join a Sense Relay room
GET  /rooms                — list active rooms for a tenant
"""

from fastapi import APIRouter
from pydantic import BaseModel

from sense_gate.deps import TenantDep
from sense_gate.services.relay_service import create_room, generate_relay_token, list_rooms

router = APIRouter(prefix="/rooms", tags=["Rooms"])


class JoinRoomRequest(BaseModel):
    user_id: str
    user_name: str = ""
    can_publish: bool = True
    can_subscribe: bool = True


class JoinRoomResponse(BaseModel):
    relay_url: str
    relay_token: str
    room_id: str
    room_name: str  # namespaced: {tenant_slug}__{room_id}


class RoomInfo(BaseModel):
    room_id: str
    room_name: str
    num_participants: int
    creation_time: int


@router.post("/{room_id}/join", response_model=JoinRoomResponse)
async def join_room(room_id: str, body: JoinRoomRequest, tenant: TenantDep):
    """
    Get a LiveKit access token for a user to join a Sense Relay room.

    The returned `relay_token` is passed directly to the LiveKit client SDK
    (web, iOS, Android) to establish a WebRTC connection.

    Rooms are auto-created on first join. Room names are namespaced per tenant.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    from sense_gate.config import get_settings
    settings = get_settings()

    # Auto-create the room if it doesn't exist
    room_name = await create_room(tenant.slug, room_id)

    # Generate LiveKit token
    relay_token = generate_relay_token(
        tenant_slug=tenant.slug,
        room_id=room_id,
        user_id=body.user_id,
        user_name=body.user_name,
        can_publish=body.can_publish,
        can_subscribe=body.can_subscribe,
    )

    return JoinRoomResponse(
        relay_url=settings.relay_url,
        relay_token=relay_token,
        room_id=room_id,
        room_name=room_name,
    )


@router.get("", response_model=list[RoomInfo])
async def get_rooms(tenant: TenantDep):
    """
    List all active rooms for this tenant on Sense Relay.

    **Auth**: Requires a valid API key (X-API-Key header).
    """
    rooms = await list_rooms(tenant.slug)
    return rooms
