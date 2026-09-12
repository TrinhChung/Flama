"""reconcile schema contracts exposed by the Phase 4 preflight

Revision ID: 20260913_000038
Revises: 20260913_000037
Create Date: 2026-09-13 00:00:38

The preflight showed that several additive migrations left intentional server
defaults absent from the ORM declaration, while the student-offer column and
index declarations did not match their migration.  This revision converges
all supported database histories on the declared contract without changing
application behavior or progress authority.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260913_000038"
down_revision = "20260913_000037"
branch_labels = None
depends_on = None


EXPECTED_DEFAULTS: dict[str, dict[str, tuple[sa.types.TypeEngine, str]]] = {
    "card_progress": {
        "revision": (sa.BigInteger(), "0"),
    },
    "connect_import_sessions": {
        "attempted_notes": (sa.Integer(), "0"),
    },
    "deck_installs": {
        "auto_update_enabled": (sa.Boolean(), "0"),
        "overlay_revision": (sa.BigInteger(), "0"),
        "pending_conflict_count": (sa.Integer(), "0"),
        "sync_mode": (sa.String(length=32), "manual"),
        "version_mode": (sa.String(length=32), "legacy_snapshot"),
    },
    "deck_marketplace_items": {
        "auto_publish_enabled": (sa.Boolean(), "0"),
        "dirty_tracking_revision": (sa.BigInteger(), "0"),
        "distribution_mode": (sa.String(length=32), "free"),
        "student_offer_mode": (sa.String(length=32), "none"),
        "working_revision": (sa.BigInteger(), "0"),
    },
}


def _normalized_default(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == "'":
        normalized = normalized[1:-1]
    return "".join(normalized.split())


def _table_columns(inspector: sa.Inspector, table_name: str) -> dict[str, dict]:
    if not inspector.has_table(table_name):
        raise RuntimeError(f"Required table {table_name} is missing.")
    return {
        str(row["name"]): row for row in inspector.get_columns(table_name)
    }


def _assert_reconcilable(bind) -> None:
    inspector = sa.inspect(bind)
    for table_name, defaults in EXPECTED_DEFAULTS.items():
        columns = _table_columns(inspector, table_name)
        missing = sorted(set(defaults) - set(columns))
        if missing:
            raise RuntimeError(
                f"Required columns are missing from {table_name}: "
                f"{', '.join(missing)}."
            )

    marketplace_columns = _table_columns(inspector, "deck_marketplace_items")
    if "taxonomy_metadata" not in marketplace_columns:
        raise RuntimeError(
            "Required column deck_marketplace_items.taxonomy_metadata is missing."
        )
    student_offer = marketplace_columns.get("student_offer_mode")
    if student_offer is None:
        raise RuntimeError(
            "Required column deck_marketplace_items.student_offer_mode is missing."
        )
    current_length = getattr(student_offer["type"], "length", None)
    if current_length is None or int(current_length) > 32:
        raise RuntimeError(
            "deck_marketplace_items.student_offer_mode cannot be safely "
            f"normalized from length {current_length!r} to 32."
        )


def _ensure_server_defaults(bind) -> None:
    for table_name, defaults in EXPECTED_DEFAULTS.items():
        inspector = sa.inspect(bind)
        columns = _table_columns(inspector, table_name)
        for column_name, (declared_type, expected_default) in defaults.items():
            column = columns.get(column_name)
            if column is None:
                raise RuntimeError(
                    f"Required column {table_name}.{column_name} is missing."
                )
            if _normalized_default(column.get("default")) == _normalized_default(
                expected_default
            ):
                continue
            server_default = (
                sa.text(expected_default)
                if expected_default == "0"
                else expected_default
            )
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.alter_column(
                    column_name,
                    existing_type=declared_type,
                    existing_nullable=bool(column.get("nullable")),
                    server_default=server_default,
                )
            inspector = sa.inspect(bind)
            columns = _table_columns(inspector, table_name)


def _ensure_marketplace_contract(bind) -> None:
    inspector = sa.inspect(bind)
    columns = _table_columns(inspector, "deck_marketplace_items")

    taxonomy = columns.get("taxonomy_metadata")
    if taxonomy is None:
        raise RuntimeError(
            "Required column deck_marketplace_items.taxonomy_metadata is missing."
        )
    if bool(taxonomy.get("nullable")):
        bind.execute(
            sa.text(
                "UPDATE deck_marketplace_items "
                "SET taxonomy_metadata = '{}' "
                "WHERE taxonomy_metadata IS NULL"
            )
        )
        with op.batch_alter_table("deck_marketplace_items") as batch_op:
            batch_op.alter_column(
                "taxonomy_metadata",
                existing_type=sa.JSON(),
                existing_nullable=True,
                nullable=False,
            )

    inspector = sa.inspect(bind)
    columns = _table_columns(inspector, "deck_marketplace_items")
    student_offer = columns.get("student_offer_mode")
    if student_offer is None:
        raise RuntimeError(
            "Required column deck_marketplace_items.student_offer_mode is missing."
        )
    current_length = getattr(student_offer["type"], "length", None)
    if current_length != 32:
        if current_length is None or int(current_length) > 32:
            raise RuntimeError(
                "deck_marketplace_items.student_offer_mode cannot be safely "
                f"normalized from length {current_length!r} to 32."
            )
        with op.batch_alter_table("deck_marketplace_items") as batch_op:
            batch_op.alter_column(
                "student_offer_mode",
                existing_type=student_offer["type"],
                existing_nullable=bool(student_offer.get("nullable")),
                type_=sa.String(length=32),
            )

    inspector = sa.inspect(bind)
    indexes = {
        str(row.get("name") or "")
        for row in inspector.get_indexes("deck_marketplace_items")
    }
    if "ix_deck_marketplace_items_student_offer_mode" not in indexes:
        op.create_index(
            "ix_deck_marketplace_items_student_offer_mode",
            "deck_marketplace_items",
            ["student_offer_mode"],
            unique=False,
        )


def upgrade() -> None:
    bind = op.get_bind()
    _assert_reconcilable(bind)
    _ensure_marketplace_contract(bind)
    _ensure_server_defaults(bind)


def downgrade() -> None:
    # Non-destructive forward repair.  Removing defaults/indexes or shrinking
    # the widened VARCHAR would only recreate known drift and could lose data.
    return None
