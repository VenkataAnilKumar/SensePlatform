"""
Sense Wire — Channel Model
A Channel is a named message stream (room chat, DM, broadcast, system).
Channels are scoped per tenant via tenant_id.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sense_wire.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Channel(Base):
    """
    A channel is a message stream.

    Types:
        room      — tied to a Sense Relay room (most common)
        dm        — direct message between two users
        broadcast — one-way announcements (agent → participants)
        system    — internal platform events
    """
    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel_type: Mapped[str] = mapped_column(String(32), default="room")
    channel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # channel_id is user-facing (e.g. "support-room-42")
    # Full unique key = tenant_id + channel_type + channel_id

    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    members: Mapped[list["ChannelMember"]] = relationship(back_populates="channel", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Channel {self.channel_type}:{self.channel_id} tenant={self.tenant_id}>"


class ChannelMember(Base):
    """A user's membership in a channel."""
    __tablename__ = "channel_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="member")
    # roles: owner, moderator, member, readonly

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False)

    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    channel: Mapped["Channel"] = relationship(back_populates="members")

    def __repr__(self) -> str:
        return f"<ChannelMember user={self.user_id} channel={self.channel_id}>"


# Avoid circular import
from sense_wire.models.message import Message  # noqa: E402, F401
