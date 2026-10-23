"""List standalone templates on the marketplace with free or paid pricing.

Revision ID: 20261019_000069
Revises: 20261014_000068
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa

revision = "20261019_000069"
down_revision = "20261014_000068"
branch_labels = None
depends_on = None
TABLE = "template_publications"
INDEX = "ix_template_publications_marketplace"
INDEX_COLUMNS = ["marketplace_status", "marketplace_published_at"]
COLUMNS = (
    ("marketplace_status", "VARCHAR(16) NOT NULL DEFAULT 'private'", lambda: sa.Column("marketplace_status", sa.String(16), nullable=False, server_default="private")),
    ("pricing_mode", "VARCHAR(16) NOT NULL DEFAULT 'free'", lambda: sa.Column("pricing_mode", sa.String(16), nullable=False, server_default="free")),
    ("price_amount_minor", "INT NOT NULL DEFAULT 0", lambda: sa.Column("price_amount_minor", sa.Integer(), nullable=False, server_default="0")),
    ("marketplace_published_at", "DATETIME NULL", lambda: sa.Column("marketplace_published_at", sa.DateTime(), nullable=True)),
)


@contextmanager
def _ddl_budget():
    bind = op.get_bind()
    previous = int(bind.execute(sa.text("SELECT @@SESSION.lock_wait_timeout")).scalar_one())
    bind.execute(sa.text("SET SESSION lock_wait_timeout = 30"))
    try:
        yield
    finally:
        bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {previous}"))


def _columns():
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(TABLE)}


def _indexes():
    return {item["name"]: item["column_names"] for item in sa.inspect(op.get_bind()).get_indexes(TABLE)}


def upgrade():
    missing = [item for item in COLUMNS if item[0] not in _columns()]
    if op.get_bind().dialect.name == "mysql":
        with _ddl_budget():
            if missing:
                clauses = ", ".join(f"ADD COLUMN {name} {ddl}" for name, ddl, _ in missing)
                op.execute(sa.text(f"ALTER TABLE {TABLE} {clauses}, ALGORITHM=INSTANT"))
            indexes = _indexes()
            if INDEX not in indexes:
                op.execute(sa.text(
                    f"ALTER TABLE {TABLE} ADD INDEX {INDEX} ({','.join(INDEX_COLUMNS)}), ALGORITHM=INPLACE, LOCK=NONE"
                ))
            elif indexes[INDEX] != INDEX_COLUMNS:
                raise RuntimeError("Template marketplace index has an incompatible contract.")
        return
    for _, _, column in missing:
        op.add_column(TABLE, column())
    indexes = _indexes()
    if INDEX not in indexes:
        op.create_index(INDEX, TABLE, INDEX_COLUMNS)
    elif indexes[INDEX] != INDEX_COLUMNS:
        raise RuntimeError("Template marketplace index has an incompatible contract.")


def downgrade():
    bind = op.get_bind()
    present = _columns()
    if "marketplace_status" in present and bind.execute(sa.text(
        f"SELECT 1 FROM {TABLE} WHERE marketplace_status <> 'private' OR price_amount_minor <> 0 LIMIT 1"
    )).first():
        raise RuntimeError("Retain listed or priced marketplace templates.")
    if INDEX in _indexes():
        op.drop_index(INDEX, table_name=TABLE)
    for name, _, _ in reversed(COLUMNS):
        if name in present:
            op.drop_column(TABLE, name)
