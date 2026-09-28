"""Bounded, read-only traversal of the durable Study batch outbox."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, or_

from models.study_session_batch import StudySessionBatch


@dataclass(frozen=True)
class StudyBatchRecoveryCursor:
    enqueued_at: datetime
    session_id: str
    batch_sequence: int
    row_id: str
    sweep_end: tuple[datetime, str, int, str]

    @classmethod
    def from_row(cls, row: StudySessionBatch, *, sweep_end):
        return cls(row.enqueued_at, row.session_id, row.batch_sequence, row.id, sweep_end)


def read_admitted_batch_page(*, limit: int, after: StudyBatchRecoveryCursor | None = None):
    """Keyset pagination keeps blocked head rows from starving later admissions.

    Caller owns the read transaction and must release it before queue I/O. A
    cursor is only a scanning hint: a full new sweep still starts at the head.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("Batch recovery page size must be between 1 and 1000.")
    columns = (
        StudySessionBatch.enqueued_at, StudySessionBatch.session_id,
        StudySessionBatch.batch_sequence, StudySessionBatch.id,
    )
    query = StudySessionBatch.query.filter_by(status="enqueued")
    # Fix a high-water mark for this sweep. Otherwise a steady stream of new
    # admissions can prevent wraparound forever, starving older repaired rows.
    if after is None:
        last = query.with_entities(*columns).order_by(*(column.desc() for column in columns)).first()
        if last is None:
            return [], None
        sweep_end = tuple(last)
    else:
        sweep_end = after.sweep_end
    query = query.filter(or_(
        *(
            and_(*(columns[j] == sweep_end[j] for j in range(i)), column < sweep_end[i])
            for i, column in enumerate(columns)
        ),
        and_(*(column == sweep_end[i] for i, column in enumerate(columns))),
    ))
    if after is not None:
        values = (after.enqueued_at, after.session_id, after.batch_sequence, after.row_id)
        query = query.filter(or_(*(
            and_(*(columns[j] == values[j] for j in range(i)), column > values[i])
            for i, column in enumerate(columns)
        )))
    rows = query.populate_existing().order_by(*(column.asc() for column in columns)).limit(limit).all()
    cursor = StudyBatchRecoveryCursor.from_row(rows[-1], sweep_end=sweep_end) if len(rows) == limit else None
    return rows, cursor
