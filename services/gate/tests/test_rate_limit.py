from fastapi import FastAPI
from fastapi.testclient import TestClient

from sense_gate.config import get_settings
from sense_gate.middleware.rate_limit import RateLimitMiddleware


class FakePipe:
    def __init__(self, store):
        self.store, self.ops = store, []

    def zremrangebyscore(self, key, lo, hi):
        self.ops.append(("rem", key, lo, hi))

    def zadd(self, key, mapping):
        self.ops.append(("add", key, mapping))

    def zcard(self, key):
        self.ops.append(("card", key))

    def expire(self, key, ttl):
        pass

    async def execute(self):
        out = []
        for op in self.ops:
            z = self.store.setdefault(op[1], {})
            if op[0] == "rem":
                for m in [m for m, s in z.items() if op[2] <= s <= op[3]]:
                    del z[m]
                out.append(0)
            elif op[0] == "add":
                z.update(op[2]); out.append(1)
            else:
                out.append(len(z))
        return out


class FakeRedis:
    def __init__(self):
        self.store = {}

    def pipeline(self):
        return FakePipe(self.store)


def make_app(redis):
    app = FastAPI()
    app.state.redis = redis  # set after middleware is added, like the lifespan does
    app.add_middleware(RateLimitMiddleware)

    @app.get("/x")
    def x():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


def test_limiter_enforced_with_state_redis():
    limit = get_settings().rate_limit_requests
    client = TestClient(make_app(FakeRedis()))
    codes = [client.get("/x", headers={"X-API-Key": "k"}).status_code for _ in range(limit + 5)]
    assert codes[:limit] == [200] * limit
    assert set(codes[limit:]) == {429}
    assert client.get("/health").status_code == 200  # health is exempt


def test_passthrough_without_redis():
    client = TestClient(make_app(None))
    assert all(client.get("/x").status_code == 200 for _ in range(150))
