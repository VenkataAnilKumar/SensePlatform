"""
Sense Wire — Redis Pub/Sub
Fan-out messages to all Wire instances so every connected WebSocket
client receives events even when running multiple pods.

Channel key format: wire:{tenant_id}:{channel_type}:{channel_id}
"""

import asyncio
import json
import logging
from typing import Any, Callable

import redis.asyncio as aioredis

from sense_wire.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _channel_key(tenant_id: str, channel_type: str, channel_id: str) -> str:
    return f"wire:{tenant_id}:{channel_type}:{channel_id}"


class RedisPubSub:
    """
    Thin wrapper around Redis pub/sub for Sense Wire fan-out.

    Usage:
        pubsub = RedisPubSub()
        await pubsub.connect()

        # Publisher (message sent by any Wire instance)
        await pubsub.publish(tenant_id, channel_type, channel_id, event)

        # Subscriber (receives events for a channel)
        await pubsub.subscribe(tenant_id, channel_type, channel_id, callback)
    """

    def __init__(self):
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._subscriptions: dict[str, list[Callable]] = {}
        self._listener_task: asyncio.Task | None = None

    async def connect(self):
        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        logger.info("Wire Redis pub/sub connected: %s", settings.redis_url)

    async def publish(
        self,
        tenant_id: str,
        channel_type: str,
        channel_id: str,
        event: dict[str, Any],
    ) -> None:
        """Publish an event to all Wire instances subscribed to this channel."""
        if not self._redis:
            return
        key = _channel_key(tenant_id, channel_type, channel_id)
        try:
            await self._redis.publish(key, json.dumps(event))
        except Exception as e:
            logger.error("Redis publish error: %s", e)

    async def subscribe(
        self,
        tenant_id: str,
        channel_type: str,
        channel_id: str,
        callback: Callable[[dict], Any],
    ) -> None:
        """Subscribe to events on a channel."""
        key = _channel_key(tenant_id, channel_type, channel_id)
        if key not in self._subscriptions:
            self._subscriptions[key] = []
            if self._pubsub:
                await self._pubsub.subscribe(key)

        self._subscriptions[key].append(callback)

        # Start listener if not running
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.ensure_future(self._listen())

    async def unsubscribe(
        self,
        tenant_id: str,
        channel_type: str,
        channel_id: str,
        callback: Callable,
    ) -> None:
        """Remove a callback from a channel subscription."""
        key = _channel_key(tenant_id, channel_type, channel_id)
        if key in self._subscriptions:
            self._subscriptions[key] = [
                cb for cb in self._subscriptions[key] if cb != callback
            ]
            if not self._subscriptions[key]:
                del self._subscriptions[key]
                if self._pubsub:
                    await self._pubsub.unsubscribe(key)

    async def _listen(self):
        """Background task — routes incoming Redis messages to callbacks."""
        if not self._pubsub:
            return
        try:
            async for message in self._pubsub.listen():
                if message["type"] != "message":
                    continue
                key = message["channel"]
                callbacks = self._subscriptions.get(key, [])
                if not callbacks:
                    continue
                try:
                    event = json.loads(message["data"])
                except json.JSONDecodeError:
                    continue
                for cb in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(cb):
                            await cb(event)
                        else:
                            cb(event)
                    except Exception as e:
                        logger.debug("Pub/sub callback error: %s", e)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Redis listener error: %s", e)

    async def close(self):
        if self._listener_task:
            self._listener_task.cancel()
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.aclose()
        logger.info("Wire Redis pub/sub closed")


# Module-level singleton
_pubsub: RedisPubSub | None = None


def get_pubsub() -> RedisPubSub:
    global _pubsub
    if _pubsub is None:
        _pubsub = RedisPubSub()
    return _pubsub
