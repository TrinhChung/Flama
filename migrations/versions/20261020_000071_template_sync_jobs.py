"""Queue template fan-out atomically and deliver recipients independently.

Revision ID: 20261020_000071
Revises: 20261020_000070
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = "20261020_000071"
down_revision = "20261020_000070"
branch_labels = None
depends_on = None
TABLE = "template_sync_jobs"
PENDING_INDEX = "ix_template_sync_jobs_pending"


def _ensure_pending_index(bind):
    if PENDING_INDEX not in {row["name"] for row in sa.inspect(bind).get_indexes(TABLE)}:
        op.create_index(PENDING_INDEX, TABLE, ["status", "available_at", "id"])


def upgrade():
    bind = op.get_bind()
    indexes = {row["name"] for row in sa.inspect(bind).get_indexes("template_subscriptions")}
    if "ix_template_subscriptions_source_cursor" not in indexes:
        if bind.dialect.name == "mysql":
            op.execute(sa.text("ALTER TABLE template_subscriptions ADD INDEX ix_template_subscriptions_source_cursor (source_template_id, auto_update_enabled, id), ALGORITHM=INPLACE, LOCK=NONE"))
        else:
            op.create_index("ix_template_subscriptions_source_cursor", "template_subscriptions", ["source_template_id", "auto_update_enabled", "id"])
    if sa.inspect(bind).has_table(TABLE):
        _ensure_pending_index(bind)
        return
    table_options = {}
    if bind.dialect.name == "mysql":
        parent_options = sa.inspect(bind).get_table_options("template_releases")
        table_options = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
        # Foreign-key string columns must match the existing parent collation,
        # which can differ from this MySQL server's charset default.
        if parent_options.get("mysql_collate"):
            table_options["mysql_collate"] = parent_options["mysql_collate"]
    op.create_table(TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_template_id", sa.String(36), nullable=False),
        sa.Column("release_id", sa.String(36), sa.ForeignKey("template_releases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipient_key", sa.String(36), nullable=False, server_default=""),
        sa.Column("after_subscription_id", sa.String(36)),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column("created_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False),
        sa.Column("completed_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")),
        sa.Column("last_error_code", sa.String(100)),
        sa.UniqueConstraint("release_id", "recipient_key", name="uq_template_sync_jobs_release_recipient"),
        sa.CheckConstraint("status IN ('pending', 'done', 'failed')", name="ck_template_sync_jobs_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_template_sync_jobs_attempts"),
        **table_options,
    )
    _ensure_pending_index(bind)


def downgrade():
    if not sa.inspect(op.get_bind()).has_table(TABLE):
        return
    if op.get_bind().execute(sa.text("SELECT 1 FROM template_sync_jobs LIMIT 1")).first():
        raise RuntimeError("Template sync downgrade refuses to discard durable delivery history.")
    op.drop_table(TABLE)
    bind = op.get_bind()
    # InnoDB can silently retire the original single-column FK index once the
    # covering cursor index exists. Restore FK coverage before removing it.
    indexes = sa.inspect(bind).get_indexes("template_subscriptions")
    if bind.dialect.name == "mysql" and not any(row["name"] != "ix_template_subscriptions_source_cursor" and row["column_names"][:1] == ["source_template_id"] for row in indexes):
        op.execute(sa.text("ALTER TABLE template_subscriptions ADD INDEX ix_template_subscriptions_source_template_id (source_template_id), ALGORITHM=INPLACE, LOCK=NONE"))
    op.drop_index("ix_template_subscriptions_source_cursor", table_name="template_subscriptions")
