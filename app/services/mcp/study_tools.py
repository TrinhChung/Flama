"""MCP study and statistics operations: due counts, study queue, review submission, stats."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import contains_eager

from app.repositories import study_repository, vocabulary_repository
from app.repositories.study_queue_repository import query_study_queue_card_refs
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.services import stats_overview
from app.services.db_errors import domain_error_code, run_with_deadlock_retry
from app.services.effective_template_service import resolve_effective_template
from app.services.flashcard_renderer import render_template_pair
from app.services.mcp.base import _resolve_deck_for_user
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_action_runtime import (
    compute_review_previews,
    execute_review_action,
)
from app.services.study_authority_read_service import (
    load_study_authority_availability_snapshot,
    load_study_authority_card_read,
    load_study_authority_card_reads,
    summarize_study_authority_queue,
)
from app.services.study_service import (
    StudyReviewError,
    execute_native_review_command,
)
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card, card_id_clause, get_card as resolve_card
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.user import User

# 5. Study & Card Review Operations
# ---------------------------------------------------------------------------


def _card_scope(cards_query):
    """The Cards of ``cards_query`` as a (deck_id, card_id, note_id) subquery."""

    return (
        cards_query.with_entities(
            Note.deck_id.label("deck_id"),
            Card.id.label("card_id"),
            Card.note_id.label("note_id"),
        )
        .order_by(None)
        .subquery("mcp_queue_scope")
    )


def _deck_options_by_card_id(*, user_id: int, cards) -> dict[str, Any]:
    """Resolve deck options once per deck, not once per Card (P5-11b)."""

    by_deck: dict[Any, Any] = {}
    options: dict[str, Any] = {}
    for card in cards:
        deck_id = card.note.deck_id
        if deck_id not in by_deck:
            by_deck[deck_id] = resolve_deck_options(user_id=user_id, deck_id=deck_id)
        options[str(card.id)] = by_deck[deck_id]
    return options


def get_due_card_counts(*, user_id: int, deck_id: int | None = None) -> dict[str, Any]:
    """Return total due, new, review, and learning card counts."""
    now = datetime.utcnow()
    user = db.session.get(User, user_id)
    timezone_name = str(getattr(user, "timezone", "UTC") or "UTC")
    try:
        authority_route = lock_study_authority_route(
            db.session,
            learner_user_id=user_id,
            allow_note_authority=True,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise RequestValidationError(
            str(exc),
            field="user_id",
            status=409,
            code=exc.code,
        ) from exc

    scoped_decks = vocabulary_repository.collect_accessible_browse_decks(
        user_id=user_id,
        admin_mode=False,
    )
    if deck_id is not None:
        target_decks = [d for d in scoped_decks if int(d.id or 0) == int(deck_id)]
    else:
        target_decks = scoped_decks

    deck_ids = [int(d.id) for d in target_decks if d.id is not None]
    if not deck_ids:
        return {
            "total_due": 0,
            "new_cards": 0,
            "review_cards": 0,
            "learn_cards": 0,
            "learning_cards": 0,
            "authority_mode": authority_route.mode_code,
        }

    cards_query = db.session.query(Card).join(Note, Card.note_id == Note.id).filter(
        Note.user_id == user_id, Note.deck_id.in_(deck_ids)
    )
    cards = query_study_queue_card_refs(cards_query)
    try:
        # Counts need availability only: read it set-wise (P5-11e).
        authority_reads = load_study_authority_availability_snapshot(
            db.session,
            learner_user_id=user_id,
            cards=tuple(cards),
            scope=_card_scope(cards_query),
            now_utc=now,
        )
        summary = summarize_study_authority_queue(
            cards=tuple(cards),
            reads_by_card_id=authority_reads,
            learner_user_id=user_id,
            now_utc=now,
            timezone_name=timezone_name,
        )
    except Exception as exc:
        code = domain_error_code(exc)
        if code is None:
            raise
        db.session.rollback()
        raise RequestValidationError(
            str(exc),
            field="card_id",
            status=409,
            code=str(code),
        ) from exc
    new_count = summary.new_count
    learn_count = summary.learn_count
    due_count = summary.due_count

    return {
        "total_due": new_count + learn_count + due_count,
        "new_cards": new_count,
        "review_cards": due_count,
        "learn_cards": learn_count,
        "learning_cards": learn_count,
        "authority_mode": authority_route.mode_code,
    }


def get_study_queue(*, user_id: int, deck_id: int | None = None, limit: int = 10) -> dict[str, Any]:
    """Retrieve cards due for study with rendered front/back & interval options."""
    now = datetime.utcnow()
    user = db.session.get(User, user_id)
    timezone_name = stats_overview.get_effective_timezone_name(getattr(user, "timezone", "UTC"))

    counts = get_due_card_counts(user_id=user_id, deck_id=deck_id)

    scoped_decks = vocabulary_repository.collect_accessible_browse_decks(user_id=user_id, admin_mode=False)
    if deck_id is not None:
        _resolve_deck_for_user(user_id=user_id, deck_id=deck_id)
        target_decks = [d for d in scoped_decks if int(d.id or 0) == int(deck_id)]
    else:
        target_decks = scoped_decks

    deck_ids = [int(d.id) for d in target_decks if d.id is not None]
    if not deck_ids:
        return {"cards": [], "queue_counts": counts}

    cards_query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Note.user_id == user_id, Note.deck_id.in_(deck_ids))
    )

    if counts["authority_mode"] == "NOTE":
        studyable = query_study_queue_card_refs(cards_query)
        candidate_cards = None
    else:
        candidate_cards = cards_query.options(contains_eager(Card.note)).all()
        studyable = tuple(card for card in candidate_cards if card.note is not None)
    try:
        if counts["authority_mode"] == "NOTE":
            # Order the whole queue set-wise, then read the returned Cards fully.
            ordering_reads = load_study_authority_availability_snapshot(
                db.session,
                learner_user_id=user_id,
                cards=studyable,
                scope=_card_scope(cards_query),
                now_utc=now,
            )
        else:
            ordering_reads = load_study_authority_card_reads(
                db.session,
                learner_user_id=user_id,
                cards=studyable,
                now_utc=now,
                timezone_name=timezone_name,
                deck_options_by_card_id=_deck_options_by_card_id(user_id=user_id, cards=studyable),
            )
        queue_summary = summarize_study_authority_queue(
            cards=studyable,
            reads_by_card_id=ordering_reads,
            learner_user_id=user_id,
            now_utc=now,
            timezone_name=timezone_name,
        )
        if counts["authority_mode"] == "NOTE":
            # Keep skip-before-limit semantics for orphaned/missing NoteTypes,
            # without loading every candidate's Note content to test it.
            renderable_ids = {
                str(row[0]) for row in cards_query.join(NoteType, Note.note_type_id == NoteType.id)
                .with_entities(Card.id).all()
            } if queue_summary.due_card_ids else set()
            returned_ids = [card_id for card_id in queue_summary.due_card_ids if card_id in renderable_ids][:limit]
            candidate_by_id = {
                str(card.id): card for card in cards_query.filter(card_id_clause(db.session, returned_ids))
                .options(contains_eager(Card.note)).all()
            } if returned_ids else {}
            returned = [candidate_by_id[card_id] for card_id in returned_ids if card_id in candidate_by_id]
        else:
            candidate_by_id = {str(card.id): card for card in candidate_cards}
            returned = [
                candidate_by_id[card_id]
                for card_id in queue_summary.due_card_ids
                if candidate_by_id[card_id].note.note_type is not None
            ][:limit]
        deck_options_by_card_id = _deck_options_by_card_id(user_id=user_id, cards=returned)
        authority_reads = load_study_authority_card_reads(
            db.session,
            learner_user_id=user_id,
            cards=tuple(returned),
            now_utc=now,
            timezone_name=timezone_name,
            deck_options_by_card_id=deck_options_by_card_id,
        )
    except Exception as exc:
        code = domain_error_code(exc)
        if code is None:
            raise
        db.session.rollback()
        raise RequestValidationError(
            str(exc),
            field="card_id",
            status=409,
            code=str(code),
        ) from exc
    actionable_cards: list[dict[str, Any]] = []

    for card in returned:
        note = card.note

        deck_options = deck_options_by_card_id[str(card.id)]
        authority_read = authority_reads[str(card.id)]
        card_state = authority_read.state

        intervals_preview = compute_review_previews(
            state=card_state,
            options=deck_options,
            now=now,
            timezone_name=timezone_name,
        )

        template = resolve_effective_template(card)
        rendered = render_template_pair(
            template=template,
            field_defs=note.note_type.field_defs,
            field_values=note.field_values,
            media_assets=note.media_assets,
        )

        actionable_cards.append(
            {
                "card_id": str(card.id),
                "note_id": str(note.id),
                "deck_id": int(note.deck_id) if note.deck_id else None,
                "template_name": template.name if template else None,
                "queue": card_state.type,
                "authority_mode": authority_read.route.mode_code,
                "authority_revision": authority_read.authority_revision,
                "review_state_version": authority_read.state_version,
                "front_html": rendered.get("front_html"),
                "back_html": rendered.get("back_html"),
                "fields": dict(note.field_values or {}),
                "intervals_preview": intervals_preview,
            }
        )

    return {
        "cards": actionable_cards,
        "queue_counts": counts,
    }


def get_card(*, user_id: int, card_id: str) -> dict[str, Any]:
    """Get single card detail with rendered HTML and scheduling intervals."""
    card = resolve_card(db.session, card_id, query=(
        Card.query.join(Note, Card.note_id == Note.id).filter(Note.user_id == user_id)
    ))
    if card is None or card.note is None:
        raise RequestValidationError(
            f"Không tìm thấy card ID {card_id} của bạn.",
            field="card_id",
            status=404,
            code="CARD_NOT_FOUND",
        )

    user = db.session.get(User, user_id)
    timezone_name = stats_overview.get_effective_timezone_name(getattr(user, "timezone", "UTC"))
    now = datetime.utcnow()
    deck_options = resolve_deck_options(user_id=user_id, deck_id=card.note.deck_id)
    try:
        authority_read = load_study_authority_card_read(
            db.session,
            learner_user_id=user_id,
            card=card,
            now_utc=now,
            timezone_name=timezone_name,
            deck_options=deck_options,
        )
    except Exception as exc:
        code = domain_error_code(exc)
        if code is None:
            raise
        db.session.rollback()
        raise RequestValidationError(
            str(exc),
            field="card_id",
            status=409,
            code=str(code),
        ) from exc
    card_state = authority_read.state
    intervals_preview = compute_review_previews(
        state=card_state,
        options=deck_options,
        now=now,
        timezone_name=timezone_name,
    )
    template = resolve_effective_template(card)
    rendered = render_template_pair(
        template=template,
        field_defs=card.note.note_type.field_defs if card.note.note_type else [],
        field_values=card.note.field_values,
        media_assets=card.note.media_assets,
    )

    return {
        "card_id": str(card.id),
        "note_id": str(card.note.id),
        "deck_id": int(card.note.deck_id) if card.note.deck_id else None,
        "template_id": str(card.template_id),
        "template_name": template.name if template else None,
        "queue": card_state.type,
        "authority_mode": authority_read.route.mode_code,
        "authority_revision": authority_read.authority_revision,
        "review_state_version": authority_read.state_version,
        "reps": int(card_state.reps or 0),
        "lapses": int(card_state.lapses or 0),
        "interval_days": float(card_state.intervalDays or 0),
        "ease_factor": float(card_state.ease or 2.5),
        "due_at": card_state.due.isoformat() if card_state.due else None,
        "front_html": rendered.get("front_html"),
        "back_html": rendered.get("back_html"),
        "fields": dict(card.note.field_values or {}),
        "tags": list(card.note.tags or []),
        "intervals_preview": intervals_preview,
    }


def submit_review(
    *,
    user_id: int,
    card_id: str,
    rating: str,
    duration_ms: int | None = None,
    operation_key: str | None = None,
) -> dict[str, Any]:
    """Submit a review answer rating ('again', 'hard', 'good', 'easy') to update card schedule."""
    card = resolve_card(db.session, card_id, query=(
        Card.query.join(Note, Card.note_id == Note.id).filter(Note.user_id == user_id)
    ))
    if card is None or card.note is None:
        raise RequestValidationError(
            f"Không tìm thấy card ID {card_id} của bạn.",
            field="card_id",
            status=404,
            code="CARD_NOT_FOUND",
        )

    user = db.session.get(User, user_id)
    timezone_name = stats_overview.get_effective_timezone_name(getattr(user, "timezone", "UTC"))
    mcp_event_id = operation_key if operation_key is not None else str(uuid4())
    service_payload = {
        "duration_ms": duration_ms,
    }
    if operation_key is not None:
        service_payload["operation_key"] = operation_key
    try:
        command_result = run_with_deadlock_retry(
            lambda: execute_native_review_command(
                user=user,
                card=card,
                action=rating,
                payload=service_payload,
                clone_scope=None,
                # MCP does not accept a scope/timezone override. Keep resolved
                # server policy out of the caller-intent replay fingerprint.
                requested_scope_id=None,
                timezone_name=timezone_name,
                client_event_id=mcp_event_id,
                source_path="native.mcp",
            ),
            session=db.session,
            label="MCP submit_review",
        )
    except StudyReviewError as exc:
        raise RequestValidationError(
            str(exc),
            field="card_id",
            status=exc.status,
            code=exc.code,
        ) from exc

    current_state = command_result.current_state
    updated_state = command_result.transition.state

    response = {
        "success": True,
        "card_id": str(card.id),
        "rating": rating,
        "previous_queue": current_state.type,
        "next_queue": updated_state.type,
        "interval_days": float(updated_state.intervalDays or 0),
        "due_at": updated_state.due.isoformat() if updated_state.due else None,
        "reps": int(updated_state.reps or 0),
        "lapses": int(updated_state.lapses or 0),
        "ease_factor": float(updated_state.ease or 2.5),
    }
    if command_result.authority_mode == "NOTE":
        response["authority"] = {
            "mode": "NOTE",
            "operation_key": command_result.operation_key,
            "authority_revision": command_result.authority_revision,
            "progress_revision": command_result.progress_revision,
            "replayed": command_result.replayed,
        }
    return response


# ---------------------------------------------------------------------------
# 6. Statistics Operations
# ---------------------------------------------------------------------------


def _is_consolidated_profile() -> bool:
    from app.repositories.study_authority_repository import read_study_storage_profile
    from app.services.study_progress_contract import CONSOLIDATED_STORAGE_PROFILE

    return read_study_storage_profile(db.session) == CONSOLIDATED_STORAGE_PROFILE


def get_deck_stats(*, user_id: int, deck_id: int) -> dict[str, Any]:
    """Return learning and review stats for a specific deck."""
    deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
    if deck is None:
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )

    note_count = Note.query.filter_by(deck_id=deck_id, user_id=user_id).count()
    due_counts = get_due_card_counts(user_id=user_id, deck_id=deck_id)
    consolidated_note = due_counts["authority_mode"] == "NOTE" and _is_consolidated_profile()
    cards_query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id == deck_id, Note.user_id == user_id)
    )
    if consolidated_note:
        card_count = cards_query.count()
        cards = ()
    else:
        cards = cards_query.options(contains_eager(Card.note)).all()
        card_count = len(cards)

    # Progress breakdown
    card_ids = [c.id for c in cards]
    young_count = 0
    mature_count = 0
    if card_count:
        if consolidated_note:
            # ADR P10 §2.7: one non-locking SELECT over the deck's Note rows.
            from app.repositories.note_analytics_read_repository import (
                consolidated_card_rows,
                state_interval_days,
            )

            for row in consolidated_card_rows(
                Card.query.join(Note, Card.note_id == Note.id)
                .filter(Note.deck_id == deck_id, Note.user_id == user_id),
                learner_user_id=user_id,
            ).all():
                if row[5] != "review":
                    continue
                if state_interval_days(row[6]) >= 21:
                    mature_count += 1
                else:
                    young_count += 1
        try:
            authority_reads = load_study_authority_card_reads(
                db.session,
                learner_user_id=user_id,
                cards=tuple(cards),
                now_utc=datetime.utcnow(),
                timezone_name=stats_overview.get_effective_timezone_name(
                    getattr(db.session.get(User, user_id), "timezone", "UTC")
                ),
                deck_options_by_card_id=_deck_options_by_card_id(
                    user_id=user_id, cards=cards
                ),
            )
        except Exception as exc:
            code = domain_error_code(exc)
            if code is None:
                raise
            db.session.rollback()
            raise RequestValidationError(
                str(exc),
                field="card_id",
                status=409,
                code=str(code),
            ) from exc
        progress_states = [read.state for read in authority_reads.values()]
        for state in progress_states:
            if state.type != "review":
                continue
            if float(state.intervalDays or 0) >= 21:
                mature_count += 1
            else:
                young_count += 1

    return {
        "deck_id": int(deck.id),
        "deck_name": deck.name,
        "note_count": note_count,
        "card_count": card_count,
        "new_cards": due_counts["new_cards"],
        "learning_cards": due_counts["learn_cards"],
        "review_due_cards": due_counts["review_cards"],
        "total_due_today": due_counts["total_due"],
        "young_cards": young_count,
        "mature_cards": mature_count,
        "authority_mode": due_counts["authority_mode"],
    }


def get_study_stats(*, user_id: int, year: int | None = None) -> dict[str, Any]:
    """Return user's overall study overview: streak, daily reviews, total decks/notes."""
    user = db.session.get(User, user_id)
    timezone_name = stats_overview.get_effective_timezone_name(getattr(user, "timezone", "UTC"))

    overview = stats_overview.build_stats_overview(
        user_id=user_id,
        year=year,
        timezone_name=timezone_name,
    )

    total_decks = Deck.query.filter_by(owner_user_id=user_id, deleted_at=None).count()
    total_notes = Note.query.filter_by(user_id=user_id).count()
    total_cards = (
        Card.query.join(Note, Card.note_id == Note.id).filter(Note.user_id == user_id).count()
    )
    due_counts = get_due_card_counts(user_id=user_id)

    metrics = overview.get("metrics") or {}
    today = overview.get("today") or {}

    current_streak = metrics.get("current_streak_days")
    if current_streak is None:
        current_streak = overview.get("current_streak", 0)
    current_streak = int(current_streak or 0)

    longest_streak = metrics.get("longest_streak_days")
    if longest_streak is None:
        longest_streak = overview.get("longest_streak", 0)
    longest_streak = int(longest_streak or 0)

    today_cards = today.get("cards")
    if today_cards is None:
        today_cards = overview.get("today_cards", 0)
    today_cards = int(today_cards or 0)

    today_minutes = today.get("minutes")
    if today_minutes is None:
        today_minutes = overview.get("today_minutes", 0.0)
    today_minutes = float(today_minutes or 0.0)

    total_reviews = metrics.get("total_cards")
    if total_reviews is None:
        total_reviews = overview.get("total_cards")
    if total_reviews is None:
        total_reviews = sum(
            int(d.get("cards") or 0)
            for d in overview.get("heatmap", [])
            if d.get("source") == "reviewed"
        )
    total_reviews = int(total_reviews or 0)

    total_minutes = metrics.get("total_minutes")
    if total_minutes is None:
        total_minutes = overview.get("total_minutes")
    if total_minutes is None:
        total_ms = sum(
            int(d.get("study_time") or 0)
            for d in overview.get("heatmap", [])
            if d.get("source") == "reviewed"
        )
        total_minutes = round(total_ms / 60000.0 + 1e-12, 2)
    learning_cards = due_counts.get("learning_cards")
    if learning_cards is None:
        learning_cards = due_counts.get("learn_cards", 0)
    learning_cards = int(learning_cards or 0)

    return {
        "current_streak_days": current_streak,
        "longest_streak_days": longest_streak,
        "reviewed_today_cards": today_cards,
        "study_time_today_minutes": today_minutes,
        "total_reviews_in_year": total_reviews,
        "total_study_time_year_minutes": total_minutes,
        "total_decks": total_decks,
        "total_notes": total_notes,
        "total_cards": total_cards,
        "new_cards": int(due_counts.get("new_cards") or 0),
        "learning_cards": learning_cards,
        "review_cards": int(due_counts.get("review_cards") or 0),
        "due_counts": due_counts,
    }


# ---------------------------------------------------------------------------
# 7. Note Type Schema
