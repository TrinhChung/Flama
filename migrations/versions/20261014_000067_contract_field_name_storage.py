"""Retire live name-key Note storage and rename-rewrite jobs after archive gate.

Populated databases deliberately stop before DDL until the offline preparation
has archived, checksummed and verified all rows with all writers quiesced.
An empty fresh chain requires no data migration. Downgrade is fail-closed:
restore immutable archive into an isolated pre-cutover database instead.
"""
from datetime import datetime
from alembic import op
import sqlalchemy as sa
from migrations.field_identity_contract import CODEC, CUTOVERS, reflected, verify_prepared, bounded_mysql_ddl

revision = "20261014_000067"
down_revision = "20261014_000066"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("notes")}
    # Also validate on retry after nontransactional MySQL DDL. A partial rename
    # contraction must not prevent completing the remaining uniqueness/job DDL.
    verify_prepared(bind, allow_partial_contract="field_values" not in columns)
    if "field_values" in columns and bind.dialect.name == "mysql":
        with bounded_mysql_ddl(bind):
            bind.execute(sa.text("ALTER TABLE notes MODIFY COLUMN field_values_by_id JSON NOT NULL, "
                "MODIFY COLUMN field_values_codec VARCHAR(32) NOT NULL DEFAULT 'field-id.v1', "
                "MODIFY COLUMN field_values_extras JSON NOT NULL, ALGORITHM=INPLACE, LOCK=NONE"))
            bind.execute(sa.text("ALTER TABLE notes DROP COLUMN field_values, ALGORITHM=INSTANT, LOCK=DEFAULT"))
    elif "field_values" in columns:
        with op.batch_alter_table("notes") as batch:
            batch.alter_column("field_values_by_id", existing_type=sa.JSON(), nullable=False)
            batch.alter_column("field_values_codec", existing_type=sa.String(32), nullable=False,
                               server_default=CODEC)
            batch.alter_column("field_values_extras", existing_type=sa.JSON(), nullable=False)
            batch.drop_column("field_values")
    unique_names = {constraint["name"] for constraint in sa.inspect(bind).get_unique_constraints("media_assets")}
    if bind.dialect.name == "mysql":
        clauses = ["MODIFY COLUMN field_identity_key VARCHAR(115) NOT NULL"]
        if "uq_media_assets_note_sha_field" in unique_names:
            clauses.append("DROP INDEX uq_media_assets_note_sha_field")
        if "uq_media_assets_note_sha_identity" not in unique_names:
            clauses.append("ADD CONSTRAINT uq_media_assets_note_sha_identity UNIQUE (note_id,sha256,field_identity_key)")
        with bounded_mysql_ddl(bind):
            bind.execute(sa.text("ALTER TABLE media_assets " + ", ".join(clauses) + ", ALGORITHM=INPLACE, LOCK=NONE"))
    else:
        with op.batch_alter_table("media_assets") as batch:
            batch.alter_column("field_identity_key", existing_type=sa.String(115), nullable=False)
            if "uq_media_assets_note_sha_field" in unique_names:
                batch.drop_constraint("uq_media_assets_note_sha_field", type_="unique")
            if "uq_media_assets_note_sha_identity" not in unique_names:
                batch.create_unique_constraint("uq_media_assets_note_sha_identity", ["note_id", "sha256", "field_identity_key"])
    if sa.inspect(bind).has_table("deck_clone_note_field_overrides"):
        names = {constraint["name"] for constraint in sa.inspect(bind).get_unique_constraints("deck_clone_note_field_overrides")}
        if bind.dialect.name == "mysql":
            clauses = ["MODIFY COLUMN field_identity_key VARCHAR(115) NOT NULL"]
            clauses.extend("DROP INDEX " + name for name in ("uq_clone_note_override_install_note_field", "uq_clone_note_override_install_note_field_def") if name in names)
            if "uq_clone_note_override_install_note_identity" not in names:
                clauses.append("ADD CONSTRAINT uq_clone_note_override_install_note_identity UNIQUE (deck_install_id,source_note_id,field_identity_key)")
            with bounded_mysql_ddl(bind):
                bind.execute(sa.text("ALTER TABLE deck_clone_note_field_overrides " + ", ".join(clauses) + ", ALGORITHM=INPLACE, LOCK=NONE"))
        else:
            with op.batch_alter_table("deck_clone_note_field_overrides") as batch:
                batch.alter_column("field_identity_key", existing_type=sa.String(115), nullable=False)
                for name in ("uq_clone_note_override_install_note_field", "uq_clone_note_override_install_note_field_def"):
                    if name in names:
                        batch.drop_constraint(name, type_="unique")
                if "uq_clone_note_override_install_note_identity" not in names:
                    batch.create_unique_constraint("uq_clone_note_override_install_note_identity", ["deck_install_id", "source_note_id", "field_identity_key"])
    if sa.inspect(bind).has_table("field_rename_jobs"):
        op.drop_table("field_rename_jobs")
    # Source definitions can disappear while old releases remain pinned. The
    # detached stable IDs/ledger preserve both schema and content overlays.
    for table in ("deck_clone_field_def_overrides", "deck_clone_note_field_overrides"):
        if not sa.inspect(bind).has_table(table):
            continue
        keys = [key for key in sa.inspect(bind).get_foreign_keys(table)
                if key["constrained_columns"] == ["source_field_def_id"] and key["referred_table"] == "field_defs"]
        for key in keys:
            if bind.dialect.name == "mysql":
                name = bind.dialect.identifier_preparer.quote(key["name"])
                with bounded_mysql_ddl(bind):
                    bind.execute(sa.text(f"ALTER TABLE {table} DROP FOREIGN KEY {name}, ALGORITHM=INPLACE, LOCK=NONE"))
            else:
                convention = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
                with op.batch_alter_table(table, naming_convention=convention) as batch:
                    batch.drop_constraint(key["name"] or f"fk_{table}_source_field_def_id_field_defs", type_="foreignkey")
    manifest = reflected(bind, CUTOVERS)
    bind.execute(sa.update(manifest).where(manifest.c.id == CODEC).values(state="contracted", completed_at=datetime.utcnow()))


def downgrade():
    raise RuntimeError("Field-ID contraction cannot recreate lost name storage or rename evidence. "
                       "Restore the verified immutable cutover archive into an isolated database and reconcile before an old writer rollback.")
