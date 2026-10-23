"""Repair constraints that only long-lived databases lack.

Databases created by the old startup ``db.create_all()`` kept an older shape
for two tables; a fresh migration chain already has the current one:

* ``mcp_access_tokens``: ``expires_at`` NOT NULL (a non-expiring token fails
  to insert), no unique ``refresh_token_hash`` index, no ``client_id`` index
  or foreign key.
* ``payment_orders.user_id`` cascades on user delete; payment history is
  kept with ``SET NULL`` like the model and the fresh chain.

Every step inspects first, so fresh and already repaired databases are
unchanged. Duplicates or orphans stop the migration for operator review.

Numbered 000072 because 000070/000071 were taken by unmerged Note Type
release work; it applies directly after 000069 and those follow it.

Revision ID: 20261021_000072
Revises: 20261019_000069
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa

revision = "20261021_000072"
down_revision = "20261019_000069"
branch_labels = None
depends_on = None

TOKENS = "mcp_access_tokens"
TOKEN_INDEXES = (
    ("ix_mcp_access_tokens_client_id", "client_id", False),
    ("ix_mcp_access_tokens_refresh_token_expires_at", "refresh_token_expires_at", False),
    ("ix_mcp_access_tokens_refresh_token_hash", "refresh_token_hash", True),
)
TOKEN_CLIENT_FK = "fk_mcp_access_tokens_client_id"
ORDERS_USER_FK = "payment_orders_ibfk_1"


@contextmanager
def _ddl_budget(bind):
    previous = int(bind.execute(sa.text("SELECT @@SESSION.lock_wait_timeout")).scalar_one())
    bind.execute(sa.text("SET SESSION lock_wait_timeout = 30"))
    try:
        yield
    finally:
        bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {previous}"))


def _repair_tokens(bind):
    inspector = sa.inspect(bind)
    if not inspector.has_table(TOKENS):
        return
    columns = {column["name"]: column for column in inspector.get_columns(TOKENS)}
    if not {"client_id", "refresh_token_hash", "refresh_token_expires_at", "expires_at"} <= set(columns):
        raise RuntimeError("mcp_access_tokens lacks a column this repair expects; review the table first.")
    if not columns["expires_at"]["nullable"]:
        op.execute(sa.text(f"ALTER TABLE {TOKENS} MODIFY expires_at DATETIME NULL"))
    indexes = sa.inspect(bind).get_indexes(TOKENS)
    for name, column, unique in TOKEN_INDEXES:
        covering = [row for row in indexes if row["column_names"][:1] == [column]]
        if unique and any(row["unique"] and row["column_names"] == [column] for row in covering):
            continue
        if not unique and covering:
            continue
        if unique and bind.execute(sa.text(
            f"SELECT 1 FROM {TOKENS} WHERE {column} IS NOT NULL GROUP BY {column} HAVING COUNT(*) > 1 LIMIT 1"
        )).first():
            raise RuntimeError(f"Duplicate {TOKENS}.{column} values; resolve them before adding the unique index.")
        kind = "UNIQUE INDEX" if unique else "INDEX"
        op.execute(sa.text(f"ALTER TABLE {TOKENS} ADD {kind} {name} ({column}), ALGORITHM=INPLACE, LOCK=NONE"))
    if not any(fk["referred_table"] == "oauth_clients" and fk["constrained_columns"] == ["client_id"]
               for fk in sa.inspect(bind).get_foreign_keys(TOKENS)):
        if bind.execute(sa.text(
            f"SELECT 1 FROM {TOKENS} t LEFT JOIN oauth_clients c ON c.id = t.client_id "
            "WHERE t.client_id IS NOT NULL AND c.id IS NULL LIMIT 1"
        )).first():
            raise RuntimeError("mcp_access_tokens.client_id references a missing OAuth client; review first.")
        op.create_foreign_key(TOKEN_CLIENT_FK, TOKENS, "oauth_clients", ["client_id"], ["id"], ondelete="SET NULL")


def _repair_order_user_fk(bind):
    inspector = sa.inspect(bind)
    if not inspector.has_table("payment_orders"):
        return
    user_fks = [fk for fk in inspector.get_foreign_keys("payment_orders")
                if fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_id"]]
    if any((fk.get("options") or {}).get("ondelete", "").upper() == "SET NULL" for fk in user_fks):
        return
    user_id = next(column for column in inspector.get_columns("payment_orders") if column["name"] == "user_id")
    if not user_id["nullable"]:
        raise RuntimeError("payment_orders.user_id is NOT NULL; SET NULL needs a nullable column.")
    for fk in user_fks:
        op.drop_constraint(fk["name"], "payment_orders", type_="foreignkey")
    op.create_foreign_key(ORDERS_USER_FK, "payment_orders", "users", ["user_id"], ["id"], ondelete="SET NULL")


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        return
    with _ddl_budget(bind):
        _repair_tokens(bind)
        _repair_order_user_fk(bind)


def downgrade():
    # The pre-repair shape rejected valid tokens and deleted payment history;
    # nothing depends on it, so there is nothing to restore.
    pass
