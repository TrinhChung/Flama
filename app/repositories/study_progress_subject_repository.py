"""Create-if-absent and lock one learner/Note progress row (ADR P10)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from models.study_progress_subject import StudyProgressSubject


def encode_logical_key(value: str, *, max_bytes: int, field_name: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string.")
    encoded = value.encode("utf-8")
    if len(encoded) > max_bytes:
        raise ValueError(f"{field_name} exceeds {max_bytes} UTF-8 bytes.")
    return encoded


def ensure_and_lock_subject(
    session: Session,
    *,
    learner_user_id: int,
    logical_note_key: str | bytes,
    live_note_id: str | None,
    now_utc: datetime,
) -> StudyProgressSubject:
    """Create-if-absent and row-lock one learner/Note envelope.

    The duplicate branch is a no-op and deliberately does not update the live
    pointer or timestamps.  The transaction owner remains responsible for
    commit/rollback.
    """

    encoded_key = (
        logical_note_key
        if isinstance(logical_note_key, bytes)
        else encode_logical_key(
            logical_note_key, max_bytes=144, field_name="logical_note_key"
        )
    )
    if not encoded_key or len(encoded_key) > 144:
        raise ValueError("logical_note_key must contain 1..144 bytes.")
    if not isinstance(learner_user_id, int) or isinstance(learner_user_id, bool):
        raise ValueError("learner_user_id must be an integer.")
    if not isinstance(now_utc, datetime):
        raise ValueError("now_utc must be a datetime.")

    table = StudyProgressSubject.__table__
    values = {
        "learner_user_id": learner_user_id,
        "logical_note_key": encoded_key,
        "live_note_id": live_note_id,
        "created_at": now_utc,
        "updated_at": now_utc,
    }
    dialect = session.get_bind().dialect.name
    if dialect == "mysql":
        statement = mysql_insert(table).values(**values)
        statement = statement.on_duplicate_key_update(id=table.c.id)
    elif dialect == "sqlite":
        statement = sqlite_insert(table).values(**values)
        statement = statement.on_conflict_do_nothing(
            index_elements=[table.c.learner_user_id, table.c.logical_note_key]
        )
    else:
        existing = session.execute(
            select(StudyProgressSubject.id).where(
                StudyProgressSubject.learner_user_id == learner_user_id,
                StudyProgressSubject.logical_note_key == encoded_key,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(StudyProgressSubject(**values))
            session.flush()
        statement = None
    if statement is not None:
        # The upsert cannot tell an insert from an existing row (PyMySQL runs
        # with CLIENT_FOUND_ROWS), so this path never marks the subject as
        # inserted and its readers keep their locks.
        session.execute(statement)

    return session.execute(
        select(StudyProgressSubject)
        .where(
            StudyProgressSubject.learner_user_id == learner_user_id,
            StudyProgressSubject.logical_note_key == encoded_key,
        )
        .with_for_update()
    ).scalar_one()
