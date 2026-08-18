"""Application service for flashcard import REST resources."""

from __future__ import annotations

from typing import Any

from app.repositories import flashcards_import_repository
from app.services import flashcards_share_service
from app.services.flashcard_import import (
    ImportValidationError,
    create_import_session,
    resolve_delimiter,
    run_import,
    suggest_mapping,
)
from models import db
from models.audit_log import AuditLog
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall


class ImportApiError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        status: int = 400,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.status = int(status)


def build_import_options(
    *,
    user_id: int,
    admin_mode: bool,
    deck_id_raw: object = None,
    note_type_id_raw: object = None,
) -> dict[str, Any]:
    decks = flashcards_import_repository.collect_accessible_decks_for_import(
        user_id=user_id,
        admin_mode=admin_mode,
    )
    deck_map = {deck.id: deck for deck in decks}
    from models.note import Note
    notes_count_by_deck = dict(
        db.session.query(Note.deck_id, db.func.count(Note.id))
        .filter(Note.deck_id.in_([d.id for d in decks]))
        .group_by(Note.deck_id)
        .all()
    )
    deck_options = [
        {
            "id": deck.id,
            "name": deck.name,
            "path": flashcards_import_repository.deck_path_label(deck, deck_map),
            "note_type_id": deck.note_type_id,
            "parent_id": deck.parent_id,
            "notes_count": notes_count_by_deck.get(deck.id, 0),
        }
        for deck in decks
    ]
    selected_deck_id = None
    if str(deck_id_raw or "").strip():
        try:
            candidate = int(str(deck_id_raw).strip())
            if candidate in deck_map:
                selected_deck_id = candidate
        except (TypeError, ValueError):
            selected_deck_id = None
    if selected_deck_id is None and deck_options:
        selected_deck_id = int(deck_options[0]["id"])

    installed_ids = [
        r[0]
        for r in db.session.query(NoteTypeInstall.installed_note_type_id)
        .filter_by(user_id=user_id)
        .all()
        if r[0]
    ]
    note_types = (
        NoteType.query.filter(
            (NoteType.user_id == user_id)
            | (NoteType.id.in_(installed_ids))
        )
        .order_by(NoteType.name.asc(), NoteType.updated_at.desc())
        .all()
    )
    note_type_options = [
        flashcards_import_repository.serialize_note_type_for_import(note_type)
        for note_type in note_types
    ]
    note_type_map = {item["id"]: item for item in note_type_options}
    selected_note_type_id = str(note_type_id_raw or "").strip() or None
    if selected_note_type_id not in note_type_map:
        selected_note_type_id = None
    if selected_note_type_id is None and selected_deck_id is not None:
        inferred = flashcards_import_repository.infer_default_note_type_id_for_deck(
            deck_id=selected_deck_id,
            user_id=user_id,
        )
        if inferred in note_type_map:
            selected_note_type_id = inferred
    if selected_note_type_id is None and note_type_options:
        selected_note_type_id = note_type_options[0]["id"]
    return {
        "deck_options": deck_options,
        "decks": deck_options,
        "note_type_options": note_type_options,
        "note_types": note_type_options,
        "initial_deck_id": selected_deck_id,
        "initial_note_type_id": selected_note_type_id,
        "uniqueness_defaults": {
            note_type.id: flashcards_import_repository.default_uniqueness_fields(
                note_type
            )
            for note_type in note_types
        },
    }


def parse_import_file(
    *,
    user_id: int,
    note_type_id: str,
    filename: str,
    file_bytes: bytes,
    delimiter_mode: str,
    custom_delimiter: str | None,
    has_header: bool,
) -> dict[str, Any]:
    note_type = NoteType.query.filter_by(
        id=note_type_id,
        user_id=user_id,
    ).first()
    if note_type is None:
        raise ImportApiError(
            "Note type not found.",
            field="note_type_id",
            status=404,
        )
    if not filename:
        raise ImportApiError("Import file is required.", field="file")
    try:
        delimiter = resolve_delimiter(delimiter_mode, custom_delimiter)
        summary = create_import_session(
            user_id=user_id,
            filename=filename,
            file_bytes=file_bytes,
            delimiter=delimiter,
            has_header=has_header,
            field_count=len(note_type.field_defs),
        )
    except ImportValidationError as exc:
        raise ImportApiError(str(exc)) from exc
    return {
        "token": summary.get("token"),
        "delimiter": summary.get("delimiter") or delimiter,
        "has_header": bool(summary.get("has_header")),
        "columns": summary.get("columns") or [],
        "column_count": int(summary.get("column_count") or 0),
        "total_rows": int(summary.get("total_rows") or 0),
        "preview_rows": summary.get("preview_rows") or [],
        "warnings": summary.get("warnings") or [],
        "suggested_mapping": suggest_mapping(
            field_defs=note_type.field_defs,
            has_header=has_header,
            header=summary.get("header") or [],
            column_count=int(summary.get("column_count") or 0),
        ),
    }


