"""Expand immutable provenance/archive for explicit offline Field-ID cutover."""
from alembic import op
import sqlalchemy as sa
from migrations.field_identity_contract import tables, bounded_mysql_ddl

revision = "20261014_000066"
down_revision = "20261014_000065"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    expected = tables(sa.MetaData())
    # Inspect all pre-existing contracts before the first MySQL DDL (which is
    # not transactionally reversible), including identity key width/PK.
    for table in expected:
        if sa.inspect(bind).has_table(table.name):
            actual = {column["name"]: column for column in sa.inspect(bind).get_columns(table.name)}
            if set(actual) != set(table.c.keys()) or any(actual[column.name]["nullable"] != column.nullable
                    for column in table.c):
                raise RuntimeError("Existing Field cutover evidence schema differs from frozen contract.")
            if sa.inspect(bind).get_pk_constraint(table.name)["constrained_columns"] != [column.name for column in table.primary_key]:
                raise RuntimeError("Existing Field cutover evidence identity differs from frozen contract.")
            for column in table.c:
                found = actual[column.name]["type"].as_generic()
                expected_type = column.type.as_generic()
                matches = type(found) is type(expected_type) and getattr(found, "length", None) == getattr(expected_type, "length", None)
                if isinstance(expected_type, sa.Boolean) and bind.dialect.name == "mysql":
                    matches = isinstance(found, sa.Integer) and getattr(actual[column.name]["type"], "display_width", None) == 1
                if isinstance(expected_type, sa.Text) and "TEXT" in str(actual[column.name]["type"]).upper():
                    matches = True
                if not matches:
                    raise RuntimeError("Existing Field cutover evidence column type differs from frozen contract.")
    for name in ("media_assets", "deck_clone_note_field_overrides"):
        if not sa.inspect(bind).has_table(name):
            continue
        actual = {column["name"]: column for column in sa.inspect(bind).get_columns(name)}
        if "field_identity_key" in actual and (not isinstance(actual["field_identity_key"]["type"], sa.String) or actual["field_identity_key"]["type"].length != 115):
            raise RuntimeError("Existing stable identity key differs from frozen contract.")
    for table in expected:
        if not sa.inspect(bind).has_table(table.name):
            table.create(bind)
    for name in ("media_assets", "deck_clone_note_field_overrides"):
        if sa.inspect(bind).has_table(name) and "field_identity_key" not in {column["name"] for column in sa.inspect(bind).get_columns(name)}:
            if bind.dialect.name == "mysql":
                with bounded_mysql_ddl(bind):
                    bind.execute(sa.text(f"ALTER TABLE `{name}` ADD COLUMN field_identity_key VARCHAR(115) NULL, ALGORITHM=INSTANT, LOCK=DEFAULT"))
            else:
                op.add_column(name, sa.Column("field_identity_key", sa.String(115), nullable=True))


def downgrade():
    bind = op.get_bind()
    for table in tables(sa.MetaData()):
        if sa.inspect(bind).has_table(table.name) and bind.execute(sa.select(sa.literal(1)).select_from(table).limit(1)).first():
            raise RuntimeError("Retain populated immutable Field cutover evidence.")
    for name in ("media_assets", "deck_clone_note_field_overrides"):
        if sa.inspect(bind).has_table(name):
            if bind.execute(sa.text(f"SELECT 1 FROM {name} WHERE field_identity_key IS NOT NULL LIMIT 1")).first():
                raise RuntimeError("Retain populated stable identity key.")
            op.drop_column(name, "field_identity_key")
    for table in reversed(tables(sa.MetaData())):
        op.drop_table(table.name)
