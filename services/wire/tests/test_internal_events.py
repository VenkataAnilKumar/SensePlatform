import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sense_wire.config import get_settings
from sense_wire.routers import events


class FakeManager:
    def __init__(self):
        self.calls = []

    async def broadcast_to_channel(self, tenant_id, ctype, cid, payload):
        self.calls.append((tenant_id, ctype, cid, payload))
        return 1


class FakePubSub:
    async def publish(self, *a):
        pass


@pytest.fixture
def client(monkeypatch):
    mgr = FakeManager()
    monkeypatch.setattr(events, "get_manager", lambda: mgr)
    monkeypatch.setattr(events, "get_pubsub", lambda: FakePubSub())
    app = FastAPI()
    app.include_router(events.internal_router)
    c = TestClient(app)
    c.mgr = mgr
    return c


BODY = {"tenant_id": "t1", "channel_id": "room1", "data": {"lens_name": "mood_lens"}}


def test_disabled_without_service_key(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "service_key", "")
    assert client.post("/internal/events", json=BODY).status_code == 503


def test_rejects_bad_key(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "service_key", "secret")
    assert client.post("/internal/events", json=BODY).status_code == 401
    assert client.post("/internal/events", json=BODY, headers={"X-Service-Key": "nope"}).status_code == 401


def test_delivers_with_valid_key(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "service_key", "secret")
    r = client.post("/internal/events", json=BODY, headers={"X-Service-Key": "secret"})
    assert r.status_code == 200 and r.json()["delivered_local"] == 1
    tenant, ctype, cid, payload = client.mgr.calls[0]
    assert (tenant, ctype, cid) == ("t1", "lens", "room1")
    assert payload["type"] == "lens.event" and payload["data"]["lens_name"] == "mood_lens"
