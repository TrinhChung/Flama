"""add Flama Connect API tokens, note references, and clone additions

Revision ID: 20260802_000011
Revises: 20260729_000010
Create Date: 2026-08-02 00:00:11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260802_000011"
down_revision = "20260729_000010"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return _inspector().has_table(name)


def _column_names(table: str) -> set[str]:
    return {row["name"] for row in _inspector().get_columns(table)} if _table_exists(table) else set()


def _unique_names(table: str) -> set[str]:
    return {
        row["name"]
        for row in _inspector().get_unique_constraints(table)
        if row.get("name")
    } if _table_exists(table) else set()


def _index_names(table: str) -> set[str]:
    return {
        row["name"]
        for row in _inspector().get_indexes(table)
        if row.get("name")
    } if _table_exists(table) else set()


def upgrade() -> None:
    if "identity_role" not in _column_names("field_defs"):
        with op.batch_alter_table("field_defs") as batch_op:
            batch_op.add_column(sa.Column("identity_role", sa.String(length=32), nullable=True))
    if "uq_field_defs_note_type_identity_role" not in _unique_names("field_defs"):
        with op.batch_alter_table("field_defs") as batch_op:
            batch_op.create_unique_constraint(
                "uq_field_defs_note_type_identity_role",
                ["note_type_id", "identity_role"],
            )

    if not _table_exists("user_api_tokens"):
        op.create_table(
            "user_api_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("token_prefix", sa.String(length=32), nullable=False),
            sa.Column("scopes", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    token_indexes = _index_names("user_api_tokens")
    if "ix_user_api_tokens_user_id" not in token_indexes:
        op.create_index("ix_user_api_tokens_user_id", "user_api_tokens", ["user_id"])
    if "ix_user_api_tokens_token_hash" not in token_indexes:
        op.create_index("ix_user_api_tokens_token_hash", "user_api_tokens", ["token_hash"], unique=True)
    if "ix_user_api_tokens_expires_at" not in token_indexes:
        op.create_index("ix_user_api_tokens_expires_at", "user_api_tokens", ["expires_at"])
    if "ix_user_api_tokens_revoked_at" not in token_indexes:
        op.create_index("ix_user_api_tokens_revoked_at", "user_api_tokens", ["revoked_at"])

    if not _table_exists("connect_note_refs"):
        op.create_table(
            "connect_note_refs",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("note_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "note_id",
                "provider",
                name="uq_connect_note_refs_user_note_provider",
            ),
        )
    ref_indexes = _index_names("connect_note_refs")
    if "ix_connect_note_refs_note_id" not in ref_indexes:
        op.create_index("ix_connect_note_refs_note_id", "connect_note_refs", ["note_id"], unique=False)
    if "ix_connect_note_refs_user_id" not in ref_indexes:
        op.create_index("ix_connect_note_refs_user_id", "connect_note_refs", ["user_id"])

    if not _table_exists("deck_clone_added_notes"):
        op.create_table(
            "deck_clone_added_notes",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("deck_install_id", sa.String(length=36), nullable=False),
            sa.Column("note_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["deck_install_id"], ["deck_installs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    clone_indexes = _index_names("deck_clone_added_notes")
    if "ix_deck_clone_added_notes_deck_install_id" not in clone_indexes:
        op.create_index("ix_deck_clone_added_notes_deck_install_id", "deck_clone_added_notes", ["deck_install_id"])
    if "ix_deck_clone_added_notes_note_id" not in clone_indexes:
        op.create_index("ix_deck_clone_added_notes_note_id", "deck_clone_added_notes", ["note_id"], unique=True)


def downgrade() -> None:
    op.drop_table("deck_clone_added_notes")
    op.drop_table("connect_note_refs")
    op.drop_table("user_api_tokens")
    with op.batch_alter_table("field_defs") as batch_op:
        batch_op.drop_constraint("uq_field_defs_note_type_identity_role", type_="unique")
        batch_op.drop_column("identity_role")
