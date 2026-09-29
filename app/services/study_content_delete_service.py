"""Multi-learner content topology changes staged inside the caller's transaction.

Admission must discover/recheck the complete scope and acquire every learner
fence in ID order before calling this coordinator. No commit or rollback here.

Deletion: ``note_ids`` are Notes deleted outright; every one of their Cards
must be in ``card_ids``. Any other Card in ``card_ids`` is a partial sibling
removal that must leave at least one Card on its Note.

Expansion: one new Template sibling per Note; every NOTE learner holding state
on a Note receives an exact compatibility row for its new Card.
"""

from dataclasses import dataclass

from sqlalchemy import select

from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.services import study_progress_lifecycle_mirror_service as lifecycle
from models.card import Card
from models.card_progress import CardProgress
from models.study_progress_contributor import StudyProgressContributor
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject

_CHUNK = 500


@dataclass
class ContentDeletePlan:
    note_plans: tuple
    legacy_plan: object
    sibling_plans: tuple = ()
    deleted_note_ids: frozenset = frozenset()
    partial: bool = False
    finalized: bool = False


def _chunks(values):
    values = tuple(values)
    for offset in range(0, len(values), _CHUNK):
        yield values[offset : offset + _CHUNK]


def _card_note_ids(session, card_ids):
    mapping = {}
    for chunk in _chunks(sorted(set(card_ids))):
        mapping.update(
            (str(card_id), str(note_id))
            for card_id, note_id in session.execute(
                select(Card.id, Card.note_id).where(Card.id.in_(chunk))
            ).all()
        )
    return mapping


def discover_content_learner_ids(session, *, card_ids, note_ids, current_read=False):
    """Learners with progress, subjects or sessions on the affected content."""

    def read(statement):
        # A second plain SELECT would reuse MySQL's REPEATABLE READ snapshot.
        return statement.with_for_update() if current_read else statement

    learner_ids = set()
    for chunk in _chunks(sorted(set(note_ids))):
        learner_ids.update(session.execute(read(
            select(StudyProgressSubject.learner_user_id).where(
                StudyProgressSubject.live_note_id.in_(chunk)
                | StudyProgressSubject.logical_note_key.in_([value.encode("utf-8") for value in chunk])
            ))).scalars())
    for chunk in _chunks(sorted(set(card_ids))):
        learner_ids.update(session.execute(read(
            select(CardProgress.user_id).where(CardProgress.card_id.in_(chunk)))).scalars())
        learner_ids.update(session.execute(read(
            select(StudyProgressSubject.learner_user_id).join(
                StudyProgressContributor,
                StudyProgressContributor.subject_id == StudyProgressSubject.id,
            ).where(StudyProgressContributor.live_card_id.in_(chunk)))).scalars())
        learner_ids.update(session.execute(read(
            select(StudySession.user_id).join(
                StudySessionCard, StudySessionCard.session_id == StudySession.id
            ).where(StudySessionCard.card_id.in_(chunk)))).scalars())
    return frozenset(int(value) for value in learner_ids)


def _affected_note_ids(session, *, card_ids, deleted_note_ids):
    return set(deleted_note_ids) | set(_card_note_ids(session, card_ids).values())


def lock_content_delete_routes(session, *, actor_user_ids, card_ids, deleted_note_ids):
    """Discover every affected learner, then take their fences in ID order.

    Call before any other learner fence in the transaction. Pair it with
    ``verify_content_delete_scope`` after ``prepare_content_delete``.
    """
    learner_ids = set(int(value) for value in actor_user_ids)
    learner_ids |= discover_content_learner_ids(session, card_ids=card_ids,
        note_ids=_affected_note_ids(session, card_ids=card_ids, deleted_note_ids=deleted_note_ids))
    return tuple(
        lock_study_authority_route(session, learner_user_id=learner_id, allow_note_authority=True)
        for learner_id in sorted(learner_ids)
    )