def run_import_request(
    *,
    user_id: int,
    admin_mode: bool,
    payload: dict[str, Any],
    apply_changes: bool,
) -> dict[str, Any]:
    try:
        session_meta, note_type, target_deck_id = (
            flashcards_import_repository.resolve_import_execution_payload(
                payload=payload,
                user_id=user_id,
                admin_mode=admin_mode,
            )
        )
        report = run_import(
            user_id=user_id,
            session_meta=session_meta,
            note_type=note_type,
            target_deck_id=target_deck_id,
            mode=(payload.get("import_mode") or "upsert"),
            uniqueness_fields=payload.get("uniqueness_fields") or [],
            raw_mapping=(
                payload.get("mapping")
                if isinstance(payload.get("mapping"), dict)
                else {}
            ),
            dont_overwrite_empty=_to_bool(
                payload.get("dont_overwrite_empty"),
                default=True,
            ),
            confirm_column_mismatch=_to_bool(
                payload.get("confirm_column_mismatch"),
                default=False,
            ),
            apply_changes=apply_changes,
            chunk_size=payload.get("chunk_size"),
        )
    except ImportValidationError as exc:
        raise ImportApiError(str(exc)) from exc
    if not apply_changes:
        return report

    summary = report.get("summary") or {}
    if int(summary.get("inserted") or 0) > 0 or int(summary.get("updated") or 0) > 0:
        flashcards_share_service.touch_note_type_install_usage(
            user_id=user_id,
            installed_note_type_id=note_type.id,
        )
        for install in NoteTypeInstall.query.filter_by(
            user_id=user_id,
            installed_note_type_id=note_type.id,
        ).all():
            source = db.session.get(NoteType, install.source_note_type_id)
            if source:
                flashcards_share_service.recompute_note_type_market_stats(
                    source,
                    note_type_active_note_threshold=3,
                    note_type_active_review_threshold=3,
                    note_type_active_days_threshold=3,
                )
    db.session.add(
        AuditLog(
            user_id=user_id,
            action="note.import",
            payload={
                "note_type_id": note_type.id,
                "target_deck_id": target_deck_id,
                "mode": report.get("mode"),
                "summary": summary,
            },
        )
    )
    db.session.commit()
    return report


def parse_batch_import_files(
    *,
    user_id: int,
    admin_mode: bool,
    parent_deck_id_raw: object,
    note_type_id: str,
    files: list[tuple[str, bytes]],
    delimiter_mode: str,
    custom_delimiter: str | None,
    has_header: bool,
    naming_mode: str = "auto",
    custom_pattern: str | None = None,
) -> dict[str, Any]:
    """Parses multiple uploaded files and prepares a batch import session."""
    if not files:
        raise ImportApiError("At least one file is required.", field="files")

    parent_deck_id = None
    if parent_deck_id_raw is not None and str(parent_deck_id_raw).strip() not in {"", "null", "undefined", "0"}:
        try:
            parent_deck_id = int(str(parent_deck_id_raw).strip())
        except (TypeError, ValueError):
            parent_deck_id = None

    if parent_deck_id is not None:
        accessible_decks = flashcards_import_repository.collect_accessible_decks_for_import(
            user_id=user_id,
            admin_mode=admin_mode,
        )
        accessible_deck_ids = {deck.id for deck in accessible_decks}
        if parent_deck_id not in accessible_deck_ids:
            raise ImportApiError(
                "Parent deck is not accessible.", field="parent_deck_id", status=404
            )

    note_type = NoteType.query.filter_by(
        id=note_type_id,
        user_id=user_id,
    ).first()
    if note_type is None:
        installed = db.session.query(NoteTypeInstall).filter_by(
            user_id=user_id,
            installed_note_type_id=note_type_id,
        ).first()
        if installed:
            note_type = NoteType.query.get(note_type_id)
        if note_type is None:
            raise ImportApiError("Note type not found.", field="note_type_id", status=404)

    from models.deck import Deck
    child_decks = []
    if parent_deck_id is not None:
        child_decks = (
            Deck.query.filter_by(
                parent_id=parent_deck_id,
                deleted_at=None,
            )
            .order_by(Deck.position.asc(), Deck.id.asc())
            .all()
        )

    uniqueness_fields = flashcards_import_repository.default_uniqueness_fields(note_type)

    from app.services.flashcard_import import create_batch_import_session
    try:
        summary = create_batch_import_session(
            user_id=user_id,
            files=files,
            parent_deck_id=parent_deck_id,
            note_type=note_type,
            child_decks=child_decks,
            delimiter_mode=delimiter_mode,
            custom_delimiter=custom_delimiter,
            has_header=has_header,
            uniqueness_fields=uniqueness_fields,
            naming_mode=naming_mode,
            custom_pattern=custom_pattern,
        )
    except ImportValidationError as exc:
        raise ImportApiError(str(exc)) from exc

    return summary


