import asyncio
import json

import pytest

from sense_wire.pubsub.redis_pubsub import RedisPubSub


class FakeRedis:
    def __init__(self):
        self.published = []

    async def publish(self, key, data):
        self.published.append((key, data))


class FakePubSub:
    def __init__(self, messages):
        self._messages = messages

    async def listen(self):
        for m in self._messages:
            yield m


@pytest.mark.asyncio
async def test_own_events_are_not_redelivered():
    ps = RedisPubSub()
    ps._redis = FakeRedis()
    await ps.publish("t", "lens", "r", {"type": "lens.event"})
    key, raw = ps._redis.published[0]
    assert json.loads(raw)["_origin"] == ps._instance_id

    foreign = json.dumps({"type": "lens.event", "_origin": "other-instance"})
    got = []
    ps._subscriptions[key] = [got.append]
    ps._pubsub = FakePubSub([
        {"type": "message", "channel": key, "data": raw},      # our own -> skipped
        {"type": "message", "channel": key, "data": foreign},  # other instance -> delivered
    ])
    await ps._listen()
    assert len(got) == 1 and "_origin" not in got[0]
