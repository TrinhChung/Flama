"""Transactional native-writer mirror for Phase 4 learner/Note progress.

The transaction owner calls ``prepare_native_mirror`` before taking any
CardProgress lock and calls ``finalize_native_mirror`` after ReviewEvent ids and
``last_review_event_id`` pointers have been flushed.  This module never commits
or rolls back.  CardProgress and ReviewEvent remain authoritative in Phase 4.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_progress_shadow_repository import (
    assert_subject_finalization_fence,
    lock_subjects_in_canonical_order,
    load_current_contributors,
)
from app.services.study_progress_contract import (
    HISTORY_SCHEMA_VERSION,
    MAPPER_VERSION,
    RAW_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_codec import (
    canonical_document,
    canonical_typed_document,
)
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    MappingFailure,
    build_contributor_evidence,
    encode_identity,
    map_card_progress,
)
from app.validators.review_event import (
    REVIEW_EVENT_PAYLOAD_SCHEMA,
    classify_review_event_payload,
)
from models.card import Card
from models.card_progress import CardProgress
from models.review_event import ReviewEvent
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lineage_ref import StudyProgressLineageRef
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject


_USABLE_SUBJECT_STATUSES = frozenset(
    {
        "MIRRORED_SINGLE",
        "MIRRORED_EQUIVALENT_FANIN",
        "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE",
    }
)
_CORRUPT_MAPPING_CODES = frozenset(
    {
        "STATE_HASH_MISMATCH",
        "STATE_DECODER_UNAVAILABLE",
    }
)
_UNSUPPORTED_MAPPING_CODES = frozenset(
    {
        "UNSUPPORTED_ALGORITHM_IDENTITY",
        "UNSUPPORTED_STATE_SCHEMA",
        "UNSUPPORTED_QUEUE",
    }
)
_SOURCE_PROVENANCE = {
    "native.rest": "NATIVE_DIRECT",
    "native.mcp": "NATIVE_MCP",
    "native.session.commit": "NATIVE_SESSION",
    "native.session.worker": "NATIVE_ASYNC_BATCH",
}
_HISTORY_PAYLOAD_FIELDS = (
    "rating",
    "mode",
    "review_kind",
    "queue_before",
    "queue_after",
    "interval_days_before",
    "interval_days_after",
    "due_day_before",
    "due_day_after",
    "days_late",
    "ease_factor_before",
    "ease_factor_after",
    "memory_stability_before",
    "memory_stability_after",
    "memory_difficulty_before",
    "memory_difficulty_after",
    "leeched_after",
    "suspended_after",
    "sequence_no",
)


class StudyProgressMirrorError(RuntimeError):
    """Unexpected mirror invariant failure; the transaction owner must rollback."""

    code = "MIRROR_INTERNAL_ERROR"


@dataclass(frozen=True)
class NativeMirrorHistoryEvent:
    review_event: ReviewEvent
    before_state_hash: str | bytes | None = None
    after_state_hash: str | bytes | None = None


@dataclass(frozen=True)
class _PreparedSubject:
    note_id: str
    subject: StudyProgressSubject
    expected_generation: int
    expected_mirror_revision: int
    shadow_progress_ids: frozenset[int]
    authority_progress_ids: frozenset[int]


@dataclass
class NativeMirrorPlan:
    session: Session
    learner_user_id: int
    prepared_at: datetime
    subjects_by_note_id: dict[str, _PreparedSubject]
    cards_by_id: dict[str, Card]
    locked_progress_by_card_id: dict[str, CardProgress]
    finalized: bool = False


@dataclass(frozen=True)
class NativeMirrorResult:
    subject_count: int
    contributor_count: int
    history_fact_count: int
    quarantine_count: int
    statuses: tuple[str, ...]


def shadow_writes_enabled() -> bool:
    """Return the default-off P4 writer gate without creating side effects."""

    return bool(current_app.config.get("STUDY_PROGRESS_SHADOW_WRITE_ENABLED", False))


def _utc_naive(value: datetime | None = None) -> datetime:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is not None:
        return moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _metric(name: str, *, status: str | None = None) -> None:
    metrics = current_app.extensions.setdefault(
        "study_progress_shadow_mirror_metrics", Counter()
    )
    key = name if status is None else f"{name}:{status}"
    metrics[key] += 1


def _fail(message: str) -> StudyProgressMirrorError:
    return StudyProgressMirrorError(message)


def prepare_native_mirror(
    session: Session,
    *,
    learner_user_id: int,
    cards: Iterable[Card],
    now_utc: datetime | None = None,
) -> NativeMirrorPlan | None:
    """Lock affected learner/Note subjects and all current CardProgress siblings.

    The function is a strict no-op while the feature flag is disabled.  With the
    flag enabled, lock order is subject keys first and authoritative progress
    rows second, both in canonical binary identity order.
    """

    if not shadow_writes_enabled():
        return None
    prepared_at = _utc_naive(now_utc)
    learner_id = int(learner_user_id)
    supplied_cards = tuple(cards)
    if not supplied_cards:
        return None

    note_ids: set[str] = set()
    for card in supplied_cards:
        note_id = str(getattr(card, "note_id", "") or "")
        card_id = str(getattr(card, "id", "") or "")
        if not note_id or not card_id:
            raise _fail("Native mirror requires attached Card and Note identities.")
        note_ids.add(note_id)

    subjects = lock_subjects_in_canonical_order(
        session,
        (
            (learner_id, note_id, note_id)
            for note_id in sorted(note_ids, key=lambda value: value.encode("utf-8"))
        ),
        now_utc=prepared_at,
    )
    subject_by_key = {bytes(row.logical_note_key): row for row in subjects}

    sibling_cards = tuple(
        session.execute(
            select(Card)
            .where(Card.note_id.in_(sorted(note_ids)))
            .order_by(Card.id.asc())
        ).scalars()
    )
    cards_by_id = {str(card.id): card for card in sibling_cards}
    for card in supplied_cards:
        if str(card.id) not in cards_by_id:
            raise _fail("A native mirror Card disappeared before subject locking.")

    card_ids = sorted(cards_by_id)
    progress_rows = tuple(
        session.execute(
            select(CardProgress)
            .where(
                CardProgress.user_id == learner_id,
                CardProgress.card_id.in_(card_ids),
            )
            .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
            .with_for_update()
        ).scalars()
    ) if card_ids else ()
    locked_progress_by_card_id = {
        str(row.card_id): row for row in progress_rows if row.card_id is not None
    }

    authority_ids_by_note: dict[str, set[int]] = {note_id: set() for note_id in note_ids}
    for progress in progress_rows:
        card = cards_by_id.get(str(progress.card_id))
        if card is None:
            raise _fail("Locked CardProgress has no current Card in the mirror scope.")
        authority_ids_by_note[str(card.note_id)].add(int(progress.id))

    prepared_subjects: dict[str, _PreparedSubject] = {}
    for note_id in sorted(note_ids, key=lambda value: value.encode("utf-8")):
        subject = subject_by_key.get(note_id.encode("utf-8"))
        if subject is None:
            raise _fail("Subject lock did not return the requested learner/Note row.")
        current_contributors = load_current_contributors(
            session,
            subject_id=int(subject.id),
            subject_generation=int(subject.subject_generation),
            for_update=True,
        )
        shadow_ids = frozenset(
            int(row.live_card_progress_id)
            for row in current_contributors
            if row.live_card_progress_id is not None
        )
        prepared_subjects[note_id] = _PreparedSubject(
            note_id=note_id,
            subject=subject,
            expected_generation=int(subject.subject_generation),
            expected_mirror_revision=int(subject.mirror_revision),
            shadow_progress_ids=shadow_ids,
            authority_progress_ids=frozenset(authority_ids_by_note[note_id]),
        )

    _metric("prepare")
    return NativeMirrorPlan(
        session=session,
        learner_user_id=learner_id,
        prepared_at=prepared_at,
        subjects_by_note_id=prepared_subjects,
        cards_by_id=cards_by_id,
        locked_progress_by_card_id=locked_progress_by_card_id,
    )


def locked_progress_map(plan: NativeMirrorPlan | None) -> dict[str, CardProgress]:
    """Expose the progress locks acquired by prepare to the transaction owner."""

    if plan is None:
        return {}
    return plan.locked_progress_by_card_id


def _decode_digest(value: str | bytes | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        if len(value) != 32:
            raise _fail("A supplied history digest is not 32 bytes.")
        return value
    token = str(value).strip()
    for prefix in ("sha256-", "sha256:"):
        if token.startswith(prefix):
            token = token[len(prefix) :]
            break
    if len(token) != 64:
        raise _fail("A supplied history digest is not canonical SHA-256.")
    try:
        decoded = bytes.fromhex(token)
    except ValueError as exc:
        raise _fail("A supplied history digest is not hexadecimal.") from exc
    if len(decoded) != 32:  # pragma: no cover - guarded by token length
        raise _fail("A supplied history digest is not 32 bytes.")
    return decoded


def _event_payload(event: ReviewEvent) -> dict[str, Any]:
    disposition = classify_review_event_payload(
        event.payload_json,
        scheduler_algorithm=event.scheduler_algorithm,
        algorithm_version=event.algorithm_version,
        scheduler_config_hash=event.scheduler_config_hash,
        study_session_id=event.study_session_id,
        client_event_id=event.client_event_id,
        sequence_no=event.sequence_no,
    )
    if disposition.category != "complete":
        raise _fail(
            "A newly written native ReviewEvent has invalid provenance: "
            f"{disposition.reason}."
        )
    try:
        payload = json.loads(event.payload_json)
    except (TypeError, ValueError) as exc:  # pragma: no cover - classifier covers it
        raise _fail("A newly written native ReviewEvent payload cannot be decoded.") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != REVIEW_EVENT_PAYLOAD_SCHEMA
    ):
        raise _fail("A newly written native ReviewEvent payload has no schema identity.")
    return payload


def _event_provenance(event: ReviewEvent) -> tuple[str, dict[str, Any], dict[str, Any]]:
    payload = _event_payload(event)
    provenance = payload.get("provenance")
    runtime = payload.get("_study_runtime")
    if not isinstance(provenance, dict) or not isinstance(runtime, dict):
        raise _fail("A newly written native ReviewEvent lacks runtime provenance.")
    source_path = str(provenance.get("source_path") or "")
    code = _SOURCE_PROVENANCE.get(source_path)
    if code is None:
        raise _fail(f"Unsupported native mirror source path: {source_path!r}.")
    return code, provenance, runtime


def _pointer_evidence(
    progress: CardProgress,
    event_by_id: Mapping[int, ReviewEvent],
) -> tuple[str, dict[str, Any]]:
    event_id = progress.last_review_event_id
    if event_id is None:
        return "ABSENT", {
            "ref_kind": "LAST_REVIEW_EVENT",
            "source_row_key": None,
            "ref_status": "ABSENT",
        }
    event = event_by_id.get(int(event_id))
    status = "VALID"
    if event is None:
        status = "MISSING_EVENT"
    elif int(event.user_id) != int(progress.user_id):
        status = "LEARNER_MISMATCH"
    elif str(event.card_id) != str(progress.card_id):
        status = "CARD_MISMATCH"
    else:
        disposition = classify_review_event_payload(
            event.payload_json,
            scheduler_algorithm=event.scheduler_algorithm,
            algorithm_version=event.algorithm_version,
            scheduler_config_hash=event.scheduler_config_hash,
            study_session_id=event.study_session_id,
            client_event_id=event.client_event_id,
            sequence_no=event.sequence_no,
        )
        if disposition.category == "complete":
            try:
                parsed = json.loads(event.payload_json)
            except (TypeError, ValueError):  # pragma: no cover - classifier covers it
                parsed = {}
            provenance = parsed.get("provenance") if isinstance(parsed, dict) else None
            if isinstance(provenance, dict) and provenance.get("kind") == "external":
                status = "EXTERNAL_POINTED"
        elif disposition.category != "legacy_unknown":
            status = "PAYLOAD_MISMATCH"
    return status, {
        "ref_kind": "LAST_REVIEW_EVENT",
        "source_row_key": str(event_id),
        "ref_status": status,
        "occurred_at": event.reviewed_at if event is not None else None,
        "source_payload_hash": (
            hashlib.sha256(str(event.payload_json).encode("utf-8")).digest()
            if event is not None
            else None
        ),
    }


def _lineage_material(row: StudyProgressLineageRef) -> dict[str, Any]:
    return {
        "ref_kind": row.ref_kind,
        "source_row_key": bytes(row.source_row_key).hex(),
        "source_key": bytes(row.source_key).hex() if row.source_key is not None else None,
        "external_card_id": (
            bytes(row.external_card_id).hex() if row.external_card_id is not None else None
        ),
        "external_note_id": (
            bytes(row.external_note_id).hex() if row.external_note_id is not None else None
        ),
        "source_snapshot_hash": (
            bytes(row.source_snapshot_hash).hex()
            if row.source_snapshot_hash is not None
            else None
        ),
        "source_payload_hash": (
            bytes(row.source_payload_hash).hex()
            if row.source_payload_hash is not None
            else None
        ),
        "ref_status": row.ref_status,
        "occurred_at": row.occurred_at,
    }


def _sync_pointer_lineage(
    session: Session,
    *,
    contributor: StudyProgressContributor,
    generation: int,
    pointer: dict[str, Any],
    now_utc: datetime,
) -> bytes:
    existing = tuple(
        session.execute(
            select(StudyProgressLineageRef)
            .where(StudyProgressLineageRef.contributor_id == contributor.id)
            .order_by(
                StudyProgressLineageRef.ref_kind.asc(),
                StudyProgressLineageRef.source_row_key.asc(),
                StudyProgressLineageRef.id.asc(),
            )
            .with_for_update()
        ).scalars()
    )
    pointer_rows = [row for row in existing if row.ref_kind == "LAST_REVIEW_EVENT"]
    external_rows = [row for row in existing if row.ref_kind != "LAST_REVIEW_EVENT"]
    for row in external_rows:
        row.subject_generation = generation

    desired_key = pointer.get("source_row_key")
    if desired_key is None:
        for row in pointer_rows:
            session.delete(row)
        lineage_payload = [
            {
                "ref_kind": "LAST_REVIEW_EVENT",
                "source_row_key": None,
                "ref_status": "ABSENT",
            },
            *[_lineage_material(row) for row in external_rows],
        ]
    else:
        encoded_key = encode_identity(
            str(desired_key), max_bytes=144, field_name="source_row_key"
        )
        selected = next(
            (row for row in pointer_rows if bytes(row.source_row_key) == encoded_key),
            None,
        )
        for row in pointer_rows:
            if row is not selected:
                session.delete(row)
        if selected is None:
            selected = StudyProgressLineageRef(
                contributor_id=int(contributor.id),
                subject_generation=generation,
                ref_kind="LAST_REVIEW_EVENT",
                source_row_key=encoded_key,
                ref_status=str(pointer["ref_status"]),
                ingested_at=now_utc,
            )
            session.add(selected)
        selected.subject_generation = generation
        selected.ref_status = str(pointer["ref_status"])
        selected.occurred_at = pointer.get("occurred_at")
        selected.source_payload_hash = pointer.get("source_payload_hash")
        selected.ingested_at = now_utc
        lineage_payload = [
            _lineage_material(selected),
            *[_lineage_material(row) for row in external_rows],
        ]

    lineage_payload.sort(
        key=lambda value: (
            str(value.get("ref_kind") or ""),
            str(value.get("source_row_key") or ""),
        )
    )
    return canonical_typed_document(
        {"references": lineage_payload},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def _mapping_quarantine(code: str) -> str:
    if code in _UNSUPPORTED_MAPPING_CODES:
        return "QUARANTINED_UNSUPPORTED_STATE"
    if code in _CORRUPT_MAPPING_CODES:
        return "QUARANTINED_CORRUPT_STATE"
    return "QUARANTINED_UNCLASSIFIED_CONTEXT"


def _upsert_availability(
    session: Session,
    *,
    contributor: StudyProgressContributor,
    mapped: MappedCardProgress,
    generation: int,
    now_utc: datetime,
) -> None:
    projection = mapped.availability
    row = session.execute(
        select(StudyProgressAvailability)
        .where(StudyProgressAvailability.contributor_id == contributor.id)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        row = StudyProgressAvailability(
            contributor_id=int(contributor.id),
            subject_id=int(contributor.subject_id),
            created_at=now_utc,
        )
        session.add(row)
    row.subject_generation = generation
    row.projection_version = projection.projection_version
    row.normalized_queue = projection.normalized_queue
    row.due_at = projection.due_at
    row.due_day = projection.due_day
    row.is_suspended = projection.is_suspended
    row.is_buried = projection.is_buried
    row.buried_until_day = projection.buried_until_day
    row.card_created_at = projection.card_created_at
    row.card_order_key = projection.card_order_key
    row.state_schema_version = projection.state_schema_version
    row.semantic_state_hash = projection.semantic_state_hash
    row.updated_at = now_utc


def _upsert_state(
    session: Session,
    *,
    subject: StudyProgressSubject,
    mapped: MappedCardProgress,
    generation: int,
    mirror_revision: int,
    now_utc: datetime,
) -> None:
    row = session.execute(
        select(StudyProgressState)
        .where(StudyProgressState.subject_id == subject.id)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        row = StudyProgressState(subject_id=int(subject.id), created_at=now_utc)
        session.add(row)
    row.subject_generation = generation
    row.mirror_revision = mirror_revision
    row.algorithm_key = mapped.algorithm_key
    row.algorithm_version = mapped.algorithm_version
    row.state_schema_version = mapped.state_schema_version
    row.storage_codec = mapped.storage_codec
    row.state_payload = mapped.state.payload
    row.state_payload_size = mapped.state.size
    row.algorithm_state_hash = mapped.algorithm_state_hash
    row.semantic_state_hash = mapped.semantic_state_hash
    row.updated_at = now_utc


def _remove_usable_state(session: Session, subject_id: int) -> None:
    row = session.execute(
        select(StudyProgressState)
        .where(StudyProgressState.subject_id == subject_id)
        .with_for_update()
    ).scalar_one_or_none()
    if row is not None:
        session.delete(row)


def _history_input(value: ReviewEvent | NativeMirrorHistoryEvent) -> NativeMirrorHistoryEvent:
    if isinstance(value, NativeMirrorHistoryEvent):
        return value
    return NativeMirrorHistoryEvent(review_event=value)


def _append_history_facts(
    session: Session,
    *,
    plan: NativeMirrorPlan,
    generation_by_note: Mapping[str, int],
    contributors_by_progress_id: Mapping[int, StudyProgressContributor],
    completeness_by_progress_id: Mapping[int, str],
    events: Sequence[ReviewEvent | NativeMirrorHistoryEvent],
    now_utc: datetime,
) -> int:
    inserted = 0
    for supplied in events:
        history = _history_input(supplied)
        event = history.review_event
        if event.id is None:
            raise _fail("Native mirror finalization requires flushed ReviewEvent ids.")
        if int(event.user_id) != plan.learner_user_id:
            raise _fail("Native mirror ReviewEvent learner does not match its plan.")
        card = plan.cards_by_id.get(str(event.card_id))
        if card is None:
            raise _fail("Native mirror ReviewEvent Card is outside its prepared subjects.")
        progress = plan.locked_progress_by_card_id.get(str(event.card_id))
        if progress is None or progress.id is None:
            raise _fail("Native mirror ReviewEvent has no final CardProgress contributor.")
        contributor = contributors_by_progress_id.get(int(progress.id))
        if contributor is None:
            raise _fail("Native mirror history cannot resolve its contributor.")
        provenance_code, provenance, runtime = _event_provenance(event)
        fact_identity = canonical_document(
            {"review_event_id": str(event.id), "source": "review_events"},
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        ).digest
        existing = session.execute(
            select(StudyProgressHistoryFact)
            .where(
                StudyProgressHistoryFact.learner_user_id == plan.learner_user_id,
                StudyProgressHistoryFact.fact_identity_hash == fact_identity,
            )
            .with_for_update()
        ).scalar_one_or_none()

        fact_material = {
            field: getattr(event, field)
            for field in _HISTORY_PAYLOAD_FIELDS
        }
        fact_material["review_event_id"] = int(event.id)
        fact = canonical_typed_document(
            fact_material,
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        )
        if existing is not None:
            if (
                existing.review_event_id != int(event.id)
                or bytes(existing.fact_payload_hash) != fact.digest
            ):
                raise _fail("History fact identity was reused with different evidence.")
            continue

        operation_key = (
            provenance.get("request_id")
            or provenance.get("client_event_id")
            or provenance.get("study_session_id")
            or f"review-event:{event.id}"
        )
        source_operation_key = encode_identity(
            str(operation_key),
            max_bytes=512,
            field_name="source_operation_key",
        )
        note_id = str(card.note_id)
        completeness = completeness_by_progress_id[int(progress.id)]
        session.add(
            StudyProgressHistoryFact(
                learner_user_id=plan.learner_user_id,
                subject_id=int(contributor.subject_id),
                logical_note_key=note_id.encode("utf-8"),
                subject_generation=generation_by_note[note_id],
                contributor_id=int(contributor.id),
                logical_card_key=encode_identity(
                    str(event.card_id), max_bytes=256, field_name="logical_card_key"
                ),
                review_event_id=int(event.id),
                fact_identity_hash=fact_identity,
                history_schema_version=HISTORY_SCHEMA_VERSION,
                storage_codec=STORAGE_CODEC,
                occurred_at=_utc_naive(event.reviewed_at),
                ingested_at=now_utc,
                provenance_code=provenance_code,
                source_operation_key=source_operation_key,
                action_key=str(runtime.get("action_key") or "") or None,
                action_version=(
                    str(runtime.get("action_contract_version") or "") or None
                ),
                review_kind=str(event.review_kind or "") or None,
                algorithm_key=str(runtime.get("algorithm_key") or "") or None,
                algorithm_version=(
                    str(runtime.get("algorithm_version") or "") or None
                ),
                state_schema_version=(
                    str(runtime.get("state_schema_version") or "") or None
                ),
                scheduler_config_hash=_decode_digest(event.scheduler_config_hash),
                before_state_hash=_decode_digest(history.before_state_hash),
                after_state_hash=_decode_digest(history.after_state_hash),
                history_completeness_code=completeness,
                gap_reason_code=(
                    None if completeness == "HISTORY_NATIVE_COMPLETE" else "LEGACY_GAP"
                ),
                fact_payload=fact.payload,
                fact_payload_size=fact.size,
                fact_payload_hash=fact.digest,
                created_at=now_utc,
            )
        )
        inserted += 1
    return inserted


def finalize_native_mirror(
    plan: NativeMirrorPlan | None,
    *,
    review_events: Sequence[ReviewEvent | NativeMirrorHistoryEvent],
    now_utc: datetime | None = None,
) -> NativeMirrorResult | None:
    """Finalize each prepared learner/Note exactly once without committing."""

    if plan is None:
        return None
    if plan.finalized:
        raise _fail("A native mirror plan may be finalized only once.")
    plan.finalized = True
    session = plan.session
    finalized_at = _utc_naive(now_utc)
    try:
        # Flush both event ids and final CardProgress pointer/timestamp values.
        session.flush()

        card_ids = sorted(plan.cards_by_id)
        final_progress_rows = tuple(
            session.execute(
                select(CardProgress)
                .where(
                    CardProgress.user_id == plan.learner_user_id,
                    CardProgress.card_id.in_(card_ids),
                )
                .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
                .with_for_update()
            ).scalars()
        ) if card_ids else ()
        plan.locked_progress_by_card_id = {
            str(row.card_id): row
            for row in final_progress_rows
            if row.card_id is not None
        }
        pointer_ids = sorted(
            {
                int(row.last_review_event_id)
                for row in final_progress_rows
                if row.last_review_event_id is not None
            }
        )
        event_by_id = {
            int(row.id): row
            for row in session.execute(
                select(ReviewEvent)
                .where(ReviewEvent.id.in_(pointer_ids))
                .with_for_update()
            ).scalars()
        } if pointer_ids else {}

        new_event_by_card: dict[str, ReviewEvent] = {}
        for supplied in review_events:
            event = _history_input(supplied).review_event
            if event.id is None:
                raise _fail("Native mirror received an unflushed ReviewEvent.")
            new_event_by_card[str(event.card_id)] = event

        progress_by_note: dict[str, list[CardProgress]] = {
            note_id: [] for note_id in plan.subjects_by_note_id
        }
        for progress in final_progress_rows:
            card = plan.cards_by_id.get(str(progress.card_id))
            if card is None:
                raise _fail("Final CardProgress has no prepared Card identity.")
            progress_by_note[str(card.note_id)].append(progress)

        contributors_by_progress_id: dict[int, StudyProgressContributor] = {}
        completeness_by_progress_id: dict[int, str] = {}
        generation_by_note: dict[str, int] = {}
        statuses: list[str] = []
        quarantine_count = 0
        contributor_total = 0

        for note_id in sorted(
            plan.subjects_by_note_id, key=lambda value: value.encode("utf-8")
        ):
            prepared = plan.subjects_by_note_id[note_id]
            subject = prepared.subject
            assert_subject_finalization_fence(
                subject,
                expected_generation=prepared.expected_generation,
                expected_mirror_revision=prepared.expected_mirror_revision,
            )
            rows = sorted(
                progress_by_note[note_id],
                key=lambda row: (str(row.card_id).encode("utf-8"), int(row.id)),
            )
            final_ids = frozenset(int(row.id) for row in rows)
            if (
                prepared.expected_mirror_revision > 0
                and prepared.shadow_progress_ids != final_ids
            ):
                generation = prepared.expected_generation + 1
            else:
                generation = prepared.expected_generation
            mirror_revision = prepared.expected_mirror_revision + 1
            generation_by_note[note_id] = generation

            prior_contributors = tuple(
                session.execute(
                    select(StudyProgressContributor)
                    .where(StudyProgressContributor.subject_id == subject.id)
                    .order_by(
                        StudyProgressContributor.logical_card_key.asc(),
                        StudyProgressContributor.id.asc(),
                    )
                    .with_for_update()
                ).scalars()
            )
            prior_by_progress_id = {
                int(row.live_card_progress_id): row
                for row in prior_contributors
                if row.live_card_progress_id is not None
            }
            stale_active = set(prior_by_progress_id) - set(final_ids)
            if stale_active:
                raise _fail(
                    "Native mirror found stale active contributors; lifecycle projection "
                    "must run before an authoritative removal."
                )

            mapped_by_progress_id: dict[int, MappedCardProgress | MappingFailure] = {}
            pointer_by_progress_id: dict[int, tuple[str, dict[str, Any]]] = {}
            provenance_by_progress_id: dict[int, str] = {}
            lineage_by_progress_id: dict[int, bytes] = {}

            # Create contributor identities first so lineage/availability/history can bind.
            for progress in rows:
                progress_id = int(progress.id)
                card = plan.cards_by_id[str(progress.card_id)]
                mapped = map_card_progress(
                    progress,
                    card_created_at=card.created_at,
                    card_order_key=str(card.id),
                )
                if isinstance(mapped, MappingFailure) and mapped.raw is None:
                    raise _fail(
                        f"CardProgress {progress_id} could not retain bounded raw evidence: "
                        f"{mapped.code}."
                    )
                mapped_by_progress_id[progress_id] = mapped
                pointer_by_progress_id[progress_id] = _pointer_evidence(
                    progress, event_by_id
                )
                prior = prior_by_progress_id.get(progress_id)
                new_event = new_event_by_card.get(str(progress.card_id))
                if new_event is not None:
                    provenance_code, _provenance, _runtime = _event_provenance(new_event)
                elif prior is not None:
                    provenance_code = str(prior.current_provenance_code)
                else:
                    provenance_code = "UNKNOWN_LEGACY"
                provenance_by_progress_id[progress_id] = provenance_code

                is_new_authority = progress_id not in prepared.authority_progress_ids
                if is_new_authority:
                    completeness = "HISTORY_NATIVE_COMPLETE"
                elif prior is not None and generation == prepared.expected_generation:
                    completeness = str(prior.history_completeness_code)
                else:
                    completeness = "HISTORY_UNKNOWN"
                completeness_by_progress_id[progress_id] = completeness

                contributor = prior
                raw = mapped.raw
                if contributor is None:
                    contributor = StudyProgressContributor(
                        subject_id=int(subject.id),
                        subject_generation=generation,
                        source_progress_id=progress_id,
                        live_card_progress_id=progress_id,
                        logical_card_key=encode_identity(
                            str(progress.card_id),
                            max_bytes=144,
                            field_name="logical_card_key",
                        ),
                        live_card_id=str(progress.card_id),
                        card_progress_revision=int(progress.revision),
                        raw_schema_version=RAW_SCHEMA_VERSION,
                        storage_codec=STORAGE_CODEC,
                        raw_payload=raw.payload,
                        raw_payload_size=raw.size,
                        raw_progress_hash=raw.digest,
                        pointer_status=pointer_by_progress_id[progress_id][0],
                        history_completeness_code=completeness,
                        current_provenance_code=provenance_code,
                        lineage_vector_hash=b"\x00" * 32,
                        contributor_status="ACTIVE",
                        created_at=finalized_at,
                        updated_at=finalized_at,
                    )
                    session.add(contributor)
                else:
                    if int(contributor.subject_id) != int(subject.id):
                        raise _fail("A live CardProgress contributor is attached elsewhere.")
                    contributor.subject_generation = generation
                    contributor.card_progress_revision = int(progress.revision)
                    contributor.raw_schema_version = RAW_SCHEMA_VERSION
                    contributor.storage_codec = STORAGE_CODEC
                    contributor.raw_payload = raw.payload
                    contributor.raw_payload_size = raw.size
                    contributor.raw_progress_hash = raw.digest
                    contributor.pointer_status = pointer_by_progress_id[progress_id][0]
                    contributor.history_completeness_code = completeness
                    contributor.current_provenance_code = provenance_code
                    contributor.contributor_status = "ACTIVE"
                    contributor.detached_at = None
                    contributor.updated_at = finalized_at
                contributors_by_progress_id[progress_id] = contributor

            session.flush()

            for progress in rows:
                progress_id = int(progress.id)
                contributor = contributors_by_progress_id[progress_id]
                pointer_status, pointer = pointer_by_progress_id[progress_id]
                lineage_hash = _sync_pointer_lineage(
                    session,
                    contributor=contributor,
                    generation=generation,
                    pointer=pointer,
                    now_utc=finalized_at,
                )
                lineage_by_progress_id[progress_id] = lineage_hash
                mapped = mapped_by_progress_id[progress_id]
                if isinstance(mapped, MappedCardProgress):
                    evidence = build_contributor_evidence(
                        mapped,
                        progress,
                        subject_generation=generation,
                        pointer_status=pointer_status,
                        history_completeness_code=(
                            completeness_by_progress_id[progress_id]
                        ),
                        current_provenance_code=provenance_by_progress_id[progress_id],
                        lineage_vector_hash=lineage_hash,
                    )
                    contributor.subject_generation = evidence.subject_generation
                    contributor.source_progress_id = evidence.source_progress_id
                    contributor.live_card_progress_id = evidence.live_card_progress_id
                    contributor.logical_card_key = evidence.logical_card_key
                    contributor.live_card_id = evidence.live_card_id
                    contributor.card_progress_revision = evidence.card_progress_revision
                    contributor.raw_schema_version = evidence.raw_schema_version
                    contributor.storage_codec = evidence.storage_codec
                    contributor.raw_payload = evidence.raw.payload
                    contributor.raw_payload_size = evidence.raw.size
                    contributor.raw_progress_hash = evidence.raw.digest
                    contributor.pointer_status = evidence.pointer_status
                    contributor.history_completeness_code = (
                        evidence.history_completeness_code
                    )
                    contributor.current_provenance_code = (
                        evidence.current_provenance_code
                    )
                    contributor.lineage_vector_hash = evidence.lineage_vector_hash
                    contributor.contributor_status = evidence.contributor_status
                    _upsert_availability(
                        session,
                        contributor=contributor,
                        mapped=mapped,
                        generation=generation,
                        now_utc=finalized_at,
                    )
                else:
                    contributor.lineage_vector_hash = lineage_hash
                    availability = session.execute(
                        select(StudyProgressAvailability)
                        .where(
                            StudyProgressAvailability.contributor_id
                            == contributor.id
                        )
                        .with_for_update()
                    ).scalar_one_or_none()
                    if availability is not None:
                        session.delete(availability)

            mapped_rows = [
                value
                for value in mapped_by_progress_id.values()
                if isinstance(value, MappedCardProgress)
            ]
            failures = [
                value
                for value in mapped_by_progress_id.values()
                if isinstance(value, MappingFailure)
            ]
            if not rows:
                status = "NO_CURRENT_PROGRESS"
            elif failures:
                status = _mapping_quarantine(failures[0].code)
            else:
                semantic_hashes = {value.semantic_state_hash for value in mapped_rows}
                if len(semantic_hashes) != 1:
                    status = "QUARANTINED_STATE_DIVERGENCE"
                elif len(mapped_rows) == 1:
                    status = "MIRRORED_SINGLE"
                elif len(set(lineage_by_progress_id.values())) == 1:
                    status = "MIRRORED_EQUIVALENT_FANIN"
                else:
                    status = "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE"

            authority_vector = canonical_document(
                {
                    "contributors": [
                        {
                            "card_id": str(row.card_id),
                            "progress_id": str(row.id),
                            "raw_progress_hash": bytes(
                                contributors_by_progress_id[int(row.id)].raw_progress_hash
                            ).hex(),
                            "revision": str(row.revision),
                        }
                        for row in rows
                    ]
                },
                too_large_code="STATE_PAYLOAD_TOO_LARGE",
            ).digest if rows else None
            lineage_vector = canonical_document(
                {
                    "contributors": [
                        {
                            "card_id": str(row.card_id),
                            "lineage_vector_hash": lineage_by_progress_id[
                                int(row.id)
                            ].hex(),
                            "progress_id": str(row.id),
                        }
                        for row in rows
                    ]
                },
                too_large_code="STATE_PAYLOAD_TOO_LARGE",
            ).digest if rows else None

            if status in _USABLE_SUBJECT_STATUSES:
                _upsert_state(
                    session,
                    subject=subject,
                    mapped=mapped_rows[0],
                    generation=generation,
                    mirror_revision=mirror_revision,
                    now_utc=finalized_at,
                )
            else:
                _remove_usable_state(session, int(subject.id))
                if status.startswith("QUARANTINED_"):
                    quarantine_count += 1

            subject.live_note_id = note_id
            subject.subject_generation = generation
            subject.mirror_revision = mirror_revision
            subject.status_code = status
            subject.contributor_count = len(rows)
            subject.authority_vector_hash = authority_vector
            subject.lineage_vector_hash = lineage_vector
            subject.mapper_version = MAPPER_VERSION
            subject.last_mirrored_at = finalized_at
            subject.updated_at = finalized_at
            contributor_total += len(rows)
            statuses.append(status)

        session.flush()
        history_fact_count = _append_history_facts(
            session,
            plan=plan,
            generation_by_note=generation_by_note,
            contributors_by_progress_id=contributors_by_progress_id,
            completeness_by_progress_id=completeness_by_progress_id,
            events=review_events,
            now_utc=finalized_at,
        )
        session.flush()
        for status in statuses:
            _metric("finalize", status=status)
        result = NativeMirrorResult(
            subject_count=len(statuses),
            contributor_count=contributor_total,
            history_fact_count=history_fact_count,
            quarantine_count=quarantine_count,
            statuses=tuple(statuses),
        )
        current_app.logger.info(
            "study_progress_shadow_mirror finalized subjects=%d contributors=%d "
            "facts=%d quarantines=%d statuses=%s",
            result.subject_count,
            result.contributor_count,
            result.history_fact_count,
            result.quarantine_count,
            ",".join(result.statuses),
        )
        return result
    except Exception:
        _metric("internal_error")
        raise
