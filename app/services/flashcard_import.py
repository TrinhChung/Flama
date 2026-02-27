"""Flashcard bulk import helpers (CSV/TSV/custom delimiter)."""

from __future__ import annotations

import csv
import json
import re
import tempfile
from datetime import datetime, timedelta
from io import TextIOWrapper
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.flashcard_renderer import is_field_empty
from models import db
from models.flashcard import Card, Note, Template

IMPORT_MAX_FILE_BYTES = 50 * 1024 * 1024
IMPORT_PREVIEW_ROWS = 4
IMPORT_DEFAULT_CHUNK_SIZE = 1000
IMPORT_MAX_ISSUES = 300
IMPORT_TMP_ROOT = Path(tempfile.gettempdir()) / "flama_flashcard_import"
IMPORT_TOKEN_REGEX = re.compile(r"^[a-f0-9-]{8,64}$")
_WHITESPACE_RE = re.compile(r"\s+")


class ImportValidationError(ValueError):
    """Raised when import payload or mapping is invalid."""


def _session_root(user_id: int, token: str) -> Path:
    return IMPORT_TMP_ROOT / str(int(user_id)) / token


def _session_meta_path(user_id: int, token: str) -> Path:
    return _session_root(user_id, token) / "meta.json"


def _session_data_path(user_id: int, token: str) -> Path:
    return _session_root(user_id, token) / "data.bin"


def resolve_delimiter(mode: str | None, custom_delimiter: str | None) -> str:
    normalized = (mode or "csv").strip().lower()
    if normalized == "csv":
        return ","
    if normalized == "tsv":
        return "\t"
    if normalized != "custom":
        raise ImportValidationError("delimiter_mode must be one of: csv, tsv, custom")

    delimiter = "" if custom_delimiter is None else str(custom_delimiter)
    if len(delimiter) != 1:
        raise ImportValidationError("custom_delimiter must contain exactly one character")
    return delimiter


def create_import_session(
    *,
    user_id: int,
    filename: str,
    file_bytes: bytes,
    delimiter: str,
    has_header: bool,
    field_count: int,
) -> dict[str, Any]:
    if not file_bytes:
        raise ImportValidationError("Uploaded file is empty")
    if len(file_bytes) > IMPORT_MAX_FILE_BYTES:
        raise ImportValidationError(f"Uploaded file exceeds {IMPORT_MAX_FILE_BYTES} bytes")

    token = str(uuid4())
    root = _session_root(user_id, token)
    root.mkdir(parents=True, exist_ok=True)

    data_path = _session_data_path(user_id, token)
    data_path.write_bytes(file_bytes)

    summary = scan_import_session(
        user_id=user_id,
        token=token,
        delimiter=delimiter,
        has_header=has_header,
        field_count=field_count,
    )

    meta_payload = {
        "token": token,
        "user_id": int(user_id),
        "filename": filename,
        "file_size": len(file_bytes),
        "delimiter": delimiter,
        "has_header": bool(has_header),
        "created_at": datetime.utcnow().isoformat(),
        "column_count": int(summary.get("column_count") or 0),
        "max_columns": int(summary.get("max_columns") or 0),
        "header": summary.get("header") or [],
        "total_rows": int(summary.get("total_rows") or 0),
    }
    _session_meta_path(user_id, token).write_text(
        json.dumps(meta_payload, ensure_ascii=True),
        encoding="utf-8",
    )

    # Best-effort cleanup for stale sessions.
    cleanup_expired_sessions(user_id=user_id)
    return summary


def cleanup_expired_sessions(*, user_id: int, older_than_hours: int = 24) -> None:
    user_root = IMPORT_TMP_ROOT / str(int(user_id))
    if not user_root.exists():
        return

    threshold = datetime.utcnow() - timedelta(hours=max(1, older_than_hours))
    for child in user_root.iterdir():
        if not child.is_dir():
            continue
        try:
            mtime = datetime.utcfromtimestamp(child.stat().st_mtime)
        except OSError:
            continue
        if mtime >= threshold:
            continue
        _safe_rmtree(child)


