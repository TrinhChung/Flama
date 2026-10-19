"""Reject obsolete declared labels before a normalizer can discard them."""
from __future__ import annotations

from flask import has_app_context
from sqlalchemy import select


def validate_incoming_field_labels(values, field_defs) -> None:
    if not isinstance(values, dict) or not has_app_context():
        return
    fields = tuple(field_defs)
    names = {field.get("name") if isinstance(field, dict) else field.name for field in fields}
    unknown = set(values) - names
    if not unknown:
        return
    scope_ids = {field.get("note_type_id") if isinstance(field, dict) else getattr(field, "note_type_id", None) for field in fields}
    scope_ids.discard(None)
    if not scope_ids:
        return
    from models import db
    from models.field_value_identity_definition import FieldValueIdentityDefinition
    from app.services.field_value_identity_service import FieldIdentityConflict
    with db.session.no_autoflush:
        definitions = db.session.execute(select(FieldValueIdentityDefinition).where(
            FieldValueIdentityDefinition.note_type_id.in_(scope_ids),
            FieldValueIdentityDefinition.identity_kind == "owned")).scalars()
        if any(unknown & set(row.label_history or [row.retained_name]) for row in definitions):
            raise FieldIdentityConflict("A field label changed or was removed; reload the schema before saving")
