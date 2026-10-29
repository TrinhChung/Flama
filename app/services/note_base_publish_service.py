"""Incremental atomic publication, independent of subscriber count.

The caller owns the transaction and holds the listing row lock. Releases retain
labels, changelogs and template pins only; no content atoms or checkpoints.
"""
from copy import deepcopy
from datetime import datetime, timezone

from app.repositories import note_base_repository as repository
from app.repositories import deck_release_repository
from app.services import deck_release_service as legacy
from app.services.note_base_context import published_base_write
from app.services.note_draft_service import merge_draft_values
from models import db
from models.deck_release import DeckRelease


def _change(*, kind, identity, before, after, deck_id=None, field_id=None, field_name=None,
            before_exists=True, after_exists=True, property_key="note"):
    return legacy._change_descriptor(
        change_key=f"{kind}:{identity}:{property_key}", entity_kind=kind,
        entity_id=str(identity), field_def_id=field_id, field_name=field_name,
        property_key=property_key, before_value=before, after_value=after,
        before_exists=before_exists, after_exists=after_exists,
        source_deck_id=deck_id, sort_key=f"{kind}:{identity}:{property_key}",
    )


def build_plan(item, *, lock=False):
    pending = repository.pending_notes(item, lock=lock)
    schema = repository.schema_snapshot(item, lock=lock)
    changes = []
    old_schema = item.published_schema_json or {}
    for field_id in sorted(set(schema) | set(old_schema)):
        before, after = old_schema.get(field_id), schema.get(field_id)
        if before != after:
            changes.append(_change(kind="field_def", identity=field_id, before=before, after=after,
                field_id=field_id, field_name=(after or before or {}).get("name"),
                before_exists=before is not None, after_exists=after is not None and not after.get("deleted_at"),
                property_key="definition"))
    for note, draft in pending:
        if draft is None:
            changes.append(_change(kind="note_field", identity=note.id, before=None,
                after={"note_id": note.id, "new_note": True}, deck_id=note.deck_id,
                before_exists=False))
            continue
        if draft.op == "delete":
            changes.append(_change(kind="note_field", identity=note.id, before={"note_id": note.id},
                after=None, deck_id=note.deck_id, after_exists=False))
            continue
        for identity, delta in sorted((draft.field_values_by_id or {}).items()):
            if identity.startswith("meta:"):
                continue
            field_name = delta.get("label") if identity.startswith("extra:") else schema.get(identity, {}).get("name")
            base = note.field_values_extras or {} if identity.startswith("extra:") else note.field_values_by_id or {}
            key = field_name if identity.startswith("extra:") else identity
            changes.append(_change(kind="note_field", identity=note.id, before=base.get(key),
                after=delta.get("value"), deck_id=note.deck_id, field_id=identity,
                field_name=field_name, before_exists=key in base, after_exists=delta.get("op") == "set",
                property_key=f"field:{identity}"))
        if draft.tags is not None or draft.deck_id is not None or "meta:deck_id" in (draft.field_values_by_id or {}):
            target_deck_id = draft.deck_id if draft.deck_id is not None else note.deck_id
            if "meta:deck_id" in (draft.field_values_by_id or {}):
                target_deck_id = draft.field_values_by_id["meta:deck_id"].get("value")
            changes.append(_change(kind="note_field", identity=note.id,
                before={"tags": note.tags, "deck_id": note.deck_id},
                after={"tags": draft.tags if draft.tags is not None else note.tags,
                       "deck_id": target_deck_id},
                deck_id=note.deck_id, property_key="metadata"))
    from app.services.template_release_service import deck_template_presentations
    before = deck_template_presentations(db.session, note_type_id=item.source_note_type_id,
        release_id=item.current_release_id) if item.current_release_id else {}
    after = deck_template_presentations(db.session, note_type_id=item.source_note_type_id)
    for identity in sorted(set(before) | set(after)):
        if before.get(identity) != after.get(identity):
            changes.append(_change(kind="template", identity=identity, before=before.get(identity),
                after=after.get(identity), before_exists=identity in before, after_exists=identity in after,
                property_key="presentation"))
    return {"pending": pending, "schema": schema, "changes": sorted(changes, key=lambda row: (row["sort_key"], row["change_key"]))}


def preview_release(*, deck_item_id, user_id, cursor=None, limit=None, entity_kind=None,
                    operation=None, source_deck_id=None, query_text=None):
    item = legacy._get_owned_item(deck_item_id=deck_item_id, user_id=user_id)
    page_limit = legacy._coerce_page_limit(limit)
    position = legacy._decode_preview_cursor(cursor)
    revision = int(item.working_revision or 0)
    if position and position[0] != revision:
        raise legacy.DeckReleaseError("WORKING_REVISION_STALE", "Refresh the draft preview.", status=409)
    kind = (entity_kind or "").strip() or None
    if kind and kind not in legacy.VISIBLE_ENTITY_KINDS:
        raise legacy.DeckReleaseError("VALIDATION_ERROR", "Invalid entity type.", field="type")
    op = legacy.FILTER_OPERATION_ALIASES.get(str(operation).strip().lower()) if operation else None
    if operation and op is None:
        raise legacy.DeckReleaseError("VALIDATION_ERROR", "Invalid operation.", field="operation")
    deck_id = legacy._coerce_optional_positive_int(source_deck_id, field_name="deck_id")
    plan = build_plan(item)
    filtered = [row for row in plan["changes"] if legacy._matches_preview_filters(row,
        entity_kind=kind, operation=op, source_deck_id=deck_id, query_text=query_text)
        and (not position or (row["sort_key"], row["change_key"]) > (position[1], position[2]))]
    page = filtered[:page_limit]
    next_cursor = legacy._encode_preview_cursor(revision, page[-1]["sort_key"], page[-1]["change_key"]) if len(filtered) > page_limit and page else None
    return {"deck_item_id": str(item.id), "deck_title": item.title,
        "base_release": legacy.serialize_release(item.current_release), "working_revision": revision,
        "snapshot_revision": str(revision), "summary": legacy._summary_for_changes(plan["changes"]),
        "initial_baseline_mode": None, "items": [legacy._serialize_change_dict(row) for row in page],
        "next_cursor": next_cursor, "content_model": "published_base"}


