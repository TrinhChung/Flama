"""add Anki card and review provenance

Revision ID: 20260814_000016
Revises: 20260811_000015
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_000016"
down_revision = "20260811_000015"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    package_columns = {
        column["name"]: column
        for column in inspector.get_columns("connect_import_packages")
    }
    if "result_json" not in package_columns:
        with op.batch_alter_table("connect_import_packages") as batch_op:
            batch_op.add_column(
                sa.Column("result_json", sa.JSON(), nullable=True)
            )

    connect_import_packages = sa.table(
        "connect_import_packages",
        sa.column("result_json", sa.JSON()),
    )
    op.execute(
        connect_import_packages.update()
        .where(connect_import_packages.c.result_json.is_(None))
        .values(result_json={})
    )

    package_columns = {
        column["name"]: column
        for column in sa.inspect(bind).get_columns("connect_import_packages")
    }
    if package_columns["result_json"].get("nullable", True):
        with op.batch_alter_table("connect_import_packages") as batch_op:
            batch_op.alter_column(
                "result_json",
                existing_type=sa.JSON(),
                nullable=False,
            )

    if not inspector.has_table("connect_source_card_refs"):
        op.create_table(
            "connect_source_card_refs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("source_key", sa.String(length=255), nullable=False),
            sa.Column("external_card_id", sa.String(length=128), nullable=False),
            sa.Column("external_note_id", sa.String(length=128), nullable=False),
            sa.Column("source_ord", sa.Integer(), nullable=False),
            sa.Column("card_id", sa.String(length=36), nullable=False),
            sa.Column("snapshot_hash", sa.String(length=64), nullable=True),
            sa.Column("applied_local_revision", sa.BigInteger(), nullable=True),
            sa.Column("review_cursor", sa.BigInteger(), nullable=True),
            sa.Column("last_session_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["card_id"], ["cards.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["last_session_id"], ["connect_import_sessions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "source_key", "external_card_id", name="uq_connect_source_card_refs_source_card"),
        )
        op.create_index("ix_connect_source_card_refs_user_id", "connect_source_card_refs", ["user_id"])
        op.create_index("ix_connect_source_card_refs_card_id", "connect_source_card_refs", ["card_id"])
        op.create_index("ix_connect_source_card_refs_last_session_id", "connect_source_card_refs", ["last_session_id"])
        op.create_index("ix_connect_source_card_refs_source_note", "connect_source_card_refs", ["user_id", "source_key", "external_note_id"])

    if not inspector.has_table("connect_review_event_refs"):
        op.create_table(
            "connect_review_event_refs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("source_key", sa.String(length=255), nullable=False),
            sa.Column("external_review_id", sa.String(length=128), nullable=False),
            sa.Column("external_card_id", sa.String(length=128), nullable=False),
            sa.Column("review_event_id", sa.Integer(), nullable=True),
            sa.Column("payload_hash", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("ignored_reason", sa.String(length=64), nullable=True),
            sa.Column("last_session_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["last_session_id"], ["connect_import_sessions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["review_event_id"], ["review_events.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "source_key", "external_review_id", name="uq_connect_review_event_refs_source_review"),
        )
        op.create_index("ix_connect_review_event_refs_user_id", "connect_review_event_refs", ["user_id"])
        op.create_index("ix_connect_review_event_refs_review_event_id", "connect_review_event_refs", ["review_event_id"])
        op.create_index("ix_connect_review_event_refs_status", "connect_review_event_refs", ["status"])
        op.create_index("ix_connect_review_event_refs_last_session_id", "connect_review_event_refs", ["last_session_id"])
        op.create_index("ix_connect_review_event_refs_source_card", "connect_review_event_refs", ["user_id", "source_key", "external_card_id"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("connect_review_event_refs"):
        op.drop_table("connect_review_event_refs")
    if inspector.has_table("connect_source_card_refs"):
        op.drop_table("connect_source_card_refs")

    package_columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("connect_import_packages")
    }
    if "result_json" in package_columns:
        with op.batch_alter_table("connect_import_packages") as batch_op:
            batch_op.drop_column("result_json")
