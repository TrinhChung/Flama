"""add deck release and clone update foundation

Revision ID: 20260812_000016
Revises: 20260811_000015
Create Date: 2026-08-12 00:00:16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260812_000016"
down_revision = "20260811_000015"
branch_labels = None
depends_on = None


BIGINT_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {row["name"] for row in _inspector().get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {
        row["name"]
        for row in _inspector().get_indexes(table_name)
        if row.get("name")
    }


def _foreign_key_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {
        row["name"]
        for row in _inspector().get_foreign_keys(table_name)
        if row.get("name")
    }


def _foreign_key_names_for_column(table_name: str, column_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {
        row["name"]
        for row in _inspector().get_foreign_keys(table_name)
        if row.get("name") and column_name in (row.get("constrained_columns") or [])
    }


def _create_index_if_missing(
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if not _table_exists(table_name) or index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _table_exists(table_name) or index_name not in _index_names(table_name):
        return
    op.drop_index(index_name, table_name=table_name)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _table_exists(table_name) or column.name in _column_names(table_name):
        return
    if op.get_bind().dialect.name == "sqlite" and column.foreign_keys:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(column)
        return
    op.add_column(table_name, column)


def _drop_added_column(
    table_name: str,
    column_name: str,
    *,
    index_name: str | None = None,
    foreign_key_name: str | None = None,
) -> None:
    if not _table_exists(table_name) or column_name not in _column_names(table_name):
        return

    if op.get_bind().dialect.name == "sqlite":
        if index_name:
            _drop_index_if_exists(table_name, index_name)
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column(column_name)
        return

    if foreign_key_name:
        foreign_key_names = _foreign_key_names_for_column(table_name, column_name)
        if foreign_key_name in _foreign_key_names(table_name):
            foreign_key_names.add(foreign_key_name)
        for existing_foreign_key_name in sorted(foreign_key_names):
            op.drop_constraint(
                existing_foreign_key_name,
                table_name,
                type_="foreignkey",
            )
    if index_name:
        _drop_index_if_exists(table_name, index_name)
    op.drop_column(table_name, column_name)


def _create_deck_releases_table() -> None:
    if _table_exists("deck_releases"):
        return
    op.create_table(
        "deck_releases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deck_item_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("version_label", sa.String(length=50), nullable=False),
        sa.Column("parent_release_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="building", nullable=False),
        sa.Column(
            "source_working_revision",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("change_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("entity_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("added_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("modified_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("removed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["deck_item_id"],
            ["deck_marketplace_items.id"],
            name="fk_deck_releases_deck_item",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_release_id"],
            ["deck_releases.id"],
            name="fk_deck_releases_parent",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_deck_releases_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deck_item_id",
            "sequence_no",
            name="uq_deck_releases_item_sequence",
        ),
        sa.UniqueConstraint(
            "deck_item_id",
            "version_label",
            name="uq_deck_releases_item_version",
        ),
        sa.UniqueConstraint(
            "deck_item_id",
            "idempotency_key",
            name="uq_deck_releases_item_idempotency",
        ),
    )


def _create_deck_release_changes_table() -> None:
    if _table_exists("deck_release_changes"):
        return
    op.create_table(
        "deck_release_changes",
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column("release_id", sa.String(length=36), nullable=False),
        sa.Column("release_sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("change_key", sa.String(length=191), nullable=False),
        sa.Column("entity_kind", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("field_def_id", sa.String(length=36), nullable=True),
        sa.Column("property_key", sa.String(length=191), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("before_value", sa.JSON(), nullable=True),
        sa.Column("after_value", sa.JSON(), nullable=True),
        sa.Column("before_hash", sa.String(length=64), nullable=True),
        sa.Column("after_hash", sa.String(length=64), nullable=True),
        sa.Column("source_deck_id", sa.Integer(), nullable=True),
        sa.Column("sort_key", sa.String(length=255), server_default="", nullable=False),
        sa.Column("source_change_request_item_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["deck_releases.id"],
            name="fk_deck_release_changes_release",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_deck_id"],
            ["decks.id"],
            name="fk_deck_release_changes_source_deck",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_change_request_item_id"],
            ["deck_change_request_items.id"],
            name="fk_deck_release_changes_request_item",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_id",
            "change_key",
            name="uq_deck_release_changes_release_key",
        ),
    )


def _create_deck_release_note_checkpoints_table() -> None:
    if _table_exists("deck_release_note_checkpoints"):
        return
    op.create_table(
        "deck_release_note_checkpoints",
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column("release_id", sa.String(length=36), nullable=False),
        sa.Column("release_sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("source_note_id", sa.String(length=36), nullable=False),
        sa.Column("source_deck_id", sa.Integer(), nullable=True),
        sa.Column("note_type_id", sa.String(length=36), nullable=False),
        sa.Column("field_values", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["deck_releases.id"],
            name="fk_deck_release_note_checkpoints_release",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_deck_id"],
            ["decks.id"],
            name="fk_deck_release_note_checkpoints_source_deck",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_id",
            "source_note_id",
            name="uq_deck_release_note_checkpoints_release_note",
        ),
    )


def _create_deck_release_entity_memberships_table() -> None:
    if _table_exists("deck_release_entity_memberships"):
        return
    op.create_table(
        "deck_release_entity_memberships",
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column("deck_item_id", sa.String(length=36), nullable=False),
        sa.Column("entity_kind", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("source_deck_id", sa.Integer(), nullable=True),
        sa.Column("introduced_sequence", sa.BigInteger(), nullable=False),
        sa.Column("removed_sequence", sa.BigInteger(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["deck_item_id"],
            ["deck_marketplace_items.id"],
            name="fk_deck_release_memberships_deck_item",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_deck_id"],
            ["decks.id"],
            name="fk_deck_release_memberships_source_deck",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deck_item_id",
            "entity_kind",
            "entity_id",
            "introduced_sequence",
            name="uq_deck_release_memberships_item_entity_start",
        ),
    )


def _create_deck_working_dirty_entities_table() -> None:
    if _table_exists("deck_working_dirty_entities"):
        return
    op.create_table(
        "deck_working_dirty_entities",
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column("deck_item_id", sa.String(length=36), nullable=False),
        sa.Column("entity_kind", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("field_def_id", sa.String(length=36), nullable=True),
        sa.Column("property_key", sa.String(length=191), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("base_hash", sa.String(length=64), nullable=True),
        sa.Column("current_hash", sa.String(length=64), nullable=True),
        sa.Column("source_deck_id", sa.Integer(), nullable=True),
        sa.Column("working_revision", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["deck_item_id"],
            ["deck_marketplace_items.id"],
            name="fk_deck_working_dirty_deck_item",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_deck_id"],
            ["decks.id"],
            name="fk_deck_working_dirty_source_deck",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deck_item_id",
            "entity_kind",
            "entity_id",
            "property_key",
            name="uq_deck_working_dirty_item_entity_property",
        ),
    )


def _create_deck_install_rebases_table() -> None:
    if _table_exists("deck_install_rebases"):
        return
    op.create_table(
        "deck_install_rebases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deck_install_id", sa.String(length=36), nullable=False),
        sa.Column("from_release_id", sa.String(length=36), nullable=True),
        sa.Column("to_release_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="prepared", nullable=False),
        sa.Column("expected_overlay_revision", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("change_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conflict_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "resolved_conflict_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("applied_change_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("prepared_at", sa.DateTime(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["deck_install_id"],
            ["deck_installs.id"],
            name="fk_deck_install_rebases_install",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_release_id"],
            ["deck_releases.id"],
            name="fk_deck_install_rebases_from_release",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["to_release_id"],
            ["deck_releases.id"],
            name="fk_deck_install_rebases_to_release",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deck_install_id",
            "idempotency_key",
            name="uq_deck_install_rebases_install_idempotency",
        ),
    )


def _create_deck_install_rebase_conflicts_table() -> None:
    if _table_exists("deck_install_rebase_conflicts"):
        return
    op.create_table(
        "deck_install_rebase_conflicts",
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column("rebase_id", sa.String(length=36), nullable=False),
        sa.Column(
            "release_change_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("conflict_key", sa.String(length=191), nullable=False),
        sa.Column("entity_kind", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("field_def_id", sa.String(length=36), nullable=True),
        sa.Column("property_key", sa.String(length=191), nullable=False),
        sa.Column("base_value", sa.JSON(), nullable=True),
        sa.Column("upstream_value", sa.JSON(), nullable=True),
        sa.Column("local_value", sa.JSON(), nullable=True),
        sa.Column("resolution_mode", sa.String(length=32), nullable=True),
        sa.Column("resolved_value", sa.JSON(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rebase_id"],
            ["deck_install_rebases.id"],
            name="fk_deck_install_rebase_conflicts_rebase",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["release_change_id"],
            ["deck_release_changes.id"],
            name="fk_deck_install_rebase_conflicts_release_change",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name="fk_deck_install_rebase_conflicts_resolved_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rebase_id",
            "conflict_key",
            name="uq_deck_install_rebase_conflicts_rebase_key",
        ),
    )


def _create_foundation_indexes() -> None:
    index_specs = (
        ("deck_releases", "ix_deck_releases_deck_item_id", ["deck_item_id"]),
        ("deck_releases", "ix_deck_releases_parent_release_id", ["parent_release_id"]),
        ("deck_releases", "ix_deck_releases_status", ["status"]),
        ("deck_releases", "ix_deck_releases_created_by_user_id", ["created_by_user_id"]),
        (
            "deck_releases",
            "ix_deck_releases_item_status_published",
            ["deck_item_id", "status", "published_at", "id"],
        ),
        ("deck_release_changes", "ix_deck_release_changes_release_id", ["release_id"]),
        (
            "deck_release_changes",
            "ix_deck_release_changes_diff_cursor",
            ["release_id", "entity_kind", "source_deck_id", "sort_key", "id"],
        ),
        (
            "deck_release_changes",
            "ix_deck_release_changes_entity_history",
            ["entity_kind", "entity_id", "property_key", "release_sequence_no", "id"],
        ),
        (
            "deck_release_note_checkpoints",
            "ix_deck_release_note_checkpoints_release_id",
            ["release_id"],
        ),
        (
            "deck_release_note_checkpoints",
            "ix_deck_release_note_checkpoints_note_sequence",
            ["source_note_id", "release_sequence_no", "id"],
        ),
        (
            "deck_release_note_checkpoints",
            "ix_deck_release_note_checkpoints_release_deck",
            ["release_id", "source_deck_id", "id"],
        ),
        (
            "deck_release_entity_memberships",
            "ix_deck_release_entity_memberships_deck_item_id",
            ["deck_item_id"],
        ),
        (
            "deck_release_entity_memberships",
            "ix_deck_release_memberships_visibility",
            ["deck_item_id", "entity_kind", "introduced_sequence", "removed_sequence", "id"],
        ),
        (
            "deck_release_entity_memberships",
            "ix_deck_release_memberships_deck_visibility",
            ["deck_item_id", "source_deck_id", "introduced_sequence", "removed_sequence", "id"],
        ),
        (
            "deck_working_dirty_entities",
            "ix_deck_working_dirty_entities_deck_item_id",
            ["deck_item_id"],
        ),
        (
            "deck_working_dirty_entities",
            "ix_deck_working_dirty_publish",
            ["deck_item_id", "working_revision", "id"],
        ),
        (
            "deck_working_dirty_entities",
            "ix_deck_working_dirty_entity_scope",
            ["deck_item_id", "entity_kind", "source_deck_id", "id"],
        ),
        ("deck_install_rebases", "ix_deck_install_rebases_deck_install_id", ["deck_install_id"]),
        ("deck_install_rebases", "ix_deck_install_rebases_from_release_id", ["from_release_id"]),
        ("deck_install_rebases", "ix_deck_install_rebases_to_release_id", ["to_release_id"]),
        ("deck_install_rebases", "ix_deck_install_rebases_status", ["status"]),
        (
            "deck_install_rebases",
            "ix_deck_install_rebases_install_status_updated",
            ["deck_install_id", "status", "updated_at", "id"],
        ),
        (
            "deck_install_rebases",
            "ix_deck_install_rebases_install_target_status",
            ["deck_install_id", "to_release_id", "status", "id"],
        ),
        (
            "deck_install_rebase_conflicts",
            "ix_deck_install_rebase_conflicts_rebase_id",
            ["rebase_id"],
        ),
        (
            "deck_install_rebase_conflicts",
            "ix_deck_install_rebase_conflicts_release_change_id",
            ["release_change_id"],
        ),
        (
            "deck_install_rebase_conflicts",
            "ix_deck_install_rebase_conflicts_resolved_by_user_id",
            ["resolved_by_user_id"],
        ),
        (
            "deck_install_rebase_conflicts",
            "ix_deck_install_rebase_conflicts_resolution",
            ["rebase_id", "resolution_mode", "id"],
        ),
        (
            "deck_install_rebase_conflicts",
            "ix_deck_install_rebase_conflicts_entity",
            ["rebase_id", "entity_kind", "entity_id", "property_key", "id"],
        ),
    )
    for table_name, index_name, columns in index_specs:
        _create_index_if_missing(table_name, index_name, columns)


def _add_existing_table_columns() -> None:
    _add_column_if_missing(
        "deck_marketplace_items",
        sa.Column(
            "current_release_id",
            sa.String(length=36),
            sa.ForeignKey(
                "deck_releases.id",
                name="fk_deck_marketplace_items_current_release",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )
    _add_column_if_missing(
        "deck_marketplace_items",
        sa.Column("working_revision", sa.BigInteger(), server_default="0", nullable=False),
    )
    _create_index_if_missing(
        "deck_marketplace_items",
        "ix_deck_marketplace_items_current_release_id",
        ["current_release_id"],
    )

    _add_column_if_missing(
        "deck_installs",
        sa.Column(
            "applied_release_id",
            sa.String(length=36),
            sa.ForeignKey(
                "deck_releases.id",
                name="fk_deck_installs_applied_release",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )
    _add_column_if_missing(
        "deck_installs",
        sa.Column(
            "seen_release_id",
            sa.String(length=36),
            sa.ForeignKey(
                "deck_releases.id",
                name="fk_deck_installs_seen_release",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )
    _add_column_if_missing(
        "deck_installs",
        sa.Column("overlay_revision", sa.BigInteger(), server_default="0", nullable=False),
    )
    _add_column_if_missing(
        "deck_installs",
        sa.Column(
            "version_mode",
            sa.String(length=32),
            server_default="legacy_snapshot",
            nullable=False,
        ),
    )
    _create_index_if_missing(
        "deck_installs",
        "ix_deck_installs_applied_release_id",
        ["applied_release_id"],
    )
    _create_index_if_missing(
        "deck_installs",
        "ix_deck_installs_seen_release_id",
        ["seen_release_id"],
    )
    _create_index_if_missing(
        "deck_installs",
        "ix_deck_installs_version_mode",
        ["version_mode"],
    )

    _add_column_if_missing(
        "deck_clone_note_field_overrides",
        sa.Column(
            "source_field_def_id",
            sa.String(length=36),
            sa.ForeignKey(
                "field_defs.id",
                name="fk_clone_note_overrides_source_field_def",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )
    _add_column_if_missing(
        "deck_clone_note_field_overrides",
        sa.Column(
            "base_release_id",
            sa.String(length=36),
            sa.ForeignKey(
                "deck_releases.id",
                name="fk_clone_note_overrides_base_release",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )
    _create_index_if_missing(
        "deck_clone_note_field_overrides",
        "ix_deck_clone_note_field_overrides_source_field_def_id",
        ["source_field_def_id"],
    )
    _create_index_if_missing(
        "deck_clone_note_field_overrides",
        "ix_deck_clone_note_field_overrides_base_release_id",
        ["base_release_id"],
    )

    _add_column_if_missing(
        "deck_change_requests",
        sa.Column(
            "base_release_id",
            sa.String(length=36),
            sa.ForeignKey(
                "deck_releases.id",
                name="fk_deck_change_requests_base_release",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )
    _add_column_if_missing(
        "deck_change_requests",
        sa.Column("revision", sa.BigInteger(), server_default="0", nullable=False),
    )
    _create_index_if_missing(
        "deck_change_requests",
        "ix_deck_change_requests_base_release_id",
        ["base_release_id"],
    )


def upgrade() -> None:
    _create_deck_releases_table()
    _create_deck_release_changes_table()
    _create_deck_release_note_checkpoints_table()
    _create_deck_release_entity_memberships_table()
    _create_deck_working_dirty_entities_table()
    _create_deck_install_rebases_table()
    _create_deck_install_rebase_conflicts_table()
    _create_foundation_indexes()
    _add_existing_table_columns()


def downgrade() -> None:
    _drop_added_column(
        "deck_change_requests",
        "base_release_id",
        index_name="ix_deck_change_requests_base_release_id",
        foreign_key_name="fk_deck_change_requests_base_release",
    )
    _drop_added_column("deck_change_requests", "revision")

    _drop_added_column(
        "deck_clone_note_field_overrides",
        "base_release_id",
        index_name="ix_deck_clone_note_field_overrides_base_release_id",
        foreign_key_name="fk_clone_note_overrides_base_release",
    )
    _drop_added_column(
        "deck_clone_note_field_overrides",
        "source_field_def_id",
        index_name="ix_deck_clone_note_field_overrides_source_field_def_id",
        foreign_key_name="fk_clone_note_overrides_source_field_def",
    )

    _drop_added_column(
        "deck_installs",
        "seen_release_id",
        index_name="ix_deck_installs_seen_release_id",
        foreign_key_name="fk_deck_installs_seen_release",
    )
    _drop_added_column(
        "deck_installs",
        "applied_release_id",
        index_name="ix_deck_installs_applied_release_id",
        foreign_key_name="fk_deck_installs_applied_release",
    )
    _drop_added_column(
        "deck_installs",
        "version_mode",
        index_name="ix_deck_installs_version_mode",
    )
    _drop_added_column("deck_installs", "overlay_revision")

    _drop_added_column(
        "deck_marketplace_items",
        "current_release_id",
        index_name="ix_deck_marketplace_items_current_release_id",
        foreign_key_name="fk_deck_marketplace_items_current_release",
    )
    _drop_added_column("deck_marketplace_items", "working_revision")

    for table_name in (
        "deck_install_rebase_conflicts",
        "deck_install_rebases",
        "deck_working_dirty_entities",
        "deck_release_entity_memberships",
        "deck_release_note_checkpoints",
        "deck_release_changes",
        "deck_releases",
    ):
        if _table_exists(table_name):
            op.drop_table(table_name)
