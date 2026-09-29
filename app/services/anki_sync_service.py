"""Incremental Anki scheduler snapshots and immutable review history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
from types import SimpleNamespace
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.repositories.study_authority_repository import (
    LockedStudyAuthoritySiblings,
    StudyAuthorityRoute,
    lock_study_authority_compatibility,
    lock_study_authority_route,
    lock_study_authority_siblings,
)
from app.repositories.review_event_repository import create_review_event_record
from app.services.anki_scheduler import _day_index, _day_index_to_datetime
from app.services.scheduler_config_service import resolve_scheduler_runtime_settings
from app.services import study_progress_shadow_mirror_service
from app.services.study_authority_cas_service import StudyAuthorityCASExpectation
from app.services.study_authority_projection_encoder import (
    LegacyProjectionMetadata,
    LegacySiblingBaseline,
    encode_note_state_to_legacy_cards,
)
from app.services.study_authority_write_service import (
    StudyAuthorityStateWrite,
    apply_study_authority_material_write,
)
from app.services.study_progress_shadow_codec import (
    RAW_CARD_PROGRESS_FIELDS,
    serialize_raw_card_progress,
)
from app.services.study_progress_shadow_mapper import MappingFailure, map_card_progress
from app.services.study_session_authority_pin_service import (
    lock_study_session_authority_subjects,
)
from app.validators.review_event import (
    ReviewEventPayloadError,
    build_anki_revlog_review_event_payload,
)
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


class AnkiProgressConflict(AnkiSyncError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _ProgressSnapshotControl:
    snapshot_hash: str
    base_snapshot_supplied: bool
    base_snapshot_hash: str | None
    legacy_unversioned: bool
    force: bool


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
    ).with_for_update().first()
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


def _progress_snapshot_control(record: dict[str, Any]) -> _ProgressSnapshotControl:
    snapshot_hash = str(record.get("snapshotHash") or "").strip().lower()
    if not SHA256_RE.fullmatch(snapshot_hash):
        raise AnkiSyncError("snapshotHash must be a SHA-256 hex string")
    base_snapshot_supplied = "baseSnapshotHash" in record
    raw_base_snapshot_hash = record.get("baseSnapshotHash")
    base_snapshot_hash = (
        str(raw_base_snapshot_hash).strip().lower()
        if raw_base_snapshot_hash is not None
        else None
    )
    if base_snapshot_hash is not None and not SHA256_RE.fullmatch(base_snapshot_hash):
        raise AnkiSyncError("baseSnapshotHash must be a SHA-256 hex string")
    return _ProgressSnapshotControl(
        snapshot_hash=snapshot_hash,
        base_snapshot_supplied=base_snapshot_supplied,
        base_snapshot_hash=base_snapshot_hash,
        legacy_unversioned=not base_snapshot_supplied,
        force=record.get("force") is True,
    )


def _progress_snapshot_values(
    session: ConnectImportSession,
    record: dict[str, Any],
) -> dict[str, Any] | None:
    """Decode an Anki snapshot without mutating either authority surface."""

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
        return None

    values: dict[str, Any] = {
        "queue": _progress_queue(card_type),
        "review_kind": {0: "new", 1: "learn", 2: "review", 3: "relearn"}[card_type],
        "scheduler_mode": "anki",
        "is_suspended": anki_queue == -1,
        "is_buried": anki_queue in {-2, -3},
        "buried_until_day": today + 1 if anki_queue in {-2, -3} else None,
        "suspension_reason": "anki_import" if anki_queue == -1 else None,
        "interval_days_raw": float(interval),
        "interval_days": max(0, int(interval)),
        "ease_factor": float(factor) / 1000.0,
        "memory_stability": None,
        "memory_difficulty": None,
        "reps": reps,
        "lapses": lapses,
        "step_index": max(0, (left % 1000) - 1) if card_type in {1, 3} else 0,
    }
    source_today = record.get("sourceToday")
    if day_based_due:
        source_today_value = _integer(
            source_today,
            "sourceToday",
            -2_000_000_000,
            4_000_000_000,
        )
        values["due_day"] = today + (raw_due - source_today_value)
        values["due_at"] = _day_index_to_datetime(
            values["due_day"],
            runtime.day_boundary_hour_local,
            timezone_name=timezone_name,
        )
    elif card_type in {1, 3} or anki_queue == 4:
        if raw_due < 0 or raw_due > 4_102_444_800:
            raise AnkiSyncError("due timestamp is out of range")
        values["due_at"] = datetime.utcfromtimestamp(raw_due)
        values["due_day"] = None
    else:
        values["due_at"] = None
        values["due_day"] = None
    return values


def _apply_progress_snapshot(
    session: ConnectImportSession,
    source_card: ConnectSourceCardRef,
    record: dict[str, Any],
) -> tuple[str, str, bool]:
    control = _progress_snapshot_control(record)
    previous_snapshot_hash = source_card.snapshot_hash

    progress = CardProgress.query.filter_by(
        user_id=session.user_id,
        card_id=source_card.card_id,
    ).with_for_update().first()
    local_diverged = progress is not None and (
        source_card.applied_local_revision is None
        or int(progress.revision or 0) != int(source_card.applied_local_revision)
    )
    same_snapshot = previous_snapshot_hash == control.snapshot_hash
    force_reapply = control.force and (local_diverged or progress is None)
    if same_snapshot and not force_reapply:
        return "unchanged", "PROGRESS_UNCHANGED", control.legacy_unversioned
    if (
        control.base_snapshot_supplied
        and (control.base_snapshot_hash or "") != (previous_snapshot_hash or "")
        and not control.force
    ):
        return "source_conflict", "SOURCE_SNAPSHOT_CHANGED", control.legacy_unversioned
    if local_diverged and not control.force:
        return "local_conflict", "LOCAL_PROGRESS_CHANGED", control.legacy_unversioned

    values = _progress_snapshot_values(session, record)
    if values is None:
        return "due_unresolved", "ANKI_DUE_UNRESOLVED", control.legacy_unversioned

    if progress is None:
        progress = CardProgress(user_id=session.user_id, card_id=source_card.card_id)
        db.session.add(progress)
    for field_name, value in values.items():
        setattr(progress, field_name, value)

    progress.revision = int(progress.revision or 0) + 1
    try:
        db.session.flush()
    except IntegrityError as exc:
        raise AnkiProgressConflict(
            "CONCURRENT_PROGRESS_WRITE",
            "card progress changed while the Anki snapshot was being applied",
        ) from exc
    source_card.snapshot_hash = control.snapshot_hash
    source_card.applied_local_revision = int(progress.revision or 0)
    return (
        "applied",
        "FORCED_PROGRESS_APPLIED" if control.force else "PROGRESS_APPLIED",
        control.legacy_unversioned,
    )


def _lock_note_source_card_refs(
    session: ConnectImportSession,
    source_card: ConnectSourceCardRef,
) -> tuple[Card, tuple[ConnectSourceCardRef, ...]]:
    """Lock current-source sibling refs before entering the NOTE authority graph."""

    db.session.flush()
    requested_card = db.session.get(Card, source_card.card_id)
    if requested_card is None:
        raise AnkiSyncError("source card no longer maps to a local Card")
    card_ids = tuple(
        row[0]
        for row in db.session.query(Card.id)
        .filter(Card.note_id == requested_card.note_id)
        .order_by(Card.id.asc())
        .all()
    )
    refs = tuple(
        ConnectSourceCardRef.query.filter(
            ConnectSourceCardRef.user_id == session.user_id,
            ConnectSourceCardRef.source_key == session.source_key,
            ConnectSourceCardRef.card_id.in_(card_ids),
        )
        .order_by(ConnectSourceCardRef.card_id.asc(), ConnectSourceCardRef.id.asc())
        .with_for_update()
        .all()
    )
    if source_card.id not in {row.id for row in refs}:
        raise AnkiSyncError("source card mapping disappeared before progress import")
    return requested_card, refs


def _note_progress_snapshot_contexts(
    *,
    siblings: LockedStudyAuthoritySiblings,
    requested_card_id: str,
    source_card: ConnectSourceCardRef,
    source_note: ConnectSourceNoteRef,
) -> dict[str, study_progress_shadow_mirror_service.ExternalProgressMirrorContext]:
    return {
        str(card.id): study_progress_shadow_mirror_service.ExternalProgressMirrorContext(
            provenance_code="CONNECT_PROGRESS_SNAPSHOT",
            history_completeness_code="HISTORY_SNAPSHOT_ONLY",
            source_card_ref=(source_card if str(card.id) == requested_card_id else None),
            source_note_ref=(source_note if str(card.id) == requested_card_id else None),
        )
        for card in siblings.cards
    }


def _apply_note_authority_progress_snapshot(
    session: ConnectImportSession,
    *,
    route: StudyAuthorityRoute,
    requested_card: Card,
    source_card: ConnectSourceCardRef,
    sibling_source_refs: tuple[ConnectSourceCardRef, ...],
    source_note: ConnectSourceNoteRef,
    record: dict[str, Any],
    now_utc: datetime,
) -> tuple[str, str, bool]:
    """Apply one external snapshot through the canonical learner/Note CAS."""

    control = _progress_snapshot_control(record)
    previous_snapshot_hash = source_card.snapshot_hash
    from app.services.scheduler_config_service import resolve_deck_options
    from app.services.study_note_pristine_service import materialize_pristine_notes

    # A never-studied Note (for example one created by this import) gets its
    # revision-zero NEW state first; the snapshot then applies through CAS.
    materialize_pristine_notes(
        db.session,
        route=route,
        cards=(requested_card,),
        starting_ease_by_note_id={
            str(requested_card.note_id): float(
                resolve_deck_options(
                    user_id=session.user_id,
                    deck_id=requested_card.note.deck_id,
                ).startingEase
            )
        },
        now_utc=now_utc,
    )
    locked_subjects = lock_study_session_authority_subjects(
        db.session,
        route=route,
        logical_note_keys=(str(requested_card.note_id),),
        now_utc=now_utc,
    )
    locked = locked_subjects.locked_by_logical_note_key[str(requested_card.note_id)]
    siblings = lock_study_authority_siblings(
        db.session,
        route=route,
        locked=locked,
        requested_card_id=str(requested_card.id),
    )
    lock_study_authority_compatibility(
        db.session,
        route=route,
        locked=locked,
        siblings=siblings,
    )
    progress = siblings.progress_by_card_id[str(requested_card.id)]

    # A newly discovered external Card has no accepted local revision yet. Its
    # first snapshot is allowed to establish lineage from the already-enrolled
    # NOTE state. Once a source snapshot exists, the local revision is a real
    # optimistic-concurrency fence.
    local_diverged = previous_snapshot_hash is not None and (
        source_card.applied_local_revision is None
        or int(progress.revision or 0) != int(source_card.applied_local_revision)
    )
    same_snapshot = previous_snapshot_hash == control.snapshot_hash
    force_reapply = control.force and local_diverged
    if same_snapshot and not force_reapply:
        return "unchanged", "PROGRESS_UNCHANGED", control.legacy_unversioned
    if (
        control.base_snapshot_supplied
        and (control.base_snapshot_hash or "") != (previous_snapshot_hash or "")
        and not control.force
    ):
        return "source_conflict", "SOURCE_SNAPSHOT_CHANGED", control.legacy_unversioned
    if local_diverged and not control.force:
        return "local_conflict", "LOCAL_PROGRESS_CHANGED", control.legacy_unversioned

    values = _progress_snapshot_values(session, record)
    if values is None:
        return "due_unresolved", "ANKI_DUE_UNRESOLVED", control.legacy_unversioned

    candidate_values = {
        field_name: getattr(progress, field_name)
        for field_name in RAW_CARD_PROGRESS_FIELDS
    }
    candidate_values.update(values)
    candidate_values["revision"] = int(progress.revision or 0) + 1
    candidate_values["updated_at"] = now_utc
    candidate = SimpleNamespace(**candidate_values)
    mapped = map_card_progress(
        candidate,
        card_created_at=requested_card.created_at,
        card_order_key=str(requested_card.id),
    )
    if isinstance(mapped, MappingFailure):
        raise AnkiProgressConflict(
            mapped.code,
            f"Anki snapshot cannot become NOTE authority: {mapped.message}",
        )

    mirror_plan = study_progress_shadow_mirror_service.compose_locked_lifecycle_plan(
        db.session,
        learner_user_id=session.user_id,
        note_id=str(requested_card.note_id),
        subject=locked.subject,
        cards=siblings.cards,
        progress_rows=siblings.progress_by_card_id.values(),
        prepared_at=now_utc,
    )
    contexts = _note_progress_snapshot_contexts(
        siblings=siblings,
        requested_card_id=str(requested_card.id),
        source_card=source_card,
        source_note=source_note,
    )
    current_semantic_hash = (
        bytes(locked.token.semantic_state_hash)
        if locked.token.semantic_state_hash is not None
        else None
    )
    if current_semantic_hash is None:
        raise AnkiProgressConflict(
            "AUTHORITY_STATE_REQUIRED",
            "NOTE authority has no current state for the imported snapshot.",
        )

    source_card.snapshot_hash = control.snapshot_hash
    if mapped.semantic_state_hash == current_semantic_hash:
        source_card.applied_local_revision = int(progress.revision or 0)
        study_progress_shadow_mirror_service.finalize_external_progress_mirror(
            mirror_plan,
            applied_contexts={str(requested_card.id): contexts[str(requested_card.id)]},
            now_utc=now_utc,
        )
        return (
            "applied",
            "FORCED_PROGRESS_APPLIED" if control.force else "PROGRESS_APPLIED",
            control.legacy_unversioned,
        )

    state_write = StudyAuthorityStateWrite(
        algorithm_key=mapped.algorithm_key,
        algorithm_version=mapped.algorithm_version,
        state_schema_version=mapped.state_schema_version,
        storage_codec=mapped.storage_codec,
        state_payload=mapped.state.payload,
        state_payload_size=mapped.state.size,
        algorithm_state_hash=mapped.algorithm_state_hash,
    )
    baselines: list[LegacySiblingBaseline] = []
    for card in siblings.cards:
        sibling_progress = siblings.progress_by_card_id[str(card.id)]
        raw = serialize_raw_card_progress(sibling_progress)
        baselines.append(
            LegacySiblingBaseline(
                card_id=str(card.id),
                expected_base_revision=int(sibling_progress.revision or 0),
                card_created_at=card.created_at,
                raw_payload=raw.payload,
                raw_payload_size=raw.size,
                raw_payload_hash=raw.digest,
                projected_last_review_event_id=sibling_progress.last_review_event_id,
            )
        )
    projection = encode_note_state_to_legacy_cards(
        expected_learner_user_id=session.user_id,
        algorithm_key=mapped.algorithm_key,
        algorithm_version=mapped.algorithm_version,
        state_schema_version=mapped.state_schema_version,
        storage_codec=mapped.storage_codec,
        state_payload=mapped.state.payload,
        expected_state_payload_size=mapped.state.size,
        expected_algorithm_state_hash=mapped.algorithm_state_hash,
        metadata=LegacyProjectionMetadata(
            interval_days_rounded=int(candidate.interval_days),
            is_buried=bool(candidate.is_buried),
            buried_until_day=candidate.buried_until_day,
            last_leech_at=candidate.last_leech_at,
            last_leech_lapses=int(candidate.last_leech_lapses),
            projected_at=now_utc,
        ),
        siblings=tuple(baselines),
    )
    write = apply_study_authority_material_write(
        db.session,
        route=route,
        locked=locked,
        expected=StudyAuthorityCASExpectation(
            enrollment_epoch=route.epoch,
            subject_generation=int(locked.subject.subject_generation),
            authority_revision=int(locked.token.authority_revision),
            semantic_state_hash=current_semantic_hash,
        ),
        next_state=state_write,
        siblings=siblings,
        projection=projection,
        now_utc=now_utc,
    )
    projected_by_card_id = {
        str(row.card_id): row for row in write.projected_progress
    }
    for source_ref in sibling_source_refs:
        projected = projected_by_card_id.get(str(source_ref.card_id))
        if projected is not None:
            source_ref.applied_local_revision = int(projected.revision or 0)
    study_progress_shadow_mirror_service.finalize_external_progress_mirror(
        mirror_plan,
        applied_contexts=contexts,
        now_utc=now_utc,
    )
    return (
        "applied",
        "FORCED_PROGRESS_APPLIED" if control.force else "PROGRESS_APPLIED",
        control.legacy_unversioned,
    )


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
                authority_route = lock_study_authority_route(
                    db.session,
                    learner_user_id=session.user_id,
                    allow_note_authority=True,
                )
                source_card = _upsert_source_card(
                    session,
                    external_card_id=card_id,
                    external_note_id=note_id,
                    source_ord=source_ord,
                )
                requested_card, sibling_source_refs = _lock_note_source_card_refs(
                    session,
                    source_card,
                )
                source_note_ref = _source_note(session, source_card.external_note_id)
                if authority_route.mode_code == "NOTE":
                    state, code, legacy_unversioned = (
                        _apply_note_authority_progress_snapshot(
                            session,
                            route=authority_route,
                            requested_card=requested_card,
                            source_card=source_card,
                            sibling_source_refs=sibling_source_refs,
                            source_note=source_note_ref,
                            record=record,
                            now_utc=datetime.utcnow().replace(microsecond=0),
                        )
                    )
                else:
                    mirror_plan = (
                        study_progress_shadow_mirror_service.prepare_native_mirror(
                            db.session,
                            learner_user_id=session.user_id,
                            cards=(requested_card,),
                        )
                    )
                    state, code, legacy_unversioned = _apply_progress_snapshot(
                        session,
                        source_card,
                        record,
                    )
                    if state == "applied":
                        study_progress_shadow_mirror_service.finalize_external_progress_mirror(
                            mirror_plan,
                            applied_contexts={
                                str(source_card.card_id): study_progress_shadow_mirror_service.ExternalProgressMirrorContext(
                                    provenance_code="CONNECT_PROGRESS_SNAPSHOT",
                                    history_completeness_code="HISTORY_SNAPSHOT_ONLY",
                                    source_card_ref=source_card,
                                    source_note_ref=source_note_ref,
                                )
                            },
                        )
                db.session.flush()
            result = {
                "sourceCardId": external_card_id,
                "applied": state == "applied",
                "state": state,
                "code": code,
                "serverSnapshotHash": (
                    str(source_card.snapshot_hash)
                    if source_card.snapshot_hash
                    else None
                ),
            }
            if legacy_unversioned:
                result["legacy_unversioned"] = True
            if state == "due_unresolved":
                result["error"] = "Anki day index could not be resolved; scheduler snapshot was not applied"
            results.append(result)
        except AnkiProgressConflict as exc:
            current_source_card = ConnectSourceCardRef.query.filter_by(
                user_id=session.user_id,
                source_key=session.source_key,
                external_card_id=str(external_card_id),
            ).first()
            results.append(
                {
                    "sourceCardId": external_card_id,
                    "applied": False,
                    "state": "conflict",
                    "code": exc.code,
                    "error": str(exc),
                    "serverSnapshotHash": (
                        str(current_source_card.snapshot_hash)
                        if current_source_card is not None
                        and current_source_card.snapshot_hash
                        else None
                    ),
                    **(
                        {"legacy_unversioned": True}
                        if isinstance(record, dict)
                        and "baseSnapshotHash" not in record
                        else {}
                    ),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "sourceCardId": external_card_id,
                    "applied": False,
                    "state": "failed",
                    "code": "PROGRESS_IMPORT_FAILED",
                    "error": str(exc),
                }
            )
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
    payload_hash, _legacy_payload_json = _canonical_hash(canonical)
    try:
        payload_json = build_anki_revlog_review_event_payload(
            source_key=str(session.source_key),
            import_session_id=str(session.id),
            external_review_id=external_review_id,
            external_card_id=external_card_id,
            record=canonical,
        )
    except ReviewEventPayloadError as exc:
        raise AnkiSyncError(str(exc)) from exc
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
                authority_route = lock_study_authority_route(
                    db.session,
                    learner_user_id=session.user_id,
                    allow_note_authority=True,
                )
                history_ingested_at = datetime.utcnow().replace(microsecond=0)
                shadow_history: list[
                    study_progress_shadow_mirror_service.ExternalMirrorHistoryEvent
                ] = []
                for current_record in sorted(
                    card_records,
                    key=lambda item: int(item.get("sourceReviewId") or 0),
                ):
                    state, ref = _import_review(session, current_record)
                    if state in {"imported", "repaired"} and ref.review_event is not None:
                        shadow_history.append(
                            study_progress_shadow_mirror_service.ExternalMirrorHistoryEvent(
                                review_event=ref.review_event,
                                source_ref=ref,
                                import_state=state,
                            )
                        )
                    card_results.append(
                        {
                            "sourceReviewId": current_record.get("sourceReviewId"),
                            "sourceCardId": current_record.get("sourceCardId"),
                            "imported": state in {"imported", "repaired"},
                            "state": state,
                        }
                    )
                if shadow_history:
                    source_card = ConnectSourceCardRef.query.filter_by(
                        user_id=session.user_id,
                        source_key=session.source_key,
                        external_card_id=source_card_id,
                    ).with_for_update().first()
                    source_card_obj = (
                        db.session.get(Card, source_card.card_id)
                        if source_card is not None
                        else None
                    )
                    if source_card is None or source_card_obj is None:
                        raise AnkiSyncError("source card has not been mapped")
                    if authority_route.mode_code == "NOTE":
                        locked_subjects = lock_study_session_authority_subjects(
                            db.session,
                            route=authority_route,
                            logical_note_keys=(str(source_card_obj.note_id),),
                            now_utc=history_ingested_at,
                        )
                        locked = locked_subjects.locked_by_logical_note_key[
                            str(source_card_obj.note_id)
                        ]
                        siblings = lock_study_authority_siblings(
                            db.session,
                            route=authority_route,
                            locked=locked,
                            requested_card_id=str(source_card_obj.id),
                        )
                        lock_study_authority_compatibility(
                            db.session,
                            route=authority_route,
                            locked=locked,
                            siblings=siblings,
                        )
                        mirror_plan = (
                            study_progress_shadow_mirror_service.compose_locked_lifecycle_plan(
                                db.session,
                                learner_user_id=session.user_id,
                                note_id=str(source_card_obj.note_id),
                                subject=locked.subject,
                                cards=siblings.cards,
                                progress_rows=siblings.progress_by_card_id.values(),
                                prepared_at=history_ingested_at,
                            )
                        )
                    else:
                        mirror_plan = (
                            study_progress_shadow_mirror_service.prepare_native_mirror(
                                db.session,
                                learner_user_id=session.user_id,
                                cards=(source_card_obj,),
                                now_utc=history_ingested_at,
                            )
                        )
                    study_progress_shadow_mirror_service.append_external_history_facts(
                        mirror_plan,
                        history_events=shadow_history,
                        now_utc=history_ingested_at,
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
