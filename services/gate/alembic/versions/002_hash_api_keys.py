"""Store API keys as SHA-256 hashes

Revision ID: 002
Revises: 001
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("key_hash", sa.String(64), nullable=True))
    op.add_column("api_keys", sa.Column("key_prefix", sa.String(16), nullable=True))
    # Backfill from the plaintext column (sha256() is built in to PostgreSQL 11+)
    op.execute(
        "UPDATE api_keys SET key_hash = encode(sha256(convert_to(key, 'UTF8')), 'hex'), "
        "key_prefix = left(key, 12)"
    )
    op.alter_column("api_keys", "key_hash", nullable=False)
    op.alter_column("api_keys", "key_prefix", nullable=False)
    op.drop_index("ix_api_keys_key", table_name="api_keys")
    op.drop_column("api_keys", "key")
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    # Raw keys cannot be recovered from hashes; existing keys are invalidated.
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.add_column("api_keys", sa.Column("key", sa.String(64), nullable=True))
    op.execute("UPDATE api_keys SET key = key_prefix || key_hash")
    op.execute("UPDATE api_keys SET is_active = false")
    op.alter_column("api_keys", "key", nullable=False)
    op.drop_column("api_keys", "key_hash")
    op.drop_column("api_keys", "key_prefix")
    op.create_index("ix_api_keys_key", "api_keys", ["key"])
