"""Regression: Alembic must use the app's DATABASE_URL, not alembic.ini's localhost default."""
from pathlib import Path


def test_env_uses_application_database_url():
    env = (Path(__file__).resolve().parents[1] / "alembic" / "env.py").read_text()
    assert "get_settings().database_url" in env
