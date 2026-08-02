"""backfill Flama Standard Vocabulary identity field

Revision ID: 20260802_000012
Revises: 20260802_000011
Create Date: 2026-08-02 00:00:12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260802_000012"
down_revision = "20260802_000011"
branch_labels = None
depends_on = None


STANDARD_MODEL_NAME = "Flama Standard Vocabulary"
STANDARD_IDENTITY_FIELD = "word"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("note_types") or not inspector.has_table("field_defs"):
        return
    field_columns = {column["name"] for column in inspector.get_columns("field_defs")}
    if "identity_role" not in field_columns:
        return

    note_type_ids = bind.execute(
        sa.text(
            """
            SELECT note_types.id
            FROM note_types
            WHERE note_types.name = :model_name
              AND EXISTS (
                  SELECT 1
                  FROM field_defs
                  WHERE field_defs.note_type_id = note_types.id
                    AND field_defs.name = :field_name
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM field_defs
                  WHERE field_defs.note_type_id = note_types.id
                    AND field_defs.identity_role = 'primary'
              )
            """
        ),
        {"model_name": STANDARD_MODEL_NAME, "field_name": STANDARD_IDENTITY_FIELD},
    ).scalars().all()

    for note_type_id in note_type_ids:
        bind.execute(
            sa.text(
                """
                UPDATE field_defs
                SET identity_role = 'primary', field_type = 'text', required = :required
                WHERE note_type_id = :note_type_id AND name = :field_name
                """
            ),
            {
                "note_type_id": note_type_id,
                "field_name": STANDARD_IDENTITY_FIELD,
                "required": True,
            },
        )


def downgrade() -> None:
    # This is a semantic data repair. Do not erase a valid identity selection
    # during downgrade because the user may have confirmed or changed it later.
    pass
