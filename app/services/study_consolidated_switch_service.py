"""Switch the NOTE storage profile CANONICAL_V1 -> CONSOLIDATED_V1 (ADR P10 §2.6).

One-way, in a write freeze, as one transaction that takes the profile row
exclusively (every NOTE route fence holds it shared). The same transaction
copies each subject's state (``study_progress_states``), authority revision
(``study_authority_subject_tokens``), availability and history/provenance (its
ACTIVE contributors' ``study_progress_availability``) onto the subject row.
Every copied row is verified first: token, state and subject agree on
generation and hash, every live Card's availability is identical and equals
the availability recomputed from the state. Any disagreement blocks the switch
and nothing is written. The old tables are left untouched for audit and
restore until contraction.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.repositories import study_authority_repository as repository
from app.services.study_note_card_projection import NoteCardBurial, project_note_state
from app.services.study_progress_contract import CONSOLIDATED_STORAGE_PROFILE
from app.services.study_progress_shadow_codec import StudyProgressCodecError
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.study_session_batch import StudySessionBatch
from models.user import User

SOURCE = "CANONICAL_V1"
TARGET = CONSOLIDATED_STORAGE_PROFILE
_TERMINAL_BATCH_STATUSES = ("completed", "failed")
_CHUNK = 1000
_SAMPLES = 5
_STATE_FIELDS = (
    "algorithm_key",
    "algorithm_version",
    "state_schema_version",
    "storage_codec",
    "state_payload",
    "state_payload_size",
    "algorithm_state_hash",
    "semantic_state_hash",
)


class ConsolidatedSwitchError(RuntimeError):
    def __init__(self, code: str, message: str, *, blockers: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.blockers = blockers


def _bytes(value):
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    return value


def _system_blockers(session: Session) -> list[str]:
    blockers = []
    if TARGET not in repository.SUPPORTED_STORAGE_PROFILES:
        blockers.append("RELEASE_DOES_NOT_SUPPORT_CONSOLIDATED_V1")
    if session.execute(
        select(func.count()).select_from(StudyAuthorityEnrollment)
        .where(StudyAuthorityEnrollment.mode_code != "NOTE")
    ).scalar_one():
        blockers.append("LEGACY_LEARNERS")
    if session.execute(
        select(func.count()).select_from(User).where(
            ~select(StudyAuthorityEnrollment.learner_user_id)
            .where(StudyAuthorityEnrollment.learner_user_id == User.id)
            .exists()
        )
    ).scalar_one():
        blockers.append("UNENROLLED_USERS")
    if session.execute(
        select(func.count()).select_from(StudySessionBatch)
        .where(StudySessionBatch.status.notin_(_TERMINAL_BATCH_STATUSES))
    ).scalar_one():
        blockers.append("UNFINISHED_BATCHES")
    return blockers


def _consolidated_values(session: Session, subjects: list[StudyProgressSubject], problems) -> list[dict[str, Any]]:
    """Verified row values for one chunk of subjects; problems are collected, not raised."""

    ids = [int(subject.id) for subject in subjects]
    states = {
        int(row.subject_id): row
        for row in session.execute(
            select(StudyProgressState).where(StudyProgressState.subject_id.in_(ids))
        ).scalars()
    }
    tokens = {
        int(row.subject_id): row
        for row in session.execute(
            select(StudyAuthoritySubjectToken).where(StudyAuthoritySubjectToken.subject_id.in_(ids))
        ).scalars()
    }
    live = defaultdict(list)
    for contributor, availability in session.execute(
        select(StudyProgressContributor, StudyProgressAvailability)
        .outerjoin(StudyProgressAvailability, StudyProgressAvailability.contributor_id == StudyProgressContributor.id)
        .where(
            StudyProgressContributor.subject_id.in_(ids),
            StudyProgressContributor.contributor_status == "ACTIVE",
        )
    ).all():
        live[int(contributor.subject_id)].append((contributor, availability))

    values = []
    for subject in subjects:
        subject_id = int(subject.id)
        generation = int(subject.subject_generation)
        state = states.get(subject_id)
        token = tokens.get(subject_id)
        rows = live.get(subject_id, [])
        if state is None:
            if rows:
                problems["PRISTINE_SUBJECT_HAS_CONTRIBUTORS"].append(subject_id)
                continue
            if token is not None and token.semantic_state_hash is not None:
                problems["TOKEN_WITHOUT_STATE"].append(subject_id)
                continue
            values.append({
                "id": subject_id,
                "authority_revision": int(token.authority_revision) if token is not None else 0,
            })
            continue
        state_hash = _bytes(state.semantic_state_hash)
        if (
            token is None
            or int(token.subject_generation) != generation
            or int(state.subject_generation) != generation
            or _bytes(token.semantic_state_hash) != state_hash
            or int(state.mirror_revision) != int(subject.mirror_revision)
        ):
            problems["STATE_TOKEN_DIVERGED"].append(subject_id)
            continue
        if not rows or any(availability is None for _contributor, availability in rows):
            problems["INCOMPLETE_AVAILABILITY"].append(subject_id)
            continue
        anchors = {
            (
                availability.projection_version, availability.normalized_queue, availability.due_at,
                availability.due_day, bool(availability.is_suspended), bool(availability.is_buried),
                availability.buried_until_day, int(availability.subject_generation),
                _bytes(availability.semantic_state_hash),
            )
            for _contributor, availability in rows
        }
        if len(anchors) != 1:
            problems["SIBLING_AVAILABILITY_DIVERGED"].append(subject_id)
            continue
        (projection_version, queue, due_at, due_day, suspended, buried, buried_until,
         availability_generation, availability_hash) = next(iter(anchors))
        try:
            projected = project_note_state(
                state.state_payload,
                burial=NoteCardBurial(
                    is_buried=buried,
                    buried_until_day=int(buried_until) if buried_until is not None else None,
                ),
            )
        except StudyProgressCodecError:
            problems["STATE_NOT_PROJECTABLE"].append(subject_id)
            continue
        if (
            availability_generation != generation
            or availability_hash != state_hash
            or projected.semantic_state_hash != state_hash
            or (projected.projection_version, projected.normalized_queue, projected.due_at,
                projected.due_day, projected.is_suspended)
            != (projection_version, queue, due_at, due_day, suspended)
        ):
            problems["AVAILABILITY_DIFFERS_FROM_STATE"].append(subject_id)
            continue
        completeness = {str(contributor.history_completeness_code) for contributor, _a in rows}
        latest = max(rows, key=lambda item: (item[0].updated_at, int(item[0].id)))[0]
        row = {name: getattr(state, name) for name in _STATE_FIELDS}
        row.update({
            "id": subject_id,
            "algorithm_state_hash": _bytes(state.algorithm_state_hash),
            "semantic_state_hash": state_hash,
            "authority_revision": int(token.authority_revision),
            "projection_version": projection_version,
            "normalized_queue": queue,
            "due_at": due_at,
            "due_day": due_day,
            "is_suspended": suspended,
            "is_buried": buried,
            "buried_until_day": buried_until,
            "history_completeness_code": (
                completeness.pop() if len(completeness) == 1 else "HISTORY_MIXED_PARTIAL"
            ),
            "current_provenance_code": str(latest.current_provenance_code),
        })
        values.append(row)
    return values


def _prepare(session: Session) -> tuple[list[list[dict[str, Any]]], dict[str, Any], list[str]]:
    problems: dict[str, list[int]] = defaultdict(list)
    batches: list[list[dict[str, Any]]] = []
    stateful = pristine = 0
    last_id = 0
    callers_objects = set(session.identity_map.keys())
    while True:
        subjects = list(session.execute(
            select(StudyProgressSubject)
            .where(StudyProgressSubject.id > last_id)
            .order_by(StudyProgressSubject.id.asc())
            .limit(_CHUNK)
        ).scalars())
        if not subjects:
            break
        last_id = int(subjects[-1].id)
        values = _consolidated_values(session, subjects, problems)
        stateful += sum(1 for row in values if "state_payload" in row)
        pristine += sum(1 for row in values if "state_payload" not in row)
        batches.append(values)
        # The values are plain dicts; keep the identity map small on 40k rows
        # without detaching what the caller had loaded.
        for key, loaded in list(session.identity_map.items()):
            if key not in callers_objects:
                session.expunge(loaded)
    report = {
        "subjects_with_state": stateful,
        "subjects_without_state": pristine,
        "states": int(session.execute(select(func.count()).select_from(StudyProgressState)).scalar_one()),
        "problems": {code: {"count": len(ids), "sample_subject_ids": ids[:_SAMPLES]} for code, ids in problems.items()},
    }
    blockers = [f"SUBJECT_EVIDENCE_{code}" for code in problems]
    if stateful != report["states"]:
        blockers.append("STATE_COUNT_MISMATCH")
    return batches, report, blockers


def plan_consolidated_switch(session: Session) -> dict[str, Any]:
    """Read-only: what the switch would copy now, and what blocks it."""

    current = repository.read_study_storage_profile(session)
    _batches, report, evidence_blockers = _prepare(session)
    blockers = _system_blockers(session) + evidence_blockers
    if current != SOURCE:
        blockers.append(f"PROFILE_IS_{current}")
    session.rollback()
    return {"current_profile": current, "target_profile": TARGET, "blockers": blockers, **report}


def apply_consolidated_switch(session: Session, *, now_utc: datetime | None = None) -> dict[str, Any]:
    """Copy and switch in the caller's transaction; the caller commits."""

    now = (now_utc or datetime.now(timezone.utc)).replace(tzinfo=None, microsecond=0)
    current = repository.read_study_storage_profile(session, lock="update")
    if current != SOURCE:
        raise ConsolidatedSwitchError(
            "PROFILE_NOT_CANONICAL", f"The NOTE storage profile is {current}, not {SOURCE}."
        )
    blockers = _system_blockers(session)
    batches, report, evidence_blockers = _prepare(session)
    blockers += evidence_blockers
    if blockers:
        raise ConsolidatedSwitchError(
            "SWITCH_BLOCKED",
            f"The NOTE storage profile cannot switch yet: {', '.join(blockers)}.",
            blockers=tuple(blockers),
        )
    for values in batches:
        with_state = [row for row in values if "state_payload" in row]
        without_state = [row for row in values if "state_payload" not in row]
        for rows in (with_state, without_state):
            if rows:
                session.execute(update(StudyProgressSubject), [{**row, "updated_at": now} for row in rows])
    # Bulk UPDATE by primary key does not refresh loaded objects.
    session.expire_all()
    profile = session.get(StudyAuthorityStorageProfile, 1)
    profile.profile_code = TARGET
    profile.epoch = int(profile.epoch or 1) + 1
    profile.switched_at = now
    profile.updated_at = now
    session.flush()
    copied = int(session.execute(
        select(func.count()).select_from(StudyProgressSubject)
        .where(StudyProgressSubject.semantic_state_hash.isnot(None))
    ).scalar_one())
    if copied != report["states"]:
        raise ConsolidatedSwitchError(
            "SWITCH_COPY_INCOMPLETE",
            f"{copied} consolidated rows for {report['states']} states.",
        )
    return {
        "switched_at_utc": now.isoformat() + "Z",
        "profile": TARGET,
        "epoch": int(profile.epoch),
        "subjects_with_state": report["subjects_with_state"],
        "subjects_without_state": report["subjects_without_state"],
    }
