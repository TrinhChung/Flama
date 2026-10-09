"""Phase 6 attribution backfill, run after migration 46 is deployed (D6-05/D6-07).

Migration 46 adds ``review_events.note_id`` without touching existing rows:
one UPDATE over every event would lock the table while learners answer. The
deploy also runs the migration while the previous release still serves
requests, so for a few seconds old code can write Cards without an occurrence
and Connect refs or events without a Note. This backfill closes both gaps:

* a Template without a compatibility occurrence gets one;
* a Card without an occurrence is bound to its Template's compatibility
  occurrence; a second Card for the same Note and occurrence is only reported
  (never deleted, it may carry history);
* a Connect card ref gets its Card's Note;
* an old review event gets its Card's Note; an event whose Card is gone keeps
  NULL.

Every step walks rows by primary key, one short committed transaction per
batch, and is safe to stop and rerun. The Card -> Note mapping is read without
locks (a Card never moves to another Note), so the only rows locked are the
ones being stamped. Without ``apply`` it only counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import and_, case, func, insert, or_, select, update

from models import db
from models.card import Card
from models.connect_source_card_ref import ConnectSourceCardRef
from models.model_uuid import uuid_str
from models.review_event import ReviewEvent
from models.study_application import COMPAT_OCCURRENCE_KEY, StudyApplication
from models.template import Template


@dataclass
class NoteAttributionReport:
    applied: bool
    templates_without_occurrence: int = 0
    occurrences_created: int = 0
    unbound_cards: int = 0
    cards_bound: int = 0
    duplicate_cards: list[str] = field(default_factory=list)
    refs_pending: int = 0
    refs_attributed: int = 0
    pending_events: int = 0
    attributed_events: int = 0
    unresolved_events: int = 0
    batches: int = 0

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _count(statement) -> int:
    return int(db.session.execute(statement).scalar_one())


def _templates_without_occurrence():
    compat = (
        select(StudyApplication.id)
        .where(
            StudyApplication.template_id == Template.id,
            StudyApplication.note_type_id == Template.note_type_id,
            StudyApplication.occurrence_key == COMPAT_OCCURRENCE_KEY,
        )
        .exists()
    )
    return select(Template.id, Template.note_type_id, Template.position).where(Template.note_type_id.isnot(None), ~compat)


def _stale_ref_condition():
    return and_(
        ConnectSourceCardRef.card_id.isnot(None),
        or_(ConnectSourceCardRef.note_id.is_(None), ConnectSourceCardRef.note_id != Card.note_id),
    )


def _survey(report: NoteAttributionReport) -> None:
    report.templates_without_occurrence = _count(
        select(func.count()).select_from(_templates_without_occurrence().subquery())
    )
    report.unbound_cards = _count(
        select(func.count()).select_from(Card).where(Card.application_id.is_(None))
    )
    report.refs_pending = _count(
        select(func.count()).select_from(ConnectSourceCardRef)
        .join(Card, Card.id == ConnectSourceCardRef.card_id)
        .where(_stale_ref_condition())
    )
    report.pending_events = _count(
        select(func.count()).select_from(ReviewEvent).where(ReviewEvent.note_id.is_(None))
    )


def _create_missing_occurrences(report: NoteAttributionReport, now) -> None:
    rows = db.session.execute(_templates_without_occurrence()).all()
    if rows:
        db.session.execute(insert(StudyApplication), [
            {
                "id": uuid_str(),
                "note_type_id": note_type_id,
                "template_id": template_id,
                "occurrence_key": COMPAT_OCCURRENCE_KEY,
                "source_ord": position if position is not None else 0,
                "status_code": "ACTIVE",
                "created_at": now,
                "updated_at": now,
            }
            for template_id, note_type_id, position in rows
        ])
    db.session.commit()
    report.occurrences_created = len(rows)


def _bind_cards(report: NoteAttributionReport, size: int) -> None:
    last_id = ""
    while True:
        rows = db.session.execute(
            select(Card.id, Card.note_id, Card.template_id)
            .where(Card.application_id.is_(None), Card.id > last_id)
            .order_by(Card.id.asc())
            .limit(size)
        ).all()
        if not rows:
            db.session.rollback()
            return
        last_id = str(rows[-1][0])
        compat = dict(db.session.execute(
            select(StudyApplication.template_id, StudyApplication.id).where(
                StudyApplication.template_id.in_({row[2] for row in rows}),
                StudyApplication.occurrence_key == COMPAT_OCCURRENCE_KEY,
            )
        ).all())
        taken = {
            (str(note_id), str(application_id))
            for note_id, application_id in db.session.execute(
                select(Card.note_id, Card.application_id).where(
                    Card.note_id.in_({row[1] for row in rows}),
                    Card.application_id.in_(set(compat.values()) or {""}),
                )
            ).all()
        }
        application_by_card = {}
        for card_id, note_id, template_id in rows:
            application_id = compat.get(template_id)
            if application_id is None:
                continue  # its Template was removed meanwhile; the Card cascades
            key = (str(note_id), str(application_id))
            if key in taken:
                report.duplicate_cards.append(str(card_id))
                continue
            taken.add(key)
            application_by_card[str(card_id)] = application_id
        if application_by_card:
            result = db.session.execute(
                update(Card)
                .where(Card.id.in_(list(application_by_card)), Card.application_id.is_(None))
                .values(application_id=case(application_by_card, value=Card.id))
                .execution_options(synchronize_session=False)
            )
            report.cards_bound += int(result.rowcount or 0)
        db.session.commit()
        report.batches += 1


def _attribute_refs(report: NoteAttributionReport, size: int) -> None:
    last_id = ""
    while True:
        rows = db.session.execute(
            select(ConnectSourceCardRef.id, Card.note_id)
            .join(Card, Card.id == ConnectSourceCardRef.card_id)
            .where(_stale_ref_condition(), ConnectSourceCardRef.id > last_id)
            .order_by(ConnectSourceCardRef.id.asc())
            .limit(size)
        ).all()
        if not rows:
            db.session.rollback()
            return
        last_id = str(rows[-1][0])
        note_by_ref = {str(ref_id): str(note_id) for ref_id, note_id in rows}
        result = db.session.execute(
            update(ConnectSourceCardRef)
            .where(ConnectSourceCardRef.id.in_(list(note_by_ref)))
            .values(note_id=case(note_by_ref, value=ConnectSourceCardRef.id))
            .execution_options(synchronize_session=False)
        )
        report.refs_attributed += int(result.rowcount or 0)
        db.session.commit()
        report.batches += 1


def _attribute_events(report: NoteAttributionReport, size: int) -> None:
    last_id = 0
    while True:
        rows = db.session.execute(
            select(ReviewEvent.id, ReviewEvent.card_id)
            .where(ReviewEvent.id > last_id, ReviewEvent.note_id.is_(None))
            .order_by(ReviewEvent.id.asc())
            .limit(size)
        ).all()
        if not rows:
            db.session.rollback()
            return
        last_id = int(rows[-1][0])
        card_ids = {card_id for _event_id, card_id in rows if card_id}
        note_by_card = dict(db.session.execute(
            select(Card.id, Card.note_id).where(Card.id.in_(card_ids))
        ).all()) if card_ids else {}
        note_by_event = {
            int(event_id): note_by_card[card_id]
            for event_id, card_id in rows
            if note_by_card.get(card_id)
        }
        if note_by_event:
            result = db.session.execute(
                update(ReviewEvent)
                .where(ReviewEvent.id.in_(list(note_by_event)), ReviewEvent.note_id.is_(None))
                .values(note_id=case(note_by_event, value=ReviewEvent.id))
                .execution_options(synchronize_session=False)
            )
            report.attributed_events += int(result.rowcount or 0)
        db.session.commit()
        report.batches += 1


def backfill_phase6_attribution(*, apply: bool, batch_size: int = 2000) -> NoteAttributionReport:
    report = NoteAttributionReport(applied=bool(apply))
    _survey(report)
    if not apply:
        report.unresolved_events = _count(
            select(func.count()).select_from(ReviewEvent)
            .outerjoin(Card, Card.id == ReviewEvent.card_id)
            .where(ReviewEvent.note_id.is_(None), Card.id.is_(None))
        )
        db.session.rollback()
        return report
    db.session.rollback()
    size = max(1, int(batch_size))
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    _create_missing_occurrences(report, now)
    _bind_cards(report, size)
    _attribute_refs(report, size)
    _attribute_events(report, size)
    report.unresolved_events = _count(
        select(func.count()).select_from(ReviewEvent).where(ReviewEvent.note_id.is_(None))
    )
    db.session.rollback()
    return report