def run_batch_import_request(
    *,
    user_id: int,
    admin_mode: bool,
    payload: dict[str, Any],
    apply_changes: bool,
) -> dict[str, Any]:
    """Estimates or executes multi-file batch flashcard import."""
    from app.services.flashcard_import import (
        load_batch_import_session,
        run_batch_import,
    )

    token = str(payload.get("token") or "").strip()
    if not token:
        raise ImportApiError("Import token is required.", field="token")

    try:
        session_meta = load_batch_import_session(user_id=user_id, token=token)
    except ImportValidationError as exc:
        raise ImportApiError(str(exc)) from exc

    note_type_id = str(
        payload.get("note_type_id") or session_meta.get("note_type_id") or ""
    ).strip()
    note_type = NoteType.query.filter_by(id=note_type_id, user_id=user_id).first()
    if note_type is None:
        installed = db.session.query(NoteTypeInstall).filter_by(
            user_id=user_id,
            installed_note_type_id=note_type_id,
        ).first()
        if installed:
            note_type = NoteType.query.get(note_type_id)
        if note_type is None:
            raise ImportApiError("Note type not found", field="note_type_id", status=404)

    parent_deck_raw = payload.get("parent_deck_id") or session_meta.get("parent_deck_id")
    parent_deck_id = None
    if parent_deck_raw is not None and str(parent_deck_raw).strip() not in {"", "null", "undefined", "0"}:
        try:
            parent_deck_id = int(str(parent_deck_raw).strip())
        except (TypeError, ValueError):
            parent_deck_id = None

    if parent_deck_id is not None:
        accessible_decks = flashcards_import_repository.collect_accessible_decks_for_import(
            user_id=user_id,
            admin_mode=admin_mode,
        )
        accessible_deck_ids = {deck.id for deck in accessible_decks}
        if parent_deck_id not in accessible_deck_ids:
            raise ImportApiError("Parent deck is not accessible", field="parent_deck_id", status=404)

    file_configs = payload.get("file_configs")
    if not isinstance(file_configs, list) or not file_configs:
        file_configs = [
            {
                "file_id": f["file_id"],
                "target_deck_name": f.get("suggested_deck_name"),
                "action": f.get("collision", {}).get("suggested_action", "create_new"),
                "target_deck_id": f.get("collision", {}).get("existing_deck_id"),
            }
            for f in session_meta.get("files", [])
        ]

    uniqueness_fields = (
        payload.get("uniqueness_fields")
        or session_meta.get("uniqueness_fields")
        or flashcards_import_repository.default_uniqueness_fields(note_type)
    )

    try:
        report = run_batch_import(
            user_id=user_id,
            batch_session_meta=session_meta,
            note_type=note_type,
            parent_deck_id=parent_deck_id,
            file_configs=file_configs,
            import_mode=payload.get("import_mode") or "upsert",
            uniqueness_fields=uniqueness_fields,
            mapping=(
                payload.get("mapping")
                if isinstance(payload.get("mapping"), dict)
                else session_meta.get("global_mapping", {})
            ),
            dont_overwrite_empty=_to_bool(
                payload.get("dont_overwrite_empty"), default=True
            ),
            confirm_column_mismatch=_to_bool(
                payload.get("confirm_column_mismatch"), default=True
            ),
            apply_changes=apply_changes,
        )
    except ImportValidationError as exc:
        raise ImportApiError(str(exc)) from exc


    if not apply_changes:
        return report

    s = report.get("overall_summary", {})
    if int(s.get("inserted") or 0) > 0 or int(s.get("updated") or 0) > 0:
        flashcards_share_service.touch_note_type_install_usage(
            user_id=user_id,
            installed_note_type_id=note_type.id,
        )

    db.session.add(
        AuditLog(
            user_id=user_id,
            action="note.batch_import",
            payload={
                "note_type_id": note_type.id,
                "parent_deck_id": parent_deck_id,
                "mode": report.get("mode"),
                "summary": s,
            },
        )
    )
    db.session.commit()
    return report


def _to_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

