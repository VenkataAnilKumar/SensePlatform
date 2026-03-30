"""Initial schema — tenants, api_keys, webhooks, usage_records

Revision ID: 001
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), unique=True, nullable=False),
        sa.Column("email", sa.String(256), unique=True, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE")),
        sa.Column("key", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(128)),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("is_test", sa.Boolean, default=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "webhooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE")),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("events", sa.Text, default="*"),
        sa.Column("secret", sa.String(64)),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "usage_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE")),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("room_id", sa.String(128), nullable=True),
        sa.Column("agent_id", sa.String(128), nullable=True),
        sa.Column("quantity", sa.Float, default=1.0),
        sa.Column("unit", sa.String(32), default="count"),
        sa.Column("participants", sa.Integer, default=0),
        sa.Column("recorded_at", sa.DateTime(timezone=True)),
    )

    # Indexes for common queries
    op.create_index("ix_api_keys_key", "api_keys", ["key"])
    op.create_index("ix_usage_tenant_type", "usage_records", ["tenant_id", "event_type"])


def downgrade() -> None:
    op.drop_table("usage_records")
    op.drop_table("webhooks")
    op.drop_table("api_keys")
    op.drop_table("tenants")
