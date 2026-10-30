"""Private comparison of sparse learner edits against the current Base."""
import hashlib
import json

from sqlalchemy import select

from models import db
from models.note import Note
from models.deck_install import DeckInstall
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from app.services.deck_install_rebase_service import DeckInstallUpdateError
from app.services.effective_note_reader import published_field_defs


def base_value_hash(value, *, exists):
    # Include presence: an explicit JSON null differs from an absent field.
    payload = {"exists": exists, "value": value if exists else None}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def _base_changed(row, value, *, exists):
    from app.services.field_value_identity_service import typed_value_equal
    differs = exists if row.operation == "remove" else not exists or not typed_value_equal(row.value, value)
    return differs and row.base_hash is not None and row.base_hash != base_value_hash(value, exists=exists)


def overrides_base_changed(install, base_named_values, overrides):
    """Compare an already-batched Browse page without loading Notes again."""
    schema = install.deck_item.published_schema_json or {}
    for row in overrides:
        if row.base_hash is None:
            continue
        field = schema.get(row.field_identity_key, {})
        label = row.field_name if row.field_identity_key.startswith("extra:") else field.get("name")
        if _base_changed(row, base_named_values.get(label), exists=label in base_named_values):
            return True
    return False


def _owned_install(install_id, user_id):
    install = db.session.execute(select(DeckInstall).where(
        DeckInstall.id == install_id, DeckInstall.user_id == user_id)).scalar_one_or_none()
    if install is None:
        raise DeckInstallUpdateError("Installed deck not found.", error="INSTALL_NOT_FOUND", status=404)
    return install


def compare_overrides(*, install_id, user_id, after=None, limit=50):
    install = _owned_install(install_id, user_id)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise DeckInstallUpdateError("limit must be an integer.", error="VALIDATION_ERROR", status=400)
    if limit < 1 or limit > 200:
        raise DeckInstallUpdateError("limit must be between 1 and 200.", error="VALIDATION_ERROR", status=400)
    schema = published_field_defs(install, include_deleted=True)
    from app.repositories.deck_tree_query import collect_subtree_ids
    source_decks = set(collect_subtree_ids(install.source_deck_id)) if install.source_deck_id else set()
    statement = select(DeckCloneNoteFieldOverride, Note).join(Note,
        Note.id == DeckCloneNoteFieldOverride.source_note_id).where(
        DeckCloneNoteFieldOverride.deck_install_id == install.id,
        Note.user_id == install.source_owner_user_id).order_by(DeckCloneNoteFieldOverride.id)
    if after:
        statement = statement.where(DeckCloneNoteFieldOverride.id > after)
    rows = db.session.execute(statement.limit(limit + 1).execution_options(
        include_deleted_notes=True, include_deleted_fields=True, include_deleted_drafts=True)).all()
    items = []
    for override, note in rows[:limit]:
        identity = override.field_identity_key
        field = schema.get(identity, {})
        values = note.field_values_extras or {} if identity.startswith("extra:") else note.field_values_by_id or {}
        key = override.field_name if identity.startswith("extra:") else identity
        exists = key in values
        value = values.get(key)
        in_base = note.published_at is not None and note.deck_id in source_decks
        if not in_base:
            exists, value = False, None
        current_hash = base_value_hash(value, exists=exists)
        items.append({"id": override.id, "note_id": note.id, "field_identity": identity,
            "field_name": field.get("name") or override.field_name, "operation": override.operation,
            "personal_value": override.value, "base_value": value, "base_exists": exists,
            "current_base_hash": current_hash,
            "base_changed": _base_changed(override, value, exists=exists),
            "note_deleted": note.deleted_at is not None or not in_base,
            "field_deleted": bool(field.get("deleted_at")) or (not field and not identity.startswith(("extra:", "added:")))})
    release = install.deck_item.current_release
    return {"content_model": "published_base", "install_id": install.id,
        "deck_title": install.deck_item.title, "overlay_revision": int(install.overlay_revision or 0),
        "content_revision": int(release.sequence_no or 0) if release else 0,
        "items": items, "next_cursor": items[-1]["id"] if len(rows) > limit else None}