def _safe_rmtree(path: Path) -> None:
    if not path.exists():
        return
    for item in sorted(path.rglob("*"), reverse=True):
        try:
            if item.is_file() or item.is_symlink():
                item.unlink(missing_ok=True)
            elif item.is_dir():
                item.rmdir()
        except OSError:
            continue
    try:
        path.rmdir()
    except OSError:
        pass


def load_import_session(*, user_id: int, token: str) -> dict[str, Any]:
    normalized = (token or "").strip().lower()
    if not IMPORT_TOKEN_REGEX.match(normalized):
        raise ImportValidationError("Invalid import token")

    meta_path = _session_meta_path(user_id, normalized)
    data_path = _session_data_path(user_id, normalized)
    if not meta_path.exists() or not data_path.exists():
        raise ImportValidationError("Import token not found or expired")

    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ImportValidationError("Import metadata is corrupted") from exc

    payload["token"] = normalized
    payload["data_path"] = str(data_path)
    return payload


def scan_import_session(
    *,
    user_id: int,
    token: str,
    delimiter: str,
    has_header: bool,
    field_count: int,
) -> dict[str, Any]:
    data_path = _session_data_path(user_id, token)
    if not data_path.exists():
        raise ImportValidationError("Uploaded file was not found")

    header: list[str] = []
    preview_rows: list[list[str]] = []
    total_rows = 0
    max_columns = 0
    first_data_columns = 0

    try:
        with data_path.open("rb") as raw_file:
            text_file = TextIOWrapper(raw_file, encoding="utf-8-sig", newline="")
            reader = csv.reader(text_file, delimiter=delimiter)
            for row_index, row in enumerate(reader, start=1):
                row_values = ["" if value is None else str(value) for value in row]
                max_columns = max(max_columns, len(row_values))

                if row_index == 1 and has_header:
                    header = row_values
                    continue

                total_rows += 1
                if first_data_columns == 0:
                    first_data_columns = len(row_values)
                if len(preview_rows) < IMPORT_PREVIEW_ROWS:
                    preview_rows.append(row_values)
    except csv.Error as exc:
        raise ImportValidationError(f"Failed to parse delimited file: {exc}") from exc

    column_count = len(header) if has_header and header else first_data_columns
    warnings: list[dict[str, str]] = []

    if column_count < field_count:
        warnings.append(
            {
                "code": "COLUMN_COUNT_SHORT",
                "severity": "danger",
                "message": (
                    f"Detected {column_count} column(s), but note type has {field_count} field(s). "
                    "Some mapped fields may be missing."
                ),
            }
        )
    elif column_count > field_count:
        warnings.append(
            {
                "code": "COLUMN_COUNT_LONG",
                "severity": "warning",
                "message": (
                    f"Detected {column_count} column(s), but note type has {field_count} field(s). "
                    "Extra columns should be ignored or explicitly mapped."
                ),
            }
        )

    columns: list[dict[str, Any]] = []
    for idx in range(max(column_count, max_columns)):
        header_name = ""
        if idx < len(header):
            header_name = (header[idx] or "").strip()
        display = header_name or f"Column {idx + 1}"
        columns.append(
            {
                "index": idx,
                "name": header_name,
                "display": display,
            }
        )

    return {
        "token": token,
        "delimiter": delimiter,
        "has_header": bool(has_header),
        "header": header,
        "columns": columns,
        "column_count": column_count,
        "max_columns": max_columns,
        "total_rows": total_rows,
        "preview_rows": preview_rows,
        "warnings": warnings,
    }


