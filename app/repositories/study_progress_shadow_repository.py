"""Transaction-neutral storage primitives for Phase 4 shadow progress.

P4-06 exposes only the coordination-row lock and read primitives needed by
later mirror/backfill tasks.  Nothing in this module commits or is connected to
an authoritative writer yet.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.repositories.study_inserted_rows import SUBJECT, inserted_in_transaction
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_subject import StudyProgressSubject


class StaleStudyProgressFenceError(RuntimeError):
    code = "STALE_SHADOW_FINALIZATION_FENCE"


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


def lock_subjects_in_canonical_order(
    session: Session,
    subjects: Iterable[tuple[int, str | bytes, str | None]],
    *,
    now_utc: datetime,
) -> tuple[StudyProgressSubject, ...]:
    prepared_by_key: dict[tuple[int, bytes], str | None] = {}
    for learner_user_id, key, live_note_id in subjects:
        encoded = (
            key
            if isinstance(key, bytes)
            else encode_logical_key(key, max_bytes=144, field_name="logical_note_key")
        )
        identity = (learner_user_id, encoded)
        existing_live_note_id = prepared_by_key.get(identity)
        if identity in prepared_by_key and existing_live_note_id != live_note_id:
            raise ValueError("One logical subject cannot have conflicting live Note pointers.")
        prepared_by_key[identity] = live_note_id
    prepared = sorted(
        (
            (learner_user_id, encoded, live_note_id)
            for (learner_user_id, encoded), live_note_id in prepared_by_key.items()
        ),
        key=lambda item: (item[0], item[1]),
    )
    return tuple(
        ensure_and_lock_subject(
            session,
            learner_user_id=learner_user_id,
            logical_note_key=key,
            live_note_id=live_note_id,
            now_utc=now_utc,
        )
        for learner_user_id, key, live_note_id in prepared
    )


def load_current_contributors(
    session: Session, *, subject_id: int, subject_generation: int, for_update: bool
) -> tuple[StudyProgressContributor, ...]:
    statement = (
        select(StudyProgressContributor)
        .where(
            StudyProgressContributor.subject_id == subject_id,
            StudyProgressContributor.subject_generation == subject_generation,
            StudyProgressContributor.contributor_status == "ACTIVE",
        )
        .order_by(
            StudyProgressContributor.logical_card_key,
            StudyProgressContributor.id,
        )
    )
    # A subject inserted by this transaction has no contributors yet; locking
    # the empty range would only take a gap lock (see study_inserted_rows).
    if for_update and not inserted_in_transaction(session, SUBJECT, subject_id):
        statement = statement.with_for_update()
    return tuple(session.execute(statement).scalars())


def find_attached_contributor(
    session: Session, *, live_card_progress_id: int
) -> StudyProgressContributor | None:
    return session.execute(
        select(StudyProgressContributor).where(
            StudyProgressContributor.live_card_progress_id == live_card_progress_id
        )
    ).scalar_one_or_none()


def assert_subject_finalization_fence(
    subject: StudyProgressSubject,
    *,
    expected_generation: int,
    expected_mirror_revision: int,
) -> None:
    """Fail before finalization if a locked envelope no longer matches input."""

    actual = (int(subject.subject_generation), int(subject.mirror_revision))
    expected = (int(expected_generation), int(expected_mirror_revision))
    if actual != expected:
        raise StaleStudyProgressFenceError(
            f"Shadow subject fence changed from {expected!r} to {actual!r}."
        )
