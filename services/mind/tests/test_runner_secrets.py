import pytest

from sense_mind.runner import SenseRunner


def test_production_refuses_default_secrets(monkeypatch):
    monkeypatch.setenv("SENSE_ENV", "production")
    monkeypatch.delenv("SENSE_RELAY_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="default secrets"):
        SenseRunner._check_secrets()


def test_production_accepts_real_secrets(monkeypatch):
    monkeypatch.setenv("SENSE_ENV", "production")
    monkeypatch.setenv("SENSE_RELAY_SECRET", "a-real-secret")
    monkeypatch.setenv("SENSE_WIRE_API_KEY", "a-real-key")
    SenseRunner._check_secrets()


def test_development_only_warns(monkeypatch):
    monkeypatch.setenv("SENSE_ENV", "development")
    monkeypatch.delenv("SENSE_RELAY_SECRET", raising=False)
    SenseRunner._check_secrets()
