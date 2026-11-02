import httpx
import pytest

from sense_mind.bridge import LensEventBridge
from sense_mind.lenses.base_lens import LensEvent


class StubPool:
    def routing(self, room):
        return ("tenant-uuid", "room1") if room == "acme__room1" else (None, None)


def make_bridge(handler):
    b = LensEventBridge(wire_url="http://wire", api_key="svc-key")
    b._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    b._pool = StubPool()
    return b


@pytest.mark.asyncio
async def test_forward_uses_internal_endpoint_and_service_key():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("X-Service-Key")
        seen["body"] = request.read()
        return httpx.Response(200, json={"status": "emitted"})

    b = make_bridge(handler)
    ok = await b.forward("acme__room1", LensEvent(lens_name="mood_lens", data={"mood": "calm"}))
    assert ok
    assert seen["url"] == "http://wire/internal/events" and seen["key"] == "svc-key"
    import json
    body = json.loads(seen["body"])
    assert body["tenant_id"] == "tenant-uuid" and body["channel_id"] == "room1"
    assert body["event_type"] == "lens.event" and body["data"]["mood"] == "calm"


@pytest.mark.asyncio
async def test_unrouted_room_is_dropped_and_rate_capped():
    b = make_bridge(lambda r: httpx.Response(200, json={}))
    assert not await b.forward("other", LensEvent(lens_name="x"))
    assert await b.forward("acme__room1", LensEvent(lens_name="x"))
    assert not await b.forward("acme__room1", LensEvent(lens_name="x"))  # < min_interval
