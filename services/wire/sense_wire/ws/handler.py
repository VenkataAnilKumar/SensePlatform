"""
Sense Wire — WebSocket Message Handler
Processes incoming client events and routes them to the correct action.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from sense_wire.models.message import Message
from sense_wire.models.channel import Channel, ChannelMember
from sense_wire.pubsub.redis_pubsub import get_pubsub
from sense_wire.ws.events import ClientEvent, ServerEvent, make_event
from sense_wire.ws.manager import ConnectionManager, WireConnection

logger = logging.getLogger(__name__)


class WireEventHandler:
    """
    Handles all incoming WebSocket events from a single client connection.
    """

    def __init__(self, conn: WireConnection, manager: ConnectionManager, db: AsyncSession):
        self._conn = conn
        self._manager = manager
        self._db = db
        self._pubsub = get_pubsub()

    async def handle(self, event: dict[str, Any]) -> None:
        """Route an incoming event to the correct handler."""
        event_type = event.get("type", "")

        handlers = {
            ClientEvent.SUBSCRIBE: self._on_subscribe,
            ClientEvent.UNSUBSCRIBE: self._on_unsubscribe,
            ClientEvent.MESSAGE_NEW: self._on_message_new,
            ClientEvent.MESSAGE_DELETE: self._on_message_delete,
            ClientEvent.REACTION_ADD: self._on_reaction_add,
            ClientEvent.REACTION_REMOVE: self._on_reaction_remove,
            ClientEvent.TYPING_START: self._on_typing,
            ClientEvent.TYPING_STOP: self._on_typing,
            ClientEvent.READ_MARK: self._on_read_mark,
            ClientEvent.CUSTOM: self._on_custom,
        }

        handler = handlers.get(event_type)
        if handler:
            await handler(event)
        else:
            await self._conn.send(make_event(
                ServerEvent.ERROR,
                message=f"Unknown event type: {event_type}",
            ))

    # ── Subscription ──────────────────────────────────────────────────────────

    async def _on_subscribe(self, event: dict) -> None:
        channel_type = event.get("channel_type", "room")
        channel_id = event.get("channel_id", "")

        ch_key = self._manager.subscribe(self._conn.websocket, channel_type, channel_id)

        # Subscribe to Redis pub/sub for cross-instance fan-out
        await self._pubsub.subscribe(
            self._conn.tenant_id, channel_type, channel_id,
            self._on_redis_event,
        )

        await self._conn.send(make_event(
            ServerEvent.CHANNEL_UPDATED,
            channel_type=channel_type,
            channel_id=channel_id,
            subscribed=True,
        ))
        logger.debug("Subscribed user=%s to %s", self._conn.user_id, ch_key)

    async def _on_unsubscribe(self, event: dict) -> None:
        channel_type = event.get("channel_type", "room")
        channel_id = event.get("channel_id", "")

        self._manager.unsubscribe(self._conn.websocket, channel_type, channel_id)
        await self._pubsub.unsubscribe(
            self._conn.tenant_id, channel_type, channel_id,
            self._on_redis_event,
        )

    # ── Messages ──────────────────────────────────────────────────────────────

    async def _on_message_new(self, event: dict) -> None:
        channel_type = event.get("channel_type", "room")
        channel_id = event.get("channel_id", "")
        text = event.get("text", "").strip()
        parent_id = event.get("parent_id")

        if not text:
            return

        # Persist to DB
        from sqlalchemy import select
        result = await self._db.execute(
            select(Channel).where(
                Channel.tenant_id == self._conn.tenant_id,
                Channel.channel_type == channel_type,
                Channel.channel_id == channel_id,
            )
        )
        channel = result.scalar_one_or_none()
        if not channel:
            await self._conn.send(make_event(ServerEvent.ERROR, message="Channel not found"))
            return

        message = Message(
            channel_id=channel.id,
            user_id=self._conn.user_id,
            user_name=event.get("user_name", self._conn.user_id),
            text=text,
            parent_id=uuid.UUID(parent_id) if parent_id else None,
            extra_data=event.get("extra_data"),
        )
        self._db.add(message)
        channel.last_message_at = datetime.now(timezone.utc)
        channel.message_count = (channel.message_count or 0) + 1
        await self._db.flush()

        # Build broadcast payload
        broadcast = make_event(
            ServerEvent.MESSAGE_NEW,
            message={
                "id": str(message.id),
                "channel_id": channel_id,
                "channel_type": channel_type,
                "user_id": self._conn.user_id,
                "user_name": event.get("user_name", self._conn.user_id),
                "text": text,
                "parent_id": parent_id,
                "created_at": message.created_at.isoformat(),
            },
        )

        # Fan-out: local connections
        await self._manager.broadcast_to_channel(
            self._conn.tenant_id, channel_type, channel_id, broadcast
        )

        # Fan-out: other Wire instances via Redis
        await self._pubsub.publish(
            self._conn.tenant_id, channel_type, channel_id, broadcast
        )

    async def _on_message_delete(self, event: dict) -> None:
        message_id = event.get("message_id")
        if not message_id:
            return

        from sqlalchemy import select
        result = await self._db.execute(
            select(Message).where(
                Message.id == uuid.UUID(message_id),
                Message.user_id == self._conn.user_id,
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            return

        message.is_deleted = True
        message.deleted_at = datetime.now(timezone.utc)

        broadcast = make_event(
            ServerEvent.MESSAGE_DELETED,
            message_id=message_id,
            channel_id=event.get("channel_id"),
            channel_type=event.get("channel_type", "room"),
        )
        await self._manager.broadcast_to_channel(
            self._conn.tenant_id,
            event.get("channel_type", "room"),
            event.get("channel_id", ""),
            broadcast,
        )

    # ── Reactions ─────────────────────────────────────────────────────────────

    async def _on_reaction_add(self, event: dict) -> None:
        from sense_wire.models.message import Reaction
        message_id = event.get("message_id")
        emoji = event.get("emoji", "")
        if not message_id or not emoji:
            return

        reaction = Reaction(
            message_id=uuid.UUID(message_id),
            user_id=self._conn.user_id,
            emoji=emoji,
        )
        self._db.add(reaction)
        await self._db.flush()

        broadcast = make_event(
            ServerEvent.REACTION_NEW,
            message_id=message_id,
            user_id=self._conn.user_id,
            emoji=emoji,
            channel_id=event.get("channel_id"),
            channel_type=event.get("channel_type", "room"),
        )
        await self._manager.broadcast_to_channel(
            self._conn.tenant_id,
            event.get("channel_type", "room"),
            event.get("channel_id", ""),
            broadcast,
        )

    async def _on_reaction_remove(self, event: dict) -> None:
        from sense_wire.models.message import Reaction
        from sqlalchemy import select, delete
        message_id = event.get("message_id")
        emoji = event.get("emoji", "")
        if not message_id or not emoji:
            return

        await self._db.execute(
            delete(Reaction).where(
                Reaction.message_id == uuid.UUID(message_id),
                Reaction.user_id == self._conn.user_id,
                Reaction.emoji == emoji,
            )
        )

        broadcast = make_event(
            ServerEvent.REACTION_DELETED,
            message_id=message_id,
            user_id=self._conn.user_id,
            emoji=emoji,
        )
        await self._manager.broadcast_to_channel(
            self._conn.tenant_id,
            event.get("channel_type", "room"),
            event.get("channel_id", ""),
            broadcast,
        )

    # ── Typing indicators ─────────────────────────────────────────────────────

    async def _on_typing(self, event: dict) -> None:
        event_type = event.get("type")
        broadcast = make_event(
            ServerEvent.TYPING_START if event_type == ClientEvent.TYPING_START else ServerEvent.TYPING_STOP,
            user_id=self._conn.user_id,
            channel_id=event.get("channel_id"),
            channel_type=event.get("channel_type", "room"),
        )
        # Broadcast to others (exclude sender)
        await self._manager.broadcast_to_channel(
            self._conn.tenant_id,
            event.get("channel_type", "room"),
            event.get("channel_id", ""),
            broadcast,
            exclude_user=self._conn.user_id,
        )

    # ── Read receipts ─────────────────────────────────────────────────────────

    async def _on_read_mark(self, event: dict) -> None:
        from sqlalchemy import select
        channel_type = event.get("channel_type", "room")
        channel_id = event.get("channel_id", "")

        result = await self._db.execute(
            select(Channel).where(
                Channel.tenant_id == self._conn.tenant_id,
                Channel.channel_type == channel_type,
                Channel.channel_id == channel_id,
            )
        )
        channel = result.scalar_one_or_none()
        if not channel:
            return

        member_result = await self._db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel.id,
                ChannelMember.user_id == self._conn.user_id,
            )
        )
        member = member_result.scalar_one_or_none()
        if member:
            member.last_read_at = datetime.now(timezone.utc)

    # ── Custom events ─────────────────────────────────────────────────────────

    async def _on_custom(self, event: dict) -> None:
        broadcast = make_event(
            ServerEvent.CUSTOM,
            user_id=self._conn.user_id,
            data=event.get("data", {}),
            channel_id=event.get("channel_id"),
            channel_type=event.get("channel_type", "room"),
        )
        await self._manager.broadcast_to_channel(
            self._conn.tenant_id,
            event.get("channel_type", "room"),
            event.get("channel_id", ""),
            broadcast,
        )

    # ── Redis fan-out receiver ─────────────────────────────────────────────────

    async def _on_redis_event(self, event: dict) -> None:
        """Receive an event from Redis pub/sub and deliver to this connection."""
        await self._conn.send(event)
