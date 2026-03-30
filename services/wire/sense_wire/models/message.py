"""
Sense Wire — Message, Reaction, Attachment Models
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sense_wire.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Message(Base):
    """
    A single message in a channel.

    Types:
        regular   — standard user/agent message
        system    — platform-generated event (user joined, call started)
        ephemeral — not persisted (typing indicators, temp status)
        reply     — threaded reply to a parent message
    """
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Author
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_agent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Content
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str] = mapped_column(String(32), default="regular")

    # Threading
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    reply_count: Mapped[int] = mapped_column(Integer, default=0)

    # State
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    # Lens event data (when message is emitted by a Vision Lens)
    lens_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Custom metadata
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    channel: Mapped["Channel"] = relationship(back_populates="messages")  # noqa: F821
    reactions: Mapped[list["Reaction"]] = relationship(back_populates="message", cascade="all, delete-orphan")
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="message", cascade="all, delete-orphan")
    replies: Mapped[list["Message"]] = relationship(
        "Message",
        foreign_keys=[parent_id],
        backref="parent",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} user={self.user_id} channel={self.channel_id}>"


class Reaction(Base):
    """An emoji reaction on a message."""
    __tablename__ = "reactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    emoji: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    message: Mapped["Message"] = relationship(back_populates="reactions")


class Attachment(Base):
    """A file attachment on a message."""
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    message: Mapped["Message"] = relationship(back_populates="attachments")


# Avoid circular import
from sense_wire.models.channel import Channel  # noqa: E402, F401
