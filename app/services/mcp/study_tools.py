"""MCP study and statistics operations: due counts, study queue, review submission, stats."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.repositories import study_repository, vocabulary_repository
from app.services import stats_overview
from app.services.flashcard_renderer import render_template_pair
from app.services.mcp.base import _resolve_deck_for_user
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_action_runtime import (
    compute_review_previews,
    execute_review_action,
)
from app.services.study_service import (
    StudyReviewError,
    execute_native_review_command,
)
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.note import Note
from models.user import User

# 5. Study & Card Review Operations
# ---------------------------------------------------------------------------


def get_due_card_counts(*, user_id: int, deck_id: int | None = None) -> dict[str, Any]:
    """Return total due, new, review, and learning card counts."""
    now = datetime.utcnow()
    user = db.session.get(User, user_id)
    timezone_name = str(getattr(user, "timezone", "UTC") or "UTC")

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
        }

    cards_query = db.session.query(Card).join(Note, Card.note_id == Note.id).filter(
        Note.user_id == user_id, Note.deck_id.in_(deck_ids)
    )
    new_count, learn_count, due_count = study_repository.query_study_queue_counts(
        cards_query,
        user_id=user_id,
        now=now,
        timezone_name=timezone_name,
    )

    return {
        "total_due": new_count + learn_count + due_count,
        "new_cards": new_count,
        "review_cards": due_count,
        "learn_cards": learn_count,
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

    # Fetch candidate cards
    candidate_cards = cards_query.all()
    actionable_cards: list[dict[str, Any]] = []

    for card in candidate_cards:
        if len(actionable_cards) >= limit:
            break
        note = card.note
        if not note or not note.note_type:
            continue

        progress = CardProgress.query.filter_by(card_id=card.id, user_id=user_id).first()
        deck_options = resolve_deck_options(user_id=user_id, deck_id=note.deck_id)
        card_state = study_repository.card_state_from_progress(
            progress,
            now,
            timezone_name=timezone_name,
            user_id=user_id,
            options=deck_options,
        )

        # Check if due/actionable
        is_actionable = False
        if card_state.type == "new":
            is_actionable = True
        elif card_state.type in ("learning", "relearning"):
            if card_state.due is None or card_state.due <= now:
                is_actionable = True
        elif card_state.type == "review":
            if card_state.dueDay is not None:
                today_idx = study_repository._today_day_index(
                    now=now,
                    timezone_name=timezone_name,
                    day_boundary_hour_local=deck_options.dayBoundaryHourLocal,
                )
                if card_state.dueDay <= today_idx:
                    is_actionable = True
            elif card_state.due is not None and card_state.due <= now:
                is_actionable = True

        if not is_actionable:
            continue

        intervals_preview = compute_review_previews(
            state=card_state,
            options=deck_options,
            now=now,
            timezone_name=timezone_name,
        )

        rendered = render_template_pair(
            template=card.template,
            field_defs=note.note_type.field_defs,
            field_values=note.field_values,
            media_assets=note.media_assets,
        )

        actionable_cards.append(
            {
                "card_id": str(card.id),
                "note_id": str(note.id),
                "deck_id": int(note.deck_id) if note.deck_id else None,
                "template_name": card.template.name if card.template else None,
                "queue": card_state.type,
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
    card = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Card.id == card_id, Note.user_id == user_id)
        .first()
    )
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
    progress = CardProgress.query.filter_by(card_id=card.id, user_id=user_id).first()
    deck_options = resolve_deck_options(user_id=user_id, deck_id=card.note.deck_id)

    card_state = study_repository.card_state_from_progress(
        progress,
        now,
        timezone_name=timezone_name,
        user_id=user_id,
        options=deck_options,
    )
    intervals_preview = compute_review_previews(
        state=card_state,
        options=deck_options,
        now=now,
        timezone_name=timezone_name,
    )
    rendered = render_template_pair(
        template=card.template,
        field_defs=card.note.note_type.field_defs if card.note.note_type else [],
        field_values=card.note.field_values,
        media_assets=card.note.media_assets,
    )

    return {
        "card_id": str(card.id),
        "note_id": str(card.note.id),
        "deck_id": int(card.note.deck_id) if card.note.deck_id else None,
        "template_id": str(card.template_id),
        "template_name": card.template.name if card.template else None,
        "queue": card_state.type,
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
) -> dict[str, Any]:
    """Submit a review answer rating ('again', 'hard', 'good', 'easy') to update card schedule."""
    card = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Card.id == card_id, Note.user_id == user_id)
        .first()
    )
    if card is None or card.note is None:
        raise RequestValidationError(
            f"Không tìm thấy card ID {card_id} của bạn.",
            field="card_id",
            status=404,
            code="CARD_NOT_FOUND",
        )

    user = db.session.get(User, user_id)
    timezone_name = stats_overview.get_effective_timezone_name(getattr(user, "timezone", "UTC"))
    service_payload = {
        "duration_ms": duration_ms,
        "timezone": timezone_name,
    }
    try:
        command_result = execute_native_review_command(
            user=user,
            card=card,
            action=rating,
            payload=service_payload,
            clone_scope=None,
            requested_scope_id=card.note.deck_id,
            timezone_name=timezone_name,
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

    return {
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


# ---------------------------------------------------------------------------
# 6. Statistics Operations
# ---------------------------------------------------------------------------


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
    cards = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id == deck_id, Note.user_id == user_id)
        .all()
    )
    card_count = len(cards)

    due_counts = get_due_card_counts(user_id=user_id, deck_id=deck_id)

    # Progress breakdown
    card_ids = [c.id for c in cards]
    young_count = 0
    mature_count = 0
    if card_ids:
        progresses = CardProgress.query.filter(
            CardProgress.user_id == user_id, CardProgress.card_id.in_(card_ids)
        ).all()
        for p in progresses:
            if p.queue == "review":
                if float(p.interval_days or 0) >= 21:
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

    return {
        "current_streak_days": overview.get("current_streak", 0),
        "longest_streak_days": overview.get("longest_streak", 0),
        "reviewed_today_cards": overview.get("today_cards", 0),
        "study_time_today_minutes": overview.get("today_minutes", 0.0),
        "total_reviews_in_year": overview.get("total_cards", 0),
        "total_study_time_year_minutes": overview.get("total_minutes", 0.0),
        "total_decks": total_decks,
        "total_notes": total_notes,
        "total_cards": total_cards,
        "due_counts": due_counts,
    }


# ---------------------------------------------------------------------------
# 7. Note Type Schema
