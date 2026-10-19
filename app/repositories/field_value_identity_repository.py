"""Scoped Core schema insertion using the same canonical identity lifecycle."""
from sqlalchemy import insert, select, update

from models.field_def import FieldDef
from models.note_type import NoteType


def insert_field_definition(session, **values):
    """Insert a definition and retained identity under its parent epoch lock."""
    from app.services.field_value_identity_hooks import retain_field_definition
    from app.services.field_value_runtime_service import clear_field_runtime_caches
    from models.model_uuid import uuid_str
    type_id = values.get("note_type_id")
    if not type_id:
        raise ValueError("Explicit NoteType scope is required")
    values.setdefault("id", uuid_str())
    session.flush()
    session.execute(select(NoteType.field_schema_revision).where(NoteType.id == type_id)
        .with_for_update()).scalar_one()
    result = session.execute(insert(FieldDef.__table__).values(**values)
        .execution_options(field_identity_scoped_schema=True))
    session.connection().execute(update(NoteType.__table__).where(NoteType.id == type_id)
        .values(field_schema_revision=NoteType.field_schema_revision + 1))
    retain_field_definition(session, identity_key=values["id"], identity_kind="owned",
        field_id=values["id"], note_type_id=type_id, name=values["name"])
    loaded = session.identity_map.get(session.identity_key(NoteType, type_id))
    if loaded is not None:
        session.expire(loaded, ["field_schema_revision", "field_defs"])
    clear_field_runtime_caches(session)
    return result
