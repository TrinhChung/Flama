"""Domain service for external note synchronization, identity mapping, diffing, and batch upsert."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime
from typing import Any

from app.repositories import template_library_repository, vocabulary_repository
from app.services import deck_working_tree_service
from app.services.anki_content_normalizer import normalize_anki_field_values
from app.services.flashcard_renderer import is_field_empty
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template


def _deck_full_path(deck_obj: Deck | None) -> str:
    """Build canonical hierarchical path like 'English::Luyện Đề::Bài 8' for a Deck."""
    if not deck_obj:
        return ""
    parts = [deck_obj.name]
    current = deck_obj.parent
    seen: set[int] = {deck_obj.id}
    while current is not None and current.id not in seen and len(parts) < 64:
        seen.add(current.id)
        parts.append(current.name)
        current = current.parent
    return "::".join(reversed(parts))


def normalize_compare_text(value: Any) -> str:
    """Normalize text value for whitespace and unicode consistency when comparing diffs."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split()).strip()


def compute_note_content_hash(
    *,
    field_values: dict[str, Any],
    tags: list[str] | None = None,
    deck_id: int | None = None,
) -> str:
    """Compute deterministic SHA-256 hash for note fields and metadata."""
    normalized_fields = {
        str(k).strip(): normalize_compare_text(v)
        for k, v in sorted(field_values.items())
        if str(k).strip()
    }
    normalized_tags = sorted(
        {normalize_compare_text(t) for t in (tags or []) if normalize_compare_text(t)}
    )
    payload = {
        "deck_id": deck_id,
        "fields": normalized_fields,
        "tags": normalized_tags,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _ensure_version_safe_note_tags_mutation(
    *,
    note: Note,
    current_tags: list[str] | None,
    next_tags: list[str] | None,
) -> None:
    current = {normalize_compare_text(tag) for tag in (current_tags or [])}
    incoming = {normalize_compare_text(tag) for tag in (next_tags or [])}
    if current == incoming:
        return
    if not deck_working_tree_service.note_has_shared_release_dependents(note):
        return
    # This service owns the batch transaction. A late tag conflict may follow
    # earlier pending note writes, so fail the whole batch closed.
    db.session.rollback()
    raise RequestValidationError(
        "Tags on a released shared note cannot change until note metadata is versioned.",
        field="tags",
        status=409,
        code="SHARED_NOTE_METADATA_VERSIONING_REQUIRED",
    )


def _ensure_version_safe_note_deck_mutation(
    *,
    note: Note,
    current_deck_id: int | None,
    next_deck_id: int | None,
) -> None:
    if current_deck_id == next_deck_id:
        return
    if not deck_working_tree_service.note_has_shared_release_dependents(note):
        return
    # This service owns the batch transaction. A late membership conflict may
    # follow earlier pending note writes, so fail the whole batch closed.
    db.session.rollback()
    raise RequestValidationError(
        "Released shared notes cannot move between decks; retire the note and add a replacement in a new release.",
        field="deck_id",
        status=409,
        code="SHARED_ENTITY_RETIRE_REQUIRED",
    )


def _resolve_deck_target(
    *,
    user_id: int,
    deck_id: int | None = None,
    deck_path: str | None = None,
    allow_create: bool = False,
) -> Deck:
    """Resolve a target deck by ID or path, with optional path auto-creation."""
    if deck_id is not None:
        deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
        if deck is not None:
            return deck
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )

    if deck_path and str(deck_path).strip():
        cleaned = str(deck_path).strip()
        tokens = [t.strip() for t in cleaned.replace("/", "::").split("::") if t.strip()]
        if not tokens:
            tokens = [cleaned]

        if allow_create:
            upsert_res = vocabulary_repository.upsert_deck_path(
                parent_id=None,
                path_tokens=tokens,
                owner_user_id=user_id,
                admin_mode=False,
            )
            if upsert_res.final_deck is not None:
                return upsert_res.final_deck
        else:
            current_parent_id: int | None = None
            leaf_deck: Deck | None = None
            for token in tokens:
                matched = Deck.query.filter_by(
                    parent_id=current_parent_id,
                    name=token,
                    owner_user_id=user_id,
                    deleted_at=None,
                ).first()
                if matched is None:
                    raise RequestValidationError(
                        f"Deck path '{deck_path}' không tồn tại.",
                        field="deck_path",
                        status=404,
                        code="DECK_NOT_FOUND",
                    )
                leaf_deck = matched
                current_parent_id = matched.id
            if leaf_deck is not None:
                return leaf_deck

    raise RequestValidationError(
        "Cần chỉ định 'deck_id' hoặc 'deck_path'.",
        field="deck_id",
        status=400,
        code="INVALID_PARAMS",
    )


