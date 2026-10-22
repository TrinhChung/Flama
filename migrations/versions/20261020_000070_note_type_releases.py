"""Add complete NoteType publications without inventing historical snapshots.

Revision ID: 20261020_000070
Revises: 20261019_000069
"""

from alembic import op
import sqlalchemy as sa

revision = "20261020_000070"
down_revision = "20261019_000069"
branch_labels = None
depends_on = None

POINTERS = (
    ("note_types", "current_release_id", "fk_note_types_current_release"),
    ("note_type_installs", "applied_release_id", "fk_note_type_installs_applied_release"),
)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_options = {}
    release_id_type = sa.String(36)
    if bind.dialect.name == "mysql":
        parent_options = inspector.get_table_options("note_types")
        table_options = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
        if parent_options.get("mysql_collate"):
            table_options["mysql_collate"] = parent_options["mysql_collate"]
        # Match UUID FK columns even when a deployment's parent table has a
        # collation different from the database default.
        parent_id = next(column for column in inspector.get_columns("note_types") if column["name"] == "id")
        release_id_type = sa.String(36, collation=getattr(parent_id["type"], "collation", None))
    if "note_type_releases" not in inspector.get_table_names():
        op.create_table("note_type_releases",
            sa.Column("id", release_id_type, primary_key=True),
            sa.Column("note_type_id", release_id_type, sa.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_label", sa.String(50), nullable=False),
            sa.Column("sequence_no", sa.BigInteger(), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("manifest_json", sa.JSON(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("note_type_id", "version_label", name="uq_note_type_releases_source_label"),
            sa.UniqueConstraint("note_type_id", "sequence_no", name="uq_note_type_releases_source_sequence"),
            sa.CheckConstraint("sequence_no > 0", name="ck_note_type_releases_sequence_positive"),
            **table_options,
        )
        op.create_index("ix_note_type_releases_note_type_id", "note_type_releases", ["note_type_id"])
    for table, column, constraint in POINTERS:
        if column not in {row["name"] for row in sa.inspect(bind).get_columns(table)}:
            if bind.dialect.name == "mysql":
                column_type = release_id_type.compile(dialect=bind.dialect)
                op.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type} NULL, ALGORITHM=INSTANT"))
            else:
                op.add_column(table, sa.Column(column, sa.String(36), nullable=True))
        index = f"ix_{table}_{column}"
        if index not in {row["name"] for row in sa.inspect(bind).get_indexes(table)}:
            if bind.dialect.name == "mysql":
                op.execute(sa.text(f"ALTER TABLE {table} ADD INDEX {index} ({column}), ALGORITHM=INPLACE, LOCK=NONE"))
            else:
                op.create_index(index, table, [column])
        # SQLite cannot ALTER constraints; its rehearsal chain keeps the plain column.
        if bind.dialect.name == "mysql" and constraint not in {
                row["name"] for row in sa.inspect(bind).get_foreign_keys(table)}:
            op.create_foreign_key(constraint, table, "note_type_releases", [column], ["id"], ondelete="SET NULL")


def downgrade():
    bind = op.get_bind()
    if "note_type_releases" not in sa.inspect(bind).get_table_names():
        return
    if bind.execute(sa.text("SELECT 1 FROM note_type_releases LIMIT 1")).first():
        raise RuntimeError("Retain complete published NoteType releases and installation provenance.")
    for table, column, constraint in reversed(POINTERS):
        if constraint in {row["name"] for row in sa.inspect(bind).get_foreign_keys(table)}:
            op.drop_constraint(constraint, table, type_="foreignkey")
        if column in {row["name"] for row in sa.inspect(bind).get_columns(table)}:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
            op.drop_column(table, column)
    op.drop_table("note_type_releases")
