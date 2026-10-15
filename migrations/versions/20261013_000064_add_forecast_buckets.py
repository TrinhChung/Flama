"""Add rebuildable forecast headers and due buckets; no state/content backfill.

Revision ID: 20261013_000064
Revises: 20261013_000063
"""

from alembic import op
import sqlalchemy as sa

from models.study_progress_types import MYSQL_TABLE_OPTIONS, binary_hash, datetime6

revision = "20261013_000064"
down_revision = "20261013_000063"
branch_labels = None
depends_on = None


HEADER = "study_forecast_snapshots"
BUCKETS = "study_forecast_due_buckets"


def _definitions():
    # Freeze this revision's schema; future model additions must not appear in
    # an old migration during upgrades from the historical bootstrap.
    return {
        HEADER: (
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                      primary_key=True, autoincrement=False),
            sa.Column("scope_hash", binary_hash(), primary_key=True),
            sa.Column("study_day", sa.Integer(), nullable=False),
            sa.Column("policy_hash", binary_hash(), nullable=False),
            sa.Column("dependency_hash", binary_hash(), nullable=False),
            sa.Column("valid_until_utc", datetime6(), nullable=False),
            sa.Column("daily_load", sa.Float(precision=53), nullable=False),
            sa.Column("bucket_count", sa.Integer(), nullable=False),
            sa.Column("computed_at", datetime6(), nullable=False),
            sa.CheckConstraint("daily_load >= 0", name="ck_forecast_load"),
            sa.CheckConstraint("bucket_count >= 0", name="ck_forecast_buckets"),
        ),
        BUCKETS: (
            sa.Column("user_id", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("scope_hash", binary_hash(), primary_key=True),
            sa.Column("due_day", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("queue", sa.String(20), primary_key=True),
            sa.Column("card_count", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(["user_id", "scope_hash"],
                [f"{HEADER}.user_id", f"{HEADER}.scope_hash"], ondelete="CASCADE",
                name="fk_forecast_bucket_snapshot"),
            sa.CheckConstraint("due_day BETWEEN 1 AND 3652059", name="ck_forecast_due_day"),
            sa.CheckConstraint("card_count > 0", name="ck_forecast_card_count"),
        ),
    }


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    definitions = _definitions()
    existing = set(inspector.get_table_names())
    # Preflight both existing tables before MySQL's nontransactional CREATEs.
    for name, items in definitions.items():
        if name in existing:
            columns = {column["name"]: column for column in inspector.get_columns(name)}
            expected = {item.name: item for item in items if isinstance(item, sa.Column)}
            if set(columns) != set(expected) or any(
                columns[key]["nullable"] != column.nullable for key, column in expected.items()
            ):
                raise RuntimeError(f"Existing {name} differs from forecast projection contract.")
            primary = [item.name for item in items if isinstance(item, sa.Column) and item.primary_key]
            if inspector.get_pk_constraint(name)["constrained_columns"] != primary:
                raise RuntimeError(f"Existing {name} has incompatible forecast identity keys.")
            if bind.dialect.name == "mysql":
                hash_names = [key for key in ("scope_hash", "policy_hash", "dependency_hash") if key in columns]
                if any(str(columns[key]["type"]).upper() != "BINARY(32)" for key in hash_names):
                    raise RuntimeError(f"Existing {name} has incompatible forecast hash storage.")
                if name == HEADER and (str(columns["daily_load"]["type"]).upper() != "DOUBLE"
                        or any(getattr(columns[key]["type"], "fsp", None) != 6
                               for key in ("computed_at", "valid_until_utc"))):
                    raise RuntimeError("Existing forecast snapshot has incompatible load/clock precision.")
    for name, items in definitions.items():
        if name not in existing:
            op.create_table(name, *items, **MYSQL_TABLE_OPTIONS)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for name in (HEADER, BUCKETS):
        if inspector.has_table(name) and bind.execute(
            sa.text(f"SELECT 1 FROM {name} LIMIT 1")
        ).first():
            raise RuntimeError("Retain populated forecast projections; disable readers to roll back.")
    for name in (BUCKETS, HEADER):
        if inspector.has_table(name):
            op.drop_table(name)
