"""
Sense Wire — Messages Router
REST endpoints for message history and management.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc

from sense_wire.deps import DBDep, UserDep
from sense_wire.models.channel import Channel
from sense_wire.models.message import Attachment, Message, Reaction

router = APIRouter(prefix="/channels", tags=["Messages"])


class MessageResponse(BaseModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    user_id: str
    user_name: str | None
    text: str | None
    is_deleted: bool
    is_pinned: bool
    parent_id: uuid.UUID | None
    reply_count: int
    created_at: datetime
    reactions: list[dict] = []
    attachments: list[dict] = []

    model_config = {"from_attributes": True}


class MessagesResponse(BaseModel):
    messages: list[MessageResponse]
    has_more: bool
    next_cursor: str | None


@router.get("/{channel_type}/{channel_id}/messages", response_model=MessagesResponse)
async def query_messages(
    channel_type: str,
    channel_id: str,
    user: UserDep,
    db: DBDep,
    limit: int = Query(default=50, le=200),
    before: str | None = Query(default=None, description="Message ID cursor for pagination"),
):
    """
    Fetch message history for a channel.

    Returns messages in reverse chronological order (newest first).
    Use `before` cursor for pagination.

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

    query = (
        select(Message)
        .where(Message.channel_id == channel.id, Message.is_deleted == False)  # noqa: E712
        .order_by(desc(Message.created_at))
        .limit(limit + 1)
    )

    if before:
        before_result = await db.execute(select(Message).where(Message.id == uuid.UUID(before)))
        before_msg = before_result.scalar_one_or_none()
        if before_msg:
            query = query.where(Message.created_at < before_msg.created_at)

    result = await db.execute(query)
    messages = list(result.scalars().all())

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = str(messages[-1].id) if has_more and messages else None

    return MessagesResponse(
        messages=messages,
        has_more=has_more,
        next_cursor=next_cursor,
    )


@router.delete("/{channel_type}/{channel_id}/messages/{message_id}")
async def delete_message(
    channel_type: str,
    channel_id: str,
    message_id: uuid.UUID,
    user: UserDep,
    db: DBDep,
):
    """
    Delete a message (soft delete — content cleared, record kept).

    Users can only delete their own messages.
    **Auth**: Sense Gate JWT
    """
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.user_id == user.get("sub"),
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found or not owned by user")

    message.is_deleted = True
    message.deleted_at = datetime.now(timezone.utc)
    message.text = None  # clear content

    return {"status": "deleted", "message_id": str(message_id)}


@router.post("/{channel_type}/{channel_id}/messages/{message_id}/pin")
async def pin_message(
    channel_type: str,
    channel_id: str,
    message_id: uuid.UUID,
    user: UserDep,
    db: DBDep,
):
    """Pin a message in a channel. Auth: Sense Gate JWT"""
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    message.is_pinned = True
    return {"status": "pinned", "message_id": str(message_id)}
