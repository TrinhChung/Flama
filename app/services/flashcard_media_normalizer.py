"""Typed, audited migration of legacy flashcard media-field values."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from types import SimpleNamespace

from sqlalchemy.orm import joinedload, selectinload

from app.services import deck_working_tree_service
from app.services.flashcard_renderer import rewrite_media_template_url_tokens
from app.services.media_field_codec import (
    MEDIA_FIELD_TYPES,
    MediaFieldValueError,
    build_media_reference_lookup,
    is_canonical_media_url,
    join_media_field_urls,
    media_family,
    media_reference_family_from_url,
    normalize_media_reference_for_write,
    split_media_field_value,
)
from models import db
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.field_def import FieldDef
from models.media_field_migration import MediaFieldMigrationItem, MediaFieldMigrationRun
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.study_application import StudyApplication


_SOUND_RE = re.compile(r"^\[sound:(.+)\]$", re.IGNORECASE)
_STROKE_KEY_RE = re.compile(r"^stroke_[a-z0-9_]+_[a-f0-9]{4,6}$", re.IGNORECASE)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_NULL_LITERALS = frozenset({"null", "none", "undefined", "nil", "n/a"})


class _MediaHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered_tag = str(tag or "").lower()
        attr_map = {str(name or "").lower(): str(value or "") for name, value in attrs}
        src = attr_map.get("src", "").strip()
        if src and lowered_tag in {"img", "audio", "video", "source"}:
            self.sources.append((lowered_tag, src, attr_map.get("type", "").strip().lower()))


@dataclass(frozen=True)
class MediaFieldDecision:
    value: str
    action: str
    reason: str
    semantic_change: bool


@dataclass(frozen=True)
class MediaBackfillResult:
    scanned: int
    scanned_fields: int
    changed: int
    normalized: int
    cleared: int
    quarantined: int
    overlays_changed: int
    templates_changed: int
    run_id: str | None
    details: list[dict[str, Any]]


@dataclass(frozen=True)
class MediaRollbackResult:
    run_id: str
    restorable: int
    restored: int
    skipped_changed_since: int
    missing: int


def _classify_one(
    raw_item: str,
    *,
    field_type: str,
    media_lookup: dict[str, Any],
) -> MediaFieldDecision:
    item = str(raw_item or "").strip()
    if not item:
        return MediaFieldDecision("", "keep", "empty", False)
    if item.casefold() in _NULL_LITERALS:
        return MediaFieldDecision("", "clear", "null_literal", True)
    if _STROKE_KEY_RE.fullmatch(item) and media_family(field_type) == "image":
        return MediaFieldDecision(
            f"/store/{item}.svg",
            "normalize",
            "legacy_stroke_key",
            False,
        )

    if item.lower().startswith("http://") and not is_canonical_media_url(item):
        return MediaFieldDecision(item, "quarantine", "insecure_http", False)
    if item.lower().startswith("data:"):
        return MediaFieldDecision(item, "quarantine", "unsupported_data_uri", False)

    try:
        normalized = normalize_media_reference_for_write(
            item,
            field_type=field_type,
            reference_lookup=media_lookup,
        )
        return MediaFieldDecision(
            normalized,
            "normalize" if normalized != item else "keep",
            "resolved_reference" if normalized != item else "canonical_url",
            False,
        )
    except MediaFieldValueError as exc:
        if exc.reason == "wrong_media_kind":
            return MediaFieldDecision("", "clear", "wrong_media_kind", True)
        if exc.reason == "unknown_media_asset":
            return MediaFieldDecision(item, "quarantine", "missing_media_asset", False)

    unwrapped = item
    sound_match = _SOUND_RE.fullmatch(item)
    if sound_match:
        if media_family(field_type) != "audio":
            return MediaFieldDecision("", "clear", "wrong_media_kind", True)
        unwrapped = sound_match.group(1).strip()

    inferred = media_reference_family_from_url(unwrapped)
    expected = media_family(field_type)
    if inferred and inferred != expected:
        return MediaFieldDecision("", "clear", "wrong_media_kind", True)
    if inferred == expected:
        return MediaFieldDecision(item, "quarantine", "missing_binary", False)
    if _UUID_RE.fullmatch(unwrapped):
        return MediaFieldDecision(item, "quarantine", "missing_media_asset", False)
    return MediaFieldDecision("", "clear", "invalid_media_value", True)


def classify_media_field_value(
    raw_value: Any,
    *,
    field_type: str,
    media_lookup: dict[str, Any] | None = None,
) -> MediaFieldDecision:
    old_value = "" if raw_value is None else str(raw_value).strip()
    if not old_value:
        return MediaFieldDecision("", "keep", "empty", False)
    lookup = media_lookup or {}
    json_items: list[str] | None = None
    if old_value.startswith("[") and old_value.endswith("]"):
        try:
            parsed_json = json.loads(old_value)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed_json = None
        if isinstance(parsed_json, list) and all(isinstance(item, str) for item in parsed_json):
            json_items = [str(item).strip() for item in parsed_json if str(item).strip()]

    if "<" in old_value and ">" in old_value:
        parser = _MediaHtmlParser()
        try:
            parser.feed(old_value)
        except Exception:
            return MediaFieldDecision(old_value, "quarantine", "malformed_media_html", False)
        expected = media_family(field_type)
        compatible: list[str] = []
        wrong_kind_seen = False
        quarantined_reason: str | None = None
        for tag, src, type_value in parser.sources:
            declared_family = (
                "audio" if tag == "audio" or type_value.startswith("audio/")
                else "image" if tag == "img" or type_value.startswith("image/")
                else media_reference_family_from_url(src)
            )
            if declared_family and declared_family != expected:
                wrong_kind_seen = True
                continue
            decision = _classify_one(src, field_type=field_type, media_lookup=lookup)
            if decision.action == "clear":
                wrong_kind_seen = True
                continue
            if decision.action == "quarantine":
                quarantined_reason = decision.reason
                continue
            compatible.append(decision.value)
        if quarantined_reason:
            return MediaFieldDecision(old_value, "quarantine", quarantined_reason, False)
        if not compatible:
            if parser.sources:
                return MediaFieldDecision("", "clear", "wrong_media_kind", True)
            return MediaFieldDecision(old_value, "quarantine", "html_without_media_url", False)
        next_value = join_media_field_urls(compatible)
        return MediaFieldDecision(
            next_value,
            "normalize",
            "html_urls_extracted_with_wrong_kind_removed" if wrong_kind_seen else "html_urls_extracted",
            wrong_kind_seen,
        )

    item_decisions = [
        _classify_one(item, field_type=field_type, media_lookup=lookup)
        for item in (json_items if json_items is not None else split_media_field_value(old_value))
    ]
    next_value = join_media_field_urls([decision.value for decision in item_decisions])
    semantic_change = any(decision.semantic_change for decision in item_decisions)
    quarantined = [decision for decision in item_decisions if decision.action == "quarantine"]
    if json_items is not None and quarantined:
        reason = quarantined[0].reason if len({item.reason for item in quarantined}) == 1 else "mixed_media_values"
        return MediaFieldDecision(old_value, "quarantine", reason, semantic_change)
    changed = next_value != old_value
    reasons = {decision.reason for decision in item_decisions if decision.reason not in {"canonical_url", "empty"}}
    reason = next(iter(reasons)) if len(reasons) == 1 else "mixed_media_values" if reasons else "canonical_url"
    if not next_value and old_value:
        return MediaFieldDecision("", "clear", reason, True)
    if quarantined:
        return MediaFieldDecision(next_value, "quarantine" if not changed else "normalize", reason, semantic_change)
    if changed:
        return MediaFieldDecision(next_value, "normalize", reason, semantic_change)
    return MediaFieldDecision(next_value, "keep", reason, semantic_change)


def normalize_single_media_reference(
    raw_item: str,
    media_lookup: dict[str, Any] | None = None,
    *,
    field_type: str = "audio",
) -> str:
    """Compatibility wrapper used by tests and operational scripts."""
    return classify_media_field_value(
        raw_item,
        field_type=field_type,
        media_lookup=media_lookup,
    ).value


def normalize_media_field_value(
    raw_value: Any,
    media_lookup: dict[str, Any] | None = None,
    *,
    field_type: str = "audio",
) -> str:
    return classify_media_field_value(
        raw_value,
        field_type=field_type,
        media_lookup=media_lookup,
    ).value


def _audit_item(
    *,
    run: MediaFieldMigrationRun,
    entity_type: str,
    entity_id: str,
    field_name: str,
    field_type: str | None,
    old_value: str,
    decision: MediaFieldDecision,
    user_id: int | None,
    deck_id: int | None,
) -> None:
    db.session.add(
        MediaFieldMigrationItem(
            run_id=run.id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            field_type=field_type,
            action=decision.action,
            reason=decision.reason[:64],
            old_value=old_value,
            new_value=decision.value,
            semantic_change=decision.semantic_change,
            user_id=user_id,
            deck_id=deck_id,
        )
    )


def backfill_media_field_values(
    *,
    user_id: int | None = None,
    deck_id: int | None = None,
    apply: bool = False,
    include_overlays: bool = True,
    include_templates: bool = True,
    detail_limit: int = 200,
) -> MediaBackfillResult:
    """Audit or apply the typed migration without touching release snapshots."""
    run = None
    if apply:
        run = MediaFieldMigrationRun(
            mode="apply",
            status="running",
            scope_user_id=user_id,
            scope_deck_id=deck_id,
            stats={},
        )
        db.session.add(run)
        db.session.flush()

    field_defs = FieldDef.query.order_by(FieldDef.position.asc(), FieldDef.id.asc()).all()
    defs_by_type: dict[str, list[FieldDef]] = {}
    for field_def in field_defs:
        defs_by_type.setdefault(str(field_def.note_type_id), []).append(field_def)

    scanned = scanned_fields = changed = normalized = cleared = quarantined = 0
    overlays_changed = templates_changed = 0
    details: list[dict[str, Any]] = []
    semantic_mutations: list[dict[str, Any]] = []

    note_query = Note.query.options(selectinload(Note.media_assets)).filter(Note.field_values_by_id.isnot(None))
    if user_id is not None:
        note_query = note_query.filter(Note.user_id == user_id)
    if deck_id is not None:
        note_query = note_query.filter(Note.deck_id == deck_id)

    last_id = ""
    while True:
        page = note_query.filter(Note.id > last_id).order_by(Note.id.asc()).limit(500).all()
        if not page:
            break
        for note in page:
            scanned += 1
            last_id = str(note.id)
            lookup = build_media_reference_lookup(note.media_assets or [])
            values = dict(note.field_values or {})
            next_values = dict(values)
            semantic_fields: set[str] = set()
            note_changed = False
            for field_def in defs_by_type.get(str(note.note_type_id), []):
                field_type = str(field_def.field_type or "").strip().lower()
                if field_type not in MEDIA_FIELD_TYPES or field_def.name not in values:
                    continue
                scanned_fields += 1
                old_value = "" if values.get(field_def.name) is None else str(values.get(field_def.name))
                decision = classify_media_field_value(old_value, field_type=field_type, media_lookup=lookup)
                if decision.action == "keep":
                    continue
                if decision.action == "quarantine":
                    quarantined += 1
                elif decision.action == "clear":
                    cleared += 1
                else:
                    normalized += 1
                if decision.value != old_value:
                    note_changed = True
                    next_values[field_def.name] = decision.value
                    semantic_fields.add(field_def.name)
                if run is not None:
                    _audit_item(
                        run=run,
                        entity_type="note",
                        entity_id=str(note.id),
                        field_name=str(field_def.name),
                        field_type=field_type,
                        old_value=old_value,
                        decision=decision,
                        user_id=int(note.user_id),
                        deck_id=note.deck_id,
                    )
                if len(details) < max(0, int(detail_limit)):
                    details.append({
                        "entity_type": "note",
                        "entity_id": str(note.id),
                        "field_name": str(field_def.name),
                        "action": decision.action,
                        "reason": decision.reason,
                    })
            if note_changed:
                changed += 1
                if apply:
                    note.field_values = next_values
                    if semantic_fields:
                        semantic_mutations.append({
                            "note": note,
                            "field_names": semantic_fields,
                            "operation": "set",
                        })
        if len(page) < 500:
            break

    if include_overlays:
        overlay_query = (
            DeckCloneNoteFieldOverride.query
            .join(DeckInstall, DeckCloneNoteFieldOverride.deck_install_id == DeckInstall.id)
            .options(
                joinedload(DeckCloneNoteFieldOverride.source_field_def),
                joinedload(DeckCloneNoteFieldOverride.source_note).selectinload(Note.media_assets),
                joinedload(DeckCloneNoteFieldOverride.deck_install),
            )
            .filter(DeckCloneNoteFieldOverride.operation == "set")
        )
        if user_id is not None:
            overlay_query = overlay_query.filter(DeckInstall.user_id == user_id)
        if deck_id is not None:
            overlay_query = overlay_query.filter(DeckInstall.local_deck_id == deck_id)
        for override in overlay_query.all():
            field_def = override.source_field_def
            field_type = str(getattr(field_def, "field_type", "") or "").strip().lower()
            if field_type not in MEDIA_FIELD_TYPES:
                continue
            scanned_fields += 1
            old_value = "" if override.value is None else str(override.value)
            lookup = build_media_reference_lookup(override.source_note.media_assets if override.source_note else [])
            decision = classify_media_field_value(old_value, field_type=field_type, media_lookup=lookup)
            if decision.action == "keep":
                continue
            quarantined += int(decision.action == "quarantine")
            cleared += int(decision.action == "clear")
            normalized += int(decision.action == "normalize")
            if decision.value != old_value:
                overlays_changed += 1
                changed += 1
                if apply:
                    override.value = decision.value
            if run is not None:
                install = override.deck_install
                _audit_item(
                    run=run,
                    entity_type="clone_override",
                    entity_id=str(override.id),
                    field_name=str(override.field_name),
                    field_type=field_type,
                    old_value=old_value,
                    decision=decision,
                    user_id=int(install.user_id) if install else None,
                    deck_id=install.local_deck_id if install else None,
                )

    if include_templates:
        template_query = Template.query
        if user_id is not None:
            template_query = template_query.filter(Template.owner_user_id == user_id)
        if deck_id is not None:
            note_type_ids = [row[0] for row in db.session.query(Note.note_type_id).filter(Note.deck_id == deck_id).distinct().all()]
            template_query = template_query.filter(Template.id.in_(
                db.session.query(StudyApplication.template_id).filter(
                    StudyApplication.note_type_id.in_(note_type_ids),
                )
            ))
        for template in template_query.all():
            template_defs = [SimpleNamespace(name=item['key'], field_type=item['type'])
                             for item in template.input_schema or []]
            for attr_name in ("front_html", "back_html"):
                old_value = str(getattr(template, attr_name, "") or "")
                new_value = rewrite_media_template_url_tokens(old_value, template_defs)
                if new_value == old_value:
                    continue
                decision = MediaFieldDecision(new_value, "normalize", "template_url_helper", False)
                templates_changed += 1
                changed += 1
                if apply:
                    setattr(template, attr_name, new_value)
                if run is not None:
                    _audit_item(
                        run=run,
                        entity_type="template",
                        entity_id=str(template.id),
                        field_name=attr_name,
                        field_type=None,
                        old_value=old_value,
                        decision=decision,
                        user_id=int(template.owner_user_id),
                        deck_id=None,
                    )

    if apply and semantic_mutations:
        deck_working_tree_service.mark_note_field_batches_changed(mutations=semantic_mutations)

    stats = {
        "scanned": scanned,
        "scanned_fields": scanned_fields,
        "changed": changed,
        "normalized": normalized,
        "cleared": cleared,
        "quarantined": quarantined,
        "overlays_changed": overlays_changed,
        "templates_changed": templates_changed,
    }
    if run is not None:
        run.stats = stats
        run.status = "completed"
        run.finished_at = datetime.utcnow()
        db.session.flush()

    return MediaBackfillResult(
        **stats,
        run_id=str(run.id) if run is not None else None,
        details=details,
    )


def rollback_media_field_migration(*, run_id: str, apply: bool = False) -> MediaRollbackResult:
    """Restore audited values only when the target still equals this run's output."""
    run = db.session.get(MediaFieldMigrationRun, str(run_id or "").strip())
    if run is None:
        raise ValueError("Media migration run not found.")
    items = (
        MediaFieldMigrationItem.query
        .filter_by(run_id=run.id)
        .order_by(MediaFieldMigrationItem.created_at.desc(), MediaFieldMigrationItem.id.desc())
        .all()
    )
    restorable = restored = skipped_changed_since = missing = 0
    semantic_mutations: dict[str, dict[str, Any]] = {}

    for item in items:
        old_value = "" if item.old_value is None else str(item.old_value)
        new_value = "" if item.new_value is None else str(item.new_value)
        if old_value == new_value:
            continue
        restorable += 1
        if item.entity_type == "note":
            note = db.session.get(Note, item.entity_id)
            if note is None:
                missing += 1
                continue
            from app.repositories.media_audit_identity_repository import resolve_media_audit_field
            identity, current_label = resolve_media_audit_field(note, item)
            values = dict(note.field_values_by_id or {})
            if identity not in values or not isinstance(values[identity], str) or values[identity] != new_value:
                skipped_changed_since += 1
                continue
            if apply:
                values[identity] = old_value
                note.field_values_by_id = values
                mutation = semantic_mutations.setdefault(
                    str(note.id),
                    {"note": note, "field_names": set(), "operation": "set"},
                )
                mutation["field_names"].add(current_label)
            restored += 1
            continue
        if item.entity_type == "clone_override":
            override = db.session.get(DeckCloneNoteFieldOverride, item.entity_id)
            if override is None:
                missing += 1
                continue
            if not isinstance(override.value, str) or override.value != new_value:
                skipped_changed_since += 1
                continue
            if apply:
                override.value = old_value
            restored += 1
            continue
        if item.entity_type == "template":
            template = db.session.get(Template, item.entity_id)
            if template is None or item.field_name not in {"front_html", "back_html"}:
                missing += 1
                continue
            if str(getattr(template, item.field_name, "") or "") != new_value:
                skipped_changed_since += 1
                continue
            if apply:
                setattr(template, item.field_name, old_value)
            restored += 1
            continue
        missing += 1

    if apply:
        if semantic_mutations:
            deck_working_tree_service.mark_note_field_batches_changed(
                mutations=list(semantic_mutations.values())
            )
        stats = dict(run.stats or {})
        stats["rollback_restored"] = restored
        stats["rollback_skipped_changed_since"] = skipped_changed_since
        stats["rollback_missing"] = missing
        run.stats = stats
        run.status = "rolled_back"
        db.session.flush()

    return MediaRollbackResult(
        run_id=str(run.id),
        restorable=restorable,
        restored=restored,
        skipped_changed_since=skipped_changed_since,
        missing=missing,
    )
