"""Add opt-in durable history projection feed; no source backfill or flag changes.

Revision ID: 20261014_000065
Revises: 20261013_000064
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from models.study_progress_types import MYSQL_TABLE_OPTIONS, ascii_string, binary_hash, datetime6

revision = "20261014_000065"
down_revision = "20261013_000064"
branch_labels = None
depends_on = None
TABLE = "review_analytics_outbox"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(TABLE):
        columns = {column["name"]: column for column in inspector.get_columns(TABLE)}
        expected = {"user_id", "source_revision", "payload_version", "events_payload", "payload_size",
                    "payload_hash", "event_count", "is_dirty", "created_at", "applied_at", "last_error_code"}
        if set(columns) != expected or any(column["nullable"] != (name in {"applied_at", "last_error_code"})
                                           for name, column in columns.items()):
            raise RuntimeError("Existing review analytics outbox has an incompatible column contract.")
        if inspector.get_pk_constraint(TABLE)["constrained_columns"] != ["user_id", "source_revision"]:
            raise RuntimeError("Existing review analytics outbox has incompatible revision identity.")
        foreign_keys = inspector.get_foreign_keys(TABLE)
        if not any(key["constrained_columns"] == ["user_id"] and key["referred_table"] == "review_analytics_heads"
                   and key["referred_columns"] == ["user_id"]
                   and key.get("options", {}).get("ondelete", "").upper() == "CASCADE" for key in foreign_keys):
            raise RuntimeError("Existing review analytics outbox has incompatible ownership.")
        if not isinstance(columns["events_payload"]["type"], sa.JSON) \
                or not isinstance(columns["source_revision"]["type"], sa.BigInteger):
            raise RuntimeError("Existing review analytics outbox has incompatible payload or revision types.")
        if op.get_bind().dialect.name == "mysql" and (not getattr(columns["source_revision"]["type"], "unsigned", False)
                or str(columns["payload_hash"]["type"]).upper() != "BINARY(32)"
                or any(getattr(columns[name]["type"], "fsp", None) != 6 for name in ("created_at", "applied_at"))):
            raise RuntimeError("Existing review analytics outbox has incompatible MySQL precision.")
        indexes = {index["name"]: index["column_names"] for index in inspector.get_indexes(TABLE)}
        if indexes.get("ix_review_analytics_outbox_pending") != ["applied_at", "user_id", "source_revision"]:
            raise RuntimeError("Existing review analytics outbox has incompatible pending index.")
        return
    op.create_table(TABLE,
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("review_analytics_heads.user_id", ondelete="CASCADE"),
                  primary_key=True, autoincrement=False),
        sa.Column("source_revision", sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
                  primary_key=True, autoincrement=False),
        sa.Column("payload_version", ascii_string(32), nullable=False),
        sa.Column("events_payload", sa.JSON(), nullable=False),
        sa.Column("payload_size", sa.Integer(), nullable=False),
        sa.Column("payload_hash", binary_hash(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("is_dirty", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", datetime6(), nullable=False),
        sa.Column("applied_at", datetime6(), nullable=True),
        sa.Column("last_error_code", ascii_string(64), nullable=True),
        sa.CheckConstraint("source_revision > 0", name="ck_review_outbox_revision"),
        sa.CheckConstraint("event_count >= 0", name="ck_review_outbox_event_count"),
        sa.CheckConstraint("payload_size BETWEEN 2 AND 2097152", name="ck_review_outbox_payload_size"),
        sa.CheckConstraint("length(payload_hash) = 32", name="ck_review_outbox_payload_hash"),
        **MYSQL_TABLE_OPTIONS)
    op.create_index("ix_review_analytics_outbox_pending", TABLE, ["applied_at", "user_id", "source_revision"])


def downgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table(TABLE):
        if bind.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
            raise RuntimeError("Retain populated history feed; drain and disable async mode to roll back.")
        op.drop_table(TABLE)