def verify_content_delete_scope(session, *, routes, card_ids, deleted_note_ids):
    """Recheck with current reads once the prepared plans hold their locks.

    Locking reads here also block a new learner's progress insert until the
    caller commits, so no learner can gain state on a deleted Card unfenced.
    """
    card_ids, deleted_note_ids = set(card_ids), set(deleted_note_ids)
    note_ids = _affected_note_ids(session, card_ids=card_ids, deleted_note_ids=deleted_note_ids)
    present = {}
    for chunk in _chunks(sorted(note_ids)):
        present.update(
            (str(card_id), str(note_id))
            for card_id, note_id in session.execute(
                select(Card.id, Card.note_id).where(Card.note_id.in_(chunk)).with_for_update(read=True)
            ).all()
        )
    deleted_cards = {card_id for card_id, note_id in present.items() if note_id in deleted_note_ids}
    locked = {route.learner_user_id for route in routes}
    current = discover_content_learner_ids(session, card_ids=card_ids, note_ids=note_ids, current_read=True)
    if not card_ids.issubset(present) or not deleted_cards.issubset(card_ids) or current - locked:
        raise StudyAuthorityFenceError(
            "CONTENT_SCOPE_CHANGED",
            "Content or its learners changed while the deletion was admitted; retry.",
        )


def _prepare_note_sibling_removal(session, *, route, partial_card_ids, card_note, now_utc):
    """Plan a NOTE learner's partial removal only for Notes it holds state on."""
    partial_note_ids = sorted({card_note[card_id] for card_id in partial_card_ids})
    target_note_ids = set()
    for chunk in _chunks(partial_note_ids):
        target_note_ids.update(
            bytes(key).decode("utf-8")
            for key in session.execute(
                select(StudyProgressSubject.logical_note_key).join(
                    StudyProgressState, StudyProgressState.subject_id == StudyProgressSubject.id
                ).where(
                    StudyProgressSubject.learner_user_id == route.learner_user_id,
                    StudyProgressSubject.logical_note_key.in_([value.encode("utf-8") for value in chunk]),
                )
            ).scalars()
        )
    for chunk in _chunks(sorted(partial_card_ids)):
        # Compatibility rows without canonical state make the planner below
        # raise INCOMPLETE_AUTHORITY_COVERAGE rather than silently dropping them.
        target_note_ids.update(
            card_note[str(card_id)]
            for card_id in session.execute(
                select(CardProgress.card_id).where(
                    CardProgress.user_id == route.learner_user_id,
                    CardProgress.card_id.in_(chunk),
                )
            ).scalars()
        )
    removed = [card_id for card_id in partial_card_ids if card_note[card_id] in target_note_ids]
    if not removed:
        return None
    return lifecycle.prepare_note_authority_sibling_removal(
        session, route=route, removed_card_ids=removed, now_utc=now_utc)


