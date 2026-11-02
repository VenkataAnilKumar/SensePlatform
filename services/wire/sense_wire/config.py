"""
Sense Wire — Configuration
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "production" refuses to start with default secrets.
    environment: str = "development"

    app_name: str = "Sense Wire"
    version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 3001

    # Database
    database_url: str = "postgresql+asyncpg://sense:sense@localhost:5432/sense_wire"

    # Redis (pub/sub fan-out across instances)
    redis_url: str = "redis://localhost:6379/1"

    # JWT (validated against Sense Gate's secret)
    jwt_secret: str = "sense_jwt_secret_change_in_production"
    jwt_algorithm: str = "HS256"

    # Shared secret for trusted internal callers (Sense Mind's LensEventBridge).
    # Empty disables the internal endpoint.
    service_key: str = ""

    # Message limits
    max_message_length: int = 5000
    max_attachments: int = 10
    message_history_limit: int = 100

    # S3-compatible storage for attachments (optional)
    storage_endpoint: str | None = None
    storage_bucket: str = "sense-wire-attachments"
    storage_access_key: str | None = None
    storage_secret_key: str | None = None


    def insecure_defaults(self) -> list[str]:
        checks = {"JWT_SECRET": self.jwt_secret, "SERVICE_KEY": self.service_key}
        return [n for n, v in checks.items() if "change_in_production" in v]


@lru_cache
def get_settings() -> Settings:
    return Settings()
