"""Incremental Anki scheduler snapshots and immutable review history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
from typing import Any

from app.repositories.review_event_repository import create_review_event_record
from app.services.anki_scheduler import _day_index, _day_index_to_datetime
from app.services.scheduler_config_service import resolve_scheduler_runtime_settings
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.connect_import_session import ConnectImportSession
from models.connect_review_event_ref import ConnectReviewEventRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.user import User


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_SYNC_RECORDS = 1000
MAX_REVIEW_DURATION_MS = 3_600_000


class AnkiSyncError(ValueError):
    pass


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnkiSyncError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise AnkiSyncError(f"{field} must be a finite number")
    return result


def _integer(value: object, field: str, minimum: int, maximum: int) -> int:
    number = _finite_number(value, field)
    if not number.is_integer() or number < minimum or number > maximum:
        raise AnkiSyncError(f"{field} is out of range")
    return int(number)


def _text_id(value: object, field: str) -> str:
    result = str(value or "").strip()
    if not result or len(result) > 128:
        raise AnkiSyncError(f"{field} is invalid")
    return result


def _canonical_hash(payload: dict[str, Any]) -> tuple[str, str]:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest(), encoded


def _source_note(session: ConnectImportSession, external_note_id: str) -> ConnectSourceNoteRef:
    row = ConnectSourceNoteRef.query.filter_by(
        user_id=session.user_id,
        source_key=session.source_key,
        external_note_id=external_note_id,
    ).first()
    if row is None or row.note is None or row.note.user_id != session.user_id:
        raise AnkiSyncError("source note has not been imported")
    return row


def _card_for_ord(note_ref: ConnectSourceNoteRef, source_ord: int) -> Card:
    cards = sorted(
        list(note_ref.note.cards),
        key=lambda card: (int(card.template.position), str(card.template_id)),
    )
    by_position = {int(card.template.position): card for card in cards}
    card = by_position.get(source_ord)
    if card is None and 0 <= source_ord < len(cards):
        card = cards[source_ord]
    if card is None:
        raise AnkiSyncError("source card ord does not map to a local template")
    return card


def _upsert_source_card(
    session: ConnectImportSession,
    *,
    external_card_id: str,
    external_note_id: str,
    source_ord: int,
) -> ConnectSourceCardRef:
    note_ref = _source_note(session, external_note_id)
    card = _card_for_ord(note_ref, source_ord)
    row = ConnectSourceCardRef.query.filter_by(
        user_id=session.user_id,
        source_key=session.source_key,
        external_card_id=external_card_id,
    ).with_for_update().first()
    if row is None:
        row = ConnectSourceCardRef(
            user_id=session.user_id,
            source_key=session.source_key,
            external_card_id=external_card_id,
            external_note_id=external_note_id,
            source_ord=source_ord,
            card_id=card.id,
        )
        db.session.add(row)
    elif row.external_note_id != external_note_id:
        raise AnkiSyncError("external card ID is already mapped to another note")
    else:
        row.source_ord = source_ord
        row.card_id = card.id
    row.last_session_id = session.id
    return row


def _progress_queue(card_type: int) -> str:
    return {0: "new", 1: "learning", 2: "review", 3: "relearning"}.get(card_type, "new")


def _apply_progress_snapshot(
    session: ConnectImportSession,
    source_card: ConnectSourceCardRef,
    record: dict[str, Any],
) -> tuple[str, CardProgress]:
    snapshot_hash = str(record.get("snapshotHash") or "").strip().lower()
    if not SHA256_RE.fullmatch(snapshot_hash):
        raise AnkiSyncError("snapshotHash must be a SHA-256 hex string")

    progress = CardProgress.query.filter_by(
        user_id=session.user_id,
        card_id=source_card.card_id,
    ).with_for_update().first()
    if source_card.snapshot_hash == snapshot_hash:
        if progress is None:
            progress = CardProgress(user_id=session.user_id, card_id=source_card.card_id)
            db.session.add(progress)
        return "unchanged", progress
    if (
        progress is not None
        and source_card.applied_local_revision is not None
        and int(progress.revision or 0) != int(source_card.applied_local_revision)
        and record.get("force") is not True
    ):
        return "local_conflict", progress
    if progress is None:
        progress = CardProgress(user_id=session.user_id, card_id=source_card.card_id)
        db.session.add(progress)

    card_type = _integer(record.get("type", 0), "type", 0, 3)
    anki_queue = _integer(record.get("queue", 0), "queue", -3, 4)
    raw_due = _integer(record.get("due", 0), "due", -2_000_000_000, 4_000_000_000)
    interval = _integer(record.get("interval", 0), "interval", -365_000 * 86400, 365_000)
    factor = _integer(record.get("factor", 0), "factor", 0, 10_000)
    reps = _integer(record.get("reps", 0), "reps", 0, 2_000_000_000)
    lapses = _integer(record.get("lapses", 0), "lapses", 0, 2_000_000_000)
    left = _integer(record.get("left", 0), "left", 0, 2_000_000_000)

    user = db.session.get(User, session.user_id)
    timezone_name = getattr(user, "timezone", "UTC") or "UTC"
    runtime = resolve_scheduler_runtime_settings(user_id=session.user_id)
    today = _day_index(
        datetime.utcnow(),
        runtime.day_boundary_hour_local,
        timezone_name=timezone_name,
    )
    day_based_due = card_type == 2 or (card_type in {1, 3} and anki_queue == 3)
    if day_based_due and record.get("sourceToday") is None:
        return "due_unresolved", progress
    progress.queue = _progress_queue(card_type)
    progress.review_kind = {0: "new", 1: "learn", 2: "review", 3: "relearn"}[card_type]
    progress.scheduler_mode = "anki"
    progress.is_suspended = anki_queue == -1
    progress.is_buried = anki_queue in {-2, -3}
    progress.buried_until_day = today + 1 if progress.is_buried else None
    progress.interval_days_raw = float(interval)
    progress.interval_days = max(0, int(interval))
    progress.ease_factor = float(factor) / 1000.0
    progress.reps = reps
    progress.lapses = lapses
    progress.step_index = max(0, (left % 1000) - 1) if card_type in {1, 3} else 0

    source_today = record.get("sourceToday")
    if day_based_due:
        source_today_value = _integer(source_today, "sourceToday", -2_000_000_000, 4_000_000_000)
        progress.due_day = today + (raw_due - source_today_value)
        progress.due_at = _day_index_to_datetime(
            progress.due_day,
            runtime.day_boundary_hour_local,
            timezone_name=timezone_name,
        )
    elif card_type in {1, 3} or anki_queue == 4:
        if raw_due < 0 or raw_due > 4_102_444_800:
            raise AnkiSyncError("due timestamp is out of range")
        progress.due_at = datetime.utcfromtimestamp(raw_due)
        progress.due_day = None
    else:
        progress.due_at = None
        progress.due_day = None

    progress.revision = int(progress.revision or 0) + 1
    db.session.flush()
    source_card.snapshot_hash = snapshot_hash
    source_card.applied_local_revision = int(progress.revision or 0)
    return "applied", progress


def import_progress(
    user_id: int,
    session: ConnectImportSession,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(records) > MAX_SYNC_RECORDS:
        raise AnkiSyncError(f"progress package has more than {MAX_SYNC_RECORDS} records")
    results: list[dict[str, Any]] = []
    for record in records:
        external_card_id = record.get("sourceCardId") if isinstance(record, dict) else None
        try:
            if not isinstance(record, dict):
                raise AnkiSyncError("progress record must be an object")
            card_id = _text_id(external_card_id, "sourceCardId")
            note_id = _text_id(record.get("externalNoteId"), "externalNoteId")
            source_ord = _integer(record.get("ord"), "ord", 0, 99)
            with db.session.begin_nested():
                source_card = _upsert_source_card(
                    session,
                    external_card_id=card_id,
                    external_note_id=note_id,
                    source_ord=source_ord,
                )
                state, progress = _apply_progress_snapshot(session, source_card, record)
                db.session.flush()
            result = {"sourceCardId": external_card_id, "applied": state == "applied", "state": state}
            if state == "due_unresolved":
                result["error"] = "Anki day index could not be resolved; scheduler snapshot was not applied"
            results.append(result)
        except Exception as exc:
            results.append({"sourceCardId": external_card_id, "applied": False, "state": "failed", "error": str(exc)})
    return results


def _reviewed_at(external_review_id: str) -> datetime:
    try:
        milliseconds = int(external_review_id)
    except ValueError as exc:
        raise AnkiSyncError("sourceReviewId must be an epoch-millisecond integer") from exc
    moment = datetime.fromtimestamp(milliseconds / 1000.0, tz=timezone.utc).replace(tzinfo=None)
    if moment < datetime(2000, 1, 1) or moment > datetime.utcnow() + timedelta(days=1):
        raise AnkiSyncError("sourceReviewId timestamp is out of range")
    return moment


def _interval_days(value: int) -> float:
    return float(value) if value >= 0 else abs(float(value)) / 86400.0


def _import_review(
    session: ConnectImportSession,
    record: dict[str, Any],
) -> tuple[str, ConnectReviewEventRef]:
    external_review_id = _text_id(record.get("sourceReviewId"), "sourceReviewId")
    external_card_id = _text_id(record.get("sourceCardId"), "sourceCardId")
    reviewed_at = _reviewed_at(external_review_id)
    ease = _integer(record.get("ease"), "ease", 0, 4)
    review_type = _integer(record.get("type"), "type", 0, 5)
    duration = _integer(record.get("time", 0), "time", 0, MAX_REVIEW_DURATION_MS)
    interval = _integer(record.get("ivl", 0), "ivl", -2_000_000_000, 2_000_000_000)
    last_interval = _integer(record.get("lastIvl", 0), "lastIvl", -2_000_000_000, 2_000_000_000)
    factor = _integer(record.get("factor", 0), "factor", 0, 10_000)
    canonical = {
        "sourceReviewId": external_review_id,
        "sourceCardId": external_card_id,
        "ease": ease,
        "type": review_type,
        "ivl": interval,
        "lastIvl": last_interval,
        "factor": factor,
        "time": duration,
    }
    payload_hash, payload_json = _canonical_hash(canonical)
    existing = ConnectReviewEventRef.query.filter_by(
        user_id=session.user_id,
        source_key=session.source_key,
        external_review_id=external_review_id,
    ).with_for_update().first()
    repairing_projection = existing is not None
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise AnkiSyncError("source review ID already exists with different content")
        existing.last_session_id = session.id
        # ReviewEvent is the analytics projection while this provenance row is
        # the durable external identity. If the projection was removed by an
        # older purge flow, replay the same Anki revlog row to repair it.
        if existing.status == "ignored" or existing.review_event_id is not None:
            return "unchanged", existing

    source_card = ConnectSourceCardRef.query.filter_by(
        user_id=session.user_id,
        source_key=session.source_key,
        external_card_id=external_card_id,
    ).with_for_update().first()
    if source_card is None or source_card.card is None:
        raise AnkiSyncError("source card has not been mapped")
    if existing is None:
        ref = ConnectReviewEventRef(
            user_id=session.user_id,
            source_key=session.source_key,
            external_review_id=external_review_id,
            external_card_id=external_card_id,
            payload_hash=payload_hash,
            last_session_id=session.id,
        )
        db.session.add(ref)
    else:
        ref = existing
        ref.external_card_id = external_card_id
        ref.ignored_reason = None
    if ease == 0:
        ref.status = "ignored"
        ref.ignored_reason = "manual_or_rescheduled"
    else:
        card = source_card.card
        note = card.note
        review_kind = {0: "learn", 1: "review", 2: "relearn", 3: "cram"}.get(review_type, "review")
        mode = "learn" if review_kind in {"learn", "relearn"} else "review"
        event = create_review_event_record(
            user_id=session.user_id,
            card_id=card.id,
            deck_id=note.deck_id,
            note_type_id=note.note_type_id,
            reviewed_at=reviewed_at,
            duration_ms=duration,
            rating={1: "again", 2: "hard", 3: "good", 4: "easy"}[ease],
            mode=mode,
            scheduler_mode="anki",
            scheduler_algorithm="anki",
            algorithm_version="revlog-v1",
            review_kind=review_kind,
            interval_days_before=_interval_days(last_interval),
            interval_days_after=_interval_days(interval),
            ease_factor_after=float(factor) / 1000.0,
            payload_json=payload_json,
        )
        db.session.flush()
        ref.review_event_id = event.id
        ref.status = "imported"
        progress = CardProgress.query.filter_by(user_id=session.user_id, card_id=card.id).first()
        if progress is not None and (
            progress.last_reviewed_at is None or reviewed_at > progress.last_reviewed_at
        ):
            progress.last_reviewed_at = reviewed_at
            progress.last_review_event_id = event.id
    source_card.review_cursor = max(int(source_card.review_cursor or 0), int(external_review_id))
    if repairing_projection and ref.status == "imported":
        return "repaired", ref
    return ref.status, ref


def import_reviews(
    user_id: int,
    session: ConnectImportSession,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(records) > MAX_SYNC_RECORDS:
        raise AnkiSyncError(f"review package has more than {MAX_SYNC_RECORDS} records")
    grouped: dict[str, list[dict[str, Any]]] = {}
    results: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            results.append(
                {
                    "sourceReviewId": None,
                    "sourceCardId": None,
                    "imported": False,
                    "state": "failed",
                    "error": "review record must be an object",
                }
            )
            continue
        source_card_id = str(record.get("sourceCardId") or "").strip()
        grouped.setdefault(source_card_id, []).append(record)

    for source_card_id, card_records in grouped.items():
        current_record: dict[str, Any] | None = None
        card_results: list[dict[str, Any]] = []
        try:
            with db.session.begin_nested():
                for current_record in sorted(
                    card_records,
                    key=lambda item: int(item.get("sourceReviewId") or 0),
                ):
                    state, _ref = _import_review(session, current_record)
                    card_results.append(
                        {
                            "sourceReviewId": current_record.get("sourceReviewId"),
                            "sourceCardId": current_record.get("sourceCardId"),
                            "imported": state in {"imported", "repaired"},
                            "state": state,
                        }
                    )
                db.session.flush()
            results.extend(card_results)
        except Exception as exc:
            results.append(
                {
                    "sourceReviewId": (
                        current_record.get("sourceReviewId")
                        if current_record is not None
                        else None
                    ),
                    "sourceCardId": source_card_id or None,
                    "imported": False,
                    "state": "failed",
                    "error": str(exc),
                    "cardAtomic": True,
                }
            )
    return results