def suggest_mapping(
    *,
    field_defs: list[Any],
    has_header: bool,
    header: list[str],
    column_count: int,
) -> dict[str, dict[str, Any]]:
    suggestions: dict[str, dict[str, Any]] = {}
    header_map: dict[str, int] = {}

    if has_header:
        for index, raw_name in enumerate(header):
            normalized = _normalize_name(raw_name)
            if normalized and normalized not in header_map:
                header_map[normalized] = index

    for position, field_def in enumerate(sorted(field_defs, key=lambda item: item.position)):
        field_name = field_def.name
        mapped_index: int | None = None

        if has_header:
            mapped_index = header_map.get(_normalize_name(field_name))
        if mapped_index is None and position < column_count:
            mapped_index = position

        if mapped_index is None:
            suggestions[field_name] = {
                "source_type": "ignore",
                "column_index": None,
                "constant_value": "",
            }
            continue

        suggestions[field_name] = {
            "source_type": "column",
            "column_index": int(mapped_index),
            "constant_value": "",
        }

    return suggestions


def _normalize_name(value: str | None) -> str:
    text = "" if value is None else str(value)
    return _WHITESPACE_RE.sub("", text.strip().lower().replace("_", "").replace("-", ""))


def _normalize_compare_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    return text


def _normalize_key_value(value: Any) -> str:
    text = _normalize_compare_value(value)
    if not text:
        return ""
    text = _WHITESPACE_RE.sub(" ", text)
    return text


def _build_compound_key(values: dict[str, Any], uniqueness_fields: list[str]) -> str | None:
    parts: list[str] = []
    for field_name in uniqueness_fields:
        normalized = _normalize_key_value(values.get(field_name, ""))
        if not normalized:
            return None
        parts.append(normalized)
    return "\u001f".join(parts)


def _normalize_mapping(
    *,
    field_defs: list[Any],
    raw_mapping: dict[str, Any] | None,
    column_count: int,
    uniqueness_fields: list[str],
) -> tuple[dict[str, dict[str, Any]], list[str], list[dict[str, str]]]:
    mapping = raw_mapping or {}
    normalized: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    warnings: list[dict[str, str]] = []

    used_columns: dict[int, list[str]] = {}
    field_by_name = {field.name: field for field in field_defs}

    for field_def in sorted(field_defs, key=lambda item: item.position):
        field_name = field_def.name
        row = mapping.get(field_name)
        if not isinstance(row, dict):
            row = {}

        source_type = str(row.get("source_type") or row.get("type") or "ignore").strip().lower()
        if source_type not in {"column", "ignore", "constant"}:
            errors.append(f"Invalid source_type for field '{field_name}'")
            source_type = "ignore"

        column_index: int | None = None
        constant_value = ""

        if source_type == "column":
            raw_index = row.get("column_index")
            try:
                column_index = int(raw_index)
            except (TypeError, ValueError):
                errors.append(f"Column index is required for field '{field_name}'")
                source_type = "ignore"

            if column_index is not None and column_index < 0:
                errors.append(f"Column index must be >= 0 for field '{field_name}'")
                source_type = "ignore"

            if column_index is not None and column_index >= max(column_count, 1):
                errors.append(
                    f"Column index {column_index + 1} is out of detected range for field '{field_name}'"
                )
                source_type = "ignore"

            if source_type == "column" and column_index is not None:
                used_columns.setdefault(column_index, []).append(field_name)

        elif source_type == "constant":
            constant_value = "" if row.get("constant_value") is None else str(row.get("constant_value"))

        normalized[field_name] = {
            "source_type": source_type,
            "column_index": column_index,
            "constant_value": constant_value,
        }

    for field_def in field_defs:
        field_name = field_def.name
        config = normalized.get(field_name, {"source_type": "ignore"})
        if not field_def.required:
            continue
        if config["source_type"] == "ignore":
            errors.append(f"Required field '{field_name}' is not mapped")

    for field_name in uniqueness_fields:
        field_def = field_by_name.get(field_name)
        if field_def is None:
            errors.append(f"Unknown uniqueness field '{field_name}'")
            continue
        config = normalized.get(field_name, {"source_type": "ignore"})
        if config["source_type"] == "ignore":
            errors.append(f"Uniqueness field '{field_name}' must be mapped")

    for column_index, field_names in sorted(used_columns.items()):
        if len(field_names) <= 1:
            continue
        warnings.append(
            {
                "code": "DUPLICATE_COLUMN_MAPPING",
                "severity": "warning",
                "message": (
                    f"Column {column_index + 1} is mapped to multiple fields: "
                    + ", ".join(field_names)
                ),
            }
        )

    return normalized, errors, warnings


