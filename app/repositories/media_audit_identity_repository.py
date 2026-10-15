"""Resolve old immutable media audit labels without retargeting replacements."""
from __future__ import annotations

import re
from sqlalchemy import or_, select

from models import db
from models.field_value_identity_definition import FieldValueIdentityDefinition
from models.media_asset import MediaAsset
from models.field_def import FieldDef
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from app.services.field_value_identity_service import FieldIdentityConflict
from app.services.field_value_runtime_service import canonical_field_schema_for_note, clone_install_for_note


def resolve_media_audit_field(note, item):
    schema = canonical_field_schema_for_note(note)
    install = clone_install_for_note(note)
    scope = FieldValueIdentityDefinition.note_type_id == note.note_type_id
    if install is not None:
        scope = or_(scope, FieldValueIdentityDefinition.deck_install_id == install.id)
    definitions = db.session.execute(select(FieldValueIdentityDefinition).where(scope,
        FieldValueIdentityDefinition.identity_kind.in_(["owned", "clone_added"]))).scalars()
    candidates = {row.identity_key for row in definitions
        if item.field_name in (row.label_history or [row.retained_name])}
    proven = set()
    # An asset created for the exact old field can disambiguate an otherwise
    # reused label. A cross-field reference is not evidence of target identity.
    asset_ids = re.findall(r"/media/proxy/([A-Za-z0-9_-]{1,128})", str(item.new_value or ""))
    if asset_ids:
        proven = set(db.session.execute(select(MediaAsset.field_identity_key).where(
            MediaAsset.note_id == note.id, MediaAsset.id.in_(asset_ids))).scalars()) & candidates
        if len(proven) == 1:
            candidates = proven
    if len(candidates) != 1:
        raise FieldIdentityConflict("The historical media field identity is ambiguous; rollback requires an explicit mapping")
    identity = next(iter(candidates))
    if identity not in schema.ids:
        raise FieldIdentityConflict("The historical media field was removed; rollback cannot edit its replacement")
    definition = db.session.get(DeckCloneAddedFieldDef, identity.rsplit(":", 1)[-1]) if identity.startswith("added:")\
        else db.session.get(FieldDef, identity)
    if definition is None or (identity not in proven and item.created_at is not None
            and definition.created_at is not None and definition.created_at >= item.created_at):
        raise FieldIdentityConflict("The historical media audit predates this field identity; rollback requires explicit provenance")
    return identity, schema.ids[identity]
