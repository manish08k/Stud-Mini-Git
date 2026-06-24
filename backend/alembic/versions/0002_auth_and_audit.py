"""add refresh_tokens, audit_logs, soft_delete, repo_name_pattern

Revision ID: 0002_auth_and_audit
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_auth_and_audit"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("created_at", sa.Float, nullable=False),
        sa.Column("expires_at", sa.Float, nullable=False),
        sa.Column("revoked", sa.Boolean, default=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False, index=True),
        sa.Column("resource", sa.String(256), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.Float, nullable=False, index=True),
    )

    op.add_column("repositories", sa.Column("deleted_at", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("repositories", "deleted_at")
    op.drop_table("audit_logs")
    op.drop_table("refresh_tokens")