def run_import(
    *,
    user_id: int,
    session_meta: dict[str, Any],
    note_type: Any,
    target_deck_id: int | None,
    mode: str,
    uniqueness_fields: list[str],
    raw_mapping: dict[str, Any] | None,
    dont_overwrite_empty: bool,
    confirm_column_mismatch: bool,
    apply_changes: bool,
    chunk_size: int | None = None,
) -> dict[str, Any]:
    normalized_mode = (mode or "upsert").strip().lower()
    if normalized_mode not in {"insert_only", "update_only", "upsert"}:
        raise ImportValidationError("import_mode must be one of: insert_only, update_only, upsert")

    uniqueness = [str(item).strip() for item in uniqueness_fields if str(item).strip()]
    if not uniqueness:
        raise ImportValidationError("At least one uniqueness field is required")

    delimiter = str(session_meta.get("delimiter") or ",")
    has_header = bool(session_meta.get("has_header"))
    token = str(session_meta.get("token") or "")
    data_path = Path(str(session_meta.get("data_path") or ""))
    if not token or not data_path.exists():
        raise ImportValidationError("Import session is invalid or expired")

    field_defs = sorted(note_type.field_defs, key=lambda item: item.position)
    column_count = int(session_meta.get("column_count") or 0)
    field_count = len(field_defs)

    mismatch_warning: list[dict[str, str]] = []
    if column_count != field_count:
        if column_count < field_count:
            mismatch_warning.append(
                {
                    "code": "COLUMN_COUNT_SHORT",
                    "severity": "danger",
                    "message": (
                        f"Detected {column_count} column(s), but note type has {field_count} field(s)."
                    ),
                }
            )
        else:
            mismatch_warning.append(
                {
                    "code": "COLUMN_COUNT_LONG",
                    "severity": "warning",
                    "message": (
                        f"Detected {column_count} column(s), but note type has {field_count} field(s)."
                    ),
                }
            )

    if mismatch_warning and not confirm_column_mismatch:
        raise ImportValidationError("Column count mismatch must be confirmed before import")

    mapping, mapping_errors, mapping_warnings = _normalize_mapping(
        field_defs=field_defs,
        raw_mapping=raw_mapping,
        column_count=max(column_count, int(session_meta.get("max_columns") or column_count)),
        uniqueness_fields=uniqueness,
    )
    if mapping_errors:
        raise ImportValidationError("; ".join(mapping_errors))

    existing_notes_query = Note.query.filter_by(user_id=user_id, note_type_id=note_type.id)
    if target_deck_id is not None:
        existing_notes_query = existing_notes_query.filter(Note.deck_id == target_deck_id)
    existing_notes = existing_notes_query.all()
    existing_by_key: dict[str, list[Note]] = {}
    for note in existing_notes:
        values = note.field_values if isinstance(note.field_values, dict) else {}
        key = _build_compound_key(values, uniqueness)
        if not key:
            continue
        existing_by_key.setdefault(key, []).append(note)

    summary = {
        "total_rows": 0,
        "valid_rows": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "unchanged": 0,
        "errors": 0,
        "processed_rows": 0,
    }
    skip_reasons: dict[str, int] = {}
    issues: list[dict[str, Any]] = []

    seen_keys: set[str] = set()
    chunk_limit = max(50, int(chunk_size or IMPORT_DEFAULT_CHUNK_SIZE))
    pending_writes = 0

    templates: list[Template] = []
    if apply_changes and normalized_mode in {"insert_only", "upsert"}:
        templates = Template.query.filter_by(note_type_id=note_type.id).order_by(Template.position.asc()).all()

    insert_payload_buffer: list[dict[str, Any]] = []

    def push_issue(*, kind: str, row: int, reason: str, message: str) -> None:
        if kind == "skip":
            summary["skipped"] += 1
            skip_reasons[reason] = int(skip_reasons.get(reason, 0)) + 1
        elif kind == "error":
            summary["errors"] += 1

        if len(issues) < IMPORT_MAX_ISSUES:
            issues.append(
                {
                    "kind": kind,
                    "row": row,
                    "reason": reason,
                    "message": message,
                }
            )

    def flush_pending() -> None:
        nonlocal pending_writes, insert_payload_buffer
        if not apply_changes or pending_writes <= 0:
            pending_writes = 0
            insert_payload_buffer = []
            return

        if insert_payload_buffer:
            notes: list[Note] = []
            for field_values in insert_payload_buffer:
                notes.append(
                    Note(
                        note_type_id=note_type.id,
                        user_id=user_id,
                        deck_id=target_deck_id,
                        field_values=field_values,
                        tags=[],
                    )
                )
            db.session.add_all(notes)
            db.session.flush()

            cards: list[Card] = []
            for note in notes:
                for template in templates:
                    cards.append(Card(note_id=note.id, template_id=template.id, queue="new"))
            if cards:
                db.session.add_all(cards)

        db.session.commit()
        insert_payload_buffer = []
        pending_writes = 0

    mapped_column_indexes = [
        int(config["column_index"])
        for config in mapping.values()
        if config.get("source_type") == "column" and config.get("column_index") is not None
    ]
    highest_required_index = max(mapped_column_indexes) if mapped_column_indexes else -1

    try:
        with data_path.open("rb") as raw_file:
            text_file = TextIOWrapper(raw_file, encoding="utf-8-sig", newline="")
            reader = csv.reader(text_file, delimiter=delimiter)
            for row_number, raw_row in enumerate(reader, start=1):
                if row_number == 1 and has_header:
                    continue

                data_row_index = summary["processed_rows"] + 1
                summary["processed_rows"] = data_row_index
                summary["total_rows"] += 1

                row = ["" if cell is None else str(cell) for cell in raw_row]
                if not any(cell.strip() for cell in row):
                    push_issue(
                        kind="skip",
                        row=data_row_index,
                        reason="empty_row",
                        message="Row is empty and was skipped.",
                    )
                    continue

                if highest_required_index >= len(row):
                    push_issue(
                        kind="skip",
                        row=data_row_index,
                        reason="invalid_column_count",
                        message=(
                            f"Expected at least {highest_required_index + 1} column(s), got {len(row)}."
                        ),
                    )
                    continue

                mapped_values: dict[str, Any] = {}
                row_failed = False

                for field_def in field_defs:
                    field_name = field_def.name
                    config = mapping.get(field_name, {"source_type": "ignore"})
                    source_type = config.get("source_type")

                    if source_type == "ignore":
                        continue

                    if source_type == "constant":
                        mapped_values[field_name] = config.get("constant_value") or ""
                        continue

                    column_index = config.get("column_index")
                    if column_index is None:
                        push_issue(
                            kind="error",
                            row=data_row_index,
                            reason="mapping_error",
                            message=f"Missing column index for field '{field_name}'.",
                        )
                        row_failed = True
                        break

                    if int(column_index) >= len(row):
                        push_issue(
                            kind="skip",
                            row=data_row_index,
                            reason="invalid_column_count",
                            message=(
                                f"Column {int(column_index) + 1} is missing for field '{field_name}'."
                            ),
                        )
                        row_failed = True
                        break

                    raw_value = row[int(column_index)]
                    mapped_values[field_name] = raw_value

                if row_failed:
                    continue

                for field_def in field_defs:
                    if not field_def.required:
                        continue
                    candidate = mapped_values.get(field_def.name, "")
                    if is_field_empty(candidate):
                        push_issue(
                            kind="error",
                            row=data_row_index,
                            reason="required_field_missing",
                            message=f"Required field '{field_def.name}' is empty.",
                        )
                        row_failed = True
                        break

                if row_failed:
                    continue

                key = _build_compound_key(mapped_values, uniqueness)
                if not key:
                    push_issue(
                        kind="skip",
                        row=data_row_index,
                        reason="missing_key",
                        message="One or more uniqueness key fields are empty.",
                    )
                    continue

                if key in seen_keys:
                    push_issue(
                        kind="skip",
                        row=data_row_index,
                        reason="duplicate_in_file",
                        message="Duplicate uniqueness key in the same import file.",
                    )
                    continue
                seen_keys.add(key)

                existing_bucket = existing_by_key.get(key, [])
                if len(existing_bucket) > 1:
                    push_issue(
                        kind="skip",
                        row=data_row_index,
                        reason="duplicate_existing",
                        message="Multiple existing notes in target deck match the same uniqueness key.",
                    )
                    continue

                summary["valid_rows"] += 1

                if normalized_mode == "insert_only":
                    if existing_bucket:
                        push_issue(
                            kind="skip",
                            row=data_row_index,
                            reason="duplicate",
                            message="Record already exists in target deck, skipped by insert-only mode.",
                        )
                        continue
                    action = "insert"
                elif normalized_mode == "update_only":
                    if not existing_bucket:
                        push_issue(
                            kind="skip",
                            row=data_row_index,
                            reason="not_found",
                            message="Record does not exist, skipped by update-only mode.",
                        )
                        continue
                    action = "update"
                else:
                    action = "update" if existing_bucket else "insert"

                if action == "insert":
                    field_values = {field_def.name: "" for field_def in field_defs}
                    for field_def in field_defs:
                        field_name = field_def.name
                        config = mapping.get(field_name, {"source_type": "ignore"})
                        if config.get("source_type") == "ignore":
                            continue
                        incoming = mapped_values.get(field_name, "")
                        if dont_overwrite_empty and is_field_empty(incoming):
                            continue
                        field_values[field_name] = incoming

                    summary["inserted"] += 1
                    pending_writes += 1
                    if apply_changes:
                        insert_payload_buffer.append(field_values)

                else:  # update
                    note_obj = existing_bucket[0]
                    current_values = note_obj.field_values if isinstance(note_obj.field_values, dict) else {}
                    merged_values = dict(current_values)
                    changed = False

                    for field_def in field_defs:
                        field_name = field_def.name
                        config = mapping.get(field_name, {"source_type": "ignore"})
                        if config.get("source_type") == "ignore":
                            continue
                        incoming = mapped_values.get(field_name, "")
                        if dont_overwrite_empty and is_field_empty(incoming):
                            continue
                        if _normalize_compare_value(current_values.get(field_name, "")) == _normalize_compare_value(incoming):
                            continue
                        merged_values[field_name] = incoming
                        changed = True

                    if not changed:
                        summary["unchanged"] += 1
                        continue

                    summary["updated"] += 1
                    pending_writes += 1
                    if apply_changes:
                        note_obj.field_values = merged_values

                if apply_changes and pending_writes >= chunk_limit:
                    flush_pending()

        if apply_changes and pending_writes > 0:
            flush_pending()

    except csv.Error as exc:
        if apply_changes:
            db.session.rollback()
        push_issue(
            kind="error",
            row=max(1, summary["processed_rows"]),
            reason="parse_error",
            message=f"CSV parser error: {exc}",
        )

    report = {
        "token": token,
        "mode": normalized_mode,
        "summary": summary,
        "skip_reasons": skip_reasons,
        "issues": issues,
        "warnings": mismatch_warning + mapping_warnings,
    }
    return report
