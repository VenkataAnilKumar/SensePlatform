import asyncio
from contextlib import asynccontextmanager

import pytest

import sense_mind.pool as pool_mod
from sense_mind.lenses.base_lens import BaseLens
from sense_mind.pool import AgentConfig, AgentPool


class FakeLens(BaseLens):
    name = "mood_lens"

    def process_frame(self, frame):
        return None


class FakeEdge:
    async def create_call(self, room):
        return object()


class FakeAgent:
    agent_user = object()

    def __init__(self, fail=False):
        self.lenses = [FakeLens()]
        self.edge = FakeEdge()
        self.fail = fail
        self.closed = False
        self._stop = asyncio.Event()

    async def authenticate(self):
        if self.fail:
            raise RuntimeError("relay down")

    @asynccontextmanager
    async def join(self, call, participant_wait_timeout=None):
        yield

    async def finish(self):
        await self._stop.wait()

    async def close(self):
        self.closed = True


@pytest.fixture
def pool(monkeypatch):
    monkeypatch.setattr(pool_mod, "_build_agent", lambda cfg: FakeAgent(fail=cfg.instructions == "fail"))
    return AgentPool()


@pytest.mark.asyncio
async def test_unknown_room_returns_none(pool):
    assert pool.get_lenses("nope") is None


@pytest.mark.asyncio
async def test_start_configure_stop(pool):
    res = await pool.start(AgentConfig(room="t__r", tenant_id="tid", room_id="r"))
    assert res["status"] == "started"
    assert (await pool.start(AgentConfig(room="t__r")))["status"] == "already_running"
    assert pool.routing("t__r") == ("tid", "r")

    # both identifiers address the lens
    for ident in ("mood_lens", "FakeLens"):
        out = pool.configure_lens("t__r", ident, throttle_seconds=9.0, enabled=False)
        assert out["status"] == "updated" and out["enabled"] is False
    assert pool.get_lenses("t__r")[0]["throttle_seconds"] == 9.0
    assert pool.configure_lens("t__r", "ghost")["status"] == "lens_not_found"

    assert (await pool.stop("t__r"))["status"] == "stopped"
    assert (await pool.stop("t__r"))["status"] == "not_found"


@pytest.mark.asyncio
async def test_failed_join_is_reported(pool):
    res = await pool.start(AgentConfig(room="bad", instructions="fail"))
    assert res["status"] == "failed" and "relay down" in res["error"]
    assert pool.status()["count"] == 0
