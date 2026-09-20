"""Resumable, fenced CardProgress -> learner/Note shadow backfill.

CardProgress remains authoritative.  Apply mode owns one small transaction per
keyset batch; dry-run is read-only.  A candidate may finalize only after the
subject generation/revision and the full contributor authority vector have
been re-read under the Phase 4 subject-before-contributor lock order.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import subprocess
from typing import Callable, Iterable, Mapping
from uuid import UUID, uuid4

from flask import current_app
import sqlalchemy as sa
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.repositories import study_progress_backfill_repository as repository
from app.services.study_phase4_preflight_service import PREFLIGHT_SCHEMA_VERSION
from app.services.study_progress_contract import (
    MAPPER_VERSION,
    PROJECTION_VERSION,
    RAW_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_codec import (
    RAW_CARD_PROGRESS_FIELDS,
    StudyProgressCodecError,
    canonical_document,
    canonical_typed_document,
    serialize_raw_card_progress,
)
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    MappingFailure,
    map_card_progress,
)
from app.services import study_progress_shadow_mirror_service as mirror
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_backfill_checkpoint import StudyProgressBackfillCheckpoint
from models.study_progress_backfill_disposition import StudyProgressBackfillDisposition
from models.study_progress_backfill_run import StudyProgressBackfillRun
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject


BACKFILL_SERVICE_VERSION = "study-progress-current-backfill.v1"
SOURCE_ROWS_PER_BATCH = 250
SUBJECTS_PER_BATCH = 100
MAX_STALE_RETRIES = 5
DISPOSITION_SAMPLE_LIMIT = 10
SHADOW_DATABASE_HEAD = "20260913_000039"

_MIRRORED_CODES = frozenset(
    {
        "MIRRORED_SINGLE",
        "MIRRORED_EQUIVALENT_FANIN",
        "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE",
    }
)
_LIFECYCLE_CODES = frozenset(
    {
        "TOMBSTONED_RESET",
        "TOMBSTONED_SUBJECT_DELETED",
        "DETACHED_CONTRIBUTOR_DELETED",
        "REKEYED_CLONE_CUTOVER",
    }
)
_UNSUPPORTED_MAPPING_CODES = frozenset(
    {"UNSUPPORTED_ALGORITHM_IDENTITY", "UNSUPPORTED_STATE_SCHEMA", "UNSUPPORTED_QUEUE"}
)
_CORRUPT_MAPPING_CODES = frozenset(
    {"STATE_HASH_MISMATCH", "STATE_DECODER_UNAVAILABLE"}
)

FaultInjector = Callable[[str, Mapping[str, object]], None]


class StudyProgressBackfillError(RuntimeError):
    code = "STUDY_PROGRESS_BACKFILL_FAILED"


class StudyProgressBackfillDisabledError(StudyProgressBackfillError):
    code = "STUDY_PROGRESS_BACKFILL_DISABLED"


class StaleBackfillBatchError(StudyProgressBackfillError):
    code = "STALE_AUTHORITY_VECTOR"

    def __init__(
        self,
        reason_code: str,
        message: str,
        snapshots: tuple["_SourceSnapshot", ...],
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.snapshots = snapshots


@dataclass(frozen=True)
class BackfillResult:
    mode: str
    status: str
    run_id: str | None
    complete: bool
    batches: int
    source_count: int
    mirrored_count: int
    quarantined_count: int
    unresolvable_count: int
    retry_count: int
    source_progress_high_water_id: int | None
    last_source_id: int | None
    disposition_counts: dict[str, int]
    samples: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "status": self.status,
            "run_id": self.run_id,
            "complete": self.complete,
            "batches": self.batches,
            "source_count": self.source_count,
            "mirrored_count": self.mirrored_count,
            "quarantined_count": self.quarantined_count,
            "unresolvable_count": self.unresolvable_count,
            "retry_count": self.retry_count,
            "source_progress_high_water_id": self.source_progress_high_water_id,
            "last_source_id": self.last_source_id,
            "disposition_counts": dict(sorted(self.disposition_counts.items())),
            "samples": list(self.samples),
            "settings": {
                "source_rows_per_batch": SOURCE_ROWS_PER_BATCH,
                "subjects_per_batch": SUBJECTS_PER_BATCH,
                "max_stale_retries": MAX_STALE_RETRIES,
            },
            "backfill_service_version": BACKFILL_SERVICE_VERSION,
        }


@dataclass(frozen=True)
class _SourceSnapshot:
    source_id: int
    learner_user_id: int
    card_id: str | None
    note_id: str | None
    resolution_code: str | None
    revision: int
    source_hash: bytes
    subject_id: int | None
    observed_generation: int | None
    observed_mirror_revision: int | None

    @property
    def subject_key(self) -> tuple[int, str] | None:
        if self.resolution_code is not None or self.note_id is None:
            return None
        return self.learner_user_id, self.note_id


@dataclass(frozen=True)
class _SubjectCandidate:
    key: tuple[int, str]
    subject_id: int | None
    observed_generation: int
    observed_mirror_revision: int
    authority_vector_hash: bytes | None
    context_approved: bool


@dataclass(frozen=True)
class _Batch:
    snapshots: tuple[_SourceSnapshot, ...]
    live_rows_by_id: dict[int, repository.CardProgressSourceRow]
    missing_retry_by_id: dict[int, StudyProgressBackfillDisposition]
    candidates: dict[tuple[int, str], _SubjectCandidate]
    source_rows_by_subject: dict[
        tuple[int, str], tuple[repository.CardProgressSourceRow, ...]
    ]
    active_subject_keys: frozenset[tuple[int, str]]

    @property
    def last_source_id(self) -> int:
        return max(row.source_id for row in self.snapshots)


def _utc_naive(value: datetime | None = None) -> datetime:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is not None:
        return moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _fault(
    injector: FaultInjector | None, boundary: str, **context: object
) -> None:
    if injector is not None:
        injector(boundary, context)


def _source_hash(progress: object) -> bytes:
    try:
        return serialize_raw_card_progress(progress).digest
    except StudyProgressCodecError:
        # Invalid legacy values still need a deterministic source identity so
        # they can be quarantined without copying user-authored content.
        material = tuple(
            (field, type(getattr(progress, field, None)).__name__, repr(getattr(progress, field, None)))
            for field in RAW_CARD_PROGRESS_FIELDS
        )
        return hashlib.sha256(repr(material).encode("utf-8")).digest()


def _source_signature(snapshot: _SourceSnapshot) -> tuple[object, ...]:
    return (
        snapshot.source_id,
        snapshot.learner_user_id,
        snapshot.card_id,
        snapshot.note_id,
        snapshot.resolution_code,
        snapshot.revision,
        snapshot.source_hash,
    )


def _authority_vector_hash(
    rows: Iterable[repository.CardProgressSourceRow],
) -> bytes | None:
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.progress.card_id or "").encode("utf-8"),
            int(row.progress.id),
        ),
    )
    if not ordered:
        return None
    return canonical_document(
        {
            "contributors": [
                {
                    "card_id": str(row.progress.card_id),
                    "progress_id": str(row.progress.id),
                    "raw_progress_hash": _source_hash(row.progress).hex(),
                    "revision": str(row.progress.revision),
                }
                for row in ordered
            ]
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def _locked_authority_vector_hash(plan: mirror.NativeMirrorPlan) -> bytes | None:
    rows = sorted(
        plan.locked_progress_by_card_id.values(),
        key=lambda row: (
            str(row.card_id or "").encode("utf-8"),
            int(row.id),
        ),
    )
    if not rows:
        return None
    return canonical_document(
        {
            "contributors": [
                {
                    "card_id": str(row.card_id),
                    "progress_id": str(row.id),
                    "raw_progress_hash": _source_hash(row).hex(),
                    "revision": str(row.revision),
                }
                for row in rows
            ]
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def _mapping_quarantine(code: str) -> str:
    if code in _UNSUPPORTED_MAPPING_CODES:
        return "QUARANTINED_UNSUPPORTED_STATE"
    if code in _CORRUPT_MAPPING_CODES:
        return "QUARANTINED_CORRUPT_STATE"
    return "QUARANTINED_UNCLASSIFIED_CONTEXT"


def _classify_subject(
    rows: tuple[repository.CardProgressSourceRow, ...],
    *,
    context_approved: bool,
) -> tuple[str, str | None]:
    if not context_approved:
        return "QUARANTINED_UNCLASSIFIED_CONTEXT", "UNCLASSIFIED_CONTEXT"
    mapped: list[MappedCardProgress] = []
    failures: list[MappingFailure] = []
    for row in rows:
        value = map_card_progress(
            row.progress,
            card_created_at=row.card_created_at,
            card_order_key=row.resolved_card_id,
        )
        if isinstance(value, MappingFailure):
            failures.append(value)
        else:
            mapped.append(value)
    if failures:
        return _mapping_quarantine(failures[0].code), failures[0].code
    semantic_hashes = {value.semantic_state_hash for value in mapped}
    if len(semantic_hashes) != 1:
        return "QUARANTINED_STATE_DIVERGENCE", "SEMANTIC_STATE_DIVERGENCE"
    if len(mapped) == 1:
        return "MIRRORED_SINGLE", None
    # Dry-run cannot mutate/synchronize lineage rows.  Distinct lineage is the
    # conservative result unless an already-trusted current projection proves
    # equivalence during apply.
    return "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE", None


def _load_subjects_by_key(
    session: Session, keys: Iterable[tuple[int, str]]
) -> dict[tuple[int, str], StudyProgressSubject]:
    normalized = sorted(
        {(int(user_id), str(note_id)) for user_id, note_id in keys},
        key=lambda value: (value[0], value[1].encode("utf-8")),
    )
    if not normalized:
        return {}
    rows = session.execute(
        select(StudyProgressSubject).where(
            tuple_(
                StudyProgressSubject.learner_user_id,
                StudyProgressSubject.logical_note_key,
            ).in_([(user_id, note_id.encode("utf-8")) for user_id, note_id in normalized])
        )
    ).scalars()
    return {
        (int(row.learner_user_id), bytes(row.logical_note_key).decode("utf-8")): row
        for row in rows
    }


def _snapshot_live_row(
    row: repository.CardProgressSourceRow,
    subject: StudyProgressSubject | None,
) -> _SourceSnapshot:
    return _SourceSnapshot(
        source_id=row.source_id,
        learner_user_id=int(row.progress.user_id),
        card_id=str(row.progress.card_id) if row.progress.card_id is not None else None,
        note_id=row.resolved_note_id,
        resolution_code=row.resolution_code,
        revision=int(row.progress.revision),
        source_hash=_source_hash(row.progress),
        subject_id=int(subject.id) if subject is not None else None,
        observed_generation=int(subject.subject_generation) if subject is not None else None,
        observed_mirror_revision=int(subject.mirror_revision) if subject is not None else None,
    )


def _parse_retry_source_id(row: StudyProgressBackfillDisposition) -> int:
    try:
        return int(bytes(row.source_row_key).decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:  # pragma: no cover - schema/service invariant
        raise StudyProgressBackfillError("Invalid persisted CARD_PROGRESS retry key.") from exc


def _build_batch(
    session: Session,
    *,
    run: StudyProgressBackfillRun,
    checkpoint: StudyProgressBackfillCheckpoint,
) -> _Batch | None:
    high_water = run.source_progress_high_water_id
    if high_water is None:
        return None
    live_page = repository.load_source_page(
        session,
        after_id=checkpoint.last_source_id,
        high_water_id=int(high_water),
        limit=SOURCE_ROWS_PER_BATCH,
    )
    retry_rows = repository.load_retry_dispositions(
        session,
        run_id=str(run.id),
        after_id=checkpoint.last_source_id,
        high_water_id=int(high_water),
    )
    retry_by_id = {_parse_retry_source_id(row): row for row in retry_rows}
    live_by_id = {row.source_id: row for row in live_page}
    candidate_ids = sorted(set(live_by_id) | set(retry_by_id))
    if not candidate_ids:
        return None

    pending_subjects = repository.load_subjects_by_id(
        session,
        [row.subject_id for row in retry_rows if row.subject_id is not None],
    )
    selected_ids: list[int] = []
    selected_subjects: set[tuple[int, str]] = set()
    for source_id in candidate_ids:
        if len(selected_ids) >= SOURCE_ROWS_PER_BATCH:
            break
        live = live_by_id.get(source_id)
        key = live.subject_key if live is not None else None
        if key is None:
            pending = retry_by_id.get(source_id)
            subject = (
                pending_subjects.get(int(pending.subject_id))
                if pending is not None and pending.subject_id is not None
                else None
            )
            if subject is not None:
                key = (
                    int(subject.learner_user_id),
                    bytes(subject.logical_note_key).decode("utf-8"),
                )
        if key is not None and key not in selected_subjects:
            if len(selected_subjects) >= SUBJECTS_PER_BATCH:
                break
            selected_subjects.add(key)
        selected_ids.append(source_id)
    if not selected_ids:
        raise StudyProgressBackfillError("Backfill subject limit made no keyset progress.")

    # A pending source may sit before the live page but still exist.  Reload all
    # selected ids without locks so observation always precedes the global
    # subject -> contributor acquisition order.
    selected_live_rows = repository.load_source_rows_by_ids(session, selected_ids)
    live_by_id = {row.source_id: row for row in selected_live_rows}

    valid_keys = {row.subject_key for row in selected_live_rows if row.subject_key is not None}
    valid_keys.update(selected_subjects)
    subjects = _load_subjects_by_key(session, valid_keys)
    authority = repository.load_subject_authority_rows(session, valid_keys)
    approved = repository.approved_subject_contexts(session, authority)
    candidates = {
        key: _SubjectCandidate(
            key=key,
            subject_id=int(subjects[key].id) if key in subjects else None,
            observed_generation=(int(subjects[key].subject_generation) if key in subjects else 0),
            observed_mirror_revision=(int(subjects[key].mirror_revision) if key in subjects else 0),
            authority_vector_hash=_authority_vector_hash(authority.get(key, ())),
            context_approved=key in approved,
        )
        for key in valid_keys
    }
    snapshots = tuple(
        _snapshot_live_row(live_by_id[source_id], subjects.get(live_by_id[source_id].subject_key))
        if source_id in live_by_id
        else _SourceSnapshot(
            source_id=source_id,
            learner_user_id=(
                int(pending_subjects[int(retry_by_id[source_id].subject_id)].learner_user_id)
                if retry_by_id[source_id].subject_id is not None
                and int(retry_by_id[source_id].subject_id) in pending_subjects
                else 0
            ),
            card_id=None,
            note_id=None,
            resolution_code="RETRY_PENDING",
            revision=int(retry_by_id[source_id].observed_revision or 0),
            source_hash=bytes(retry_by_id[source_id].source_hash),
            subject_id=(
                int(retry_by_id[source_id].subject_id)
                if retry_by_id[source_id].subject_id is not None
                else None
            ),
            observed_generation=(
                int(retry_by_id[source_id].observed_generation)
                if retry_by_id[source_id].observed_generation is not None
                else None
            ),
            observed_mirror_revision=None,
        )
        for source_id in selected_ids
    )
    return _Batch(
        snapshots=snapshots,
        live_rows_by_id=live_by_id,
        missing_retry_by_id={
            source_id: retry_by_id[source_id]
            for source_id in selected_ids
            if source_id not in live_by_id
        },
        candidates=candidates,
        source_rows_by_subject=authority,
        active_subject_keys=frozenset(
            row.subject_key
            for row in selected_live_rows
            if row.subject_key is not None
        ),
    )


def _repository_commit() -> str:
    configured = os.getenv("FLAMA_BUILD_COMMIT", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", configured):
        return configured
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    value = result.stdout.strip().lower() if result is not None and result.returncode == 0 else ""
    if re.fullmatch(r"[0-9a-f]{40}", value):
        return value
    if current_app.testing:
        return "0" * 40
    raise StudyProgressBackfillError("Cannot freeze the repository commit identity.")


def _database_head(session: Session) -> str:
    inspector = sa.inspect(session.get_bind())
    if not inspector.has_table("alembic_version"):
        if current_app.testing:
            return "create-all-test"
        raise StudyProgressBackfillError("alembic_version is required for apply mode.")
    heads = tuple(
        str(value)
        for value in session.execute(
            sa.text("SELECT version_num FROM alembic_version ORDER BY version_num")
        ).scalars()
    )
    if len(heads) != 1:
        raise StudyProgressBackfillError("Apply mode requires exactly one database head.")
    return heads[0]


def _contract_hash(
    *,
    repository_commit: str,
    database_head: str,
    source_high_water_id: int | None,
    source_count: int,
) -> bytes:
    return canonical_typed_document(
        {
            "backfill_service_version": BACKFILL_SERVICE_VERSION,
            "run_kind": "CURRENT_PROGRESS",
            "repository_commit": repository_commit,
            "database_head": database_head,
            "audit_schema_version": PREFLIGHT_SCHEMA_VERSION,
            "mapper_version": MAPPER_VERSION,
            "raw_schema_version": RAW_SCHEMA_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "storage_codec": STORAGE_CODEC,
            "projection_version": PROJECTION_VERSION,
            "source_progress_high_water_id": source_high_water_id,
            "source_count": source_count,
            "settings": {
                "source_rows_per_batch": SOURCE_ROWS_PER_BATCH,
                "subjects_per_batch": SUBJECTS_PER_BATCH,
                "max_stale_retries": MAX_STALE_RETRIES,
            },
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def _normalize_run_id(value: str) -> str:
    try:
        normalized = str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise StudyProgressBackfillError("run_id must be a canonical UUID.") from exc
    if normalized != str(value).lower():
        raise StudyProgressBackfillError("run_id must be a canonical UUID.")
    return normalized


def _create_run(session: Session, *, now_utc: datetime) -> tuple[StudyProgressBackfillRun, StudyProgressBackfillCheckpoint]:
    minimum, maximum, source_count = repository.source_progress_bounds(session)
    if minimum is not None and minimum < 0:
        raise StudyProgressBackfillError("Negative CardProgress ids cannot be keyset-fenced.")
    repository_commit = _repository_commit()
    database_head = _database_head(session)
    run = StudyProgressBackfillRun(
        id=str(uuid4()),
        run_kind="CURRENT_PROGRESS",
        status_code="RUNNING",
        repository_commit=repository_commit,
        database_head=database_head,
        audit_schema_version=PREFLIGHT_SCHEMA_VERSION,
        mapper_version=MAPPER_VERSION,
        state_schema_version=STATE_SCHEMA_VERSION,
        projection_version=PROJECTION_VERSION,
        contract_hash=_contract_hash(
            repository_commit=repository_commit,
            database_head=database_head,
            source_high_water_id=maximum,
            source_count=source_count,
        ),
        observed_at=now_utc,
        source_progress_high_water_id=maximum,
        source_event_high_water_id=None,
        source_count=source_count,
        started_at=now_utc,
        updated_at=now_utc,
    )
    checkpoint = StudyProgressBackfillCheckpoint(
        run_id=run.id,
        shard_no=0,
        status_code="RUNNING",
        range_start_id=minimum,
        range_end_id=maximum,
        last_source_id=None,
        processed_count=0,
        retry_count=0,
        updated_at=now_utc,
    )
    session.add_all((run, checkpoint))
    session.commit()
    return run, checkpoint


def _validate_run_contract(session: Session, run: StudyProgressBackfillRun) -> None:
    expected = {
        "run_kind": "CURRENT_PROGRESS",
        "repository_commit": _repository_commit(),
        "database_head": _database_head(session),
        "audit_schema_version": PREFLIGHT_SCHEMA_VERSION,
        "mapper_version": MAPPER_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "projection_version": PROJECTION_VERSION,
    }
    for field, value in expected.items():
        if str(getattr(run, field)) != str(value):
            raise StudyProgressBackfillError(
                f"Run contract mismatch for {field}; start a new versioned run."
            )
    expected_hash = _contract_hash(
        repository_commit=str(run.repository_commit),
        database_head=str(run.database_head),
        source_high_water_id=(
            int(run.source_progress_high_water_id)
            if run.source_progress_high_water_id is not None
            else None
        ),
        source_count=int(run.source_count),
    )
    if bytes(run.contract_hash) != expected_hash:
        raise StudyProgressBackfillError("Run contract digest does not match current code/settings.")


def _redacted_evidence(
    snapshot: _SourceSnapshot,
    *,
    disposition_code: str,
    reason_code: str | None,
    authority_hash: bytes | None,
) -> object:
    subject_digest = (
        hashlib.sha256(
            f"{snapshot.learner_user_id}:{snapshot.note_id}".encode("utf-8")
        ).hexdigest()[:16]
        if snapshot.note_id is not None
        else None
    )
    return canonical_typed_document(
        {
            "backfill_service_version": BACKFILL_SERVICE_VERSION,
            "source_identity_digest": hashlib.sha256(
                str(snapshot.source_id).encode("ascii")
            ).hexdigest()[:16],
            "subject_identity_digest": subject_digest,
            "disposition_code": disposition_code,
            "reason_code": reason_code,
            "authority_vector_hash": authority_hash.hex() if authority_hash else None,
            "mapper_version": MAPPER_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    )


def _upsert_source_disposition(
    session: Session,
    *,
    run_id: str,
    snapshot: _SourceSnapshot,
    disposition_code: str,
    reason_code: str | None,
    subject_id: int | None,
    generation: int | None,
    mirror_revision: int | None,
    result_hash: bytes | None,
    now_utc: datetime,
) -> None:
    evidence = _redacted_evidence(
        snapshot,
        disposition_code=disposition_code,
        reason_code=reason_code,
        authority_hash=result_hash,
    )
    repository.upsert_disposition(
        session,
        run_id=run_id,
        source_row_key=str(snapshot.source_id).encode("ascii"),
        subject_id=subject_id,
        observed_generation=generation,
        observed_revision=(mirror_revision if mirror_revision is not None else snapshot.revision),
        source_hash=snapshot.source_hash,
        disposition_code=disposition_code,
        reason_code=reason_code,
        result_hash=result_hash,
        evidence_payload=evidence.payload,
        evidence_payload_size=evidence.size,
        evidence_payload_hash=evidence.digest,
        now_utc=now_utc,
    )


def _category_counts(counts: Mapping[str, int]) -> tuple[int, int, int, int]:
    mirrored = sum(count for code, count in counts.items() if code in _MIRRORED_CODES)
    quarantined = sum(
        count for code, count in counts.items() if code.startswith("QUARANTINED_")
    )
    retry = sum(
        count
        for code, count in counts.items()
        if code in {"RETRY_PENDING", "STALE_GENERATION", "STALE_AUTHORITY_VECTOR", "STALE_MAPPER_VERSION"}
    )
    unresolvable = sum(counts.values()) - mirrored - quarantined - retry
    return mirrored, quarantined, unresolvable, retry


def _update_run_counts(session: Session, run: StudyProgressBackfillRun) -> dict[str, int]:
    counts = repository.disposition_counts(session, str(run.id))
    mirrored, quarantined, unresolvable, _retry_pending = _category_counts(counts)
    run.mirrored_count = mirrored
    run.quarantined_count = quarantined
    run.unresolvable_count = unresolvable
    return counts


def _assert_candidate_fences(
    batch: _Batch,
    plans_by_key: dict[tuple[int, str], mirror.NativeMirrorPlan],
) -> None:
    for key, candidate in batch.candidates.items():
        plan = plans_by_key.get(key)
        if plan is None:
            raise StaleBackfillBatchError(
                "STALE_AUTHORITY_VECTOR", "A candidate subject disappeared before locking.", batch.snapshots
            )
        prepared = next(iter(plan.subjects_by_note_id.values()))
        subject = prepared.subject
        if candidate.subject_id is None:
            pristine = (
                int(prepared.expected_generation) == 1
                and int(prepared.expected_mirror_revision) == 0
                and str(subject.status_code) == "NO_CURRENT_PROGRESS"
                and int(subject.contributor_count) == 0
                and subject.authority_vector_hash is None
            )
            if not pristine:
                raise StaleBackfillBatchError(
                    "STALE_GENERATION", "A new subject was materialized after observation.", batch.snapshots
                )
        elif (
            int(subject.id) != candidate.subject_id
            or int(prepared.expected_generation) != candidate.observed_generation
            or int(prepared.expected_mirror_revision) != candidate.observed_mirror_revision
        ):
            raise StaleBackfillBatchError(
                "STALE_GENERATION", "The subject generation/revision changed before lock.", batch.snapshots
            )

        locked_hash = _locked_authority_vector_hash(plan)
        if locked_hash != candidate.authority_vector_hash:
            raise StaleBackfillBatchError(
                "STALE_AUTHORITY_VECTOR", "The contributor authority vector changed before lock.", batch.snapshots
            )


def _force_unclassified_quarantine(
    session: Session, plan: mirror.NativeMirrorPlan, *, now_utc: datetime
) -> None:
    prepared = next(iter(plan.subjects_by_note_id.values()))
    subject = prepared.subject
    state = session.get(StudyProgressState, int(subject.id))
    if state is not None:
        session.delete(state)
    contributors = tuple(
        session.execute(
            select(StudyProgressContributor).where(
                StudyProgressContributor.subject_id == int(subject.id),
                StudyProgressContributor.subject_generation == int(subject.subject_generation),
                StudyProgressContributor.contributor_status == "ACTIVE",
            )
        ).scalars()
    )
    for contributor in contributors:
        availability = session.get(StudyProgressAvailability, int(contributor.id))
        if availability is not None:
            session.delete(availability)
    subject.status_code = "QUARANTINED_UNCLASSIFIED_CONTEXT"
    subject.last_mirrored_at = now_utc
    subject.updated_at = now_utc


def _terminal_missing_retry(
    session: Session,
    *,
    source_id: int,
    pending: StudyProgressBackfillDisposition,
) -> tuple[str, StudyProgressSubject, str | None]:
    contributor = repository.latest_contributor_for_source(
        session, source_progress_id=source_id
    )
    subject = (
        session.get(StudyProgressSubject, int(contributor.subject_id))
        if contributor is not None
        else (
            session.get(StudyProgressSubject, int(pending.subject_id))
            if pending.subject_id is not None
            else None
        )
    )
    if subject is None:
        raise StudyProgressBackfillError(
            "A deleted retry source has no retained lifecycle subject fence."
        )
    if contributor is not None:
        status = str(contributor.contributor_status)
        if status == "REKEYED":
            return "REKEYED_CLONE_CUTOVER", subject, "SOURCE_REKEYED_DURING_BACKFILL"
        if status == "DETACHED":
            return "DETACHED_CONTRIBUTOR_DELETED", subject, "SOURCE_DELETED_DURING_BACKFILL"
        if status == "TOMBSTONED" and str(subject.status_code) in _LIFECYCLE_CODES:
            return str(subject.status_code), subject, "SOURCE_TOMBSTONED_DURING_BACKFILL"
    if str(subject.status_code) in _LIFECYCLE_CODES:
        return str(subject.status_code), subject, "SOURCE_LIFECYCLE_DURING_BACKFILL"
    raise StudyProgressBackfillError(
        "A deleted retry source is not covered by a retained lifecycle disposition."
    )


def _record_retry(
    session: Session,
    *,
    run_id: str,
    snapshots: tuple[_SourceSnapshot, ...],
    reason_code: str,
    now_utc: datetime,
) -> int:
    run = repository.lock_run(session, run_id)
    checkpoint = repository.lock_checkpoint(session, run_id)
    if run is None or checkpoint is None:
        raise StudyProgressBackfillError("Backfill retry lost its run/checkpoint.")
    subjects = _load_subjects_by_key(
        session,
        [snapshot.subject_key for snapshot in snapshots if snapshot.subject_key is not None],
    )
    for snapshot in snapshots:
        subject = subjects.get(snapshot.subject_key) if snapshot.subject_key is not None else None
        _upsert_source_disposition(
            session,
            run_id=run_id,
            snapshot=snapshot,
            disposition_code="RETRY_PENDING",
            reason_code=reason_code,
            subject_id=(int(subject.id) if subject is not None else snapshot.subject_id),
            generation=(
                int(subject.subject_generation)
                if subject is not None
                else snapshot.observed_generation
            ),
            mirror_revision=(
                int(subject.mirror_revision) if subject is not None else snapshot.observed_mirror_revision
            ),
            result_hash=None,
            now_utc=now_utc,
        )
    run.retry_count = int(run.retry_count) + 1
    checkpoint.retry_count = int(checkpoint.retry_count) + 1
    run.status_code = "RUNNING"
    checkpoint.status_code = "RUNNING"
    run.updated_at = now_utc
    checkpoint.updated_at = now_utc
    session.commit()
    return int(run.retry_count)


def _sanitize_error(exc: BaseException) -> str:
    message = f"{type(exc).__name__}: {exc}"
    message = re.sub(r"://([^:@\s]*):([^@\s]+)@", r"://\1:***@", message)
    message = re.sub(
        r"(password|pwd|secret|api[_-]?key|token)=([^;&\s]+)",
        r"\1=***",
        message,
        flags=re.IGNORECASE,
    )
    return message[:1000]


def _mark_failed(session: Session, *, run_id: str, exc: BaseException) -> None:
    session.rollback()
    run = repository.lock_run(session, run_id)
    checkpoint = repository.lock_checkpoint(session, run_id)
    if run is not None:
        now_utc = _utc_naive()
        run.status_code = "FAILED"
        run.error_summary = _sanitize_error(exc)
        run.updated_at = now_utc
        if checkpoint is not None:
            checkpoint.status_code = "FAILED"
            checkpoint.updated_at = now_utc
        session.commit()


def _result_from_run(
    session: Session,
    run: StudyProgressBackfillRun,
    checkpoint: StudyProgressBackfillCheckpoint,
    *,
    batches: int,
) -> BackfillResult:
    counts = repository.disposition_counts(session, str(run.id))
    return BackfillResult(
        mode="apply",
        status=str(run.status_code),
        run_id=str(run.id),
        complete=str(run.status_code) == "COMPLETED",
        batches=batches,
        source_count=int(run.source_count),
        mirrored_count=int(run.mirrored_count),
        quarantined_count=int(run.quarantined_count),
        unresolvable_count=int(run.unresolvable_count),
        retry_count=int(run.retry_count),
        source_progress_high_water_id=(
            int(run.source_progress_high_water_id)
            if run.source_progress_high_water_id is not None
            else None
        ),
        last_source_id=(
            int(checkpoint.last_source_id) if checkpoint.last_source_id is not None else None
        ),
        disposition_counts=counts,
        samples=(),
    )


def _dry_run(session: Session) -> BackfillResult:
    _minimum, high_water, source_count = repository.source_progress_bounds(session)
    cursor: int | None = None
    counts: Counter[str] = Counter()
    samples: list[dict[str, object]] = []
    batches = 0
    while high_water is not None:
        page = repository.load_source_page(
            session,
            after_id=cursor,
            high_water_id=high_water,
            limit=SOURCE_ROWS_PER_BATCH,
        )
        if not page:
            break
        selected: list[repository.CardProgressSourceRow] = []
        subject_keys: set[tuple[int, str]] = set()
        for row in page:
            key = row.subject_key
            if key is not None and key not in subject_keys:
                if len(subject_keys) >= SUBJECTS_PER_BATCH:
                    break
                subject_keys.add(key)
            selected.append(row)
        authority = repository.load_subject_authority_rows(session, subject_keys)
        approved = repository.approved_subject_contexts(session, authority)
        outcome_by_subject = {
            key: _classify_subject(rows, context_approved=key in approved)
            for key, rows in authority.items()
        }
        for row in selected:
            if row.resolution_code is not None:
                code, reason = row.resolution_code, row.resolution_code
            else:
                code, reason = outcome_by_subject[row.subject_key]
            counts[code] += 1
            if len(samples) < DISPOSITION_SAMPLE_LIMIT and (
                code.startswith("QUARANTINED_") or code.startswith("UNRESOLVABLE_")
            ):
                samples.append(
                    {
                        "source_identity_digest": hashlib.sha256(
                            str(row.source_id).encode("ascii")
                        ).hexdigest()[:16],
                        "disposition_code": code,
                        "reason_code": reason,
                    }
                )
        cursor = selected[-1].source_id
        batches += 1
    mirrored, quarantined, unresolvable, _retry = _category_counts(counts)
    session.rollback()
    return BackfillResult(
        mode="dry-run",
        status="DRY_RUN",
        run_id=None,
        complete=(mirrored + quarantined + unresolvable == source_count),
        batches=batches,
        source_count=source_count,
        mirrored_count=mirrored,
        quarantined_count=quarantined,
        unresolvable_count=unresolvable,
        retry_count=0,
        source_progress_high_water_id=high_water,
        last_source_id=cursor,
        disposition_counts=dict(counts),
        samples=tuple(samples),
    )


def run_current_progress_backfill(
    session: Session,
    *,
    apply: bool = False,
    run_id: str | None = None,
    max_batches: int | None = None,
    fault_injector: FaultInjector | None = None,
    now_utc: datetime | None = None,
) -> BackfillResult:
    """Run or resume the fenced CURRENT_PROGRESS backfill.

    ``max_batches`` is an operational stop control for rehearsal and workers;
    it does not change the frozen batch contract.  A completed run is a strict
    no-op when resumed.
    """

    if not current_app.config.get("STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED", False):
        raise StudyProgressBackfillDisabledError(
            "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED must be true."
        )
    if max_batches is not None and (isinstance(max_batches, bool) or int(max_batches) < 1):
        raise StudyProgressBackfillError("max_batches must be a positive integer.")
    if not apply:
        if run_id is not None:
            raise StudyProgressBackfillError("run_id is only valid with --apply.")
        return _dry_run(session)
    if not current_app.config.get("STUDY_PROGRESS_SHADOW_WRITE_ENABLED", False):
        raise StudyProgressBackfillDisabledError(
            "Apply requires STUDY_PROGRESS_SHADOW_WRITE_ENABLED=true so concurrent writers are fenced."
        )

    started = _utc_naive(now_utc)
    if run_id is None:
        run, checkpoint = _create_run(session, now_utc=started)
        normalized_run_id = str(run.id)
    else:
        normalized_run_id = _normalize_run_id(run_id)
        run = repository.lock_run(session, normalized_run_id)
        checkpoint = repository.lock_checkpoint(session, normalized_run_id)
        if run is None or checkpoint is None:
            session.rollback()
            raise StudyProgressBackfillError("Backfill run/checkpoint was not found.")
        _validate_run_contract(session, run)
        if str(run.status_code) == "COMPLETED":
            result = _result_from_run(session, run, checkpoint, batches=0)
            session.rollback()
            return result
        if str(run.status_code) == "CANCELLED":
            session.rollback()
            raise StudyProgressBackfillError("A cancelled backfill run cannot resume.")
        run.status_code = "RUNNING"
        checkpoint.status_code = "RUNNING"
        run.error_summary = None
        run.updated_at = started
        checkpoint.updated_at = started
        session.commit()

    batches = 0
    stale_attempts = 0
    while max_batches is None or batches < int(max_batches):
        try:
            run = repository.lock_run(session, normalized_run_id)
            checkpoint = repository.lock_checkpoint(session, normalized_run_id)
            if run is None or checkpoint is None:
                raise StudyProgressBackfillError("Backfill run/checkpoint disappeared.")
            _validate_run_contract(session, run)
            batch = _build_batch(session, run=run, checkpoint=checkpoint)
            if batch is None:
                counts = _update_run_counts(session, run)
                mirrored, quarantined, unresolvable, retry_pending = _category_counts(counts)
                terminal = mirrored + quarantined + unresolvable
                if retry_pending or terminal != int(run.source_count):
                    raise StudyProgressBackfillError(
                        "Frozen source accounting is incomplete; retain evidence and resume or start a new run."
                    )
                completed_at = _utc_naive()
                run.status_code = "COMPLETED"
                run.completed_at = completed_at
                run.updated_at = completed_at
                checkpoint.status_code = "COMPLETED"
                checkpoint.lease_token_hash = None
                checkpoint.lease_expires_at = None
                checkpoint.updated_at = completed_at
                session.commit()
                result = _result_from_run(session, run, checkpoint, batches=batches)
                session.rollback()
                return result

            _fault(fault_injector, "read", source_count=len(batch.snapshots))
            # Candidate reads intentionally populate the identity map.  Expire
            # them before SELECT ... FOR UPDATE so SQLAlchemy cannot hand the
            # CAS layer a pre-concurrency ORM value on MySQL REPEATABLE READ.
            session.expire_all()
            subject_keys = set(batch.candidates)
            for pending in batch.missing_retry_by_id.values():
                if pending.subject_id is None:
                    continue
                subject = session.get(StudyProgressSubject, int(pending.subject_id))
                if subject is not None:
                    subject_keys.add(
                        (
                            int(subject.learner_user_id),
                            bytes(subject.logical_note_key).decode("utf-8"),
                        )
                    )
            plans = mirror.prepare_mirror_scopes(
                session,
                subject_keys=subject_keys,
                now_utc=_utc_naive(),
            )
            plans_by_key = {
                (plan.learner_user_id, next(iter(plan.subjects_by_note_id))): plan
                for plan in plans
            }
            locked_source = repository.lock_and_reload_source_rows(
                session, batch.live_rows_by_id
            )
            locked_by_id = {row.source_id: row for row in locked_source}
            for snapshot in batch.snapshots:
                if snapshot.source_id in batch.missing_retry_by_id:
                    continue
                row = locked_by_id.get(snapshot.source_id)
                if row is None:
                    raise StaleBackfillBatchError(
                        "STALE_AUTHORITY_VECTOR",
                        "A source row was deleted before the contributor lock.",
                        batch.snapshots,
                    )
                current_subject = _load_subjects_by_key(
                    session, [row.subject_key] if row.subject_key is not None else []
                ).get(row.subject_key)
                current = _snapshot_live_row(row, current_subject)
                if _source_signature(current) != _source_signature(snapshot):
                    raise StaleBackfillBatchError(
                        "STALE_AUTHORITY_VECTOR",
                        "A source identity/revision/hash changed before lock.",
                        batch.snapshots,
                    )
            _assert_candidate_fences(batch, plans_by_key)
            locked_authority = repository.load_subject_authority_rows(
                session, batch.source_rows_by_subject
            )
            locked_approved = repository.approved_subject_contexts(session, locked_authority)
            if any(
                candidate.context_approved != (key in locked_approved)
                for key, candidate in batch.candidates.items()
            ):
                raise StaleBackfillBatchError(
                    "STALE_AUTHORITY_VECTOR",
                    "A subject ownership/install context changed before lock.",
                    batch.snapshots,
                )
            _fault(fault_injector, "lock", subject_count=len(subject_keys))

            outcome_by_subject: dict[
                tuple[int, str], tuple[str, StudyProgressSubject, str | None]
            ] = {}
            finalized_at = _utc_naive()
            for key in sorted(
                batch.active_subject_keys,
                key=lambda value: (value[0], value[1].encode("utf-8")),
            ):
                plan = plans_by_key[key]
                mirror.finalize_native_mirror(
                    plan,
                    review_events=(),
                    now_utc=finalized_at,
                )
                prepared = next(iter(plan.subjects_by_note_id.values()))
                subject = prepared.subject
                reason: str | None = None
                if key not in locked_approved:
                    _force_unclassified_quarantine(session, plan, now_utc=finalized_at)
                    reason = "UNCLASSIFIED_CONTEXT"
                elif str(subject.status_code) == "QUARANTINED_STATE_DIVERGENCE":
                    reason = "SEMANTIC_STATE_DIVERGENCE"
                elif str(subject.status_code).startswith("QUARANTINED_"):
                    _status, reason = _classify_subject(
                        locked_authority[key], context_approved=True
                    )
                outcome_by_subject[key] = (str(subject.status_code), subject, reason)

            missing_outcomes: dict[
                int, tuple[str, StudyProgressSubject, str | None]
            ] = {}
            for source_id, pending in batch.missing_retry_by_id.items():
                missing_outcomes[source_id] = _terminal_missing_retry(
                    session, source_id=source_id, pending=pending
                )
            session.flush()
            _fault(fault_injector, "upsert", subject_count=len(outcome_by_subject))

            for snapshot in batch.snapshots:
                if snapshot.source_id in missing_outcomes:
                    code, subject, reason = missing_outcomes[snapshot.source_id]
                elif snapshot.resolution_code is not None:
                    code = snapshot.resolution_code
                    subject = None
                    reason = snapshot.resolution_code
                else:
                    code, subject, reason = outcome_by_subject[snapshot.subject_key]
                _upsert_source_disposition(
                    session,
                    run_id=normalized_run_id,
                    snapshot=snapshot,
                    disposition_code=code,
                    reason_code=reason,
                    subject_id=int(subject.id) if subject is not None else None,
                    generation=(
                        int(subject.subject_generation) if subject is not None else None
                    ),
                    mirror_revision=(
                        int(subject.mirror_revision) if subject is not None else None
                    ),
                    result_hash=(
                        bytes(subject.authority_vector_hash)
                        if subject is not None and subject.authority_vector_hash is not None
                        else None
                    ),
                    now_utc=finalized_at,
                )
            session.flush()
            _fault(fault_injector, "disposition", source_count=len(batch.snapshots))

            checkpoint.last_source_id = batch.last_source_id
            checkpoint.processed_count = int(checkpoint.processed_count) + len(batch.snapshots)
            checkpoint.status_code = "RUNNING"
            checkpoint.updated_at = finalized_at
            run.updated_at = finalized_at
            _update_run_counts(session, run)
            session.flush()
            _fault(fault_injector, "checkpoint", last_source_id=batch.last_source_id)
            session.commit()
            batches += 1
            stale_attempts = 0
        except StaleBackfillBatchError as exc:
            session.rollback()
            stale_attempts += 1
            _record_retry(
                session,
                run_id=normalized_run_id,
                snapshots=exc.snapshots,
                reason_code=exc.reason_code,
                now_utc=_utc_naive(),
            )
            if stale_attempts >= MAX_STALE_RETRIES:
                _mark_failed(session, run_id=normalized_run_id, exc=exc)
                raise StudyProgressBackfillError(
                    "Backfill batch exhausted its stale-CAS retry budget."
                ) from exc
        except Exception as exc:
            _mark_failed(session, run_id=normalized_run_id, exc=exc)
            if isinstance(exc, StudyProgressBackfillError):
                raise
            raise StudyProgressBackfillError(_sanitize_error(exc)) from exc

    run = repository.lock_run(session, normalized_run_id)
    checkpoint = repository.lock_checkpoint(session, normalized_run_id)
    if run is None or checkpoint is None:
        session.rollback()
        raise StudyProgressBackfillError("Backfill run/checkpoint disappeared.")
    result = _result_from_run(session, run, checkpoint, batches=batches)
    session.rollback()
    return result
