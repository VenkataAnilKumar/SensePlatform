import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from sense_gate import deps
from sense_gate.config import Settings


def make_client(monkeypatch, **overrides):
    settings = Settings(**overrides)
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    app = FastAPI()

    @app.post("/t", dependencies=[__import__("fastapi").Depends(deps.require_admin)])
    def create():
        return {"ok": True}

    return TestClient(app)


def test_open_in_development_without_admin_key(monkeypatch):
    assert make_client(monkeypatch).post("/t").status_code == 200


def test_disabled_in_production_without_admin_key(monkeypatch):
    assert make_client(monkeypatch, environment="production").post("/t").status_code == 403


def test_admin_key_required_when_configured(monkeypatch):
    c = make_client(monkeypatch, admin_api_key="adm")
    assert c.post("/t").status_code == 401
    assert c.post("/t", headers={"X-Admin-Key": "wrong"}).status_code == 401
    assert c.post("/t", headers={"X-Admin-Key": "adm"}).status_code == 200


def test_insecure_defaults_detected():
    assert set(Settings().insecure_defaults()) == {"JWT_SECRET", "RELAY_API_SECRET"}
    safe = Settings(jwt_secret="x" * 32, relay_api_secret="y" * 32)
    assert safe.insecure_defaults() == []


@pytest.mark.asyncio
async def test_production_refuses_default_secrets(monkeypatch):
    from sense_gate import main

    monkeypatch.setattr(main, "settings", Settings(environment="production"))
    with pytest.raises(RuntimeError, match="default secrets"):
        async with main.lifespan(FastAPI()):
            pass
