"""First-state NOTE materialization without ``card_progress`` (P9-05b).

Under the ``CANONICAL_V1`` storage profile a never-studied Note gets its
subject envelope, state, one ``CANONICAL`` contributor and one availability
row per Card directly (ADR P9-03 §2.3, §2.5). The rows match what the
projection path derives from the ``new`` CardProgress rows it inserts,
except that no CardProgress row exists and contributors carry no raw
evidence. The caller holds the learner fence and the subject locks and owns
the transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import StudyAuthorityFenceError
from app.services.study_note_card_projection import NoteCardBurial, project_note_card
from app.services.study_progress_contract import MAPPER_VERSION
from app.services.study_progress_shadow_codec import (
    CanonicalDocument,
    StudyProgressCodecError,
    canonical_document,
    canonical_typed_document,
)
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    encode_identity,
    map_card_progress,
)
from models.card import Card
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject

_BULK_CHUNK = 500
_PRISTINE_CARD_KEY = "pristine-card"
_PRISTINE_TIME = datetime(2000, 1, 1)


@dataclass(frozen=True)
class CanonicalPristineItem:
    """One locked pristine Note and its live Cards."""

    note_id: str
    subject: StudyProgressSubject
    cards: tuple[Card, ...]
    starting_ease: float


def pristine_state(starting_ease: float) -> MappedCardProgress:
    """The Algorithm State of a never-reviewed Card with this starting ease.

    It is exactly what ``map_card_progress`` derives from the ``new`` row the
    projection path inserts. Row identity (id, learner, Card, timestamps) is
    not part of Algorithm State, so this in-memory row is never persisted and
    its placeholder identity reaches no stored value.
    """

    mapped = map_card_progress(
        SimpleNamespace(
            id=1,
            user_id=1,
            card_id=_PRISTINE_CARD_KEY,
            queue="new",
            step_index=0,
            due_at=None,
            due_day=None,
            interval_days=0,
            interval_days_raw=0.0,
            is_suspended=False,
            is_buried=False,
            buried_until_day=None,
            review_kind="review",
            scheduler_mode="legacy",
            ease_factor=float(starting_ease),
            memory_stability=None,
            memory_difficulty=None,
            suspension_reason=None,
            last_leech_at=None,
            last_leech_lapses=0,
            last_review_event_id=None,
            reps=0,
            lapses=0,
            last_reviewed_at=None,
            revision=0,
            created_at=_PRISTINE_TIME,
            updated_at=_PRISTINE_TIME,
        ),
        card_created_at=_PRISTINE_TIME,
        card_order_key=_PRISTINE_CARD_KEY,
    )
    if not isinstance(mapped, MappedCardProgress):
        raise StudyAuthorityFenceError(
            "AUTHORITY_MATERIALIZATION_INCOMPLETE",
            f"Pristine state cannot be built: {mapped.code}.",
        )
    return mapped


def _absent_lineage_hash() -> bytes:
    return canonical_typed_document(
        {"references": [{"ref_kind": "LAST_REVIEW_EVENT", "source_row_key": None, "ref_status": "ABSENT"}]},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def finalize_canonical_pristine_materialization(
    session: Session,
    *,
    learner_user_id: int,
    items: Sequence[CanonicalPristineItem],
    provenance_code: str,
    now_utc: datetime,
) -> dict[int, bytes]:
    """Write state, contributors and availability for locked pristine subjects.

    Returns each subject's semantic state hash for its token. Any adapter
    failure or sibling divergence refuses the whole batch.
    """

    from app.services.study_progress_shadow_mirror_service import _use_stored_card_created_at

    _use_stored_card_created_at(
        session, {str(card.id): card for item in items for card in item.cards}
    )
    lineage_hash = _absent_lineage_hash()
    state_by_ease: dict[float, MappedCardProgress] = {}
    contributor_values: list[dict[str, Any]] = []
    pending: dict[tuple[int, bytes], tuple[int, Any]] = {}
    state_values: list[dict[str, Any]] = []
    hash_by_subject: dict[int, bytes] = {}
    cards_by_subject: dict[int, tuple[Card, ...]] = {}
    for item in sorted(items, key=lambda value: value.note_id.encode("utf-8")):
        subject = item.subject
        if int(subject.learner_user_id) != int(learner_user_id):
            raise StudyAuthorityFenceError("WRONG_LEARNER", "A pristine subject belongs to another learner.")
        cards = tuple(sorted(item.cards, key=lambda card: str(card.id).encode("utf-8")))
        if not cards or any(str(card.note_id) != item.note_id for card in cards):
            raise StudyAuthorityFenceError(
                "INCOMPLETE_AUTHORITY_COVERAGE", "New Note authority requires every generated Card."
            )
        ease = float(item.starting_ease)
        state = state_by_ease.get(ease) or state_by_ease.setdefault(ease, pristine_state(ease))
        generation = int(subject.subject_generation)
        try:
            projections = [
                project_note_card(
                    state.state.payload,
                    burial=NoteCardBurial(),
                    card_id=str(card.id),
                    card_created_at=card.created_at,
                )
                for card in cards
            ]
        except StudyProgressCodecError as exc:
            raise StudyAuthorityFenceError("AUTHORITY_MATERIALIZATION_INCOMPLETE", str(exc)) from exc
        semantic = {projection.semantic_state_hash for projection in projections}
        if semantic != {state.semantic_state_hash}:
            raise StudyAuthorityFenceError(
                "AUTHORITY_MATERIALIZATION_INCOMPLETE",
                "New Note authority did not build complete canonical state.",
            )
        for card, projection in zip(cards, projections):
            card_key = encode_identity(str(card.id), max_bytes=144, field_name="logical_card_key")
            contributor_values.append({
                "subject_id": int(subject.id),
                "subject_generation": generation,
                "evidence_kind": "CANONICAL",
                "source_progress_id": None,
                "live_card_progress_id": None,
                "logical_card_key": card_key,
                "live_card_id": str(card.id),
                "card_progress_revision": None,
                "raw_schema_version": None,
                "storage_codec": None,
                "raw_payload": None,
                "raw_payload_size": None,
                "raw_progress_hash": None,
                "pointer_status": "ABSENT",
                "history_completeness_code": "HISTORY_NATIVE_COMPLETE",
                "current_provenance_code": provenance_code,
                "lineage_vector_hash": lineage_hash,
                "contributor_status": "ACTIVE",
                "detached_at": None,
                "created_at": now_utc,
                "updated_at": now_utc,
            })
            pending[(int(subject.id), card_key)] = (generation, projection.availability)
        mirror_revision = int(subject.mirror_revision) + 1
        state_values.append({
            "subject_id": int(subject.id),
            "subject_generation": generation,
            "mirror_revision": mirror_revision,
            "algorithm_key": state.algorithm_key,
            "algorithm_version": state.algorithm_version,
            "state_schema_version": state.state_schema_version,
            "storage_codec": state.storage_codec,
            "state_payload": state.state.payload,
            "state_payload_size": state.state.size,
            "algorithm_state_hash": state.algorithm_state_hash,
            "semantic_state_hash": state.semantic_state_hash,
            "created_at": now_utc,
            "updated_at": now_utc,
        })
        hash_by_subject[int(subject.id)] = state.semantic_state_hash
        cards_by_subject[int(subject.id)] = cards
        subject.live_note_id = item.note_id
        subject.mirror_revision = mirror_revision
        subject.status_code = "MIRRORED_SINGLE" if len(cards) == 1 else "MIRRORED_EQUIVALENT_FANIN"
        subject.contributor_count = len(cards)
        subject.mapper_version = MAPPER_VERSION
        subject.last_mirrored_at = now_utc
        subject.updated_at = now_utc

    contributor_table = StudyProgressContributor.__table__
    for start in range(0, len(contributor_values), _BULK_CHUNK):
        session.execute(contributor_table.insert(), contributor_values[start:start + _BULK_CHUNK])
    contributor_id_by_key: dict[tuple[int, bytes], int] = {}
    subject_ids = sorted(cards_by_subject)
    for start in range(0, len(subject_ids), _BULK_CHUNK):
        chunk = subject_ids[start:start + _BULK_CHUNK]
        for contributor_id, subject_id, card_key, generation in session.execute(
            select(
                StudyProgressContributor.id,
                StudyProgressContributor.subject_id,
                StudyProgressContributor.logical_card_key,
                StudyProgressContributor.subject_generation,
            ).where(
                StudyProgressContributor.subject_id.in_(chunk),
                StudyProgressContributor.contributor_status == "ACTIVE",
            )
        ).all():
            key = (int(subject_id), bytes(card_key))
            if key in pending and int(generation) == pending[key][0]:
                contributor_id_by_key[key] = int(contributor_id)
    if set(contributor_id_by_key) != set(pending):
        raise StudyAuthorityFenceError(
            "AUTHORITY_MATERIALIZATION_INCOMPLETE",
            "A bulk-inserted contributor could not be read back.",
        )

    availability_values = []
    for key, (generation, projection) in pending.items():
        availability_values.append({
            "contributor_id": contributor_id_by_key[key],
            "subject_id": key[0],
            "subject_generation": generation,
            "projection_version": projection.projection_version,
            "normalized_queue": projection.normalized_queue,
            "due_at": projection.due_at,
            "due_day": projection.due_day,
            "is_suspended": projection.is_suspended,
            "is_buried": projection.is_buried,
            "buried_until_day": projection.buried_until_day,
            "card_created_at": projection.card_created_at,
            "card_order_key": projection.card_order_key,
            "state_schema_version": projection.state_schema_version,
            "semantic_state_hash": projection.semantic_state_hash,
            "created_at": now_utc,
            "updated_at": now_utc,
        })
    for table, values in (
        (StudyProgressAvailability.__table__, availability_values),
        (StudyProgressState.__table__, state_values),
    ):
        for start in range(0, len(values), _BULK_CHUNK):
            session.execute(table.insert(), values[start:start + _BULK_CHUNK])

    # Same material as the canonical review writer (ADR P9-03 §2.9).
    for subject_id, cards in cards_by_subject.items():
        subject = next(item.subject for item in items if int(item.subject.id) == subject_id)
        rows = []
        for card in cards:
            key = (subject_id, encode_identity(str(card.id), max_bytes=144, field_name="logical_card_key"))
            rows.append((str(card.id), contributor_id_by_key[key]))
        subject.authority_vector_hash = _digest([
            {
                "card_id": card_id,
                "contributor_id": str(contributor_id),
                "evidence": "CANONICAL",
                "semantic_state_hash": hash_by_subject[subject_id].hex(),
            }
            for card_id, contributor_id in rows
        ])
        subject.lineage_vector_hash = _digest([
            {
                "card_id": card_id,
                "contributor_id": str(contributor_id),
                "lineage_vector_hash": lineage_hash.hex(),
            }
            for card_id, contributor_id in rows
        ])
    session.flush()
    return hash_by_subject


def _digest(contributors: list[dict[str, str]]) -> bytes:
    document: CanonicalDocument = canonical_document(
        {"contributors": contributors}, too_large_code="STATE_PAYLOAD_TOO_LARGE"
    )
    return document.digest
