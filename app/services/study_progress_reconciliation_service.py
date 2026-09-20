"""Read-only Phase 4 comparison between CardProgress and its shadow projection.

The comparator never repairs either side and never exposes the shadow as a
product read authority.  It is intentionally executed inside the dedicated
audit application so one database snapshot can produce deterministic evidence.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping

from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories import study_progress_backfill_repository as backfill_repository
from app.repositories import study_repository
from app.repositories.deck_tree_query import collect_subtree_ids
from app.services import flashcards_share_service
from app.services.anki_scheduler import (
    _day_index,
    computeAnswerPreview,
)
from app.services.scheduler_config_service import (
    resolve_deck_options,
    resolve_scheduler_runtime_settings,
)
from app.services.stats_overview import get_effective_timezone_name
from app.services.study_progress_contract import (
    ALGORITHM_KEY,
    ALGORITHM_VERSION,
    BACKFILL_DISPOSITIONS,
    HISTORY_SCHEMA_VERSION,
    LIFECYCLE_EVIDENCE_SCHEMA_VERSION,
    MAPPER_VERSION,
    PROJECTION_VERSION,
    RAW_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_codec import (
    STATE_DECODERS,
    StudyProgressCodecError,
    canonical_document,
    canonical_typed_document,
)
from app.services.study_progress_shadow_mapper import (
    AvailabilityProjection,
    MappedCardProgress,
    MappingFailure,
    map_card_progress,
)
from models.card import Card
from models.card_progress import CardProgress
from models.connect_review_event_ref import ConnectReviewEventRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.note import Note
from models.review_event import ReviewEvent
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_backfill_disposition import StudyProgressBackfillDisposition
from models.study_progress_backfill_run import StudyProgressBackfillRun
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_lineage_ref import StudyProgressLineageRef
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.user import User


RECONCILIATION_SCHEMA_VERSION = "study-progress-reconciliation.v1"
COMPARISON_POLICY_VERSION = "phase4-shadow-comparison.v1"
MAX_SAMPLES_PER_CODE = 10
USABLE_SUBJECT_STATUSES = {
    "MIRRORED_SINGLE",
    "MIRRORED_EQUIVALENT_FANIN",
    "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE",
}
UNSUPPORTED_MAPPING_CODES = {
    "UNSUPPORTED_ALGORITHM_IDENTITY",
    "UNSUPPORTED_STATE_SCHEMA",
    "UNSUPPORTED_QUEUE",
    "STATE_DECODER_UNAVAILABLE",
}
CORRUPT_MAPPING_CODES = {
    "INVALID_STATE_VALUE",
    "NON_FINITE_STATE_NUMBER",
    "INCOMPLETE_MEMORY_STATE",
    "RAW_PROGRESS_PAYLOAD_TOO_LARGE",
    "STATE_PAYLOAD_TOO_LARGE",
    "STATE_HASH_MISMATCH",
}


def disabled_study_progress_reconciliation() -> dict[str, Any]:
    """Describe the default-off comparison without touching shadow tables."""

    return {
        "schema_version": RECONCILIATION_SCHEMA_VERSION,
        "mode": "DISABLED",
        "gate": {
            "status": "NOT_RUN",
            "blockers": [],
            "enforced": False,
        },
    }


def _utc_naive(value: datetime | None) -> datetime:
    resolved = value or datetime.now(timezone.utc)
    if resolved.tzinfo is not None:
        resolved = resolved.astimezone(timezone.utc).replace(tzinfo=None)
    return resolved


def _identity_sample(*parts: object) -> str:
    material = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:20]


def _bytes(value: bytes | bytearray | memoryview | None) -> bytes | None:
    return bytes(value) if value is not None else None


def _decode_source_hash(value: str | bytes | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value if len(value) == 32 else None
    token = str(value).strip()
    for prefix in ("sha256-", "sha256:"):
        if token.startswith(prefix):
            token = token[len(prefix) :]
            break
    if len(token) != 64:
        return None
    try:
        decoded = bytes.fromhex(token)
    except ValueError:
        return None
    return decoded if len(decoded) == 32 else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="microseconds") if value is not None else None


def _record(
    counts: Counter[str],
    samples: dict[str, list[str]],
    code: str,
    *identity: object,
) -> None:
    counts[code] += 1
    if len(samples[code]) < MAX_SAMPLES_PER_CODE:
        samples[code].append(_identity_sample(*identity))


def _mapping_quarantine(code: str) -> str:
    if code in UNSUPPORTED_MAPPING_CODES:
        return "QUARANTINED_UNSUPPORTED_STATE"
    if code in CORRUPT_MAPPING_CODES:
        return "QUARANTINED_CORRUPT_STATE"
    return "QUARANTINED_UNCLASSIFIED_CONTEXT"


def _lineage_material(row: StudyProgressLineageRef) -> dict[str, Any]:
    return {
        "ref_kind": str(row.ref_kind),
        "source_row_key": bytes(row.source_row_key).hex(),
        "source_key": bytes(row.source_key).hex() if row.source_key is not None else None,
        "external_card_id": (
            bytes(row.external_card_id).hex()
            if row.external_card_id is not None
            else None
        ),
        "external_note_id": (
            bytes(row.external_note_id).hex()
            if row.external_note_id is not None
            else None
        ),
        "source_snapshot_hash": (
            bytes(row.source_snapshot_hash).hex()
            if row.source_snapshot_hash is not None
            else None
        ),
        "source_payload_hash": (
            bytes(row.source_payload_hash).hex()
            if row.source_payload_hash is not None
            else None
        ),
        "ref_status": str(row.ref_status),
        "occurred_at": row.occurred_at,
    }


def _lineage_hash(
    rows: Iterable[StudyProgressLineageRef],
    *,
    pointer_status: str,
) -> bytes:
    material = [_lineage_material(row) for row in rows]
    if not any(value["ref_kind"] == "LAST_REVIEW_EVENT" for value in material):
        if pointer_status == "ABSENT":
            material.append(
                {
                    "ref_kind": "LAST_REVIEW_EVENT",
                    "source_row_key": None,
                    "ref_status": "ABSENT",
                }
            )
    material.sort(
        key=lambda value: (
            str(value["ref_kind"]),
            str(value.get("source_row_key") or ""),
        )
    )
    return canonical_typed_document(
        {"references": material},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def _expected_pointer_status(
    progress: CardProgress,
    event_by_id: Mapping[int, ReviewEvent],
) -> str:
    if progress.last_review_event_id is None:
        return "ABSENT"
    event = event_by_id.get(int(progress.last_review_event_id))
    if event is None:
        return "MISSING_EVENT"
    if int(event.user_id) != int(progress.user_id):
        return "LEARNER_MISMATCH"
    if str(event.card_id) != str(progress.card_id):
        return "CARD_MISMATCH"

    from app.validators.review_event import classify_review_event_payload

    disposition = classify_review_event_payload(
        event.payload_json,
        scheduler_algorithm=event.scheduler_algorithm,
        algorithm_version=event.algorithm_version,
        scheduler_config_hash=event.scheduler_config_hash,
        study_session_id=event.study_session_id,
        client_event_id=event.client_event_id,
        sequence_no=event.sequence_no,
    )
    if disposition.category == "complete":
        try:
            payload = json.loads(event.payload_json)
        except (TypeError, ValueError):
            payload = {}
        provenance = payload.get("provenance") if isinstance(payload, dict) else None
        if isinstance(provenance, dict) and provenance.get("kind") == "external":
            return "EXTERNAL_POINTED"
        return "VALID"
    return "VALID" if disposition.category == "legacy_unknown" else "PAYLOAD_MISMATCH"


def _native_event_provenance(event: ReviewEvent | None) -> str | None:
    if event is None:
        return None
    try:
        payload = json.loads(event.payload_json)
    except (TypeError, ValueError):
        return None
    provenance = payload.get("provenance") if isinstance(payload, dict) else None
    source_path = provenance.get("source_path") if isinstance(provenance, dict) else None
    return {
        "native.rest": "NATIVE_DIRECT",
        "native.mcp": "NATIVE_MCP",
        "native.session": "NATIVE_SESSION",
        "native.worker": "NATIVE_ASYNC_BATCH",
    }.get(str(source_path or ""))


def _availability_from_row(row: StudyProgressAvailability) -> AvailabilityProjection:
    return AvailabilityProjection(
        projection_version=str(row.projection_version),
        normalized_queue=str(row.normalized_queue),
        due_at=row.due_at,
        due_day=int(row.due_day) if row.due_day is not None else None,
        is_suspended=bool(row.is_suspended),
        is_buried=bool(row.is_buried),
        buried_until_day=(
            int(row.buried_until_day) if row.buried_until_day is not None else None
        ),
        card_created_at=row.card_created_at,
        card_order_key=bytes(row.card_order_key),
        state_schema_version=str(row.state_schema_version),
        semantic_state_hash=bytes(row.semantic_state_hash),
    )


def _projection_signature(projection: AvailabilityProjection) -> tuple[object, ...]:
    return (
        projection.projection_version,
        projection.normalized_queue,
        projection.due_at,
        projection.due_day,
        projection.is_suspended,
        projection.is_buried,
        projection.buried_until_day,
        projection.card_created_at,
        projection.card_order_key,
        projection.state_schema_version,
        projection.semantic_state_hash,
    )


def _entry_from_projection(projection: AvailabilityProjection) -> dict[str, Any]:
    return {
        "card_id": projection.card_order_key.decode("utf-8"),
        "created_at": projection.card_created_at,
        "queue": projection.normalized_queue,
        "due_at": projection.due_at,
        "due_day": projection.due_day,
        "is_suspended": projection.is_suspended,
        "is_buried": projection.is_buried,
        "buried_until_day": projection.buried_until_day,
    }


def _entry_for_new_card(card: Card) -> dict[str, Any]:
    return {
        "card_id": str(card.id),
        "created_at": card.created_at,
        "queue": "new",
        "due_at": None,
        "due_day": None,
        "is_suspended": False,
        "is_buried": False,
        "buried_until_day": None,
    }


def _query_signature(
    entries: Iterable[dict[str, Any]],
    *,
    now_utc: datetime,
    timezone_name: str,
    day_boundary_hour: int,
    learn_ahead_seconds: int,
) -> dict[str, Any]:
    """Produce the accepted static count/order projection for one card scope."""

    today = _day_index(
        now_utc,
        day_boundary_hour,
        timezone_name=timezone_name,
    )
    cutoff = now_utc + timedelta(seconds=learn_ahead_seconds)
    counts = {"new": 0, "learning": 0, "review": 0}
    due_groups: dict[str, list[tuple[tuple[object, ...], str]]] = {
        "relearning": [],
        "learning": [],
        "review": [],
        "new": [],
    }
    ahead_groups: dict[str, list[tuple[tuple[object, ...], str]]] = {
        "relearning": [],
        "learning": [],
    }
    pending: list[datetime] = []
    pending_count = 0

    for entry in entries:
        card_id = str(entry["card_id"])
        created_at = entry["created_at"] or datetime.max
        queue = "learning" if entry["queue"] == "learn" else str(entry["queue"])
        due_at = entry["due_at"]
        due_day = entry["due_day"]
        count_bucket = study_repository.counter_bucket_for_progress_values(
            queue=queue,
            due_at=due_at,
            due_day=due_day,
            is_suspended=entry["is_suspended"],
            is_buried=entry["is_buried"],
            buried_until_day=entry["buried_until_day"],
            now=now_utc,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour,
        )
        if count_bucket in counts:
            counts[count_bucket] += 1
        buried = bool(entry["is_buried"]) and (
            entry["buried_until_day"] is None
            or int(entry["buried_until_day"]) >= today
        )
        if bool(entry["is_suspended"]) or buried:
            continue
        due = False
        ahead = False
        if queue == "new":
            due = True
        elif queue in {"learning", "relearning"}:
            if due_day is not None:
                due = int(due_day) <= today
            else:
                due = due_at is None or due_at <= now_utc
                ahead = not due and due_at is not None and due_at <= cutoff
            if not due and not ahead and (due_day is not None or due_at is not None):
                # The product's SQL pending summary counts future day-based
                # learning even with NULL due_at, but MIN(due_at) stays NULL.
                if due_at is not None:
                    pending.append(due_at)
                pending_count += 1
        elif queue == "review":
            due = (
                int(due_day) <= today
                if due_day is not None
                else _day_index(
                    due_at or now_utc,
                    day_boundary_hour,
                    timezone_name=timezone_name,
                ) <= today
            )
        else:
            raise StudyProgressCodecError(
                "UNSUPPORTED_QUEUE", f"Unsupported comparison queue {queue!r}."
            )

        if queue == "review":
            sort_key = (
                due_day is None,
                int(due_day) if due_day is not None else 0,
                due_at is None,
                due_at or datetime.max,
                created_at,
                card_id,
            )
        elif queue in {"learning", "relearning"}:
            sort_key = (due_at or datetime.max, created_at, card_id)
        else:
            sort_key = (created_at, card_id)
        if due:
            due_groups[queue].append((sort_key, card_id))
        elif ahead and queue in ahead_groups:
            ahead_groups[queue].append((sort_key, card_id))

    ordered = [
        card_id
        for queue in ("relearning", "learning", "review", "new")
        for _key, card_id in sorted(due_groups[queue])
    ]
    fallback = [
        card_id
        for queue in ("relearning", "learning")
        for _key, card_id in sorted(ahead_groups[queue])
    ]
    selectable = ordered if ordered else fallback
    return {
        "counts": counts,
        "ordered_card_ids": selectable,
        "selected_card_id": selectable[0] if selectable else None,
        "pending_learning_count": pending_count,
        "next_due_at": _iso(min(pending) if pending else None),
    }


def _redacted_query_signature(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "counts": dict(value["counts"]),
        "ordered_card_digests": [
            _identity_sample(card_id) for card_id in value["ordered_card_ids"]
        ],
        "selected_card_digest": (
            _identity_sample(value["selected_card_id"])
            if value["selected_card_id"] is not None
            else None
        ),
        "pending_learning_count": int(value["pending_learning_count"]),
        "next_due_at": value["next_due_at"],
    }


def _scope_queries(session: Session) -> list[tuple[str, int, Any]]:
    """Enumerate canonical product study scopes without using request globals."""

    scopes: list[tuple[str, int, Any]] = []
    owned_decks = tuple(
        session.execute(
            select(Deck)
            .where(Deck.owner_user_id.is_not(None), Deck.deleted_at.is_(None))
            .order_by(Deck.owner_user_id.asc(), Deck.id.asc())
        ).scalars()
    )
    for deck in owned_decks:
        subtree_ids = collect_subtree_ids(int(deck.id))
        if not subtree_ids:
            continue
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            Note.user_id == int(deck.owner_user_id),
            Note.deck_id.in_(subtree_ids),
        )
        if query.with_entities(Card.id).first() is not None:
            scopes.append((f"deck:{deck.id}", int(deck.owner_user_id), query))

    installs = tuple(
        session.execute(
            select(DeckInstall)
            .where(
                DeckInstall.clone_mode == "logical_overlay",
                DeckInstall.local_deck_id.is_not(None),
            )
            .order_by(DeckInstall.user_id.asc(), DeckInstall.id.asc())
        ).scalars()
    )
    installed_deck_ids: dict[str, set[int]] = defaultdict(set)
    for install_id, local_deck_id in session.execute(
        select(DeckCloneDeckMap.deck_install_id, DeckCloneDeckMap.local_deck_id)
    ):
        installed_deck_ids[str(install_id)].add(int(local_deck_id))
    for install in installs:
        root_id = int(install.local_deck_id)
        local_ids = {root_id, *installed_deck_ids.get(str(install.id), set())}
        for local_deck_id in sorted(local_ids):
            clone_scope = flashcards_share_service.resolve_clone_scope_for_local_deck(
                user_id=int(install.user_id),
                local_deck_id=local_deck_id,
            )
            if clone_scope is None:
                continue
            query = flashcards_share_service.query_clone_scope_cards(clone_scope)
            if query.with_entities(Card.id).first() is not None:
                scope_key = (
                    f"install:{install.id}"
                    if local_deck_id == root_id
                    else f"install:{install.id}:deck:{local_deck_id}"
                )
                scopes.append((scope_key, int(install.user_id), query))

    note_type_scopes = session.execute(
        select(Note.user_id, Note.note_type_id)
        .join(Card, Card.note_id == Note.id)
        .distinct()
        .order_by(Note.user_id.asc(), Note.note_type_id.asc())
    ).all()
    for user_id, note_type_id in note_type_scopes:
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            Note.user_id == int(user_id),
            Note.note_type_id == str(note_type_id),
        )
        scopes.append((f"note_type:{note_type_id}", int(user_id), query))
    return scopes


def _compare_query_scopes(
    session: Session,
    *,
    observed_at: datetime,
    progress_by_user_card: Mapping[tuple[int, str], CardProgress],
    trusted_projection_by_progress: Mapping[int, AvailabilityProjection],
    unresolved_progress_ids: frozenset[int],
    unexplained_counts: Counter[str],
    unexplained_samples: dict[str, list[str]],
    understood_counts: Counter[str],
    understood_samples: dict[str, list[str]],
) -> dict[str, Any]:
    checked = 0
    excluded = 0
    parity = 0
    scope_checksums: list[str] = []

    for scope_key, user_id, query in _scope_queries(session):
        cards_by_id = {
            str(card.id): card
            for card in query.order_by(Card.created_at.asc(), Card.id.asc()).all()
        }
        cards = list(cards_by_id.values())
        if not cards:
            continue
        checked += 1
        user = session.get(User, user_id)
        timezone_name = get_effective_timezone_name(
            getattr(user, "timezone", "UTC") if user is not None else "UTC"
        )
        runtime = resolve_scheduler_runtime_settings(user_id=user_id)
        day_boundary = int(runtime.day_boundary_hour_local)
        learn_ahead = int(runtime.learn_ahead_seconds)
        raw_entries: list[dict[str, Any]] = []
        shadow_entries: list[dict[str, Any]] = []
        scope_untrusted = False
        for card in cards:
            progress = progress_by_user_card.get((user_id, str(card.id)))
            if progress is None:
                raw_entries.append(_entry_for_new_card(card))
                shadow_entries.append(_entry_for_new_card(card))
                continue
            mapped = map_card_progress(
                progress,
                card_created_at=card.created_at,
                card_order_key=str(card.id),
            )
            if isinstance(mapped, MappingFailure):
                scope_untrusted = True
                continue
            raw_entries.append(_entry_from_projection(mapped.availability))
            stored = trusted_projection_by_progress.get(int(progress.id))
            if stored is None or int(progress.id) in unresolved_progress_ids:
                scope_untrusted = True
            else:
                shadow_entries.append(_entry_from_projection(stored))

        if scope_untrusted:
            excluded += 1
            _record(
                understood_counts,
                understood_samples,
                "QUERY_SCOPE_EXCLUDED_QUARANTINE",
                user_id,
                scope_key,
            )
            continue

        expected = _query_signature(
            raw_entries,
            now_utc=observed_at,
            timezone_name=timezone_name,
            day_boundary_hour=day_boundary,
            learn_ahead_seconds=learn_ahead,
        )
        shadow = _query_signature(
            shadow_entries,
            now_utc=observed_at,
            timezone_name=timezone_name,
            day_boundary_hour=day_boundary,
            learn_ahead_seconds=learn_ahead,
        )
        current_counts = study_repository.query_study_queue_counts(
            query,
            user_id=user_id,
            now=observed_at,
            timezone_name=timezone_name,
        )
        current_selected = study_repository.query_next_due_card_id(
            query,
            user_id=user_id,
            now=observed_at,
            timezone_name=timezone_name,
        )
        pending_count, next_due_at = study_repository.query_pending_learning_summary(
            query,
            user_id=user_id,
            now=observed_at,
            timezone_name=timezone_name,
        )
        product = {
            "counts": {
                "new": int(current_counts[0]),
                "learning": int(current_counts[1]),
                "review": int(current_counts[2]),
            },
            "selected_card_id": current_selected,
            "pending_learning_count": int(pending_count),
            "next_due_at": _iso(next_due_at),
        }
        expected_product = {
            key: expected[key]
            for key in (
                "counts",
                "selected_card_id",
                "pending_learning_count",
                "next_due_at",
            )
        }
        if product != expected_product:
            _record(
                unexplained_counts,
                unexplained_samples,
                "CURRENT_QUERY_INTERNAL_MISMATCH",
                user_id,
                scope_key,
            )
        if shadow != expected:
            _record(
                unexplained_counts,
                unexplained_samples,
                "SHADOW_QUERY_MISMATCH",
                user_id,
                scope_key,
            )
        else:
            parity += 1
        redacted = {
            "scope": _identity_sample(user_id, scope_key),
            "timezone": timezone_name,
            "day_boundary_hour_local": day_boundary,
            "learn_ahead_seconds": learn_ahead,
            "expected": _redacted_query_signature(expected),
            "shadow": _redacted_query_signature(shadow),
        }
        scope_checksums.append(
            hashlib.sha256(
                json.dumps(redacted, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
        )

    return {
        "scope_count": checked,
        "comparable_scope_count": checked - excluded,
        "quarantined_scope_count": excluded,
        "exact_parity_scope_count": parity,
        "scope_checksum": hashlib.sha256("".join(sorted(scope_checksums)).encode("ascii")).hexdigest(),
    }


def build_study_progress_reconciliation(
    session: Session,
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a deterministic, read-only P4-10 comparison report."""

    fixed_now = _utc_naive(observed_at)
    unexplained: Counter[str] = Counter()
    unexplained_samples: dict[str, list[str]] = defaultdict(list)
    quarantine: Counter[str] = Counter()
    quarantine_samples: dict[str, list[str]] = defaultdict(list)
    understood: Counter[str] = Counter()
    understood_samples: dict[str, list[str]] = defaultdict(list)

    source_rows = tuple(
        session.execute(
            select(CardProgress, Card, Note, User)
            .outerjoin(Card, Card.id == CardProgress.card_id)
            .outerjoin(Note, Note.id == Card.note_id)
            .outerjoin(User, User.id == CardProgress.user_id)
            .order_by(CardProgress.id.asc())
        ).all()
    )
    progress_by_id = {int(row[0].id): row[0] for row in source_rows}
    progress_by_user_card = {
        (int(progress.user_id), str(progress.card_id)): progress
        for progress, card, note, user in source_rows
        if card is not None and note is not None and user is not None and progress.card_id is not None
    }
    source_wrappers = tuple(
        backfill_repository.CardProgressSourceRow(
            progress=progress,
            resolved_card_id=str(card.id) if card is not None else None,
            card_note_id=(
                str(card.note_id)
                if card is not None and card.note_id is not None
                else None
            ),
            resolved_note_id=str(note.id) if note is not None else None,
            card_created_at=card.created_at if card is not None else None,
            note_owner_user_id=int(note.user_id) if note is not None else None,
            note_deck_id=int(note.deck_id) if note is not None and note.deck_id is not None else None,
            learner_exists=user is not None,
        )
        for progress, card, note, user in source_rows
    )
    grouped: dict[tuple[int, str], list[backfill_repository.CardProgressSourceRow]] = defaultdict(list)
    unresolved_ids: set[int] = set()
    for row in source_wrappers:
        if row.subject_key is None:
            unresolved_ids.add(row.source_id)
        else:
            grouped[row.subject_key].append(row)
    grouped_tuples = {key: tuple(value) for key, value in grouped.items()}
    approved_contexts = backfill_repository.approved_subject_contexts(session, grouped_tuples)
    installed_source_deck_contexts: dict[tuple[int, int], set[int]] = defaultdict(set)
    for learner_id, source_deck_id, local_deck_id in session.execute(
        select(
            DeckInstall.user_id,
            DeckCloneDeckMap.source_deck_id,
            DeckCloneDeckMap.local_deck_id,
        )
        .join(DeckCloneDeckMap, DeckCloneDeckMap.deck_install_id == DeckInstall.id)
        .where(DeckInstall.clone_mode == "logical_overlay")
    ):
        installed_source_deck_contexts[
            (int(learner_id), int(source_deck_id))
        ].add(int(local_deck_id))
    for learner_id, source_deck_id, local_deck_id in session.execute(
        select(
            DeckInstall.user_id,
            DeckInstall.source_deck_id,
            DeckInstall.local_deck_id,
        ).where(
            DeckInstall.clone_mode == "logical_overlay",
            DeckInstall.source_deck_id.is_not(None),
            DeckInstall.local_deck_id.is_not(None),
        )
    ):
        installed_source_deck_contexts[
            (int(learner_id), int(source_deck_id))
        ].add(int(local_deck_id))

    subjects = tuple(
        session.execute(select(StudyProgressSubject).order_by(StudyProgressSubject.id.asc())).scalars()
    )
    subjects_by_id = {int(subject.id): subject for subject in subjects}
    subjects_by_key: dict[tuple[int, str], StudyProgressSubject] = {}
    for subject in subjects:
        try:
            key = (
                int(subject.learner_user_id),
                bytes(subject.logical_note_key).decode("utf-8"),
            )
        except UnicodeDecodeError:
            _record(unexplained, unexplained_samples, "INVALID_SUBJECT_KEY_ENCODING", subject.id)
            continue
        subjects_by_key[key] = subject

    contributors = tuple(
        session.execute(
            select(StudyProgressContributor).order_by(StudyProgressContributor.id.asc())
        ).scalars()
    )
    contributors_by_id = {int(row.id): row for row in contributors}
    contributors_by_subject: dict[int, list[StudyProgressContributor]] = defaultdict(list)
    active_by_progress: dict[int, StudyProgressContributor] = {}
    for contributor in contributors:
        contributors_by_subject[int(contributor.subject_id)].append(contributor)
        if contributor.contributor_status == "ACTIVE" and contributor.live_card_progress_id is not None:
            progress_id = int(contributor.live_card_progress_id)
            if progress_id in active_by_progress:
                _record(unexplained, unexplained_samples, "DUPLICATE_ACTIVE_CONTRIBUTOR", progress_id)
            active_by_progress[progress_id] = contributor

    availability_by_contributor = {
        int(row.contributor_id): row
        for row in session.execute(
            select(StudyProgressAvailability).order_by(StudyProgressAvailability.contributor_id.asc())
        ).scalars()
    }
    states_by_subject = {
        int(row.subject_id): row
        for row in session.execute(
            select(StudyProgressState).order_by(StudyProgressState.subject_id.asc())
        ).scalars()
    }
    lineage_by_contributor: dict[int, list[StudyProgressLineageRef]] = defaultdict(list)
    lineage_rows = tuple(
        session.execute(
            select(StudyProgressLineageRef).order_by(
                StudyProgressLineageRef.contributor_id.asc(),
                StudyProgressLineageRef.ref_kind.asc(),
                StudyProgressLineageRef.source_row_key.asc(),
                StudyProgressLineageRef.id.asc(),
            )
        ).scalars()
    )
    for row in lineage_rows:
        lineage_by_contributor[int(row.contributor_id)].append(row)

    event_ids = sorted(
        {
            int(progress.last_review_event_id)
            for progress in progress_by_id.values()
            if progress.last_review_event_id is not None
        }
    )
    event_by_id = {
        int(row.id): row
        for row in session.execute(select(ReviewEvent).where(ReviewEvent.id.in_(event_ids))).scalars()
    } if event_ids else {}

    source_card_refs = {
        str(row.id): row
        for row in session.execute(select(ConnectSourceCardRef)).scalars()
    }
    source_note_refs = {
        str(row.id): row
        for row in session.execute(select(ConnectSourceNoteRef)).scalars()
    }
    source_note_refs_by_origin: dict[
        tuple[int, str, str, str], list[ConnectSourceNoteRef]
    ] = defaultdict(list)
    for note_ref in source_note_refs.values():
        source_note_refs_by_origin[
            (
                int(note_ref.user_id),
                str(note_ref.source_key),
                str(note_ref.external_note_id),
                str(note_ref.note_id),
            )
        ].append(note_ref)
    connect_event_refs = {
        str(row.id): row
        for row in session.execute(select(ConnectReviewEventRef)).scalars()
    }
    applied_card_refs_by_user_card: dict[
        tuple[int, str], list[ConnectSourceCardRef]
    ] = defaultdict(list)
    for source_ref in source_card_refs.values():
        applied_card_refs_by_user_card[
            (int(source_ref.user_id), str(source_ref.card_id))
        ].append(source_ref)

    mapped_by_progress: dict[int, MappedCardProgress | MappingFailure] = {}
    trusted_projection_by_progress: dict[int, AvailabilityProjection] = {}
    options_by_context: dict[tuple[int, int], Any] = {}
    decoded_transition_count = 0
    expected_subject_status: dict[tuple[int, str], str] = {}

    for key in sorted(grouped, key=lambda value: (value[0], value[1].encode("utf-8"))):
        rows = tuple(sorted(grouped[key], key=lambda value: (str(value.resolved_card_id), value.source_id)))
        mapped_rows: list[MappedCardProgress] = []
        failures: list[MappingFailure] = []
        for row in rows:
            mapped = map_card_progress(
                row.progress,
                card_created_at=row.card_created_at,
                card_order_key=row.resolved_card_id,
            )
            mapped_by_progress[row.source_id] = mapped
            if isinstance(mapped, MappingFailure):
                failures.append(mapped)
            else:
                mapped_rows.append(mapped)

        if key not in approved_contexts:
            expected_status = "QUARANTINED_UNCLASSIFIED_CONTEXT"
        elif failures:
            expected_status = _mapping_quarantine(failures[0].code)
        elif len({row.semantic_state_hash for row in mapped_rows}) != 1:
            expected_status = "QUARANTINED_STATE_DIVERGENCE"
        elif len(mapped_rows) == 1:
            expected_status = "MIRRORED_SINGLE"
        else:
            lineage_hashes = {
                _bytes(active_by_progress.get(row.source_id).lineage_vector_hash)
                for row in rows
                if active_by_progress.get(row.source_id) is not None
            }
            expected_status = (
                "MIRRORED_EQUIVALENT_FANIN"
                if len(lineage_hashes) == 1
                else "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE"
            )
        expected_subject_status[key] = expected_status
        subject = subjects_by_key.get(key)
        if subject is None:
            _record(unexplained, unexplained_samples, "MISSING_SUBJECT", *key)
            continue
        if subject.status_code != expected_status:
            _record(unexplained, unexplained_samples, "SUBJECT_STATUS_MISMATCH", *key)
        if subject.live_note_id != key[1]:
            _record(unexplained, unexplained_samples, "SUBJECT_NOTE_ID_MISMATCH", *key)
        if subject.mapper_version != MAPPER_VERSION:
            _record(unexplained, unexplained_samples, "SUBJECT_MAPPER_VERSION_MISMATCH", *key)
        current_contributors = [
            row
            for row in contributors_by_subject.get(int(subject.id), ())
            if row.contributor_status == "ACTIVE"
            and int(row.subject_generation) == int(subject.subject_generation)
        ]
        if int(subject.contributor_count) != len(rows) or len(current_contributors) != len(rows):
            _record(unexplained, unexplained_samples, "SUBJECT_CONTRIBUTOR_COUNT_MISMATCH", *key)

        authority_material: list[dict[str, str]] = []
        lineage_material: list[dict[str, str]] = []
        for row in rows:
            mapped = mapped_by_progress[row.source_id]
            contributor = active_by_progress.get(row.source_id)
            if contributor is None:
                _record(unexplained, unexplained_samples, "MISSING_ACTIVE_CONTRIBUTOR", row.source_id)
                continue
            if int(contributor.subject_id) != int(subject.id):
                _record(unexplained, unexplained_samples, "CONTRIBUTOR_SUBJECT_MISMATCH", row.source_id)
            raw = mapped.raw
            if raw is None:
                _record(unexplained, unexplained_samples, "SOURCE_RAW_UNREADABLE", row.source_id)
                continue
            expected_fields = (
                int(contributor.source_progress_id) == row.source_id,
                int(contributor.subject_generation) == int(subject.subject_generation),
                contributor.live_card_id == row.resolved_card_id,
                bytes(contributor.logical_card_key) == str(row.resolved_card_id).encode("utf-8"),
                int(contributor.card_progress_revision) == int(row.progress.revision),
                contributor.raw_schema_version == RAW_SCHEMA_VERSION,
                contributor.storage_codec == STORAGE_CODEC,
                contributor.raw_payload == raw.payload,
                int(contributor.raw_payload_size) == raw.size,
                _bytes(contributor.raw_progress_hash) == raw.digest,
            )
            if not all(expected_fields):
                _record(unexplained, unexplained_samples, "CONTRIBUTOR_RAW_MISMATCH", row.source_id)

            pointer_status = _expected_pointer_status(row.progress, event_by_id)
            if contributor.pointer_status != pointer_status:
                _record(unexplained, unexplained_samples, "CONTRIBUTOR_POINTER_MISMATCH", row.source_id)
            contributor_lineage = lineage_by_contributor.get(int(contributor.id), [])
            lineage_card_ref_keys = {
                bytes(ref.source_row_key).decode("utf-8", errors="replace")
                for ref in contributor_lineage
                if ref.ref_kind == "CONNECT_SOURCE_CARD"
            }
            applicable_card_refs = [
                source_ref
                for source_ref in applied_card_refs_by_user_card.get(
                    (int(row.progress.user_id), str(row.resolved_card_id)),
                    (),
                )
                if source_ref.applied_local_revision is not None
                and int(source_ref.applied_local_revision) == int(row.progress.revision)
            ]
            missing_applied_refs = [
                source_ref
                for source_ref in applicable_card_refs
                if str(source_ref.id) not in lineage_card_ref_keys
            ]
            if missing_applied_refs:
                _record(
                    unexplained,
                    unexplained_samples,
                    "MISSING_APPLIED_CONNECT_CARD_LINEAGE",
                    row.source_id,
                )
            lineage_note_ref_keys = {
                bytes(ref.source_row_key).decode("utf-8", errors="replace")
                for ref in contributor_lineage
                if ref.ref_kind == "CONNECT_SOURCE_NOTE"
            }
            expected_note_refs = [
                note_ref
                for card_ref in applicable_card_refs
                for note_ref in source_note_refs_by_origin.get(
                    (
                        int(card_ref.user_id),
                        str(card_ref.source_key),
                        str(card_ref.external_note_id),
                        str(row.resolved_note_id),
                    ),
                    (),
                )
            ]
            if any(str(ref.id) not in lineage_note_ref_keys for ref in expected_note_refs):
                _record(
                    unexplained,
                    unexplained_samples,
                    "MISSING_APPLIED_CONNECT_NOTE_LINEAGE",
                    row.source_id,
                )
            pointed_event = (
                event_by_id.get(int(row.progress.last_review_event_id))
                if row.progress.last_review_event_id is not None
                else None
            )
            expected_native_provenance = _native_event_provenance(pointed_event)
            if (
                expected_native_provenance is not None
                and contributor.current_provenance_code != expected_native_provenance
            ):
                _record(
                    unexplained,
                    unexplained_samples,
                    "CONTRIBUTOR_PROVENANCE_MISMATCH",
                    row.source_id,
                )
            if applicable_card_refs and contributor.current_provenance_code not in {
                "CONNECT_PROGRESS_SNAPSHOT",
                "CONNECT_LEGACY_PROGRESS",
            }:
                _record(
                    unexplained,
                    unexplained_samples,
                    "CONTRIBUTOR_CONNECT_PROVENANCE_MISMATCH",
                    row.source_id,
                )
            try:
                lineage_hash = _lineage_hash(
                    contributor_lineage,
                    pointer_status=str(contributor.pointer_status),
                )
            except StudyProgressCodecError:
                lineage_hash = None
                _record(unexplained, unexplained_samples, "LINEAGE_HASH_UNREADABLE", row.source_id)
            if lineage_hash != _bytes(contributor.lineage_vector_hash):
                _record(unexplained, unexplained_samples, "LINEAGE_VECTOR_HASH_MISMATCH", row.source_id)
            authority_material.append(
                {
                    "card_id": str(row.resolved_card_id),
                    "progress_id": str(row.source_id),
                    "raw_progress_hash": raw.digest.hex(),
                    "revision": str(row.progress.revision),
                }
            )
            lineage_material.append(
                {
                    "card_id": str(row.resolved_card_id),
                    "lineage_vector_hash": (
                        lineage_hash.hex() if lineage_hash is not None else ""
                    ),
                    "progress_id": str(row.source_id),
                }
            )

            for ref in contributor_lineage:
                try:
                    source_key = bytes(ref.source_row_key).decode("utf-8")
                except UnicodeDecodeError:
                    _record(unexplained, unexplained_samples, "LINEAGE_REF_KEY_UNREADABLE", ref.id)
                    continue
                if ref.ref_kind == "LAST_REVIEW_EVENT":
                    event = event_by_id.get(int(source_key)) if source_key.isdigit() else None
                    expected_payload_hash = (
                        hashlib.sha256(str(event.payload_json).encode("utf-8")).digest()
                        if event is not None
                        else None
                    )
                    if (
                        event is None
                        or int(event.id) != int(row.progress.last_review_event_id or 0)
                        or ref.ref_status != pointer_status
                        or _bytes(ref.source_payload_hash) != expected_payload_hash
                    ):
                        _record(unexplained, unexplained_samples, "LINEAGE_EVENT_REF_MISMATCH", ref.id)
                elif ref.ref_kind == "CONNECT_SOURCE_CARD":
                    source_ref = source_card_refs.get(source_key)
                    if (
                        source_ref is None
                        or int(source_ref.user_id) != int(row.progress.user_id)
                        or str(source_ref.card_id) != str(row.resolved_card_id)
                        or bytes(ref.source_key or b"") != str(source_ref.source_key).encode("utf-8")
                        or bytes(ref.external_card_id or b"")
                        != str(source_ref.external_card_id).encode("utf-8")
                        or bytes(ref.external_note_id or b"")
                        != str(source_ref.external_note_id).encode("utf-8")
                        or _bytes(ref.source_snapshot_hash)
                        != _decode_source_hash(source_ref.snapshot_hash)
                        or ref.ref_status != "VALID"
                    ):
                        _record(unexplained, unexplained_samples, "LINEAGE_CARD_REF_MISMATCH", ref.id)
                elif ref.ref_kind == "CONNECT_SOURCE_NOTE":
                    source_ref = source_note_refs.get(source_key)
                    live_payload_hash = (
                        _decode_source_hash(source_ref.content_hash)
                        if source_ref is not None
                        else None
                    )
                    captured_payload_hash = _bytes(ref.source_payload_hash)
                    content_advanced_after_capture = (
                        source_ref is not None
                        and live_payload_hash != captured_payload_hash
                        and ref.occurred_at is not None
                        and source_ref.updated_at is not None
                        and source_ref.updated_at > ref.occurred_at
                    )
                    identity_mismatch = (
                        source_ref is None
                        or int(source_ref.user_id) != int(row.progress.user_id)
                        or str(source_ref.note_id) != str(row.resolved_note_id)
                        or bytes(ref.source_key or b"") != str(source_ref.source_key).encode("utf-8")
                        or bytes(ref.external_note_id or b"")
                        != str(source_ref.external_note_id).encode("utf-8")
                        or ref.ref_status != "VALID"
                    )
                    if identity_mismatch or (
                        captured_payload_hash != live_payload_hash
                        and not content_advanced_after_capture
                    ):
                        _record(unexplained, unexplained_samples, "LINEAGE_NOTE_REF_MISMATCH", ref.id)
                    elif content_advanced_after_capture:
                        _record(
                            understood,
                            understood_samples,
                            "CONNECT_NOTE_CONTENT_ADVANCED_AFTER_PROGRESS",
                            ref.id,
                        )

            availability = availability_by_contributor.get(int(contributor.id))
            if expected_status not in USABLE_SUBJECT_STATUSES:
                _record(quarantine, quarantine_samples, expected_status, row.source_id)
            if isinstance(mapped, MappingFailure):
                if availability is not None:
                    _record(unexplained, unexplained_samples, "QUARANTINE_HAS_AVAILABILITY", row.source_id)
                continue
            if availability is None:
                _record(unexplained, unexplained_samples, "MISSING_AVAILABILITY", row.source_id)
            else:
                stored_projection = _availability_from_row(availability)
                if (
                    int(availability.subject_id) != int(subject.id)
                    or int(availability.subject_generation) != int(subject.subject_generation)
                    or _projection_signature(stored_projection)
                    != _projection_signature(mapped.availability)
                ):
                    _record(unexplained, unexplained_samples, "AVAILABILITY_MISMATCH", row.source_id)
                elif expected_status in USABLE_SUBJECT_STATUSES:
                    trusted_projection_by_progress[row.source_id] = stored_projection

        expected_authority_hash = canonical_document(
            {"contributors": authority_material},
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        ).digest if authority_material else None
        expected_lineage_hash = canonical_document(
            {"contributors": lineage_material},
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        ).digest if lineage_material else None
        if _bytes(subject.authority_vector_hash) != expected_authority_hash:
            _record(unexplained, unexplained_samples, "SUBJECT_AUTHORITY_VECTOR_MISMATCH", *key)
        if _bytes(subject.lineage_vector_hash) != expected_lineage_hash:
            _record(unexplained, unexplained_samples, "SUBJECT_LINEAGE_VECTOR_MISMATCH", *key)

        state = states_by_subject.get(int(subject.id))
        if expected_status not in USABLE_SUBJECT_STATUSES:
            if state is not None:
                _record(unexplained, unexplained_samples, "QUARANTINE_HAS_STATE", *key)
            continue
        if state is None or not mapped_rows:
            _record(unexplained, unexplained_samples, "MISSING_SUBJECT_STATE", *key)
            continue
        expected_state = mapped_rows[0]
        state_matches = (
            int(state.subject_generation) == int(subject.subject_generation)
            and int(state.mirror_revision) == int(subject.mirror_revision)
            and state.algorithm_key == expected_state.algorithm_key
            and state.algorithm_version == expected_state.algorithm_version
            and state.state_schema_version == expected_state.state_schema_version
            and state.storage_codec == expected_state.storage_codec
            and state.state_payload == expected_state.state.payload
            and int(state.state_payload_size) == expected_state.state.size
            and _bytes(state.algorithm_state_hash) == expected_state.algorithm_state_hash
            and _bytes(state.semantic_state_hash) == expected_state.semantic_state_hash
        )
        if not state_matches:
            _record(unexplained, unexplained_samples, "SUBJECT_STATE_MISMATCH", *key)
            continue
        try:
            decoded = STATE_DECODERS.decode(
                algorithm_key=str(state.algorithm_key),
                algorithm_version=str(state.algorithm_version),
                state_schema_version=str(state.state_schema_version),
                storage_codec=str(state.storage_codec),
                payload=state.state_payload,
                expected_size=int(state.state_payload_size),
                expected_hash=bytes(state.algorithm_state_hash),
            )
            timezone_name = get_effective_timezone_name(
                getattr(session.get(User, key[0]), "timezone", "UTC")
            )
            for row in rows:
                if row.note_deck_id is None:
                    _record(unexplained, unexplained_samples, "TRANSITION_CONTEXT_MISSING", row.source_id)
                    continue
                if row.note_owner_user_id == key[0]:
                    context_deck_ids = {int(row.note_deck_id)}
                else:
                    context_deck_ids = installed_source_deck_contexts.get(
                        (key[0], int(row.note_deck_id)), set()
                    )
                if not context_deck_ids:
                    _record(unexplained, unexplained_samples, "TRANSITION_CONTEXT_MISSING", row.source_id)
                    continue
                for context_deck_id in sorted(context_deck_ids):
                    try:
                        context_key = (key[0], context_deck_id)
                        options = options_by_context.get(context_key)
                        if options is None:
                            options = resolve_deck_options(
                                user_id=key[0], deck_id=context_deck_id
                            )
                            options_by_context[context_key] = options
                        product_state = study_repository.card_state_from_progress(
                            row.progress,
                            fixed_now,
                            timezone_name=timezone_name,
                            user_id=key[0],
                            options=options,
                        )
                        shadow_state = decoded
                        if row.progress.due_at is None:
                            shadow_state = replace(shadow_state, due=product_state.due)
                            _record(
                                understood,
                                understood_samples,
                                "STATE_NULL_DUE_PRODUCT_FALLBACK",
                                row.source_id,
                                context_deck_id,
                            )
                        if row.progress.queue == "review" and row.progress.due_day is None:
                            shadow_state = replace(
                                shadow_state, dueDay=product_state.dueDay
                            )
                            _record(
                                understood,
                                understood_samples,
                                "STATE_REVIEW_DAY_PRODUCT_DERIVATION",
                                row.source_id,
                                context_deck_id,
                            )
                        if shadow_state != product_state:
                            _record(
                                unexplained,
                                unexplained_samples,
                                "STATE_PRODUCT_PROJECTION_MISMATCH",
                                row.source_id,
                                context_deck_id,
                            )
                            continue
                        if computeAnswerPreview(
                            shadow_state,
                            options,
                            fixed_now,
                            timezone_name=timezone_name,
                        ) != computeAnswerPreview(
                            product_state,
                            options,
                            fixed_now,
                            timezone_name=timezone_name,
                        ):
                            _record(
                                unexplained,
                                unexplained_samples,
                                "TRANSITION_PREVIEW_MISMATCH",
                                row.source_id,
                                context_deck_id,
                            )
                        else:
                            decoded_transition_count += 1
                    except (OverflowError, ValueError, TypeError):
                        _record(
                            unexplained,
                            unexplained_samples,
                            "TRANSITION_EVALUATION_FAILURE",
                            row.source_id,
                            context_deck_id,
                        )
        except (StudyProgressCodecError, ValueError, TypeError):
            _record(unexplained, unexplained_samples, "STATE_DECODER_FAILURE", *key)

    for row in source_wrappers:
        if row.source_id not in unresolved_ids:
            continue
        code = str(row.resolution_code or "UNRESOLVABLE_MISSING_LEARNER")
        _record(understood, understood_samples, code, row.source_id)
        if row.source_id in active_by_progress:
            _record(unexplained, unexplained_samples, "UNRESOLVABLE_HAS_ACTIVE_CONTRIBUTOR", row.source_id)

    lifecycle_subject_ids = {
        int(row.subject_id)
        for row in session.execute(select(StudyProgressLifecycleEvent)).scalars()
    }
    history_contributor_ids = {
        int(row.contributor_id)
        for row in session.execute(select(StudyProgressHistoryFact)).scalars()
        if row.contributor_id is not None
    }
    successor_sources = {
        int(row.source_progress_id)
        for row in contributors
        if row.contributor_status == "ACTIVE"
    }
    for contributor in contributors:
        if contributor.contributor_status == "ACTIVE":
            progress = progress_by_id.get(int(contributor.live_card_progress_id or 0))
            subject = subjects_by_id.get(int(contributor.subject_id))
            if (
                progress is None
                or subject is None
                or int(contributor.subject_generation) != int(subject.subject_generation)
            ):
                _record(unexplained, unexplained_samples, "ORPHAN_ACTIVE_CONTRIBUTOR", contributor.id)
        elif (
            int(contributor.source_progress_id) not in successor_sources
            and int(contributor.subject_id) not in lifecycle_subject_ids
            and int(contributor.id) not in history_contributor_ids
        ):
            _record(unexplained, unexplained_samples, "UNACCOUNTED_DETACHED_CONTRIBUTOR", contributor.id)

    for contributor_id, availability in sorted(availability_by_contributor.items()):
        contributor = contributors_by_id.get(contributor_id)
        if (
            contributor is None
            or contributor.contributor_status != "ACTIVE"
            or int(contributor.subject_id) != int(availability.subject_id)
        ):
            _record(
                unexplained,
                unexplained_samples,
                "ORPHAN_AVAILABILITY",
                contributor_id,
            )

    for key, subject in sorted(subjects_by_key.items()):
        if key in grouped:
            continue
        if subject.status_code not in {
            "NO_CURRENT_PROGRESS",
            "TOMBSTONED_RESET",
            "TOMBSTONED_SUBJECT_DELETED",
            "REKEYED_CLONE_CUTOVER",
        }:
            _record(unexplained, unexplained_samples, "STALE_SUBJECT_WITHOUT_AUTHORITY", *key)
        if states_by_subject.get(int(subject.id)) is not None:
            _record(unexplained, unexplained_samples, "EMPTY_SUBJECT_HAS_STATE", *key)

    for ref in lineage_rows:
        if ref.ref_kind == "CONNECT_SOURCE_CARD":
            try:
                key = bytes(ref.source_row_key).decode("utf-8")
            except UnicodeDecodeError:
                continue
            if key not in source_card_refs:
                _record(unexplained, unexplained_samples, "ORPHAN_CONNECT_CARD_LINEAGE", ref.id)
        elif ref.ref_kind == "CONNECT_SOURCE_NOTE":
            try:
                key = bytes(ref.source_row_key).decode("utf-8")
            except UnicodeDecodeError:
                continue
            if key not in source_note_refs:
                _record(unexplained, unexplained_samples, "ORPHAN_CONNECT_NOTE_LINEAGE", ref.id)

    for ref_id, ref in sorted(connect_event_refs.items()):
        if ref.review_event_id is not None and session.get(ReviewEvent, int(ref.review_event_id)) is None:
            _record(unexplained, unexplained_samples, "ORPHAN_CONNECT_REVIEW_EVENT_REF", ref_id)

    runs = tuple(
        session.execute(
            select(StudyProgressBackfillRun).order_by(
                StudyProgressBackfillRun.started_at.asc(),
                StudyProgressBackfillRun.id.asc(),
            )
        ).scalars()
    )
    completed_runs = [
        row
        for row in runs
        if row.run_kind == "CURRENT_PROGRESS" and row.status_code == "COMPLETED"
    ]
    latest_run = completed_runs[-1] if completed_runs else None
    disposition_counts: Counter[str] = Counter()
    invalid_disposition_count = 0
    if latest_run is not None:
        dispositions = tuple(
            session.execute(
                select(StudyProgressBackfillDisposition)
                .where(StudyProgressBackfillDisposition.run_id == latest_run.id)
                .order_by(StudyProgressBackfillDisposition.id.asc())
            ).scalars()
        )
        for disposition in dispositions:
            code = str(disposition.disposition_code)
            disposition_counts[code] += 1
            if code not in BACKFILL_DISPOSITIONS or code == "RETRY_PENDING":
                invalid_disposition_count += 1
                _record(unexplained, unexplained_samples, "INVALID_COMPLETED_DISPOSITION", disposition.id)
            try:
                evidence = canonical_typed_document(
                    disposition.evidence_payload,
                    too_large_code="STATE_PAYLOAD_TOO_LARGE",
                )
            except StudyProgressCodecError:
                _record(
                    unexplained,
                    unexplained_samples,
                    "BACKFILL_DISPOSITION_EVIDENCE_UNREADABLE",
                    disposition.id,
                )
            else:
                if (
                    int(disposition.evidence_payload_size) != evidence.size
                    or _bytes(disposition.evidence_payload_hash) != evidence.digest
                ):
                    _record(
                        unexplained,
                        unexplained_samples,
                        "BACKFILL_DISPOSITION_EVIDENCE_MISMATCH",
                        disposition.id,
                    )
        disposition_total = sum(disposition_counts.values())
        mirrored_total = sum(
            count
            for code, count in disposition_counts.items()
            if code.startswith("MIRRORED_")
        )
        quarantined_total = sum(
            count
            for code, count in disposition_counts.items()
            if code.startswith("QUARANTINED_")
        )
        retry_total = sum(
            count
            for code, count in disposition_counts.items()
            if code.startswith("STALE_") or code == "RETRY_PENDING"
        )
        unresolvable_total = disposition_total - mirrored_total - quarantined_total - retry_total
        if (
            disposition_total != int(latest_run.source_count)
            or mirrored_total != int(latest_run.mirrored_count)
            or quarantined_total != int(latest_run.quarantined_count)
            or unresolvable_total != int(latest_run.unresolvable_count)
        ):
            _record(
                unexplained,
                unexplained_samples,
                "BACKFILL_RUN_ACCOUNTING_MISMATCH",
                latest_run.id,
            )

    query_parity = _compare_query_scopes(
        session,
        observed_at=fixed_now,
        progress_by_user_card=progress_by_user_card,
        trusted_projection_by_progress=trusted_projection_by_progress,
        unresolved_progress_ids=frozenset(unresolved_ids),
        unexplained_counts=unexplained,
        unexplained_samples=unexplained_samples,
        understood_counts=understood,
        understood_samples=understood_samples,
    )

    understood_count = sum(understood.values())
    quarantine_count = sum(quarantine.values())
    unexplained_count = sum(unexplained.values())
    accounted_sources = sum(
        1
        for row in source_wrappers
        if row.source_id in unresolved_ids or row.source_id in active_by_progress
    )
    accounting = {
        "source_rows": len(source_wrappers),
        "accounted_source_rows": accounted_sources,
        "resolvable_source_rows": len(source_wrappers) - len(unresolved_ids),
        "unresolvable_source_rows": len(unresolved_ids),
        "subjects": len(subjects),
        "contributors": len(contributors),
        "active_contributors": sum(1 for row in contributors if row.contributor_status == "ACTIVE"),
        "detached_contributors": sum(1 for row in contributors if row.contributor_status != "ACTIVE"),
        "availability_rows": len(availability_by_contributor),
        "state_rows": len(states_by_subject),
        "lineage_rows": len(lineage_rows),
        "decoded_transition_samples": decoded_transition_count,
        "source_partition": accounted_sources == len(source_wrappers),
        "zero_unexplained": unexplained_count == 0,
        "query_scope_partition": (
            query_parity["comparable_scope_count"]
            + query_parity["quarantined_scope_count"]
            == query_parity["scope_count"]
        ),
        "query_parity": (
            query_parity["exact_parity_scope_count"]
            == query_parity["comparable_scope_count"]
        ),
    }
    provenance_counts = Counter(str(row.current_provenance_code) for row in contributors)
    lifecycle_counts = Counter(
        str(row.transition_code)
        for row in session.execute(select(StudyProgressLifecycleEvent)).scalars()
    )
    history_provenance_counts = Counter(
        str(row.provenance_code)
        for row in session.execute(select(StudyProgressHistoryFact)).scalars()
    )
    required_writer_classes = (
        "NATIVE_DIRECT",
        "NATIVE_MCP",
        "NATIVE_SESSION",
        "NATIVE_ASYNC_BATCH",
        "CONNECT_PROGRESS_SNAPSHOT",
        "CONNECT_LEGACY_PROGRESS",
        "CONNECT_REVLOG",
        "PROGRESS_RESET",
        "CONTENT_DELETE",
        "CLONE_CUTOVER",
    )
    writer_matrix: dict[str, dict[str, Any]] = {}
    for writer_class in required_writer_classes:
        current_count = int(provenance_counts.get(writer_class, 0))
        history_count = int(history_provenance_counts.get(writer_class, 0))
        if writer_class == "PROGRESS_RESET":
            lifecycle_count = int(lifecycle_counts.get("TOMBSTONED_RESET", 0))
        elif writer_class == "CONTENT_DELETE":
            lifecycle_count = sum(
                int(lifecycle_counts.get(code, 0))
                for code in (
                    "DETACHED_CONTRIBUTOR_DELETED",
                    "TOMBSTONED_SUBJECT_DELETED",
                )
            )
        elif writer_class == "CLONE_CUTOVER":
            lifecycle_count = int(lifecycle_counts.get("REKEYED_CLONE_CUTOVER", 0))
        else:
            lifecycle_count = 0
        observed_count = max(current_count, history_count, lifecycle_count)
        writer_matrix[writer_class] = {
            "observed_count": observed_count,
            "current_contributor_count": current_count,
            "history_fact_count": history_count,
            "lifecycle_event_count": lifecycle_count,
            "status": (
                "NOT_OBSERVED"
                if observed_count == 0
                else "PASS" if unexplained_count == 0 else "BLOCK"
            ),
        }
    writer_coverage = {
        "current_contributor_provenance": dict(sorted(provenance_counts.items())),
        "history_fact_provenance": dict(sorted(history_provenance_counts.items())),
        "lifecycle_transitions": dict(sorted(lifecycle_counts.items())),
        "required_writer_classes": list(required_writer_classes),
        "matrix": writer_matrix,
    }
    enabled = bool(current_app.config.get("STUDY_PROGRESS_SHADOW_COMPARE_ENABLED", False))
    blockers: list[str] = []
    if not accounting["source_partition"]:
        blockers.append("shadow_source_accounting_incomplete")
    if not accounting["zero_unexplained"]:
        blockers.append("shadow_unexplained_mismatch")
    if not accounting["query_scope_partition"] or not accounting["query_parity"]:
        blockers.append("shadow_query_parity_failed")
    if source_rows and latest_run is None:
        blockers.append("completed_current_progress_backfill_missing")

    version_inventory = {
        "comparison_schema_version": RECONCILIATION_SCHEMA_VERSION,
        "comparison_policy_version": COMPARISON_POLICY_VERSION,
        "mapper_version": MAPPER_VERSION,
        "raw_schema_version": RAW_SCHEMA_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "storage_codec": STORAGE_CODEC,
        "projection_version": PROJECTION_VERSION,
        "history_schema_version": HISTORY_SCHEMA_VERSION,
        "lifecycle_evidence_schema_version": LIFECYCLE_EVIDENCE_SCHEMA_VERSION,
        "algorithm_key": ALGORITHM_KEY,
        "algorithm_version": ALGORITHM_VERSION,
        "backfill_runs": [
            {
                "run_digest": _identity_sample(row.id),
                "kind": str(row.run_kind),
                "status": str(row.status_code),
                "repository_commit": str(row.repository_commit),
                "database_head": str(row.database_head),
                "audit_schema_version": str(row.audit_schema_version),
                "mapper_version": str(row.mapper_version),
                "state_schema_version": str(row.state_schema_version),
                "projection_version": str(row.projection_version),
                "contract_hash": bytes(row.contract_hash).hex(),
            }
            for row in runs
        ],
    }
    report: dict[str, Any] = {
        "schema_version": RECONCILIATION_SCHEMA_VERSION,
        "mode": "ENFORCED" if enabled else "OBSERVE_ONLY",
        "observed_at": fixed_now.isoformat(timespec="seconds"),
        "versions": version_inventory,
        "accounting": accounting,
        "query_parity": query_parity,
        "writer_coverage": writer_coverage,
        "understood_representations": {
            "count": understood_count,
            "by_code": dict(sorted(understood.items())),
            "samples": {key: sorted(value) for key, value in sorted(understood_samples.items())},
            "tolerances": [
                {
                    "code": "STATE_NULL_DUE_PRODUCT_FALLBACK",
                    "field": "CardState.due",
                    "bound": "CardProgress.due_at IS NULL only",
                    "count": understood.get("STATE_NULL_DUE_PRODUCT_FALLBACK", 0),
                },
                {
                    "code": "STATE_REVIEW_DAY_PRODUCT_DERIVATION",
                    "field": "CardState.dueDay",
                    "bound": "queue=review and CardProgress.due_day IS NULL only",
                    "count": understood.get("STATE_REVIEW_DAY_PRODUCT_DERIVATION", 0),
                },
                {
                    "code": "CONNECT_NOTE_CONTENT_ADVANCED_AFTER_PROGRESS",
                    "field": "StudyProgressLineageRef.source_payload_hash",
                    "bound": "live ConnectSourceNoteRef.updated_at strictly later than captured occurred_at",
                    "count": understood.get("CONNECT_NOTE_CONTENT_ADVANCED_AFTER_PROGRESS", 0),
                },
            ],
        },
        "quarantines": {
            "count": quarantine_count,
            "by_code": dict(sorted(quarantine.items())),
            "samples": {key: sorted(value) for key, value in sorted(quarantine_samples.items())},
        },
        "unexplained": {
            "count": unexplained_count,
            "by_code": dict(sorted(unexplained.items())),
            "samples": {key: sorted(value) for key, value in sorted(unexplained_samples.items())},
        },
        "latest_completed_backfill": (
            {
                "run_digest": _identity_sample(latest_run.id),
                "source_count": int(latest_run.source_count),
                "disposition_count": sum(disposition_counts.values()),
                "dispositions": dict(sorted(disposition_counts.items())),
                "invalid_disposition_count": invalid_disposition_count,
            }
            if latest_run is not None
            else None
        ),
        "gate": {
            "status": "PASS" if not blockers else "BLOCK",
            "blockers": sorted(blockers),
            "enforced": enabled,
        },
    }
    checksum_material = json.dumps(
        report,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    report["checksum_sha256"] = hashlib.sha256(checksum_material).hexdigest()
    return report
