"""add durable Anki import sessions and source mappings

Revision ID: 20260809_000014
Revises: 20260802_000013
Create Date: 2026-08-09 00:00:14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_000014"
down_revision = "20260802_000013"
branch_labels = None
depends_on = None


def _ensure_index(table: str, name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    existing = {
        row["name"]
        for row in sa.inspect(bind).get_indexes(table)
        if row.get("name")
    }
    if name not in existing:
        op.create_index(name, table, columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("connect_import_sessions"):
        op.create_table(
            "connect_import_sessions",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(64), nullable=False),
            sa.Column("source_key", sa.String(255), nullable=False),
            sa.Column("mode", sa.String(32), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("source_root_path", sa.String(2048), nullable=True),
            sa.Column("target_root_path", sa.String(2048), nullable=True),
            sa.Column("selected_decks", sa.JSON(), nullable=False),
            sa.Column("note_type_bindings", sa.JSON(), nullable=False),
            sa.Column("blockers", sa.JSON(), nullable=False),
            sa.Column("plan_hash", sa.String(64), nullable=True),
            sa.Column("total_notes", sa.Integer(), nullable=False),
            sa.Column("total_media", sa.Integer(), nullable=False),
            sa.Column("processed_notes", sa.Integer(), nullable=False),
            sa.Column("processed_media", sa.Integer(), nullable=False),
            sa.Column("error_summary", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("connect_import_sessions", "ix_connect_import_sessions_user_id", ["user_id"])
    _ensure_index("connect_import_sessions", "ix_connect_import_sessions_status", ["status"])
    _ensure_index("connect_import_sessions", "ix_connect_import_sessions_plan_hash", ["plan_hash"])
    _ensure_index("connect_import_sessions", "ix_connect_import_sessions_expires_at", ["expires_at"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("connect_note_type_refs"):
        op.create_table(
            "connect_note_type_refs",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("source_key", sa.String(255), nullable=False),
            sa.Column("external_model_id", sa.String(128), nullable=False),
            sa.Column("external_model_name", sa.String(255), nullable=False),
            sa.Column("note_type_id", sa.String(36), nullable=False),
            sa.Column("schema_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["note_type_id"], ["note_types.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "source_key",
                "external_model_id",
                name="uq_connect_note_type_refs_source_model",
            ),
        )
    _ensure_index("connect_note_type_refs", "ix_connect_note_type_refs_user_id", ["user_id"])
    _ensure_index("connect_note_type_refs", "ix_connect_note_type_refs_note_type_id", ["note_type_id"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("connect_source_deck_refs"):
        op.create_table(
            "connect_source_deck_refs",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("source_key", sa.String(255), nullable=False),
            sa.Column("external_deck_id", sa.String(128), nullable=False),
            sa.Column("source_path", sa.String(2048), nullable=False),
            sa.Column("deck_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "source_key",
                "external_deck_id",
                name="uq_connect_source_deck_refs_source_deck",
            ),
        )
    _ensure_index("connect_source_deck_refs", "ix_connect_source_deck_refs_user_id", ["user_id"])
    _ensure_index("connect_source_deck_refs", "ix_connect_source_deck_refs_deck_id", ["deck_id"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("connect_source_note_refs"):
        op.create_table(
            "connect_source_note_refs",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("source_key", sa.String(255), nullable=False),
            sa.Column("external_note_id", sa.String(128), nullable=False),
            sa.Column("source_model_id", sa.String(128), nullable=False),
            sa.Column("source_deck_path", sa.String(2048), nullable=False),
            sa.Column("note_id", sa.String(36), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("last_session_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["last_session_id"], ["connect_import_sessions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "source_key",
                "external_note_id",
                name="uq_connect_source_note_refs_source_note",
            ),
        )
    _ensure_index("connect_source_note_refs", "ix_connect_source_note_refs_user_id", ["user_id"])
    _ensure_index("connect_source_note_refs", "ix_connect_source_note_refs_note_id", ["note_id"])
    _ensure_index("connect_source_note_refs", "ix_connect_source_note_refs_last_session_id", ["last_session_id"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("connect_import_packages"):
        op.create_table(
            "connect_import_packages",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("storage_path", sa.String(1024), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("item_count", sa.Integer(), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["connect_import_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "session_id",
                "kind",
                "sequence",
                name="uq_connect_import_packages_session_kind_sequence",
            ),
        )
    _ensure_index("connect_import_packages", "ix_connect_import_packages_session_id", ["session_id"])
    _ensure_index("connect_import_packages", "ix_connect_import_packages_status", ["status"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("connect_import_media"):
        op.create_table(
            "connect_import_media",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("media_kind", sa.String(16), nullable=False),
            sa.Column("mime_type", sa.String(64), nullable=False),
            sa.Column("storage_path", sa.String(1024), nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["connect_import_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "filename", name="uq_connect_import_media_session_filename"),
        )
    _ensure_index("connect_import_media", "ix_connect_import_media_session_id", ["session_id"])
    _ensure_index("connect_import_media", "ix_connect_import_media_user_id", ["user_id"])
    _ensure_index("connect_import_media", "ix_connect_import_media_sha256", ["sha256"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in (
        "connect_import_media",
        "connect_import_packages",
        "connect_source_note_refs",
        "connect_source_deck_refs",
        "connect_note_type_refs",
        "connect_import_sessions",
    ):
        if inspector.has_table(table):
            op.drop_table(table)
            inspector = sa.inspect(bind)

