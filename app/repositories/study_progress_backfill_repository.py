"""Persistence primitives for the resumable Phase 4 progress backfill.

The service owns transaction boundaries.  This repository never commits or
rolls back and every source page is ordered by the immutable CardProgress
primary key; OFFSET pagination is deliberately unsupported.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from models.card import Card
from models.card_progress import CardProgress
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.note import Note
from models.study_progress_backfill_checkpoint import StudyProgressBackfillCheckpoint
from models.study_progress_backfill_disposition import StudyProgressBackfillDisposition
from models.study_progress_backfill_run import StudyProgressBackfillRun
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_subject import StudyProgressSubject
from models.user import User


@dataclass(frozen=True)
class CardProgressSourceRow:
    progress: CardProgress
    resolved_card_id: str | None
    card_note_id: str | None
    card_created_at: datetime | None
    resolved_note_id: str | None
    note_owner_user_id: int | None
    note_deck_id: int | None
    learner_exists: bool

    @property
    def source_id(self) -> int:
        return int(self.progress.id)

    @property
    def subject_key(self) -> tuple[int, str] | None:
        if self.resolution_code is not None or self.resolved_note_id is None:
            return None
        return int(self.progress.user_id), str(self.resolved_note_id)

    @property
    def resolution_code(self) -> str | None:
        if self.progress.card_id is None:
            return "UNRESOLVABLE_NULL_CARD_ID"
        if self.resolved_card_id is None:
            return "UNRESOLVABLE_MISSING_CARD"
        if self.card_note_id is None:
            return "UNRESOLVABLE_NULL_NOTE_ID"
        if self.resolved_note_id is None:
            return "UNRESOLVABLE_MISSING_NOTE"
        if not self.learner_exists:
            return "UNRESOLVABLE_MISSING_LEARNER"
        return None


def source_progress_bounds(session: Session) -> tuple[int | None, int | None, int]:
    minimum, maximum, count = session.execute(
        select(
            func.min(CardProgress.id),
            func.max(CardProgress.id),
            func.count(CardProgress.id),
        )
    ).one()
    return (
        int(minimum) if minimum is not None else None,
        int(maximum) if maximum is not None else None,
        int(count or 0),
    )


def _source_statement():
    return (
        select(
            CardProgress,
            Card.id.label("resolved_card_id"),
            Card.note_id.label("card_note_id"),
            Card.created_at.label("card_created_at"),
            Note.id.label("resolved_note_id"),
            Note.user_id.label("note_owner_user_id"),
            Note.deck_id.label("note_deck_id"),
            User.id.label("resolved_learner_id"),
        )
        .outerjoin(Card, Card.id == CardProgress.card_id)
        .outerjoin(Note, Note.id == Card.note_id)
        .outerjoin(User, User.id == CardProgress.user_id)
    )


def _source_rows(rows: Iterable[object]) -> tuple[CardProgressSourceRow, ...]:
    return tuple(
        CardProgressSourceRow(
            progress=row.CardProgress,
            resolved_card_id=(
                str(row.resolved_card_id) if row.resolved_card_id is not None else None
            ),
            card_note_id=str(row.card_note_id) if row.card_note_id is not None else None,
            card_created_at=row.card_created_at,
            resolved_note_id=(
                str(row.resolved_note_id) if row.resolved_note_id is not None else None
            ),
            note_owner_user_id=(
                int(row.note_owner_user_id)
                if row.note_owner_user_id is not None
                else None
            ),
            note_deck_id=int(row.note_deck_id) if row.note_deck_id is not None else None,
            learner_exists=row.resolved_learner_id is not None,
        )
        for row in rows
    )


def load_source_page(
    session: Session,
    *,
    after_id: int | None,
    high_water_id: int,
    limit: int,
) -> tuple[CardProgressSourceRow, ...]:
    statement = _source_statement().where(CardProgress.id <= int(high_water_id))
    if after_id is not None:
        statement = statement.where(CardProgress.id > int(after_id))
    statement = statement.order_by(CardProgress.id.asc()).limit(int(limit))
    return _source_rows(session.execute(statement).all())


def lock_and_reload_source_rows(
    session: Session, source_ids: Iterable[int]
) -> tuple[CardProgressSourceRow, ...]:
    ids = sorted({int(value) for value in source_ids})
    if not ids:
        return ()
    # Lock only the authority table here.  Outer-joined Card/Note/User rows are
    # resolved afterwards without introducing a reverse lock edge.
    session.execute(
        select(CardProgress)
        .where(CardProgress.id.in_(ids))
        .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    statement = (
        _source_statement()
        .where(CardProgress.id.in_(ids))
        .order_by(CardProgress.id.asc())
        .execution_options(populate_existing=True)
    )
    return _source_rows(session.execute(statement).all())


def load_source_rows_by_ids(
    session: Session, source_ids: Iterable[int]
) -> tuple[CardProgressSourceRow, ...]:
    ids = sorted({int(value) for value in source_ids})
    if not ids:
        return ()
    statement = (
        _source_statement()
        .where(CardProgress.id.in_(ids))
        .order_by(CardProgress.id.asc())
    )
    return _source_rows(session.execute(statement).all())


def load_subject_authority_rows(
    session: Session, subject_keys: Iterable[tuple[int, str]]
) -> dict[tuple[int, str], tuple[CardProgressSourceRow, ...]]:
    keys = sorted(
        {(int(learner_id), str(note_id)) for learner_id, note_id in subject_keys},
        key=lambda value: (value[0], value[1].encode("utf-8")),
    )
    grouped: dict[tuple[int, str], list[CardProgressSourceRow]] = {
        key: [] for key in keys
    }
    if not keys:
        return {}
    statement = (
        _source_statement()
        .where(tuple_(CardProgress.user_id, Card.note_id).in_(keys))
        .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
    )
    for row in _source_rows(session.execute(statement).all()):
        key = row.subject_key
        if key in grouped:
            grouped[key].append(row)
    return {key: tuple(rows) for key, rows in grouped.items()}


def approved_subject_contexts(
    session: Session,
    source_rows_by_subject: dict[tuple[int, str], tuple[CardProgressSourceRow, ...]],
) -> frozenset[tuple[int, str]]:
    """Return subjects backed by ownership or a current logical-overlay context."""

    keys = sorted(source_rows_by_subject)
    if not keys:
        return frozenset()
    approved = {
        key
        for key, rows in source_rows_by_subject.items()
        if rows and rows[0].note_owner_user_id == key[0]
    }

    installed_local = session.execute(
        select(DeckInstall.user_id, DeckCloneAddedNote.note_id)
        .join(
            DeckCloneAddedNote,
            DeckCloneAddedNote.deck_install_id == DeckInstall.id,
        )
        .where(tuple_(DeckInstall.user_id, DeckCloneAddedNote.note_id).in_(keys))
    ).all()
    approved.update((int(user_id), str(note_id)) for user_id, note_id in installed_local)

    note_decks = {
        key: int(rows[0].note_deck_id)
        for key, rows in source_rows_by_subject.items()
        if rows and rows[0].note_deck_id is not None
    }
    users = sorted({key[0] for key in note_decks})
    if users:
        direct = {
            (int(user_id), int(deck_id))
            for user_id, deck_id in session.execute(
                select(DeckInstall.user_id, DeckInstall.source_deck_id).where(
                    DeckInstall.user_id.in_(users),
                    DeckInstall.source_deck_id.is_not(None),
                )
            )
        }
        mapped = {
            (int(user_id), int(deck_id))
            for user_id, deck_id in session.execute(
                select(DeckInstall.user_id, DeckCloneDeckMap.source_deck_id)
                .join(
                    DeckCloneDeckMap,
                    DeckCloneDeckMap.deck_install_id == DeckInstall.id,
                )
                .where(
                    DeckInstall.user_id.in_(users),
                    DeckCloneDeckMap.source_deck_id.is_not(None),
                )
            )
        }
        approved.update(
            key
            for key, deck_id in note_decks.items()
            if (key[0], deck_id) in direct or (key[0], deck_id) in mapped
        )
    return frozenset(approved)


def lock_run(
    session: Session, run_id: str
) -> StudyProgressBackfillRun | None:
    return session.execute(
        select(StudyProgressBackfillRun)
        .where(StudyProgressBackfillRun.id == str(run_id))
        .with_for_update()
    ).scalar_one_or_none()


def lock_checkpoint(
    session: Session, run_id: str, *, shard_no: int = 0
) -> StudyProgressBackfillCheckpoint | None:
    return session.execute(
        select(StudyProgressBackfillCheckpoint)
        .where(
            StudyProgressBackfillCheckpoint.run_id == str(run_id),
            StudyProgressBackfillCheckpoint.shard_no == int(shard_no),
        )
        .with_for_update()
    ).scalar_one_or_none()


def upsert_disposition(
    session: Session,
    *,
    run_id: str,
    source_row_key: bytes,
    subject_id: int | None,
    observed_generation: int | None,
    observed_revision: int | None,
    source_hash: bytes,
    disposition_code: str,
    reason_code: str | None,
    result_hash: bytes | None,
    evidence_payload: dict[str, object],
    evidence_payload_size: int,
    evidence_payload_hash: bytes,
    now_utc: datetime,
) -> StudyProgressBackfillDisposition:
    row = session.execute(
        select(StudyProgressBackfillDisposition)
        .where(
            StudyProgressBackfillDisposition.run_id == str(run_id),
            StudyProgressBackfillDisposition.source_kind == "CARD_PROGRESS",
            StudyProgressBackfillDisposition.source_row_key == source_row_key,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        row = StudyProgressBackfillDisposition(
            run_id=str(run_id),
            source_kind="CARD_PROGRESS",
            source_row_key=source_row_key,
            created_at=now_utc,
            attempt_count=1,
        )
        session.add(row)
    else:
        row.attempt_count = int(row.attempt_count) + 1
    row.subject_id = subject_id
    row.observed_generation = observed_generation
    row.observed_revision = observed_revision
    row.source_hash = source_hash
    row.disposition_code = disposition_code
    row.reason_code = reason_code
    row.result_hash = result_hash
    row.evidence_payload = evidence_payload
    row.evidence_payload_size = evidence_payload_size
    row.evidence_payload_hash = evidence_payload_hash
    row.updated_at = now_utc
    return row


def disposition_counts(session: Session, run_id: str) -> dict[str, int]:
    return {
        str(code): int(count)
        for code, count in session.execute(
            select(
                StudyProgressBackfillDisposition.disposition_code,
                func.count(StudyProgressBackfillDisposition.id),
            )
            .where(StudyProgressBackfillDisposition.run_id == str(run_id))
            .group_by(StudyProgressBackfillDisposition.disposition_code)
        )
    }


def load_retry_dispositions(
    session: Session,
    *,
    run_id: str,
    after_id: int | None,
    high_water_id: int,
) -> tuple[StudyProgressBackfillDisposition, ...]:
    """Return pending source rows in numeric keyset order.

    ``source_row_key`` is VARBINARY for cross-source identities, so SQL lexical
    order is not numeric CardProgress order.  Retry volume is bounded by failed
    batches; parse and sort it explicitly instead of pretending the binary key
    is an integer index.
    """

    rows = tuple(
        session.execute(
            select(StudyProgressBackfillDisposition).where(
                StudyProgressBackfillDisposition.run_id == str(run_id),
                StudyProgressBackfillDisposition.source_kind == "CARD_PROGRESS",
                StudyProgressBackfillDisposition.disposition_code == "RETRY_PENDING",
            )
        ).scalars()
    )
    selected: list[tuple[int, StudyProgressBackfillDisposition]] = []
    for row in rows:
        try:
            source_id = int(bytes(row.source_row_key).decode("ascii"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError("A CARD_PROGRESS retry key is not a numeric identity.") from exc
        if source_id > int(high_water_id) or (
            after_id is not None and source_id <= int(after_id)
        ):
            continue
        selected.append((source_id, row))
    selected.sort(key=lambda item: item[0])
    return tuple(row for _source_id, row in selected)


def latest_contributor_for_source(
    session: Session, *, source_progress_id: int
) -> StudyProgressContributor | None:
    return session.execute(
        select(StudyProgressContributor)
        .where(StudyProgressContributor.source_progress_id == int(source_progress_id))
        .order_by(
            StudyProgressContributor.subject_generation.desc(),
            StudyProgressContributor.id.desc(),
        )
        .with_for_update()
        .limit(1)
    ).scalar_one_or_none()


def load_subjects_by_id(
    session: Session, subject_ids: Iterable[int]
) -> dict[int, StudyProgressSubject]:
    ids = sorted({int(value) for value in subject_ids})
    if not ids:
        return {}
    return {
        int(row.id): row
        for row in session.execute(
            select(StudyProgressSubject).where(StudyProgressSubject.id.in_(ids))
        ).scalars()
    }