def _resolve_note_type(
    *,
    user_id: int,
    note_type_id: str | None = None,
    note_type_name: str | None = None,
) -> NoteType:
    """Resolve NoteType for the user."""
    query = NoteType.query.filter(
        db.or_(
            NoteType.user_id == user_id,
            NoteType.is_official == True,
            NoteType.publish_status == "published",
        )
    )
    if note_type_id:
        nt = query.filter(NoteType.id == note_type_id).first()
    elif note_type_name:
        nt = query.filter(NoteType.name == note_type_name).first()
    else:
        nt = query.order_by(NoteType.is_official.desc(), NoteType.created_at.asc()).first()

    if nt is None:
        raise RequestValidationError(
            f"Không tìm thấy NoteType ({note_type_id or note_type_name}).",
            field="note_type_id",
            status=404,
            code="NOTE_TYPE_NOT_FOUND",
        )
    return nt


def _validate_and_normalize_note_fields(
    raw_fields: dict[str, Any],
    field_defs: list[FieldDef],
) -> tuple[dict[str, str], list[str]]:
    """Validate required fields and normalize field values according to NoteType definition."""
    errors: list[str] = []
    normalized = normalize_anki_field_values(raw_fields or {}, tuple(field_defs))

    for f_def in field_defs:
        if f_def.required:
            val = normalized.get(f_def.name, "")
            if is_field_empty(val):
                errors.append(f"Trường bắt buộc '{f_def.name}' không được để trống.")

    return normalized, errors


