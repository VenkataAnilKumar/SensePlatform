"""
Sense Gate — Relay Service
Vends LiveKit access tokens for frontend clients to join Sense Relay rooms.
Namespace rooms per tenant: {tenant_slug}__{room_id}
"""

import logging

from livekit import api

from sense_gate.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def build_room_name(tenant_slug: str, room_id: str) -> str:
    """Namespace room names per tenant to prevent cross-tenant access."""
    return f"{tenant_slug}__{room_id}"


async def create_room(tenant_slug: str, room_id: str) -> str:
    """
    Create a room on Sense Relay for a tenant.

    Returns:
        The namespaced room name.
    """
    room_name = build_room_name(tenant_slug, room_id)
    lk_api = api.LiveKitAPI(
        url=settings.relay_url.replace("ws://", "http://").replace("wss://", "https://"),
        api_key=settings.relay_api_key,
        api_secret=settings.relay_api_secret,
    )
    try:
        await lk_api.room.create_room(api.CreateRoomRequest(name=room_name))
        logger.info("Created Relay room: %s", room_name)
    except Exception:
        logger.debug("Room %s already exists — continuing", room_name)
    finally:
        await lk_api.aclose()

    return room_name


def generate_relay_token(
    tenant_slug: str,
    room_id: str,
    user_id: str,
    user_name: str = "",
    can_publish: bool = True,
    can_subscribe: bool = True,
) -> str:
    """
    Generate a LiveKit JWT for a participant to join a Sense Relay room.

    This is what your frontend passes to the LiveKit client SDK.

    Args:
        tenant_slug:    Tenant identifier (used for room namespacing).
        room_id:        Room identifier (user-facing, not namespaced).
        user_id:        Participant identity.
        user_name:      Display name in the room.
        can_publish:    Allow publishing audio/video.
        can_subscribe:  Allow subscribing to others.

    Returns:
        Signed LiveKit JWT string.
    """
    room_name = build_room_name(tenant_slug, room_id)

    token = (
        api.AccessToken(settings.relay_api_key, settings.relay_api_secret)
        .with_identity(user_id)
        .with_name(user_name or user_id)
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=can_publish,
            can_subscribe=can_subscribe,
        ))
        .to_jwt()
    )

    logger.debug("Generated Relay token for user=%s room=%s", user_id, room_name)
    return token


async def list_rooms(tenant_slug: str) -> list[dict]:
    """List all active rooms for a tenant on Sense Relay."""
    lk_api = api.LiveKitAPI(
        url=settings.relay_url.replace("ws://", "http://").replace("wss://", "https://"),
        api_key=settings.relay_api_key,
        api_secret=settings.relay_api_secret,
    )
    try:
        response = await lk_api.room.list_rooms(api.ListRoomsRequest())
        prefix = f"{tenant_slug}__"
        rooms = [
            {
                "room_id": r.name.removeprefix(prefix),
                "room_name": r.name,
                "num_participants": r.num_participants,
                "creation_time": r.creation_time,
            }
            for r in response.rooms
            if r.name.startswith(prefix)
        ]
        return rooms
    finally:
        await lk_api.aclose()