def prepare_content_delete(session, *, routes, card_ids, note_ids, now_utc=None,
                           cancel_legacy_sessions=True):
    """Validate every learner before deleting any compatibility/content row.

    Owner-initiated deletes pass ``cancel_legacy_sessions=False`` to keep the
    existing LEGACY behavior of leaving other open sessions untouched.
    """
    routes = tuple(routes)
    learner_ids = tuple(route.learner_user_id for route in routes)
    if learner_ids != tuple(sorted(set(learner_ids))):
        raise StudyAuthorityFenceError("INVALID_AUTHORITY_ROUTE_ORDER", "Deletion routes must be unique and ordered.")
    card_ids = tuple(str(value) for value in card_ids)
    note_ids = tuple(str(value) for value in note_ids)
    deleted_note_ids = frozenset(note_ids)
    card_note = _card_note_ids(session, card_ids)
    partial_card_ids = tuple(card_id for card_id in card_ids if card_note.get(card_id) not in deleted_note_ids)
    if any(card_id not in card_note for card_id in partial_card_ids):
        raise StudyAuthorityFenceError("AUTHORITY_CARD_MISSING", "Deletion contains a Card that no longer exists.")
    full_card_ids = tuple(card_id for card_id in card_ids if card_note[card_id] in deleted_note_ids)
    note_plans = []
    sibling_plans = []
    legacy_ids = []
    note_learner_ids = []
    for route in routes:
        if route.mode_code == "NOTE":
            note_learner_ids.append(route.learner_user_id)
            plan = lifecycle.prepare_note_authority_reset(session, route=route,
                removed_card_ids=full_card_ids, skip_pristine=False, now_utc=now_utc)
            covered = set(plan.siblings_by_note_id) if plan is not None else set()
            if not covered.issubset(deleted_note_ids):
                raise StudyAuthorityFenceError("PARTIAL_CONTENT_DELETE", "Deletion must include every affected Note.")
            # A broken/cardless Note must not leave a live canonical state
            # behind merely because the Card-driven reset planner found none.
            live_states = session.execute(select(StudyProgressSubject).join(
                StudyProgressState, StudyProgressState.subject_id == StudyProgressSubject.id).where(
                    StudyProgressSubject.learner_user_id == route.learner_user_id,
                    StudyProgressSubject.live_note_id.in_(note_ids)).with_for_update()).scalars()
            if any(str(subject.live_note_id) not in covered for subject in live_states):
                raise StudyAuthorityFenceError("AUTHORITY_DELETE_INCOMPLETE", "Canonical state is outside the complete deletion plan.")
            if plan is not None:
                note_plans.append(plan)
            if partial_card_ids:
                sibling_plan = _prepare_note_sibling_removal(session, route=route,
                    partial_card_ids=partial_card_ids, card_note=card_note, now_utc=now_utc)
                if sibling_plan is not None:
                    sibling_plans.append(sibling_plan)
        elif route.mode_code == "LEGACY":
            legacy_ids.append(route.learner_user_id)
        else:
            raise StudyAuthorityFenceError("AUTHORITY_MODE_CONFLICT", "Unknown deletion authority mode.")
    legacy_plan = lifecycle.prepare_lifecycle_mirror(session, removed_card_ids=card_ids,
        deleted_note_ids=note_ids, learner_user_ids=legacy_ids, now_utc=now_utc) if legacy_ids else None
    cancelled_ids = learner_ids if cancel_legacy_sessions else tuple(note_learner_ids)
    if card_ids and cancelled_ids:
        affected_sessions = select(StudySessionCard.session_id).where(StudySessionCard.card_id.in_(card_ids))
        sessions = session.execute(select(StudySession).where(
            StudySession.user_id.in_(cancelled_ids), StudySession.status == "open",
            StudySession.id.in_(affected_sessions)).order_by(StudySession.id).with_for_update()).scalars()
        for study_session in sessions:
            study_session.status = "cancelled"
    return ContentDeletePlan(tuple(note_plans), legacy_plan, tuple(sibling_plans),
        deleted_note_ids, partial=bool(partial_card_ids))


@dataclass
class ContentExpansionPlan:
    plans: tuple
    finalized: bool = False


def _note_card_ids(session, note_ids, *, current_read=False):
    card_ids = set()
    for chunk in _chunks(sorted(set(note_ids))):
        statement = select(Card.id).where(Card.note_id.in_(chunk))
        if current_read:
            statement = statement.with_for_update(read=True)
        card_ids.update(str(value) for value in session.execute(statement).scalars())
    return card_ids


def lock_content_expansion_routes(session, *, actor_user_ids, note_ids):
    """Fence the actors and every learner with state on ``note_ids`` in ID order."""
    learner_ids = set(int(value) for value in actor_user_ids)
    learner_ids |= discover_content_learner_ids(session,
        card_ids=_note_card_ids(session, note_ids), note_ids=note_ids)
    return tuple(
        lock_study_authority_route(session, learner_user_id=learner_id, allow_note_authority=True)
        for learner_id in sorted(learner_ids)
    )


