"""track attempted Anki notes separately from successful notes

Revision ID: 20260814_000017
Revises: 20260814_000016
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_000017"
down_revision = "20260814_000016"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"] for column in inspector.get_columns("connect_import_sessions")
    }
    if "attempted_notes" not in columns:
        with op.batch_alter_table("connect_import_sessions") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "attempted_notes",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
        op.execute(
            "UPDATE connect_import_sessions "
            "SET attempted_notes = processed_notes"
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"] for column in inspector.get_columns("connect_import_sessions")
    }
    if "attempted_notes" in columns:
        with op.batch_alter_table("connect_import_sessions") as batch_op:
            batch_op.drop_column("attempted_notes")
