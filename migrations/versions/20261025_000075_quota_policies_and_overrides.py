"""Add admin-managed usage quota policies and per-user overrides.

Both tables are keyed by their primary key only: policies by quota kind, and
overrides by (user_id, quota_kind), which also covers the user foreign key. Every
policy starts in monitor mode, so usage is counted without blocking anyone.

Revision ID: 20261025_000075
Revises: 20261025_000074
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "20261025_000075"
down_revision = "20261025_000074"
branch_labels = None
depends_on = None

POLICIES = "quota_policies"
OVERRIDES = "user_quota_overrides"

# API/MCP limits mirror the former RATE_LIMIT_*_DAILY_MAX defaults; media is MB.
DEFAULT_POLICIES = {
    "api": {"regular": 300, "creator": 2000, "enterprise": 10000},
    "mcp": {"regular": 300, "creator": 2000, "enterprise": 10000},
    "media": {"regular": 100, "creator": 500, "enterprise": 2000},
}


def _table_options(bind):
    if bind.dialect.name != "mysql":
        return {}
    return {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(POLICIES):
        policies = op.create_table(
            POLICIES,
            sa.Column("quota_kind", sa.String(16), primary_key=True),
            sa.Column("enforce", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("period", sa.String(8), nullable=False, server_default="day"),
            sa.Column("role_limits", sa.JSON(), nullable=False),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("period IN ('day', 'month', 'year')", name="ck_quota_policies_period"),
            **_table_options(bind),
        )
        now = datetime.utcnow()
        op.bulk_insert(
            policies,
            [
                {"quota_kind": kind, "enforce": False, "period": "day", "role_limits": limits, "updated_at": now}
                for kind, limits in DEFAULT_POLICIES.items()
            ],
        )
    if not inspector.has_table(OVERRIDES):
        op.create_table(
            OVERRIDES,
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_user_quota_overrides_user_id"),
                primary_key=True,
            ),
            sa.Column("quota_kind", sa.String(16), primary_key=True),
            sa.Column("limit_value", sa.BigInteger(), nullable=False),
            sa.Column("period", sa.String(8), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("note", sa.String(255), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "period IS NULL OR period IN ('day', 'month', 'year')",
                name="ck_user_quota_overrides_period",
            ),
            sa.CheckConstraint("limit_value >= -1", name="ck_user_quota_overrides_limit"),
            **_table_options(bind),
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(OVERRIDES):
        op.drop_table(OVERRIDES)
    if inspector.has_table(POLICIES):
        op.drop_table(POLICIES)
