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


def _categorize_verdicts(metrics: dict[str, Any]) -> dict[str, list[str]]:
    """Return pass/warn/block categories based on metric thresholds.

    Block = data corruption requiring investigation before cutover.
    Warn  = anomalies that may be valid but need operator review.
    Pass  = healthy or informational metric.
    """
    verdicts: dict[str, list[str]] = {"pass": [], "warn": [], "block": []}

    # Template gates
    tg = metrics["template_gates"]
    if tg["cross_note_type_cards"] > 0:
        verdicts["block"].append(
            f"cross_note_type_cards: {tg['cross_note_type_cards']} card(s) reference"
            " a Template from a different NoteType than their Note"
        )
    else:
        verdicts["pass"].append("cross_note_type_cards: 0")

    if tg["default_count_anomalies"] > 0:
        verdicts["warn"].append(
            f"default_count_anomalies: {tg['default_count_anomalies']} NoteType(s)"
            " have != 1 default Template"
        )
    else:
        verdicts["pass"].append("default_count_anomalies: 0")

    if tg["note_types_without_templates"] > 0:
        verdicts["warn"].append(
            f"note_types_without_templates: {tg['note_types_without_templates']}"
        )
    else:
        verdicts["pass"].append("note_types_without_templates: 0")

    # Card gates
    cg = metrics["card_gates"]
    if cg["notes_without_cards"] > 0:
        verdicts["warn"].append(
            f"notes_without_cards: {cg['notes_without_cards']}"
        )
    else:
        verdicts["pass"].append("notes_without_cards: 0")

    # Progress gates
    pg = metrics["progress_gates"]
    if pg["null_card_id_rows"] > 0:
        verdicts["block"].append(
            f"null_card_id_rows: {pg['null_card_id_rows']} CardProgress row(s)"
            " with NULL card_id"
        )
    else:
        verdicts["pass"].append("null_card_id_rows: 0")

    if pg["orphan_card_id_rows"] > 0:
        verdicts["block"].append(
            f"orphan_card_id_rows: {pg['orphan_card_id_rows']} CardProgress row(s)"
            " reference deleted Card"
        )
    else:
        verdicts["pass"].append("orphan_card_id_rows: 0")

    if pg["partial_fsrs_state_rows"] > 0:
        verdicts["warn"].append(
            f"partial_fsrs_state_rows: {pg['partial_fsrs_state_rows']}"
        )
    else:
        verdicts["pass"].append("partial_fsrs_state_rows: 0")

    # ReviewEvent gates
    rg = metrics["review_event_gates"]
    if rg["orphan_card_id_events"] > 0:
        verdicts["warn"].append(
            f"orphan_card_id_events: {rg['orphan_card_id_events']} ReviewEvent(s)"
            " reference deleted Card"
        )
    else:
        verdicts["pass"].append("orphan_card_id_events: 0")

    if rg["null_algorithm_events"] > 0:
        verdicts["warn"].append(
            f"null_algorithm_events: {rg['null_algorithm_events']} ReviewEvent(s)"
            " with NULL scheduler_algorithm"
        )
    else:
        verdicts["pass"].append("null_algorithm_events: 0")

    # Session gates
    sg = metrics["session_gates"]
    if sg["expired_open_sessions"] > 0:
        verdicts["warn"].append(
            f"expired_open_sessions: {sg['expired_open_sessions']}"
        )
    else:
        verdicts["pass"].append("expired_open_sessions: 0")

    return verdicts


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

    # --- ReviewEvent detached/orphan accounting (Cleanup Order 5) ---
    orphan_review_events = int(
        db.session.query(db.func.count(ReviewEvent.id))
        .outerjoin(Card, Card.id == ReviewEvent.card_id)
        .filter(ReviewEvent.card_id.isnot(None), Card.id.is_(None))
        .scalar()
        or 0
    )
    null_session_review_events = int(
        ReviewEvent.query.filter(ReviewEvent.study_session_id.is_(None)).count()
    )
    null_algorithm_events = int(
        ReviewEvent.query.filter(ReviewEvent.scheduler_algorithm.is_(None)).count()
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

    # --- Algorithm distribution with native/import provenance ---
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

    algorithm_distribution = []
    for scheduler_mode, algorithm_key, algorithm_version, count in algorithm_rows:
        provenance = "native"
        if scheduler_mode == "anki" and algorithm_key == "anki":
            provenance = "import"
        algorithm_distribution.append({
            "scheduler_mode": scheduler_mode,
            "algorithm_key": algorithm_key,
            "algorithm_version": algorithm_version,
            "provenance": provenance,
            "count": int(count or 0),
        })

    metrics = {
        "schema_version": "study-architecture-audit.v2",
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
            "cross_note_type_cards": cross_note_type_cards,
        },
        "card_gates": {
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
        "review_event_gates": {
            "orphan_card_id_events": orphan_review_events,
            "null_session_id_events": null_session_review_events,
            "null_algorithm_events": null_algorithm_events,
        },
        "session_gates": {
            "expired_open_sessions": expired_open_sessions,
        },
        "review_event_algorithm_distribution": algorithm_distribution,
    }

    metrics["verdicts"] = _categorize_verdicts(metrics)

    return metrics

