"""Explicit, transaction-neutral learner authority enrollment transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    LockedStudyAuthorityCompatibility,
    LockedStudyAuthoritySiblings,
    LockedStudyAuthoritySubject,
    StudyAuthorityFenceError,
    StudyAuthorityRoute,
    lock_study_authority_compatibility,
    lock_study_authority_siblings,
    lock_study_authority_subject,
)
from app.services import study_progress_lifecycle_mirror_service
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    MappingFailure,
    map_card_progress,
)
from models.card import Card
from models.card_progress import CardProgress
from models.deck_install import DeckInstall
from models.note import Note
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.user import User


class StudyAuthorityEnrollmentError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


@dataclass(frozen=True)
class StudyAuthorityEnrollmentResult:
    learner_user_id: int
    previous_mode: str
    previous_epoch: int
    mode_code: str
    epoch: int
    subject_count: int
    card_count: int
    cancelled_session_count: int


def _fail(code: str, message: str) -> StudyAuthorityEnrollmentError:
    return StudyAuthorityEnrollmentError(code, message)


def _verify_lossless_legacy_projection(
    *,
    locked: LockedStudyAuthoritySubject,
    siblings: LockedStudyAuthoritySiblings,
    compatibility: LockedStudyAuthorityCompatibility,
) -> None:
    """Prove every legacy row is an exact projection of one NOTE state."""

    state = locked.state
    if state is None:
        raise _fail(
            "AUTHORITY_STATE_REQUIRED",
            "Authority transition requires an existing Note state.",
        )
    subject = locked.subject
    expected_cards = set(siblings.card_ids)
    if (
        int(subject.contributor_count) != len(expected_cards)
        or set(siblings.progress_by_card_id) != expected_cards
        or set(compatibility.contributor_by_card_id) != expected_cards
    ):
        raise _fail(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "Authority subject does not have one complete legacy projection per Card.",
        )

    card_by_id = {str(card.id): card for card in siblings.cards}
    for card_id in sorted(expected_cards, key=lambda value: value.encode("utf-8")):
        progress = siblings.progress_by_card_id[card_id]
        mapped = map_card_progress(
            progress,
            card_created_at=card_by_id[card_id].created_at,
            card_order_key=card_id,
        )
        if isinstance(mapped, MappingFailure) or not isinstance(
            mapped, MappedCardProgress
        ):
            code = mapped.code if isinstance(mapped, MappingFailure) else "UNKNOWN"
            raise _fail(
                "UNPROJECTABLE_LEGACY_STATE",
                f"Card {card_id} cannot prove a lossless legacy projection: {code}.",
            )
        if (
            mapped.algorithm_key != state.algorithm_key
            or mapped.algorithm_version != state.algorithm_version
            or mapped.state_schema_version != state.state_schema_version
            or mapped.storage_codec != state.storage_codec
            or mapped.state.payload != state.state_payload
            or mapped.state.size != int(state.state_payload_size)
            or mapped.algorithm_state_hash != bytes(state.algorithm_state_hash)
            or mapped.semantic_state_hash != bytes(state.semantic_state_hash)
        ):
            raise _fail(
                "LOSSY_LEGACY_PROJECTION",
                f"Card {card_id} does not encode the current authoritative Note state.",
            )

        contributor = compatibility.contributor_by_card_id[card_id]
        availability = compatibility.availability_by_contributor_id.get(
            int(contributor.id)
        )
        projected = mapped.availability
        if availability is None or (
            availability.projection_version != projected.projection_version
            or availability.normalized_queue != projected.normalized_queue
            or availability.due_at != projected.due_at
            or availability.due_day != projected.due_day
            or bool(availability.is_suspended) != projected.is_suspended
            or bool(availability.is_buried) != projected.is_buried
            or availability.buried_until_day != projected.buried_until_day
            or availability.card_created_at != projected.card_created_at
            or bytes(availability.card_order_key) != projected.card_order_key
            or availability.state_schema_version != projected.state_schema_version
            or bytes(availability.semantic_state_hash)
            != projected.semantic_state_hash
        ):
            raise _fail(
                "STALE_AUTHORITY_AVAILABILITY",
                f"Card {card_id} availability does not match its legacy projection.",
            )


def _cancel_open_sessions(
    session: Session,
    *,
    learner_user_id: int,
) -> int:
    open_sessions = tuple(
        session.execute(
            select(StudySession)
            .where(
                StudySession.user_id == learner_user_id,
                StudySession.status == "open",
            )
            .order_by(StudySession.id.asc())
            .with_for_update()
        ).scalars()
    )
    open_session_ids = [row.id for row in open_sessions]
    if open_session_ids:
        pending_batch = session.execute(
            select(StudySessionBatch.id)
            .where(
                StudySessionBatch.session_id.in_(open_session_ids),
                StudySessionBatch.status.in_(("enqueued", "processing", "retrying")),
            )
            .limit(1)
            .with_for_update()
        ).scalar_one_or_none()
        if pending_batch is not None:
            raise _fail(
                "AUTHORITY_BATCH_IN_FLIGHT",
                "Learner has an asynchronous Study batch still in flight.",
            )
    for study_session in open_sessions:
        study_session.status = "cancelled"
    return len(open_sessions)


def stage_note_authority_enrollment(
    session: Session,
    *,
    learner_user_id: int,
    now_utc: datetime,
) -> StudyAuthorityEnrollmentResult:
    """Fence, prove existing-state coverage, then stage LEGACY -> NOTE."""

    if (
        isinstance(learner_user_id, bool)
        or not isinstance(learner_user_id, int)
        or learner_user_id <= 0
    ):
        raise _fail("INVALID_LEARNER_ID", "Learner ID must be positive.")
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail(
            "INVALID_AUTHORITY_TIME",
            "Authority enrollment time must be naive UTC.",
        )

    learner = session.execute(
        select(User).where(User.id == learner_user_id).with_for_update()
    ).scalar_one_or_none()
    if learner is None:
        raise _fail("LEARNER_NOT_FOUND", "Learner authority fence row is missing.")
    enrollment = session.execute(
        select(StudyAuthorityEnrollment)
        .where(StudyAuthorityEnrollment.learner_user_id == learner_user_id)
        .with_for_update()
    ).scalar_one_or_none()
    previous_mode = str(enrollment.mode_code) if enrollment is not None else "LEGACY"
    previous_epoch = int(enrollment.epoch) if enrollment is not None else 0
    if previous_mode == "NOTE":
        return StudyAuthorityEnrollmentResult(
            learner_user_id=learner_user_id,
            previous_mode="NOTE",
            previous_epoch=previous_epoch,
            mode_code="NOTE",
            epoch=previous_epoch,
            subject_count=0,
            card_count=0,
            cancelled_session_count=0,
        )
    if previous_mode != "LEGACY" or previous_epoch < 0:
        raise _fail(
            "INVALID_AUTHORITY_ENROLLMENT",
            "Existing learner authority enrollment is invalid.",
        )
    if session.execute(
        select(DeckInstall.id)
        .where(
            DeckInstall.user_id == learner_user_id,
            DeckInstall.clone_mode == "logical_overlay",
        )
        .limit(1)
        .with_for_update(read=True)
    ).scalar_one_or_none() is not None:
        raise _fail(
            "OVERLAY_AUTHORITY_NOT_READY",
            "NOTE enrollment for logical-overlay installs requires P5-06 routing.",
        )
    # Checkout takes the same User fence before creating an order. A pending
    # paid-deck order could otherwise fulfill after enrollment and become an
    # unusable overlay (or leave a paid order with a failed grant).
    pending_deck_order = session.execute(
        select(PaymentOrder.id)
        .join(PaymentOrderItem, PaymentOrderItem.order_id == PaymentOrder.id)
        .where(
            PaymentOrder.user_id == learner_user_id,
            PaymentOrderItem.product_type == "deck_marketplace_item",
            (
                PaymentOrder.status.in_(("pending_payment", "under_review"))
                | (
                    (PaymentOrder.status == "paid")
                    & (PaymentOrder.grant_status != "completed")
                )
            ),
        )
        .limit(1)
        .with_for_update(read=True)
    ).scalar_one_or_none()
    if pending_deck_order is not None:
        raise _fail(
            "PENDING_DECK_ORDER",
            "NOTE enrollment must wait until paid-deck checkout and fulfillment settle.",
        )

    next_epoch = previous_epoch + 1
    route = StudyAuthorityRoute(
        learner_user_id=learner_user_id,
        mode_code="NOTE",
        epoch=next_epoch,
        persisted=True,
    )
    owned_notes = tuple(
        session.execute(
            select(Note)
            .where(Note.user_id == learner_user_id)
            .order_by(Note.id.asc())
        ).scalars()
    )
    owned_note_by_id = {str(note.id): note for note in owned_notes}
    owned_cards = tuple(
        session.execute(
            select(Card)
            .where(Card.note_id.in_(tuple(owned_note_by_id)))
            .order_by(Card.note_id.asc(), Card.id.asc())
        ).scalars()
    ) if owned_note_by_id else ()
    cards_by_note_id: dict[str, list[Card]] = {
        note_id: [] for note_id in owned_note_by_id
    }
    for card in owned_cards:
        cards_by_note_id[str(card.note_id)].append(card)
    cardless_note_ids = {
        note_id for note_id, cards in cards_by_note_id.items() if not cards
    }
    if cardless_note_ids:
        raise _fail(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            f"Learner has {len(cardless_note_ids)} owned Note(s) without Card siblings.",
        )
    owned_card_ids = {str(card.id) for card in owned_cards}
    progress_rows = tuple(
        session.execute(
            select(CardProgress)
            .where(CardProgress.user_id == learner_user_id)
            .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
        ).scalars()
    )
    progress_card_ids = {str(row.card_id) for row in progress_rows}
    partially_covered_note_ids: list[str] = []
    pristine_note_ids: list[str] = []
    for note_id, cards in cards_by_note_id.items():
        card_ids = {str(card.id) for card in cards}
        covered_count = len(card_ids & progress_card_ids)
        if covered_count == 0:
            pristine_note_ids.append(note_id)
        elif covered_count != len(card_ids):
            partially_covered_note_ids.append(note_id)
    if partially_covered_note_ids:
        raise _fail(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "Learner has partially covered Note siblings; enrollment cannot infer "
            "whether missing Cards should inherit reviewed state.",
        )
    for note_id in sorted(
        pristine_note_ids,
        key=lambda value: value.encode("utf-8"),
    ):
        try:
            result = (
                study_progress_lifecycle_mirror_service.materialize_new_note_authority(
                    session,
                    route=route,
                    note=owned_note_by_id[note_id],
                    cards=cards_by_note_id[note_id],
                    provenance_code="UNKNOWN_LEGACY",
                    now_utc=now_utc,
                )
            )
        except StudyAuthorityFenceError as exc:
            raise _fail(exc.code, str(exc)) from exc
        if result is None:
            raise _fail(
                "AUTHORITY_MATERIALIZATION_INCOMPLETE",
                "Pristine Note enrollment did not materialize authority state.",
            )

    if pristine_note_ids:
        progress_rows = tuple(
            session.execute(
                select(CardProgress)
                .where(CardProgress.user_id == learner_user_id)
                .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
            ).scalars()
        )
        progress_card_ids = {str(row.card_id) for row in progress_rows}
    missing_owned = owned_card_ids - progress_card_ids
    if missing_owned:
        raise _fail(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            f"Learner has {len(missing_owned)} owned Card(s) without progress evidence.",
        )

    card_note_rows = tuple(
        session.execute(
            select(Card.id, Card.note_id)
            .where(Card.id.in_(sorted(progress_card_ids)))
            .order_by(Card.id.asc())
        ).all()
    )
    note_by_card_id = {str(row.id): str(row.note_id) for row in card_note_rows}
    if set(note_by_card_id) != progress_card_ids:
        raise _fail(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "Learner progress references a missing Card.",
        )
    note_ids = sorted(set(note_by_card_id.values()), key=lambda value: value.encode("utf-8"))
    subjects = tuple(
        session.execute(
            select(StudyProgressSubject)
            .where(
                StudyProgressSubject.learner_user_id == learner_user_id,
                StudyProgressSubject.logical_note_key.in_(
                    [note_id.encode("utf-8") for note_id in note_ids]
                ),
            )
            .order_by(StudyProgressSubject.logical_note_key.asc())
            .with_for_update()
        ).scalars()
    )
    subject_by_note_id = {
        bytes(row.logical_note_key).decode("utf-8"): row for row in subjects
    }
    if set(subject_by_note_id) != set(note_ids):
        raise _fail(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "One or more learner Notes have no mirrored authority subject.",
        )

    locked_by_note_id = {}
    for note_id in note_ids:
        subject = subject_by_note_id[note_id]
        if (
            str(subject.live_note_id or "") != note_id
            or not str(subject.status_code or "").startswith("MIRRORED_")
        ):
            raise _fail(
                "AUTHORITY_SUBJECT_NOT_READY",
                "Learner authority subject is detached, quarantined, or tombstoned.",
            )
        locked = lock_study_authority_subject(
            session,
            route=route,
            subject=subject,
            now_utc=now_utc,
        )
        if locked.state is None:
            raise _fail(
                "AUTHORITY_STATE_REQUIRED",
                "NOTE enrollment requires an existing mirrored state.",
            )
        locked_by_note_id[note_id] = locked
    for note_id in note_ids:
        locked = locked_by_note_id[note_id]
        siblings = lock_study_authority_siblings(
            session,
            route=route,
            locked=locked,
        )
        compatibility = lock_study_authority_compatibility(
            session,
            route=route,
            locked=locked,
            siblings=siblings,
        )
        _verify_lossless_legacy_projection(
            locked=locked,
            siblings=siblings,
            compatibility=compatibility,
        )

    cancelled_session_count = _cancel_open_sessions(
        session,
        learner_user_id=learner_user_id,
    )

    if enrollment is None:
        enrollment = StudyAuthorityEnrollment(
            learner_user_id=learner_user_id,
            created_at=now_utc,
        )
        session.add(enrollment)
    enrollment.mode_code = "NOTE"
    enrollment.epoch = next_epoch
    enrollment.updated_at = now_utc
    return StudyAuthorityEnrollmentResult(
        learner_user_id=learner_user_id,
        previous_mode=previous_mode,
        previous_epoch=previous_epoch,
        mode_code="NOTE",
        epoch=next_epoch,
        subject_count=len(subjects),
        card_count=len(progress_rows),
        cancelled_session_count=cancelled_session_count,
    )


def stage_legacy_authority_enrollment(
    session: Session,
    *,
    learner_user_id: int,
    now_utc: datetime,
) -> StudyAuthorityEnrollmentResult:
    """Prove lossless compatibility, then fence NOTE -> LEGACY."""

    if (
        isinstance(learner_user_id, bool)
        or not isinstance(learner_user_id, int)
        or learner_user_id <= 0
    ):
        raise _fail("INVALID_LEARNER_ID", "Learner ID must be positive.")
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail(
            "INVALID_AUTHORITY_TIME",
            "Authority enrollment time must be naive UTC.",
        )

    learner = session.execute(
        select(User).where(User.id == learner_user_id).with_for_update()
    ).scalar_one_or_none()
    if learner is None:
        raise _fail("LEARNER_NOT_FOUND", "Learner authority fence row is missing.")
    enrollment = session.execute(
        select(StudyAuthorityEnrollment)
        .where(StudyAuthorityEnrollment.learner_user_id == learner_user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if enrollment is None:
        return StudyAuthorityEnrollmentResult(
            learner_user_id=learner_user_id,
            previous_mode="LEGACY",
            previous_epoch=0,
            mode_code="LEGACY",
            epoch=0,
            subject_count=0,
            card_count=0,
            cancelled_session_count=0,
        )
    previous_mode = str(enrollment.mode_code)
    previous_epoch = int(enrollment.epoch)
    if previous_mode == "LEGACY" and previous_epoch >= 0:
        return StudyAuthorityEnrollmentResult(
            learner_user_id=learner_user_id,
            previous_mode="LEGACY",
            previous_epoch=previous_epoch,
            mode_code="LEGACY",
            epoch=previous_epoch,
            subject_count=0,
            card_count=0,
            cancelled_session_count=0,
        )
    if previous_mode != "NOTE" or previous_epoch < 1:
        raise _fail(
            "INVALID_AUTHORITY_ENROLLMENT",
            "Existing learner authority enrollment is invalid.",
        )

    subjects = tuple(
        session.execute(
            select(StudyProgressSubject)
            .where(StudyProgressSubject.learner_user_id == learner_user_id)
            .order_by(StudyProgressSubject.logical_note_key.asc())
            .with_for_update()
        ).scalars()
    )
    # A Note deleted under NOTE authority leaves a retired tombstone with no
    # live Note, state or contributor; there is nothing to project back.
    retired_ids = [
        int(subject.id)
        for subject in subjects
        if str(subject.status_code) == "TOMBSTONED_SUBJECT_DELETED"
        and subject.live_note_id is None
    ]
    if retired_ids:
        residual_state = session.execute(
            select(StudyProgressState.subject_id)
            .where(StudyProgressState.subject_id.in_(retired_ids))
            .limit(1)
            .with_for_update()
        ).scalar_one_or_none()
        residual_contributor = session.execute(
            select(StudyProgressContributor.id)
            .where(
                StudyProgressContributor.subject_id.in_(retired_ids),
                StudyProgressContributor.contributor_status == "ACTIVE",
            )
            .limit(1)
            .with_for_update()
        ).scalar_one_or_none()
        if residual_state is not None or residual_contributor is not None:
            raise _fail(
                "AUTHORITY_SUBJECT_NOT_READY",
                "A deleted NOTE subject still holds canonical state or contributors.",
            )
        retired = set(retired_ids)
        subjects = tuple(subject for subject in subjects if int(subject.id) not in retired)
    if not subjects:
        owned_card_id = session.execute(
            select(Card.id)
            .join(Note, Card.note_id == Note.id)
            .where(Note.user_id == learner_user_id)
            .limit(1)
            .with_for_update(read=True)
        ).scalar_one_or_none()
        progress_id = session.execute(
            select(CardProgress.id)
            .where(CardProgress.user_id == learner_user_id)
            .limit(1)
            .with_for_update()
        ).scalar_one_or_none()
        if owned_card_id is not None or progress_id is not None:
            raise _fail(
                "NO_AUTHORITY_SUBJECTS",
                "NOTE enrollment has live Card state without authority subjects.",
            )
        cancelled_session_count = _cancel_open_sessions(
            session,
            learner_user_id=learner_user_id,
        )
        next_epoch = previous_epoch + 1
        enrollment.mode_code = "LEGACY"
        enrollment.epoch = next_epoch
        enrollment.updated_at = now_utc
        return StudyAuthorityEnrollmentResult(
            learner_user_id=learner_user_id,
            previous_mode="NOTE",
            previous_epoch=previous_epoch,
            mode_code="LEGACY",
            epoch=next_epoch,
            subject_count=0,
            card_count=0,
            cancelled_session_count=cancelled_session_count,
        )
    route = StudyAuthorityRoute(
        learner_user_id=learner_user_id,
        mode_code="NOTE",
        epoch=previous_epoch,
        persisted=True,
    )
    locked_subjects: list[LockedStudyAuthoritySubject] = []
    for subject in subjects:
        if not str(subject.live_note_id or "") or not str(
            subject.status_code or ""
        ).startswith("MIRRORED_"):
            raise _fail(
                "AUTHORITY_SUBJECT_NOT_READY",
                "NOTE rollback cannot recover a detached, quarantined, or tombstoned subject.",
            )
        locked_subjects.append(
            lock_study_authority_subject(
                session,
                route=route,
                subject=subject,
                now_utc=now_utc,
            )
        )

    card_count = 0
    for locked in locked_subjects:
        siblings = lock_study_authority_siblings(
            session,
            route=route,
            locked=locked,
        )
        compatibility = lock_study_authority_compatibility(
            session,
            route=route,
            locked=locked,
            siblings=siblings,
        )
        _verify_lossless_legacy_projection(
            locked=locked,
            siblings=siblings,
            compatibility=compatibility,
        )
        card_count += len(siblings.cards)

    cancelled_session_count = _cancel_open_sessions(
        session,
        learner_user_id=learner_user_id,
    )
    next_epoch = previous_epoch + 1
    enrollment.mode_code = "LEGACY"
    enrollment.epoch = next_epoch
    enrollment.updated_at = now_utc
    return StudyAuthorityEnrollmentResult(
        learner_user_id=learner_user_id,
        previous_mode="NOTE",
        previous_epoch=previous_epoch,
        mode_code="LEGACY",
        epoch=next_epoch,
        subject_count=len(subjects),
        card_count=card_count,
        cancelled_session_count=cancelled_session_count,
    )
