"""
Sense Gate — Tenant & API Key Models
Each tenant is one product deployment (contact center, fitness app, etc.)
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sense_gate.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    """
    A Tenant is one developer account or product deployment.
    Rooms, agents, and channels are all namespaced per tenant.
    """
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    webhooks: Mapped[list["Webhook"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    usage_records: Mapped[list["UsageRecord"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug}>"


class ApiKey(Base):
    """
    API key for a tenant. Used to authenticate SDK/server requests.
    Format: sk_live_<random> or sk_test_<random>
    """
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # Only a SHA-256 digest of the key is stored; the raw key is shown once at creation.
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), default="Default Key")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="api_keys")

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @classmethod
    def generate(
        cls, tenant_id: uuid.UUID, name: str = "Default Key", test: bool = False
    ) -> tuple["ApiKey", str]:
        """Create a new key row. Returns ``(row, raw_key)``; the raw key is not stored."""
        prefix = "sk_test_" if test else "sk_live_"
        raw_key = prefix + secrets.token_urlsafe(32)
        row = cls(
            tenant_id=tenant_id,
            key_hash=cls.hash_key(raw_key),
            key_prefix=raw_key[:12],
            name=name,
            is_test=test,
        )
        return row, raw_key

    def __repr__(self) -> str:
        return f"<ApiKey id={self.id} key={self.key_prefix}...>"


class Webhook(Base):
    """Registered webhook endpoint for a tenant."""
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[str] = mapped_column(Text, default="*")  # comma-separated or "*"
    secret: Mapped[str] = mapped_column(String(64), default=lambda: secrets.token_hex(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="webhooks")


# Import here to avoid circular imports
from sense_gate.models.usage import UsageRecord  # noqa: E402, F401
