"""Stable Phase 4 shadow-progress schema and codec identifiers.

This module is intentionally dependency-free so ORM declarations, migration
contract tests and pure codecs can share one bounded vocabulary.  Adding a new
value is a schema change; callers must never persist arbitrary status strings.
"""

from __future__ import annotations


RAW_SCHEMA_VERSION = "raw-card-progress.v1"
STATE_SCHEMA_VERSION = "anki-card-state.v1"
STORAGE_CODEC = "flama-canonical-state-json.v1"
MAPPER_VERSION = "card-progress-legacy-anki.v1"
PROJECTION_VERSION = "availability-anchor.v1"
HISTORY_SCHEMA_VERSION = "study-progress-history-fact.v1"
AUTHORITY_RECEIPT_SCHEMA_VERSION = "study-authority-command-receipt.v1"
LIFECYCLE_EVIDENCE_SCHEMA_VERSION = "study-progress-lifecycle-evidence.v1"
ALGORITHM_KEY = "legacy-anki"
ALGORITHM_VERSION = "1.0.0"
MAX_CANONICAL_PAYLOAD_BYTES = 16_384

SUBJECT_STATUSES = (
    "NO_CURRENT_PROGRESS",
    "MIRRORED_SINGLE",
    "MIRRORED_EQUIVALENT_FANIN",
    "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE",
    "QUARANTINED_STATE_DIVERGENCE",
    "QUARANTINED_UNSUPPORTED_STATE",
    "QUARANTINED_CORRUPT_STATE",
    "QUARANTINED_UNCLASSIFIED_CONTEXT",
    "TOMBSTONED_RESET",
    "TOMBSTONED_SUBJECT_DELETED",
    "REKEYED_CLONE_CUTOVER",
)

CONTRIBUTOR_STATUSES = ("ACTIVE", "DETACHED", "REKEYED", "TOMBSTONED")

# LEGACY_PROJECTION evidence describes a CardProgress row; CANONICAL rows are
# written without one and carry no raw evidence (ADR P9-03 §2.3).
EVIDENCE_KINDS = ("LEGACY_PROJECTION", "CANONICAL")
CONTRIBUTOR_RAW_EVIDENCE_COLUMNS = (
    "source_progress_id",
    "card_progress_revision",
    "raw_schema_version",
    "storage_codec",
    "raw_payload",
    "raw_payload_size",
    "raw_progress_hash",
)

# One system-wide NOTE storage profile, switched once in a write freeze.
# CONSOLIDATED_V1 (ADR P10) keeps state, revision and availability on the
# subject row instead of the state/token/contributor/availability tables.
STORAGE_PROFILES = ("PROJECTION_V1", "CANONICAL_V1", "CONSOLIDATED_V1")
DEFAULT_STORAGE_PROFILE = "PROJECTION_V1"
CONSOLIDATED_STORAGE_PROFILE = "CONSOLIDATED_V1"

# ADR P10 §2.1: the consolidated subject row. The state group, the
# availability group and the history/provenance pair are all present for a
# Note with current progress and all NULL for a Note without one.
SUBJECT_STATE_COLUMNS = (
    "algorithm_key",
    "algorithm_version",
    "state_schema_version",
    "storage_codec",
    "state_payload",
    "state_payload_size",
    "algorithm_state_hash",
    "semantic_state_hash",
)
SUBJECT_AVAILABILITY_COLUMNS = (
    "projection_version",
    "normalized_queue",
    "is_suspended",
    "is_buried",
)
SUBJECT_AVAILABILITY_NULLABLE_COLUMNS = ("due_at", "due_day", "buried_until_day")
SUBJECT_HISTORY_COLUMNS = ("history_completeness_code", "current_provenance_code")
SUBJECT_PROGRESS_COLUMNS = (
    SUBJECT_STATE_COLUMNS + SUBJECT_AVAILABILITY_COLUMNS + SUBJECT_HISTORY_COLUMNS
)

POINTER_STATUSES = (
    "VALID",
    "ABSENT",
    "MISSING_EVENT",
    "LEARNER_MISMATCH",
    "CARD_MISMATCH",
    "EXTERNAL_POINTED",
    "MISSING_TARGET",
    "PAYLOAD_MISMATCH",
    "REPAIRED",
)

HISTORY_COMPLETENESS_CODES = (
    "HISTORY_NATIVE_COMPLETE",
    "HISTORY_IMPORTED_PARTIAL",
    "HISTORY_SNAPSHOT_ONLY",
    "HISTORY_MIXED_PARTIAL",
    "HISTORY_REPAIRED_PARTIAL",
    "HISTORY_UNKNOWN",
    "HISTORY_DETACHED",
)

PROVENANCE_CODES = (
    "NATIVE_DIRECT",
    "NATIVE_MCP",
    "NATIVE_SESSION",
    "NATIVE_ASYNC_BATCH",
    "CONNECT_PROGRESS_SNAPSHOT",
    "CONNECT_LEGACY_PROGRESS",
    "CONNECT_REVLOG",
    "CLONE_CUTOVER",
    "PROGRESS_RESET",
    "CONTENT_DELETE",
    "REPAIR",
    "UNKNOWN_LEGACY",
)

LINEAGE_REF_KINDS = (
    "LAST_REVIEW_EVENT",
    "CONNECT_SOURCE_CARD",
    "CONNECT_SOURCE_NOTE",
)

LIFECYCLE_TRANSITIONS = (
    "TOMBSTONED_RESET",
    "TOMBSTONED_SUBJECT_DELETED",
    "DETACHED_CONTRIBUTOR_DELETED",
    "REKEYED_CLONE_CUTOVER",
    "LIFECYCLE_MAPPING_AMBIGUOUS",
)

