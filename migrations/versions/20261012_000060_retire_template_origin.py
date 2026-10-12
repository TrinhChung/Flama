"""Retire Template origin coupling after explicit attachment/owner cutover.

Revision ID: 20261012_000060
Revises: 20261012_000059

Populated old templates require a verified full-row archive before any writes.
Ownership is derived only for NULL owners from the actual old origin NoteType;
unknown ownership blocks. Typed input metadata is frozen before the origin is
removed. Source/history/published releases and all application identities,
bindings and scope metadata stay unchanged. No new application is guessed.
"""

from types import SimpleNamespace
from alembic import op
import sqlalchemy as sa
from migrations.retirement_archive import assert_archive_matches

revision = "20261012_000060"
down_revision = "20261012_000059"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("templates"):
        return
    templates = sa.Table("templates", sa.MetaData(), autoload_with=bind, resolve_fks=False)
    if "note_type_id" not in templates.c:
        missing = bind.execute(sa.select(sa.func.count()).select_from(templates)
                               .where(templates.c.owner_user_id.is_(None))).scalar_one()
        if missing:
            raise RuntimeError("Template ownership is incomplete after origin retirement.")
        return
    note_types = sa.Table("note_types", sa.MetaData(), autoload_with=bind, resolve_fks=False)
    users = sa.Table("users", sa.MetaData(), autoload_with=bind, resolve_fks=False)
    applications = sa.Table("study_applications", sa.MetaData(), autoload_with=bind, resolve_fks=False)
    source_rows = bind.execute(sa.select(templates).order_by(templates.c.id)).mappings().all()
    owners = dict(bind.execute(sa.select(note_types.c.id, note_types.c.user_id)).all())
    valid_users = set(bind.execute(sa.select(users.c.id)).scalars())
    for row in source_rows:
        owner = row["owner_user_id"] if row["owner_user_id"] is not None else owners.get(row["note_type_id"])
        if owner not in valid_users:
            raise RuntimeError(f"Template {row['id']} has no verified author; origin contraction refused.")
        if row["note_type_id"] and not bind.execute(sa.select(applications.c.id).where(
            applications.c.template_id == row["id"], applications.c.note_type_id == row["note_type_id"],
        ).limit(1)).first():
            raise RuntimeError(f"Template {row['id']} has an unconverted origin attachment; contraction refused.")
    if source_rows:
        assert_archive_matches(bind, ["templates"])
    # SQLite parent rebuilds under FK enforcement can cascade/delete immutable
    # versions and pins. Require the same maintenance rehearsal as migration54.
    if bind.dialect.name == "sqlite" and bind.exec_driver_sql("PRAGMA foreign_keys").scalar():
        raise RuntimeError("SQLite Template origin contraction requires foreign_keys=OFF before its transaction.")
    fields_by_note_type = {}
    if inspector.has_table("field_defs"):
        fields = sa.Table("field_defs", sa.MetaData(), autoload_with=bind, resolve_fks=False)
        for field in bind.execute(sa.select(fields).order_by(fields.c.position, fields.c.id)).mappings():
            fields_by_note_type.setdefault(field["note_type_id"], []).append(SimpleNamespace(**dict(field)))
    from app.validators.template_library import infer_input_schema
    for row in source_rows:
        changes = {}
        if row["owner_user_id"] is None:
            changes["owner_user_id"] = owners[row["note_type_id"]]
        if row["input_schema"] is None:
            changes["input_schema"] = infer_input_schema(row["front_html"], row["back_html"],
                                                         fields_by_note_type.get(row["note_type_id"], ()))
        if changes:
            # Avoid changing source timestamps; this is metadata contraction.
            if "updated_at" in templates.c:
                changes["updated_at"] = row["updated_at"]
            bind.execute(templates.update().where(templates.c.id == row["id"]).values(**changes))
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table("templates", naming_convention=naming) as batch:
        for fk in inspector.get_foreign_keys("templates"):
            if fk.get("constrained_columns") == ["note_type_id"]:
                batch.drop_constraint(fk.get("name") or "fk_templates_note_type_id_note_types", type_="foreignkey")
        for index in inspector.get_indexes("templates"):
            if "note_type_id" in index.get("column_names", []):
                batch.drop_index(index["name"])
        batch.alter_column("owner_user_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("note_type_id")


def downgrade():
    raise RuntimeError("Template origin contraction requires verified archive/backup restoration into an isolated database; "
                       "new reusable attachments have no single original NoteType to reconstruct.")
