"""
Sense Gate — Usage Metering Model
Tracks API calls, room minutes, and participant counts per tenant.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sense_gate.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UsageRecord(Base):
    """
    One record per billable event: room session, API call, agent minute, etc.
    """
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    # Event classification
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # e.g.: "room_session", "agent_minute", "api_call", "stt_second", "tts_character"

    room_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Quantity (minutes, characters, count, etc.)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit: Mapped[str] = mapped_column(String(32), default="count")
    # e.g.: "minutes", "characters", "count", "seconds"

    participants: Mapped[int] = mapped_column(Integer, default=0)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="usage_records")  # noqa: F821

    def __repr__(self) -> str:
        return f"<UsageRecord tenant={self.tenant_id} type={self.event_type} qty={self.quantity}>"