def clear_override(*, install_id, override_id, user_id, expected_overlay_revision):
    """Deleting the sparse row is distinct from the stored remove operation."""
    from app.services.clone_field_identity_service import lock_clone_overlay_write
    from app.services.field_value_identity_service import FieldIdentityError, FieldIdentityConflict
    install = _owned_install(install_id, user_id)
    if expected_overlay_revision is None:
        raise DeckInstallUpdateError("expected_overlay_revision is required.", error="VALIDATION_ERROR", status=400)
    try:
        install = lock_clone_overlay_write(install, expected_revision=expected_overlay_revision)
        row = db.session.execute(select(DeckCloneNoteFieldOverride).where(
            DeckCloneNoteFieldOverride.id == override_id,
            DeckCloneNoteFieldOverride.deck_install_id == install.id).with_for_update()).scalar_one_or_none()
        if row is None:
            raise DeckInstallUpdateError("Personal override not found.", error="OVERRIDE_NOT_FOUND", status=404)
        db.session.delete(row)
        install.overlay_revision = int(install.overlay_revision or 0) + 1
        db.session.commit()
        return {"success": True, "overlay_revision": int(install.overlay_revision)}
    except (FieldIdentityError, FieldIdentityConflict) as exc:
        db.session.rollback()
        raise DeckInstallUpdateError(str(exc), error="OVERLAY_REVISION_STALE", status=409) from exc
    except Exception:
        db.session.rollback()
        raise


def keep_override(*, install_id, override_id, user_id, expected_overlay_revision, expected_base_hash):
    """Acknowledge exactly the Base shown in the comparison, retaining the edit."""
    from app.services.clone_field_identity_service import lock_clone_overlay_write
    from app.services.field_value_identity_service import FieldIdentityError, FieldIdentityConflict
    from app.repositories import note_base_repository
    from models.deck_marketplace_item import DeckMarketplaceItem
    from models.note_type import NoteType
    if expected_overlay_revision is None or not isinstance(expected_base_hash, str) or len(expected_base_hash) != 64:
        raise DeckInstallUpdateError("Expected overlay revision and Base hash are required.", error="VALIDATION_ERROR", status=400)
    install = _owned_install(install_id, user_id)
    try:
        install = lock_clone_overlay_write(install, expected_revision=expected_overlay_revision)
        item = db.session.execute(select(DeckMarketplaceItem).where(
            DeckMarketplaceItem.id == install.deck_item_id).with_for_update()
            .execution_options(populate_existing=True)).scalar_one()
        db.session.execute(select(NoteType.id).where(NoteType.id == install.source_note_type_id)
            .with_for_update()).first()
        row = db.session.execute(select(DeckCloneNoteFieldOverride).where(
            DeckCloneNoteFieldOverride.id == override_id,
            DeckCloneNoteFieldOverride.deck_install_id == install.id).with_for_update()
            .execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            raise DeckInstallUpdateError("Personal override not found.", error="OVERRIDE_NOT_FOUND", status=404)
        note = db.session.execute(select(Note).where(Note.id == row.source_note_id,
            Note.user_id == install.source_owner_user_id).with_for_update()
            .execution_options(populate_existing=True, include_deleted_notes=True,
                include_deleted_drafts=True)).scalar_one_or_none()
        values = (note.field_values_extras or {} if row.field_identity_key.startswith("extra:")
            else note.field_values_by_id or {}) if note is not None else {}
        key = row.field_name if row.field_identity_key.startswith("extra:") else row.field_identity_key
        in_base = note is not None and note.published_at is not None and note.deck_id in note_base_repository.source_deck_ids(item, lock=True)
        exists = in_base and key in values
        current_hash = base_value_hash(values.get(key), exists=exists)
        if current_hash != expected_base_hash:
            raise DeckInstallUpdateError("The Base changed; reload before keeping your edit.", error="BASE_REVISION_STALE", status=409)
        row.base_hash = current_hash
        row.base_release_id = item.current_release_id
        install.overlay_revision = int(install.overlay_revision or 0) + 1
        db.session.commit()
        return {"success": True, "overlay_revision": int(install.overlay_revision)}
    except (FieldIdentityError, FieldIdentityConflict) as exc:
        db.session.rollback()
        raise DeckInstallUpdateError(str(exc), error="OVERLAY_REVISION_STALE", status=409) from exc
    except Exception:
        db.session.rollback()
        raise