class PublishedBaseAdapter(legacy._DeckPublishAdapter):
    def find_replay(self, key):
        from sqlalchemy import select
        return db.session.execute(select(DeckRelease).where(DeckRelease.deck_item_id == self.item.id,
            DeckRelease.idempotency_key == key).with_for_update()
            .execution_options(populate_existing=True)).scalar_one_or_none()

    def label_exists(self, label):
        from sqlalchemy import select
        return db.session.execute(select(DeckRelease.id).where(DeckRelease.deck_item_id == self.item.id,
            DeckRelease.version_label == label).with_for_update()).first() is not None

    def plan(self):
        # Same lock order as author flushes: listing -> schema -> Notes.
        from sqlalchemy import select
        from models.note_type import NoteType
        if self.item.current_release_id:
            status = db.session.execute(select(DeckRelease.status).where(
                DeckRelease.id == self.item.current_release_id).with_for_update()).scalar_one_or_none()
            if status != "published":
                self.fail("RELEASE_HEAD_INVALID", "The current release is not published.")
        if self.item.source_note_type_id:
            db.session.execute(select(NoteType.id).where(
                NoteType.id == self.item.source_note_type_id).with_for_update()).first()
        return build_plan(self.item, lock=True)

    def has_changes(self, plan):
        return bool(plan["changes"])

    def persist(self, plan, request):
        item = self.item
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        removed = [note.id for note, draft in plan["pending"] if draft is not None and draft.op == "delete"]
        referenced = repository.referenced_note_ids(removed)
        deck_ids = set()
        with published_base_write(reason="publish", session=db.session):
            for note, draft in plan["pending"]:
                if note.deck_id is not None:
                    deck_ids.add(note.deck_id)
                if draft is not None:
                    if draft.op == "delete":
                        if note.id in referenced:
                            note.deleted_at = now
                        else:
                            from models.card import forget_card_identities
                            forget_card_identities(db.session, [note.id])
                            db.session.delete(note)
                        db.session.delete(draft)
                        continue
                    values, extras = merge_draft_values(note.field_values_by_id or {}, note.field_values_extras or {}, draft.field_values_by_id or {})
                    note.field_values_by_id = values
                    note.field_values_extras = extras
                    from sqlalchemy.orm.attributes import flag_modified
                    # JSON booleans and numbers must not collapse through
                    # Python's True == 1 equality when SQLAlchemy compares.
                    flag_modified(note, "field_values_by_id")
                    flag_modified(note, "field_values_extras")
                    if draft.tags is not None:
                        note.tags = deepcopy(draft.tags)
                    if draft.deck_id is not None:
                        note.deck_id = draft.deck_id
                    elif "meta:deck_id" in (draft.field_values_by_id or {}):
                        note.deck_id = draft.field_values_by_id["meta:deck_id"].get("value")
                    db.session.delete(draft)
                note.published_at = note.published_at or now
                # The identity hook increments revisions for actual Base writes.
                if note.deck_id is not None:
                    deck_ids.add(note.deck_id)
            item.published_schema_json = plan["schema"]
            from sqlalchemy import select
            sequence = db.session.execute(select(DeckRelease.sequence_no).where(
                DeckRelease.deck_item_id == item.id).order_by(DeckRelease.sequence_no.desc())
                .limit(1).with_for_update()).scalar_one_or_none()
            release = DeckRelease(deck_item_id=item.id,
                sequence_no=int(sequence or 0) + 1,
                version_label=request.version_label, parent_release_id=request.expected_head_id,
                status="published", publish_mode="manual", source_working_revision=int(item.working_revision or 0),
                manifest_hash=legacy._release_manifest_hash(plan["changes"]), changelog=request.change_note,
                idempotency_key=request.idempotency_key, created_by_user_id=self.user_id,
                published_at=now, **legacy._summary_for_changes(plan["changes"]))
            db.session.add(release)
            db.session.flush()
            from app.services.template_release_service import capture_deck_release_template_pins
            capture_deck_release_template_pins(db.session, release, actor_user_id=self.user_id)
            item.current_release = release
            item.current_release_id = release.id
            item.version = request.version_label
            item.changelog = request.change_note
            item.published_at = now
            # Lazily rebuild samples from this Base, never the author property.
            item.preview_samples_release_id = None
            item.preview_samples_json = None
            from app.repositories.deck_count_snapshot_repository import bump_content_revisions
            bump_content_revisions(db.session, sorted(deck_ids))
            db.session.flush()
        return release
