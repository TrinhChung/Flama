"""Cover oldest-pending learner discovery without reading JSON feed payloads.

Revision ID: 20261014_000068
Revises: 20261014_000067
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa

revision = "20261014_000068"
down_revision = "20261014_000067"
branch_labels = None
depends_on = None
TABLE = "review_analytics_outbox"
INDEX = "ix_review_analytics_outbox_pending_age"
COLUMNS = ["applied_at", "user_id", "created_at"]


@contextmanager
def _ddl_budget():
    bind = op.get_bind()
    previous = int(bind.execute(sa.text("SELECT @@SESSION.lock_wait_timeout")).scalar_one())
    bind.execute(sa.text("SET SESSION lock_wait_timeout = 30"))
    try:
        yield
    finally:
        bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {previous}"))


def upgrade():
    indexes = {item["name"]: item["column_names"] for item in sa.inspect(op.get_bind()).get_indexes(TABLE)}
    if INDEX in indexes:
        if indexes[INDEX] != COLUMNS:
            raise RuntimeError("Outbox pending-age index has an incompatible contract.")
        return
    if op.get_bind().dialect.name == "mysql":
        with _ddl_budget():
            op.execute(sa.text(
                f"ALTER TABLE {TABLE} ADD INDEX {INDEX} (applied_at,user_id,created_at), ALGORITHM=INPLACE, LOCK=NONE"
            ))
    else:
        op.create_index(INDEX, TABLE, COLUMNS)


def downgrade():
    if INDEX not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(TABLE)}:
        return
    if op.get_bind().dialect.name == "mysql":
        with _ddl_budget():
            op.execute(sa.text(f"ALTER TABLE {TABLE} DROP INDEX {INDEX}, ALGORITHM=INPLACE, LOCK=NONE"))
    else:
        op.drop_index(INDEX, table_name=TABLE)
