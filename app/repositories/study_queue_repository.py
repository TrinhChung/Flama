"""Minimal Card metadata for counting and ordering an already-authorized queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from models.card import Card


@dataclass(frozen=True, slots=True)
class StudyQueueCardRef:
    id: str
    note_id: str
    created_at: datetime
    order_key: str | None = None

    def __post_init__(self):
        if self.order_key is None:
            object.__setattr__(self, 'order_key', self.id)


def query_study_queue_card_refs(card_query) -> tuple[StudyQueueCardRef, ...]:
    """Keep the caller's filters and ORM Card identity deduplication.

    Availability and queue ordering need no Note content or Card templates.
    The selected Card must still be hydrated and read under the normal
    authority locks before it is rendered or returned to a learner.
    """

    rows = card_query.with_entities(Card.id, Card.note_id, Card.created_at, Card.order_key).order_by(Card.id.asc()).all()
    by_id = {
        str(card_id): StudyQueueCardRef(str(card_id), str(note_id), created_at, str(order_key))
        for card_id, note_id, created_at, order_key in rows
    }
    return tuple(by_id.values())
