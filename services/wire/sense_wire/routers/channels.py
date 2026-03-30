"""
Sense Wire — Channels Router
Create, query, and manage message channels.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from sense_wire.deps import DBDep, UserDep
from sense_wire.models.channel import Channel, ChannelMember

router = APIRouter(prefix="/channels", tags=["Channels"])


class CreateChannelRequest(BaseModel):
    channel_type: str = "room"
    channel_id: str
    name: str | None = None
    description: str | None = None
    members: list[str] = []


class ChannelResponse(BaseModel):
    id: uuid.UUID
    tenant_id: str
    channel_type: str
    channel_id: str
    name: str | None
    description: str | None
    member_count: int
    message_count: int
    is_frozen: bool

    model_config = {"from_attributes": True}


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(body: CreateChannelRequest, user: UserDep, db: DBDep):
    """
    Create a new channel.

    Channels are automatically namespaced to the authenticated tenant.
    If the channel already exists, it is returned as-is.

    **Auth**: Sense Gate JWT (Authorization: Bearer <token>)
    """
    tenant_id = user.get("tenant_id", "")

    # Idempotent — return existing channel if found
    result = await db.execute(
        select(Channel).where(
            Channel.tenant_id == tenant_id,
            Channel.channel_type == body.channel_type,
            Channel.channel_id == body.channel_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    channel = Channel(
        tenant_id=tenant_id,
        channel_type=body.channel_type,
        channel_id=body.channel_id,
        name=body.name,
        description=body.description,
        created_by=user.get("sub"),
        member_count=len(body.members),
    )
    db.add(channel)
    await db.flush()

    # Add initial members
    for uid in body.members:
        db.add(ChannelMember(channel_id=channel.id, user_id=uid))

    return channel


@router.get("/{channel_type}/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_type: str, channel_id: str, user: UserDep, db: DBDep):
    """Get a channel by type and ID."""
    tenant_id = user.get("tenant_id", "")
    result = await db.execute(
        select(Channel).where(
            Channel.tenant_id == tenant_id,
            Channel.channel_type == channel_type,
            Channel.channel_id == channel_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.post("/{channel_type}/{channel_id}/members")
async def add_member(
    channel_type: str, channel_id: str,
    user_id: str,
    user: UserDep, db: DBDep,
):
    """Add a member to a channel."""
    tenant_id = user.get("tenant_id", "")
    result = await db.execute(
        select(Channel).where(
            Channel.tenant_id == tenant_id,
            Channel.channel_type == channel_type,
            Channel.channel_id == channel_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    member = ChannelMember(channel_id=channel.id, user_id=user_id)
    db.add(member)
    channel.member_count = (channel.member_count or 0) + 1
    return {"status": "added", "user_id": user_id}


@router.delete("/{channel_type}/{channel_id}/members/{user_id}")
async def remove_member(
    channel_type: str, channel_id: str, user_id: str,
    user: UserDep, db: DBDep,
):
    """Remove a member from a channel."""
    tenant_id = user.get("tenant_id", "")
    result = await db.execute(
        select(Channel).where(
            Channel.tenant_id == tenant_id,
            Channel.channel_type == channel_type,
            Channel.channel_id == channel_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    member_result = await db.execute(
        select(ChannelMember).where(
            ChannelMember.channel_id == channel.id,
            ChannelMember.user_id == user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if member:
        await db.delete(member)
        channel.member_count = max(0, (channel.member_count or 1) - 1)

    return {"status": "removed", "user_id": user_id}