def preview_sync_notes(
    *,
    user_id: int,
    source_key: str | None = None,
    deck_id: int | None = None,
    deck_path: str | None = None,
    note_type_id: str | None = None,
    note_type_name: str | None = None,
    notes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Preview external note synchronization without making any database changes (readOnly)."""
    default_deck: Deck | None = None
    if deck_id is not None or deck_path is not None:
        try:
            default_deck = _resolve_deck_target(
                user_id=user_id,
                deck_id=deck_id,
                deck_path=deck_path,
                allow_create=False,
            )
        except RequestValidationError:
            default_deck = None

    note_type = _resolve_note_type(
        user_id=user_id,
        note_type_id=note_type_id,
        note_type_name=note_type_name,
    )
    if not template_library_repository.card_slots(db.session, note_type.id):
        raise RequestValidationError(
            f"NoteType '{note_type.name}' (ID: {note_type.id}) không có template nào. Một NoteType hợp lệ để tạo thẻ phải có ít nhất một Template.",
            field="note_type_id",
            status=400,
            code="NOTE_TYPE_HAS_NO_TEMPLATE",
        )
    field_defs = sorted(note_type.field_defs, key=lambda f: f.position)
    effective_source_key = (str(source_key).strip() if source_key else "default")

    # Load existing refs for this user and source_key
    external_ids_in_batch = [
        str(n.get("external_id") or "").strip()
        for n in notes
        if str(n.get("external_id") or "").strip()
    ]
    existing_refs_map: dict[str, ConnectSourceNoteRef] = {}
    if external_ids_in_batch:
        refs = ConnectSourceNoteRef.query.filter(
            ConnectSourceNoteRef.user_id == user_id,
            ConnectSourceNoteRef.source_key == effective_source_key,
            ConnectSourceNoteRef.external_note_id.in_(external_ids_in_batch),
        ).all()
        for ref in refs:
            existing_refs_map[ref.external_note_id] = ref

    # Primary identity field fallback
    primary_field = next((f for f in field_defs if f.identity_role == "primary"), None)

    summary = {
        "total": len(notes),
        "create": 0,
        "update": 0,
        "unchanged": 0,
        "invalid": 0,
        "conflicts": 0,
    }
    items_report: list[dict[str, Any]] = []
    seen_external_ids: set[str] = set()

    for idx, item in enumerate(notes):
        raw_external_id = item.get("external_id")
        ext_id = str(raw_external_id).strip() if raw_external_id is not None else None
        item_fields = item.get("fields") or {}
        item_tags = list(item.get("tags") or [])
        item_deck_id = item.get("deck_id")
        item_deck_path = item.get("deck_path")

        # Resolve deck for item
        target_deck = default_deck
        if item_deck_id is not None or item_deck_path is not None:
            try:
                target_deck = _resolve_deck_target(
                    user_id=user_id,
                    deck_id=item_deck_id,
                    deck_path=item_deck_path,
                    allow_create=False,
                )
            except RequestValidationError as exc:
                summary["invalid"] += 1
                items_report.append(
                    {
                        "index": idx,
                        "external_id": ext_id,
                        "action": "invalid",
                        "note_id": None,
                        "deck_id": item_deck_id,
                        "reason": f"Target deck error: {exc.message}",
                        "validation_errors": [exc.message],
                    }
                )
                continue

        target_deck_id_val = target_deck.id if target_deck else (deck_id or None)

        # Validate fields
        normalized_fields, field_errors = _validate_and_normalize_note_fields(item_fields, field_defs)
        if field_errors:
            summary["invalid"] += 1
            items_report.append(
                {
                    "index": idx,
                    "external_id": ext_id,
                    "action": "invalid",
                    "note_id": None,
                    "deck_id": target_deck_id_val,
                    "reason": "Missing or invalid required fields",
                    "validation_errors": field_errors,
                }
            )
            continue

        # Check duplicate external_id inside the current payload
        if ext_id:
            if ext_id in seen_external_ids:
                summary["conflicts"] += 1
                items_report.append(
                    {
                        "index": idx,
                        "external_id": ext_id,
                        "action": "conflict",
                        "note_id": None,
                        "deck_id": target_deck_id_val,
                        "reason": f"Duplicate external_id '{ext_id}' in the same payload",
                        "validation_errors": [f"Trùng lặp external_id '{ext_id}' trong cùng yêu cầu sync."],
                    }
                )
                continue
            seen_external_ids.add(ext_id)

        # Lookup existing note via ref or primary identity
        existing_ref = existing_refs_map.get(ext_id) if ext_id else None
        existing_note: Note | None = None
        if existing_ref and existing_ref.note:
            existing_note = existing_ref.note
            if str(existing_note.note_type_id) != str(note_type.id):
                summary["conflicts"] += 1
                items_report.append(
                    {
                        "index": idx,
                        "external_id": ext_id,
                        "action": "conflict",
                        "note_id": str(existing_note.id),
                        "deck_id": target_deck_id_val,
                        "reason": f"NoteType mismatch: existing note #{existing_note.id} uses NoteType '{existing_note.note_type_id}', but sync requested NoteType '{note_type.id}'. NoteType migration during sync is not supported.",
                        "validation_errors": [
                            f"NoteType không khớp: Note #{existing_note.id} đang dùng NoteType '{existing_note.note_type_id}', không thể sync dưới NoteType '{note_type.id}'."
                        ],
                    }
                )
                continue
        elif not ext_id and primary_field and target_deck_id_val:
            primary_val = normalize_compare_text(normalized_fields.get(primary_field.name))
            if primary_val:
                candidate_notes = Note.query.filter_by(
                    user_id=user_id,
                    deck_id=target_deck_id_val,
                    note_type_id=note_type.id,
                ).all()
                for cn in candidate_notes:
                    c_val = normalize_compare_text((cn.field_values or {}).get(primary_field.name))
                    if c_val == primary_val:
                        existing_note = cn
                        break

        if existing_note is None:
            # Action: CREATE
            summary["create"] += 1
            items_report.append(
                {
                    "index": idx,
                    "external_id": ext_id,
                    "action": "create",
                    "note_id": None,
                    "deck_id": target_deck_id_val,
                    "reason": "New external record to be created",
                    "validation_errors": [],
                }
            )
        else:
            # Check diff
            cur_fields = dict(existing_note.field_values or {})
            cur_tags = list(existing_note.tags or [])
            cur_deck_id = existing_note.deck_id

            changed_fields: list[str] = []
            for f_def in field_defs:
                new_v = normalized_fields.get(f_def.name, "")
                old_v = cur_fields.get(f_def.name, "")
                if normalize_compare_text(new_v) != normalize_compare_text(old_v):
                    changed_fields.append(f_def.name)

            tags_changed = set(normalize_compare_text(t) for t in item_tags) != set(
                normalize_compare_text(t) for t in cur_tags
            )
            deck_changed = (target_deck_id_val is not None and cur_deck_id != target_deck_id_val)

            if changed_fields or tags_changed or deck_changed:
                summary["update"] += 1
                items_report.append(
                    {
                        "index": idx,
                        "external_id": ext_id,
                        "action": "update",
                        "note_id": str(existing_note.id),
                        "deck_id": target_deck_id_val,
                        "reason": "Record exists but content or metadata changed",
                        "changed_fields": changed_fields,
                        "tags_changed": tags_changed,
                        "deck_changed": deck_changed,
                        "validation_errors": [],
                    }
                )
            else:
                summary["unchanged"] += 1
                items_report.append(
                    {
                        "index": idx,
                        "external_id": ext_id,
                        "action": "unchanged",
                        "note_id": str(existing_note.id),
                        "deck_id": cur_deck_id,
                        "reason": "Record content identical to existing note",
                        "validation_errors": [],
                    }
                )

    return {
        "source_key": effective_source_key,
        "note_type_id": str(note_type.id),
        "note_type_name": note_type.name,
        "summary": summary,
        "items": items_report,
    }


def execute_sync_notes(
    *,
    user_id: int,
    source_key: str | None = None,
    deck_id: int | None = None,
    deck_path: str | None = None,
    note_type_id: str | None = None,
    note_type_name: str | None = None,
    notes: list[dict[str, Any]],
    stop_on_error: bool = False,
    ensure_decks: bool = True,
) -> dict[str, Any]:
    """Execute idempotent external note synchronization (create/update/skip)."""
    default_deck: Deck | None = None
    if deck_id is not None or deck_path is not None:
        default_deck = _resolve_deck_target(
            user_id=user_id,
            deck_id=deck_id,
            deck_path=deck_path,
            allow_create=ensure_decks,
        )

    note_type = _resolve_note_type(
        user_id=user_id,
        note_type_id=note_type_id,
        note_type_name=note_type_name,
    )
    field_defs = sorted(note_type.field_defs, key=lambda f: f.position)
    # Cards are derived from active occurrences, including reusable/received
    # templates (ADR P11); a NoteType without one would present no Card.
    if not template_library_repository.card_slots(db.session, note_type.id):
        raise RequestValidationError(
            f"NoteType '{note_type.name}' (ID: {note_type.id}) không có template nào. Một NoteType hợp lệ để tạo thẻ phải có ít nhất một Template.",
            field="note_type_id",
            status=400,
            code="NOTE_TYPE_HAS_NO_TEMPLATE",
        )

    effective_source_key = (str(source_key).strip() if source_key else "default")

    # Load existing refs
    external_ids_in_batch = [
        str(n.get("external_id") or "").strip()
        for n in notes
        if str(n.get("external_id") or "").strip()
    ]
    existing_refs_map: dict[str, ConnectSourceNoteRef] = {}
    if external_ids_in_batch:
        refs = ConnectSourceNoteRef.query.filter(
            ConnectSourceNoteRef.user_id == user_id,
            ConnectSourceNoteRef.source_key == effective_source_key,
            ConnectSourceNoteRef.external_note_id.in_(external_ids_in_batch),
        ).all()
        for ref in refs:
            existing_refs_map[ref.external_note_id] = ref

    primary_field = next((f for f in field_defs if f.identity_role == "primary"), None)

    summary = {
        "total": len(notes),
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "failed": 0,
    }
    created_note_ids: list[str] = []
    updated_note_ids: list[str] = []
    unchanged_note_ids: list[str] = []
    failed_items: list[dict[str, Any]] = []
    seen_external_ids: set[str] = set()
    dirty_mutations: list[dict[str, Any]] = []

    for idx, item in enumerate(notes):
        raw_external_id = item.get("external_id")
        ext_id = str(raw_external_id).strip() if raw_external_id is not None else None
        item_fields = item.get("fields") or {}
        item_tags = [str(t).strip() for t in (item.get("tags") or []) if str(t).strip()]
        item_deck_id = item.get("deck_id")
        item_deck_path = item.get("deck_path")

        # Resolve deck for item
        target_deck = default_deck
        if item_deck_id is not None or item_deck_path is not None:
            try:
                target_deck = _resolve_deck_target(
                    user_id=user_id,
                    deck_id=item_deck_id,
                    deck_path=item_deck_path,
                    allow_create=ensure_decks,
                )
            except RequestValidationError as exc:
                summary["failed"] += 1
                err_detail = {"index": idx, "external_id": ext_id, "error": f"Target deck error: {exc.message}"}
                failed_items.append(err_detail)
                if stop_on_error:
                    db.session.rollback()
                    raise RequestValidationError(f"Lỗi ở item #{idx}: {exc.message}", status=400)
                continue

        if target_deck is None:
            summary["failed"] += 1
            err_detail = {"index": idx, "external_id": ext_id, "error": "Chưa chỉ định target deck."}
            failed_items.append(err_detail)
            if stop_on_error:
                db.session.rollback()
                raise RequestValidationError(f"Lỗi ở item #{idx}: Chưa chỉ định target deck.", status=400)
            continue

        target_deck_id_val = target_deck.id

        # Validate fields
        normalized_fields, field_errors = _validate_and_normalize_note_fields(item_fields, field_defs)
        if field_errors:
            summary["failed"] += 1
            err_detail = {"index": idx, "external_id": ext_id, "error": "; ".join(field_errors)}
            failed_items.append(err_detail)
            if stop_on_error:
                db.session.rollback()
                raise RequestValidationError(f"Lỗi ở item #{idx}: {'; '.join(field_errors)}", status=400)
            continue

        # Duplicate external_id in payload check
        if ext_id:
            if ext_id in seen_external_ids:
                summary["failed"] += 1
                err_detail = {"index": idx, "external_id": ext_id, "error": f"Duplicate external_id '{ext_id}' in batch."}
                failed_items.append(err_detail)
                if stop_on_error:
                    db.session.rollback()
                    raise RequestValidationError(f"Lỗi ở item #{idx}: Trùng lặp external_id '{ext_id}'.", status=400)
                continue
            seen_external_ids.add(ext_id)

        # Lookup existing note
        existing_ref = existing_refs_map.get(ext_id) if ext_id else None
        existing_note: Note | None = None
        if existing_ref and existing_ref.note:
            existing_note = existing_ref.note
            if str(existing_note.note_type_id) != str(note_type.id):
                summary["failed"] += 1
                err_detail = {
                    "index": idx,
                    "external_id": ext_id,
                    "error": f"NoteType mismatch: existing note #{existing_note.id} uses NoteType '{existing_note.note_type_id}', but sync requested NoteType '{note_type.id}'. NoteType migration during sync is not supported.",
                    "code": "NOTE_TYPE_MISMATCH",
                }
                failed_items.append(err_detail)
                if stop_on_error:
                    db.session.rollback()
                    raise RequestValidationError(
                        f"Lỗi ở item #{idx}: Note #{existing_note.id} đang dùng NoteType '{existing_note.note_type_id}', không thể đồng bộ dưới NoteType '{note_type.id}'.",
                        status=409,
                        code="NOTE_TYPE_MISMATCH",
                    )
                continue
        elif not ext_id and primary_field:
            primary_val = normalize_compare_text(normalized_fields.get(primary_field.name))
            if primary_val:
                candidate_notes = Note.query.filter_by(
                    user_id=user_id,
                    deck_id=target_deck_id_val,
                    note_type_id=note_type.id,
                ).all()
                for cn in candidate_notes:
                    c_val = normalize_compare_text((cn.field_values or {}).get(primary_field.name))
                    if c_val == primary_val:
                        existing_note = cn
                        break

        deck_path_label = _deck_full_path(target_deck)
        content_hash = compute_note_content_hash(
            field_values=normalized_fields,
            tags=item_tags,
            deck_id=target_deck_id_val,
        )

        if existing_note is None:
            # 1. CREATE NOTE
            new_note = Note(
                note_type_id=note_type.id,
                user_id=user_id,
                deck_id=target_deck_id_val,
                field_values=normalized_fields,
                tags=item_tags,
            )
            db.session.add(new_note)
            db.session.flush()
            dirty_mutations.append(
                {
                    "note": new_note,
                    "field_names": set(normalized_fields) | {
                        str(field_def.name)
                        for field_def in field_defs
                        if str(field_def.name or "").strip()
                    },
                    "operation": "add",
                }
            )

            # Create ConnectSourceNoteRef if ext_id present
            if ext_id:
                new_ref = ConnectSourceNoteRef(
                    user_id=user_id,
                    source_key=effective_source_key,
                    external_note_id=ext_id,
                    source_model_id=str(note_type.id),
                    source_deck_path=deck_path_label,
                    note_id=new_note.id,
                    content_hash=content_hash,
                )
                db.session.add(new_ref)
                existing_refs_map[ext_id] = new_ref

            created_note_ids.append(str(new_note.id))
            summary["created"] += 1

        else:
            # 2. UPDATE OR UNCHANGED
            cur_fields = dict(existing_note.field_values or {})
            cur_tags = list(existing_note.tags or [])
            cur_deck_id = existing_note.deck_id

            changed_fields: list[str] = []
            for f_def in field_defs:
                new_v = normalized_fields.get(f_def.name, "")
                old_v = cur_fields.get(f_def.name, "")
                if normalize_compare_text(new_v) != normalize_compare_text(old_v):
                    changed_fields.append(f_def.name)

            tags_changed = set(normalize_compare_text(t) for t in item_tags) != set(
                normalize_compare_text(t) for t in cur_tags
            )
            deck_changed = (cur_deck_id != target_deck_id_val)

            if changed_fields or tags_changed or deck_changed:
                if deck_changed:
                    _ensure_version_safe_note_deck_mutation(
                        note=existing_note,
                        current_deck_id=cur_deck_id,
                        next_deck_id=target_deck_id_val,
                    )
                if tags_changed:
                    _ensure_version_safe_note_tags_mutation(
                        note=existing_note,
                        current_tags=cur_tags,
                        next_tags=item_tags,
                    )
                existing_note.field_values = normalized_fields
                existing_note.tags = item_tags
                existing_note.deck_id = target_deck_id_val
                existing_note.updated_at = datetime.utcnow()

                if deck_changed:
                    all_field_names = {
                        str(field_def.name)
                        for field_def in field_defs
                        if str(field_def.name or "").strip()
                    } | set(cur_fields) | set(normalized_fields)
                    dirty_mutations.extend(
                        [
                            {
                                "note": existing_note,
                                "field_names": all_field_names,
                                "operation": "remove",
                                "deck_id": cur_deck_id,
                            },
                            {
                                "note": existing_note,
                                "field_names": all_field_names,
                                "operation": "add",
                                "deck_id": target_deck_id_val,
                            },
                        ]
                    )
                elif changed_fields:
                    dirty_mutations.append(
                        {
                            "note": existing_note,
                            "field_names": set(changed_fields),
                            "operation": "set",
                        }
                    )

                if existing_ref:
                    existing_ref.content_hash = content_hash
                    existing_ref.source_deck_path = deck_path_label
                    existing_ref.updated_at = datetime.utcnow()
                elif ext_id:
                    new_ref = ConnectSourceNoteRef(
                        user_id=user_id,
                        source_key=effective_source_key,
                        external_note_id=ext_id,
                        source_model_id=str(note_type.id),
                        source_deck_path=deck_path_label,
                        note_id=existing_note.id,
                        content_hash=content_hash,
                    )
                    db.session.add(new_ref)
                    existing_refs_map[ext_id] = new_ref

                updated_note_ids.append(str(existing_note.id))
                summary["updated"] += 1
            else:
                unchanged_note_ids.append(str(existing_note.id))
                summary["unchanged"] += 1

    deck_working_tree_service.mark_note_field_batches_changed(
        mutations=dirty_mutations,
    )
    db.session.commit()

    return {
        "success": summary["failed"] == 0 or (not stop_on_error and (summary["created"] + summary["updated"] + summary["unchanged"] > 0)),
        "source_key": effective_source_key,
        "note_type_id": str(note_type.id),
        "note_type_name": note_type.name,
        "summary": summary,
        "created_note_ids": created_note_ids,
        "updated_note_ids": updated_note_ids,
        "unchanged_note_ids": unchanged_note_ids,
        "failed_items": failed_items,
    }