BACKFILL_RUN_KINDS = ("CURRENT_PROGRESS", "HISTORY", "FULL")
BACKFILL_STATUSES = ("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")
BACKFILL_SOURCE_KINDS = (
    "CARD_PROGRESS",
    "REVIEW_EVENT",
    "CONNECT_SOURCE_CARD_REF",
    "CONNECT_SOURCE_NOTE_REF",
    "CONNECT_REVIEW_EVENT_REF",
)

MIRROR_DISPOSITIONS = (
    "MIRRORED_SINGLE",
    "MIRRORED_EQUIVALENT_FANIN",
    "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE",
    "NO_CURRENT_PROGRESS",
    "QUARANTINED_STATE_DIVERGENCE",
    "QUARANTINED_UNSUPPORTED_STATE",
    "QUARANTINED_CORRUPT_STATE",
    "QUARANTINED_UNCLASSIFIED_CONTEXT",
    "UNRESOLVABLE_NULL_CARD_ID",
    "UNRESOLVABLE_MISSING_CARD",
    "UNRESOLVABLE_NULL_NOTE_ID",
    "UNRESOLVABLE_MISSING_NOTE",
    "UNRESOLVABLE_MISSING_LEARNER",
    "TOMBSTONED_RESET",
    "TOMBSTONED_SUBJECT_DELETED",
    "DETACHED_CONTRIBUTOR_DELETED",
    "REKEYED_CLONE_CUTOVER",
)

BACKFILL_DISPOSITIONS = MIRROR_DISPOSITIONS + (
    "LIFECYCLE_MAPPING_AMBIGUOUS",
    "STALE_GENERATION",
    "STALE_AUTHORITY_VECTOR",
    "STALE_MAPPER_VERSION",
    "RETRY_PENDING",
)

NORMALIZED_QUEUES = ("new", "learning", "relearning", "review")

MAPPING_REASON_CODES = (
    "UNSUPPORTED_ALGORITHM_IDENTITY",
    "UNSUPPORTED_STATE_SCHEMA",
    "UNSUPPORTED_QUEUE",
    "INVALID_STATE_VALUE",
    "NON_FINITE_STATE_NUMBER",
    "INCOMPLETE_MEMORY_STATE",
    "RAW_PROGRESS_PAYLOAD_TOO_LARGE",
    "STATE_PAYLOAD_TOO_LARGE",
    "STATE_HASH_MISMATCH",
    "STATE_DECODER_UNAVAILABLE",
    "INVALID_AVAILABILITY_CONTEXT",
    "MISSING_CARD_IDENTITY",
    "MISSING_CARD_CREATED_AT",
)


def sql_allowlist(column_name: str, values: tuple[str, ...]) -> str:
    """Return a stable SQL CHECK expression for an internal allowlist."""

    if not column_name.replace("_", "").isalnum():
        raise ValueError("Unsafe SQL identifier.")
    literals = ", ".join("'" + value.replace("'", "''") + "'" for value in values)
    return f"{column_name} IN ({literals})"


def contributor_evidence_check() -> str:
    """CHECK pairing ``evidence_kind`` with its raw CardProgress evidence.

    ``live_card_progress_id`` stays out: MySQL refuses a CHECK on a column
    whose foreign key has a referential action (``ON DELETE SET NULL``), so
    CANONICAL writers leave it NULL by contract, not by constraint.
    """

    present = " AND ".join(f"{name} IS NOT NULL" for name in CONTRIBUTOR_RAW_EVIDENCE_COLUMNS)
    absent = " AND ".join(f"{name} IS NULL" for name in CONTRIBUTOR_RAW_EVIDENCE_COLUMNS)
    return (
        f"(evidence_kind = 'LEGACY_PROJECTION' AND {present}) OR "
        f"(evidence_kind = 'CANONICAL' AND {absent})"
    )


def subject_progress_checks() -> dict[str, str]:
    """CHECK expressions of the consolidated subject row (ADR P10 §2.1).

    A row either carries the whole current progress (state, availability,
    history/provenance) or none of it; the per-value checks admit NULL so the
    group check alone decides presence.
    """

    present = " AND ".join(f"{name} IS NOT NULL" for name in SUBJECT_PROGRESS_COLUMNS)
    absent = " AND ".join(
        f"{name} IS NULL"
        for name in SUBJECT_PROGRESS_COLUMNS + SUBJECT_AVAILABILITY_NULLABLE_COLUMNS
    )
    return {
        "ck_sp_subject_progress_group": f"({present}) OR ({absent})",
        "ck_sp_subject_authority_revision": "authority_revision >= 0",
        "ck_sp_subject_state_size": (
            "state_payload_size IS NULL OR state_payload_size BETWEEN 0 AND 16384"
        ),
        "ck_sp_subject_algorithm_hash": (
            "algorithm_state_hash IS NULL OR length(algorithm_state_hash) = 32"
        ),
        "ck_sp_subject_semantic_hash": (
            "semantic_state_hash IS NULL OR length(semantic_state_hash) = 32"
        ),
        "ck_sp_subject_queue": (
            "normalized_queue IS NULL OR " + sql_allowlist("normalized_queue", NORMALIZED_QUEUES)
        ),
        "ck_sp_subject_history_code": (
            "history_completeness_code IS NULL OR "
            + sql_allowlist("history_completeness_code", HISTORY_COMPLETENESS_CODES)
        ),
        "ck_sp_subject_provenance_code": (
            "current_provenance_code IS NULL OR "
            + sql_allowlist("current_provenance_code", PROVENANCE_CODES)
        ),
    }
