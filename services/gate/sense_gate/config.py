"""
Sense Gate — Configuration
All settings read from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Deployment ────────────────────────────────────────────────────────────
    # "production" refuses to start with default secrets and disables open tenant creation.
    environment: str = "development"
    # Protects POST /tenants (send as X-Admin-Key). Required in production.
    admin_api_key: str = ""

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "Sense Gate"
    version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 3000

    # ── Database (PostgreSQL) ─────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://sense:sense@localhost:5432/sense_gate"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_secret: str = "sense_jwt_secret_change_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    # ── Sense Relay ───────────────────────────────────────────────────────────
    relay_url: str = "ws://localhost:7880"
    relay_api_key: str = "sense_gateway"
    relay_api_secret: str = "secret_change_in_production"

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins, e.g. "https://app.example.com".
    cors_origins: str = "*"

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_requests: int = 100       # requests per window
    rate_limit_window_seconds: int = 60  # window size

    # ── Webhooks ──────────────────────────────────────────────────────────────
    webhook_timeout_seconds: int = 10
    webhook_max_retries: int = 3

    # ── Sense Mind (agent orchestration) ─────────────────────────────────────
    mind_url: str = "http://localhost:8080"


    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def insecure_defaults(self) -> list[str]:
        """Names of secrets still set to their shipped default values."""
        checks = {"JWT_SECRET": self.jwt_secret, "RELAY_API_SECRET": self.relay_api_secret}
        return [name for name, value in checks.items() if "change_in_production" in value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