def prepare_content_expansion(session, *, routes, note_ids, now_utc=None):
    """Lock every NOTE learner's affected subjects before new Cards are created.

    A NOTE learner is planned for the Notes it holds canonical state on or has
    compatibility progress on (the latter fails closed without state). A
    never-studied (pristine) Note needs no row: its new sibling is pristine too.
    """
    note_ids = tuple(sorted({str(value) for value in note_ids}))
    card_note = _card_note_ids(session, _note_card_ids(session, note_ids))
    plans = []
    for route in routes:
        if route.mode_code != "NOTE":
            continue
        targets = set()
        for chunk in _chunks(note_ids):
            targets.update(bytes(key).decode("utf-8") for key in session.execute(
                select(StudyProgressSubject.logical_note_key).join(
                    StudyProgressState, StudyProgressState.subject_id == StudyProgressSubject.id
                ).where(
                    StudyProgressSubject.learner_user_id == route.learner_user_id,
                    StudyProgressSubject.logical_note_key.in_([value.encode("utf-8") for value in chunk]),
                )).scalars())
        for chunk in _chunks(sorted(card_note)):
            targets.update(card_note[str(card_id)] for card_id in session.execute(
                select(CardProgress.card_id).where(
                    CardProgress.user_id == route.learner_user_id,
                    CardProgress.card_id.in_(chunk))).scalars())
        if targets:
            plans.append(lifecycle.prepare_note_authority_sibling_expansion(
                session, route=route, note_ids=sorted(targets), now_utc=now_utc))
    return ContentExpansionPlan(tuple(plan for plan in plans if plan is not None))


def verify_content_expansion_scope(session, *, routes, note_ids):
    """Current-read recheck that no unfenced learner gained state meanwhile."""
    locked = {route.learner_user_id for route in routes}
    current = discover_content_learner_ids(session,
        card_ids=_note_card_ids(session, note_ids, current_read=True), note_ids=note_ids, current_read=True)
    if current - locked:
        raise StudyAuthorityFenceError(
            "CONTENT_SCOPE_CHANGED",
            "Content learners changed while the Template change was admitted; retry.",
        )


def finalize_content_expansion(plan, *, new_cards, now_utc=None, provenance_code="NATIVE_DIRECT"):
    """Attach each NOTE learner's copied compatibility row for its new Cards."""
    if plan.finalized:
        raise StudyAuthorityFenceError("AUTHORITY_LIFECYCLE_REPLAY", "Content expansion already finalized.")
    plan.finalized = True
    new_cards = tuple(new_cards)
    return tuple(
        lifecycle.finalize_note_authority_sibling_expansion(
            learner_plan,
            new_cards=[card for card in new_cards if str(card.note_id) in learner_plan.locked_by_note_id],
            now_utc=now_utc,
            provenance_code=provenance_code,
        )
        for learner_plan in plan.plans
    )


def finalize_content_delete(plan, *, source_path, operation_key, now_utc=None):
    """Call after deleting all affected CardProgress, before deleting Cards."""
    if plan.finalized:
        raise StudyAuthorityFenceError("AUTHORITY_LIFECYCLE_REPLAY", "Content deletion already finalized.")
    plan.finalized = True
    results = []
    for note_plan in plan.note_plans:
        results.append(lifecycle.finalize_note_authority_delete(note_plan,
            source_path=source_path, operation_key=operation_key, now_utc=now_utc))
    for sibling_plan in plan.sibling_plans:
        results.append(lifecycle.finalize_note_authority_sibling_removal(sibling_plan,
            source_path=source_path, operation_key=operation_key, now_utc=now_utc))
    if plan.legacy_plan is not None:
        # Whole-Note deletes keep their historical single transition code.
        results.append(lifecycle.finalize_lifecycle_mirror(plan.legacy_plan,
            transition_code="DETACHED_CONTRIBUTOR_DELETED" if plan.partial else "TOMBSTONED_SUBJECT_DELETED",
            transition_by_note_id=(
                {note_id: "TOMBSTONED_SUBJECT_DELETED" for note_id in plan.deleted_note_ids}
                if plan.partial else None),
            source_path=source_path, operation_key=operation_key, now_utc=now_utc))
    return tuple(results)
