"""Explicit, transaction-neutral learner authority enrollment transitions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    StudyAuthorityRoute,
    bind_storage_profile,
)
from app.services import study_progress_lifecycle_mirror_service
from models.card import Card
from models.deck_install import DeckInstall
from models.note import Note
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.user import User

logger = logging.getLogger(__name__)


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
    # Every enrollment writer holds the User row above FOR UPDATE, so only an
    # existing row needs its own lock. Locking an absent row would take a gap
    # lock at the end of the primary key, where concurrent sign-ups then
    # deadlock on their inserts. If this snapshot predates another
    # enrollment's commit, the insert below fails on the primary key instead.
    enrollment_exists = session.execute(
        select(StudyAuthorityEnrollment.learner_user_id)
        .where(StudyAuthorityEnrollment.learner_user_id == learner_user_id)
    ).first() is not None
    enrollment = (
        session.execute(
            select(StudyAuthorityEnrollment)
            .where(StudyAuthorityEnrollment.learner_user_id == learner_user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if enrollment_exists
        else None
    )
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
    if enrollment is not None:
        raise _fail("STUDY_AUTHORITY_MIGRATION_REQUIRED", "Existing LEGACY enrollment requires offline migration.")
    # Logical-overlay installs are supported: installed source Notes use the
    # (learner, source Note) subject and never-studied ones read as pristine.
    # A legacy full-copy install still awaits the startup clone cutover, whose
    # progress rekey is only defined for LEGACY learners.
    if session.execute(
        select(DeckInstall.id)
        .where(
            DeckInstall.user_id == learner_user_id,
            DeckInstall.clone_mode != "logical_overlay",
        )
        .limit(1)
        .with_for_update(read=True)
    ).scalar_one_or_none() is not None:
        raise _fail(
            "CLONE_CUTOVER_PENDING",
            "NOTE enrollment requires every deck install to be cut over to logical overlay.",
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
    route = bind_storage_profile(session, StudyAuthorityRoute(
        learner_user_id=learner_user_id,
        mode_code="NOTE",
        epoch=next_epoch,
        persisted=True,
    ))
    owned_notes = tuple(
        session.execute(
            select(Note)
            .where(Note.user_id == learner_user_id)
            .order_by(Note.id.asc())
        ).scalars()
    )
    if owned_notes:
        raise _fail("STUDY_AUTHORITY_MIGRATION_REQUIRED", "An unenrolled account with existing Notes requires offline migration.")
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
    return _stage_canonical_enrollment(
        session,
        route=route,
        enrollment=enrollment,
        previous_mode=previous_mode,
        previous_epoch=previous_epoch,
        owned_note_by_id=owned_note_by_id,
        cards_by_note_id=cards_by_note_id,
        now_utc=now_utc,
    )


def _stage_canonical_enrollment(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    enrollment: StudyAuthorityEnrollment | None,
    previous_mode: str,
    previous_epoch: int,
    owned_note_by_id: dict,
    cards_by_note_id: dict,
    now_utc: datetime,
) -> StudyAuthorityEnrollmentResult:
    """CANONICAL_V1: no LEGACY learner exists and card_progress is frozen.

    Nothing is seeded from the projection; every owned Note starts pristine
    (only an account staged before its first write reaches this). A Note
    that already has authority evidence is refused by the materializer.
    """

    card_count = 0
    for note_id in sorted(owned_note_by_id, key=lambda value: value.encode("utf-8")):
        try:
            study_progress_lifecycle_mirror_service.materialize_new_note_authority(
                session,
                route=route,
                note=owned_note_by_id[note_id],
                cards=cards_by_note_id[note_id],
                provenance_code="UNKNOWN_LEGACY",
                now_utc=now_utc,
            )
        except StudyAuthorityFenceError as exc:
            raise _fail(exc.code, str(exc)) from exc
        card_count += len(cards_by_note_id[note_id])
    cancelled_session_count = _cancel_open_sessions(session, learner_user_id=route.learner_user_id)
    if enrollment is None:
        enrollment = StudyAuthorityEnrollment(learner_user_id=route.learner_user_id, created_at=now_utc)
        session.add(enrollment)
    enrollment.mode_code = "NOTE"
    enrollment.epoch = route.epoch
    enrollment.updated_at = now_utc
    return StudyAuthorityEnrollmentResult(
        learner_user_id=route.learner_user_id,
        previous_mode=previous_mode,
        previous_epoch=previous_epoch,
        mode_code="NOTE",
        epoch=route.epoch,
        subject_count=len(owned_note_by_id),
        card_count=card_count,
        cancelled_session_count=cancelled_session_count,
    )


def enroll_new_learner_note_authority(
    session: Session,
    *,
    user: User,
) -> StudyAuthorityEnrollmentResult:
    """Stage NOTE for a just-created account inside the caller's transaction.

    Every new account starts in NOTE (Phase 9, D9-09): no environment flag
    decides it, so a drifted ``STUDY_NEW_LEARNER_NOTE_ENABLED`` or
    ``STUDY_WIRE_V4_ENABLED`` can no longer create LEGACY learners. Wire or
    async misconfiguration affects every NOTE learner alike and is reported
    at system level. A new account owns no Notes, progress or installs, so
    the proof is trivial; if it is still refused, the error propagates and
    the caller's signup fails instead of leaving a LEGACY account. No commit.
    """

    session.flush()
    try:
        return stage_note_authority_enrollment(
            session,
            learner_user_id=int(user.id),
            now_utc=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    except (StudyAuthorityEnrollmentError, StudyAuthorityFenceError) as exc:
        logger.warning(
            "Signup of %s refused: NOTE enrollment failed (%s)",
            user.id,
            getattr(exc, "code", "AUTHORITY_TRANSITION_FAILED"),
        )
        raise


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
    # LEGACY reads card_progress, which no NOTE write maintains (D9-02, ADR P10).
    raise _fail(
        "LEGACY_ROLLBACK_RETIRED",
        "A learner cannot return to LEGACY once NOTE progress lives on its rows.",
    )
