"""Initial schema – users, tokens, repositories, collaborators.

Revision ID: 0001_initial
Revises: 
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=True),
    )
    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=True),
        sa.Column("last_used_at", sa.Float(), nullable=True),
    )
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_private", sa.Boolean(), nullable=True),
        sa.Column("default_branch", sa.String(128), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=True),
        sa.UniqueConstraint("owner_id", "name", name="uq_owner_repo_name"),
    )
    op.create_table(
        "collaborators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=True),
        sa.UniqueConstraint("repo_id", "user_id", name="uq_repo_user"),
    )


def downgrade() -> None:
    op.drop_table("collaborators")
    op.drop_table("repositories")
    op.drop_table("tokens")
    op.drop_table("users")
