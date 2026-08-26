"""Read-only reconciliation metrics for the study architecture rollout."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_session import StudySession
from models.template import Template


def _group_count(query) -> int:
    return int(db.session.query(db.func.count()).select_from(query.subquery()).scalar() or 0)


def build_study_architecture_audit(*, now: datetime | None = None) -> dict[str, Any]:
    """Return aggregate-only rollout gates without mutating or exposing user content."""

    observed_at = now or datetime.utcnow()

    template_counts = (
        db.session.query(
            NoteType.id.label("note_type_id"),
            db.func.count(Template.id).label("template_count"),
            db.func.sum(
                db.case((Template.is_default.is_(True), 1), else_=0)
            ).label("default_count"),
        )
        .outerjoin(Template, Template.note_type_id == NoteType.id)
        .group_by(NoteType.id)
        .subquery()
    )
    note_types_without_templates = int(
        db.session.query(db.func.count())
        .select_from(template_counts)
        .filter(template_counts.c.template_count == 0)
        .scalar()
        or 0
    )
    note_types_with_multiple_templates = int(
        db.session.query(db.func.count())
        .select_from(template_counts)
        .filter(template_counts.c.template_count > 1)
        .scalar()
        or 0
    )
    template_default_anomalies = int(
        db.session.query(db.func.count())
        .select_from(template_counts)
        .filter(template_counts.c.default_count != 1)
        .scalar()
        or 0
    )

    duplicate_template_names = _group_count(
        db.session.query(Template.note_type_id, db.func.lower(Template.name))
        .group_by(Template.note_type_id, db.func.lower(Template.name))
        .having(db.func.count(Template.id) > 1)
    )
    duplicate_template_positions = _group_count(
        db.session.query(Template.note_type_id, Template.position)
        .group_by(Template.note_type_id, Template.position)
        .having(db.func.count(Template.id) > 1)
    )

    cross_note_type_cards = int(
        db.session.query(db.func.count(Card.id))
        .join(Note, Note.id == Card.note_id)
        .join(Template, Template.id == Card.template_id)
        .filter(Note.note_type_id != Template.note_type_id)
        .scalar()
        or 0
    )
    notes_without_cards = int(
        db.session.query(db.func.count(Note.id))
        .outerjoin(Card, Card.note_id == Note.id)
        .filter(Card.id.is_(None))
        .scalar()
        or 0
    )
    notes_with_multiple_cards = _group_count(
        db.session.query(Card.note_id)
        .group_by(Card.note_id)
        .having(db.func.count(Card.id) > 1)
    )

    null_progress_subjects = int(
        CardProgress.query.filter(CardProgress.card_id.is_(None)).count()
    )
    orphan_progress_subjects = int(
        db.session.query(db.func.count(CardProgress.id))
        .outerjoin(Card, Card.id == CardProgress.card_id)
        .filter(CardProgress.card_id.isnot(None), Card.id.is_(None))
        .scalar()
        or 0
    )
    progress_fan_in_groups = _group_count(
        db.session.query(CardProgress.user_id, Card.note_id)
        .join(Card, Card.id == CardProgress.card_id)
        .group_by(CardProgress.user_id, Card.note_id)
        .having(db.func.count(db.distinct(CardProgress.card_id)) > 1)
    )
    review_history_fan_in_groups = _group_count(
        db.session.query(ReviewEvent.user_id, Card.note_id)
        .join(Card, Card.id == ReviewEvent.card_id)
        .group_by(ReviewEvent.user_id, Card.note_id)
        .having(db.func.count(db.distinct(ReviewEvent.card_id)) > 1)
    )

    expired_open_sessions = int(
        StudySession.query.filter(
            StudySession.status == "open",
            StudySession.expires_at < observed_at,
        ).count()
    )
    fsrs_progress_rows = int(
        CardProgress.query.filter(
            db.func.lower(CardProgress.scheduler_mode) == "fsrs"
        ).count()
    )
    partial_fsrs_state_rows = int(
        CardProgress.query.filter(
            db.or_(
                db.and_(
                    CardProgress.memory_stability.is_(None),
                    CardProgress.memory_difficulty.isnot(None),
                ),
                db.and_(
                    CardProgress.memory_stability.isnot(None),
                    CardProgress.memory_difficulty.is_(None),
                ),
            )
        ).count()
    )

    algorithm_rows = (
        db.session.query(
            ReviewEvent.scheduler_mode,
            ReviewEvent.scheduler_algorithm,
            ReviewEvent.algorithm_version,
            db.func.count(ReviewEvent.id),
        )
        .group_by(
            ReviewEvent.scheduler_mode,
            ReviewEvent.scheduler_algorithm,
            ReviewEvent.algorithm_version,
        )
        .order_by(
            ReviewEvent.scheduler_mode.asc(),
            ReviewEvent.scheduler_algorithm.asc(),
            ReviewEvent.algorithm_version.asc(),
        )
        .all()
    )

    return {
        "schema_version": "study-architecture-audit.v1",
        "observed_at": observed_at.isoformat(timespec="seconds"),
        "counts": {
            "note_types": int(NoteType.query.count()),
            "templates": int(Template.query.count()),
            "notes": int(Note.query.count()),
            "cards": int(Card.query.count()),
            "card_progress": int(CardProgress.query.count()),
            "review_events": int(ReviewEvent.query.count()),
            "study_sessions": int(StudySession.query.count()),
        },
        "template_gates": {
            "note_types_without_templates": note_types_without_templates,
            "note_types_with_multiple_templates": note_types_with_multiple_templates,
            "default_count_anomalies": template_default_anomalies,
            "duplicate_name_groups": duplicate_template_names,
            "duplicate_position_groups": duplicate_template_positions,
        },
        "card_gates": {
            "cross_note_type_cards": cross_note_type_cards,
            "notes_without_cards": notes_without_cards,
            "notes_with_multiple_cards": notes_with_multiple_cards,
        },
        "progress_gates": {
            "null_card_id_rows": null_progress_subjects,
            "orphan_card_id_rows": orphan_progress_subjects,
            "learner_note_fan_in_groups": progress_fan_in_groups,
            "learner_note_history_fan_in_groups": review_history_fan_in_groups,
            "fsrs_rows": fsrs_progress_rows,
            "partial_fsrs_state_rows": partial_fsrs_state_rows,
        },
        "session_gates": {
            "expired_open_sessions": expired_open_sessions,
        },
        "review_event_algorithm_distribution": [
            {
                "scheduler_mode": scheduler_mode,
                "algorithm_key": algorithm_key,
                "algorithm_version": algorithm_version,
                "count": int(count or 0),
            }
            for scheduler_mode, algorithm_key, algorithm_version, count in algorithm_rows
        ],
    }

