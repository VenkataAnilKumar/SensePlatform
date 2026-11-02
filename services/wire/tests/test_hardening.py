import pytest
from fastapi import FastAPI

from sense_wire.config import Settings


def test_insecure_defaults_detected():
    assert "JWT_SECRET" in Settings().insecure_defaults()
    assert Settings(jwt_secret="x" * 32, service_key="y" * 32).insecure_defaults() == []


@pytest.mark.asyncio
async def test_production_refuses_default_secrets(monkeypatch):
    from sense_wire import main

    monkeypatch.setattr(main, "settings", Settings(environment="production"))
    with pytest.raises(RuntimeError, match="default secrets"):
        async with main.lifespan(FastAPI()):
            pass
