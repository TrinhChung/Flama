"""Read-only evidence for the Phase 9 contraction gates.

Phase 9 removes old storage and compatibility code only after telemetry
proves nothing still uses it, and every destructive step needs a verified
backup and a separate approval. This report only counts; it never writes.
Each gate is ``ready`` when its evidence is empty over the observation window
and ``waiting`` otherwise, with ``blocking_reasons`` where the cause is not
plain usage. Owner decisions D9-01/D9-02 (docs/task/decoupling/
P9_EXECUTION_PLAN_2026-09-30.md) removed the former ``decision`` status.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, or_, select

from app.validators.study_session_wire import SESSION_SCHEMA_V4
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.connect_source_card_ref import ConnectSourceCardRef
from models.study_application import StudyApplication
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.user import User

SCHEMA_VERSION = "study-phase9-readiness.v3"
PROJECTION_DEPENDENT_NOTE_CODE = "NOTE_STILL_DEPENDS_ON_PROJECTION"


def _count(statement) -> int:
    return int(db.session.execute(statement).scalar_one() or 0)


def build_phase9_readiness(
    *,
    now_utc: datetime | None = None,
    window_days: int = 30,
    projection_since_utc: datetime | None = None,
    retirement_observation: dict | None = None,
) -> dict:
    from app.services.study_phase4_preflight_service import collect_connection_safety

    if not 30 <= int(window_days) <= 365:
        raise ValueError("Retirement observation requires at least 30 days.")
    if db.session.new or db.session.dirty or db.session.deleted:
        raise ValueError("Readiness requires a transaction without pending writes.")
    try:
        with db.session.no_autoflush:
            safety = collect_connection_safety()
            return _build_phase9_readiness(now_utc=now_utc, window_days=window_days,
                                          projection_since_utc=projection_since_utc,
                                          retirement_observation=retirement_observation,
                                          connection_safety=safety)
    finally:
        db.session.rollback()


def _build_phase9_readiness(
    *, now_utc, window_days, projection_since_utc, retirement_observation, connection_safety,
) -> dict:
    """``projection_since_utc`` is the cutover instant T0 (P9-06): after it no
    ``card_progress`` row may be created or updated. Without it the cutover
    gate is ``unknown`` rather than silently zero.
    """

    now = (now_utc or datetime.utcnow()).replace(microsecond=0)
    since = now - timedelta(days=int(window_days))
    profile = db.session.get(StudyAuthorityStorageProfile, 1)
    storage_profile = profile.profile_code if profile else "PROJECTION_V1"
    switched_at = profile.switched_at if profile else None
    projection_since_utc = projection_since_utc or switched_at
    if projection_since_utc is not None and projection_since_utc > now:
        raise ValueError("Projection cutover time cannot be in the future.")

    legacy_learners = _count(
        select(func.count()).select_from(StudyAuthorityEnrollment)
        .where(StudyAuthorityEnrollment.mode_code != "NOTE")
    )
    unenrolled_users = _count(
        select(func.count()).select_from(User).where(
            ~select(StudyAuthorityEnrollment.learner_user_id)
            .where(StudyAuthorityEnrollment.learner_user_id == User.id)
            .exists()
        )
    )
    old_wire_rows = db.session.execute(
        select(StudySession.wire_schema_version, func.count(), func.max(StudySession.opened_at))
        .where(
            StudySession.opened_at >= since,
            func.coalesce(StudySession.wire_schema_version, "") != SESSION_SCHEMA_V4,
        )
        .group_by(StudySession.wire_schema_version)
    ).all()
    old_wire_open = _count(
        select(func.count()).select_from(StudySession).where(
            StudySession.status == "open",
            StudySession.expires_at > now,
            func.coalesce(StudySession.wire_schema_version, "") != SESSION_SCHEMA_V4,
        )
    )
    # Native occurrences need no Anki ordinal. Only external mappings can
    # block retirement; detached or mismatched refs cannot silently pass.
    external_cards = select(ConnectSourceCardRef.card_id).where(ConnectSourceCardRef.card_id.isnot(None))
    unbound_cards = _count(select(func.count()).select_from(Card).where(
        Card.id.in_(external_cards), Card.application_id.is_(None)))
    ordinal_less = _count(select(func.count()).select_from(ConnectSourceCardRef)
                         .join(Card, Card.id == ConnectSourceCardRef.card_id)
                         .join(StudyApplication, StudyApplication.id == Card.application_id)
                         .where(or_(StudyApplication.source_ord.is_(None),
                                    StudyApplication.source_ord != ConnectSourceCardRef.source_ord)))
    duplicates = (select(Card.note_id, StudyApplication.source_ord).join(
        StudyApplication, StudyApplication.id == Card.application_id
    ).where(Card.id.in_(external_cards), StudyApplication.source_ord.isnot(None))
                  .group_by(Card.note_id, StudyApplication.source_ord)
                  .having(func.count() > 1).subquery())
    duplicate_ordinals = _count(select(func.count()).select_from(duplicates))
    unbound_refs = _count(
        select(func.count()).select_from(ConnectSourceCardRef)
        .outerjoin(Card, Card.id == ConnectSourceCardRef.card_id)
        .where(Card.id.is_(None))
    )
    card_progress_rows = _count(select(func.count()).select_from(CardProgress))
    projection_writes_since = None
    if projection_since_utc is not None:
        projection_writes_since = _count(
            select(func.count()).select_from(CardProgress).where(or_(
                CardProgress.created_at >= projection_since_utc,
                CardProgress.updated_at >= projection_since_utc,
            ))
        )
    # Work issued under the current storage profile must drain before cutover:
    # a lease is valid until it expires, an admitted batch until it finishes.
    leases = [
        {"wire": str(wire or "<none>"), "valid": bool(valid), "sessions": int(count)}
        for wire, valid, count in db.session.execute(
            select(
                StudySession.wire_schema_version,
                StudySession.expires_at > now,
                func.count(),
            )
            .where(StudySession.status == "open")
            .group_by(StudySession.wire_schema_version, StudySession.expires_at > now)
        ).all()
    ]
    batches = {
        str(status): int(count)
        for status, count in db.session.execute(
            select(StudySessionBatch.status, func.count()).group_by(StudySessionBatch.status)
        ).all()
    }
    db.session.rollback()

    old_wire = {
        str(version or "<none>"): {"sessions": int(count), "last_opened_utc": last.isoformat() + "Z"}
        for version, count, last in old_wire_rows
    }
    # D9-02 replaced D6-02: NOTE keeps new data and repairs come from backup,
    # so the projection gate is technical, not a product decision.
    projection_blockers = []
    if storage_profile not in {"PROJECTION_V1", "CANONICAL_V1"}:
        projection_blockers.append("UNKNOWN_STORAGE_PROFILE")
    if legacy_learners:
        projection_blockers.append("LEGACY_LEARNERS")
    if unenrolled_users:
        projection_blockers.append("UNENROLLED_USERS")
    # NOTE readers/writers depend on CardProgress until this release can run
    # the projection-independent profile (P9-03..P9-05d).
    from app.repositories.study_authority_repository import SUPPORTED_STORAGE_PROFILES

    if "CANONICAL_V1" not in SUPPORTED_STORAGE_PROFILES:
        projection_blockers.append(PROJECTION_DEPENDENT_NOTE_CODE)
    gates = {
        "legacy_projection_writes": {
            "evidence": {"legacy_learners": legacy_learners, "unenrolled_users": unenrolled_users,
                         "card_progress_rows": card_progress_rows},
            "status": "waiting" if projection_blockers else "ready",
            "blocking_reasons": projection_blockers,
        },
        "old_session_wire_versions": {
            "evidence": {"sessions_in_window": old_wire, "open_sessions": old_wire_open},
            "status": "ready" if not old_wire and not old_wire_open else "waiting",
        },
        "projection_cutover": {
            "evidence": {
                "storage_profile": storage_profile,
                "since_utc": projection_since_utc.isoformat() + "Z" if projection_since_utc else None,
                "card_progress_rows_written_since": projection_writes_since,
                "evidence_scope": "surviving_rows_only",
            },
            "blocking_reasons": ["PROFILE_NOT_CANONICAL"] if storage_profile != "CANONICAL_V1" else [],
            "status": (
                "unknown" if projection_writes_since is None
                else "ready" if projection_writes_since == 0 and storage_profile == "CANONICAL_V1" else "waiting"
            ),
        },
        "work_drain": {
            "evidence": {"open_leases": leases, "batches": batches},
            "status": (
                "waiting"
                if any(row["valid"] for row in leases) or any(
                    count for status, count in batches.items() if status not in {"completed", "failed"}
                )
                else "ready"
            ),
        },
        "positional_anki_ordinals": {
            "evidence": {"cards_without_occurrence": unbound_cards,
                         "occurrences_without_ordinal": ordinal_less,
                         "duplicate_external_ordinals": duplicate_ordinals,
                         "connect_refs_without_card": unbound_refs},
            "status": "ready" if not any((unbound_cards, ordinal_less, unbound_refs, duplicate_ordinals)) else "waiting",
        },
    }
    from app.services.study_retirement_telemetry_service import retirement_usage_evidence

    for gate_name in ("old_session_wire_versions", "positional_anki_ordinals"):
        runtime = retirement_usage_evidence(retirement_observation, gate=gate_name, since=since, now=now)
        gate = gates[gate_name]
        gate["runtime_observation"] = runtime
        gate["blocking_reasons"] = list(runtime["blocking_reasons"])
        if gate["status"] == "waiting":
            gate["blocking_reasons"].append("PERSISTED_COMPATIBILITY_DEPENDENCIES")
        else:
            gate["status"] = runtime["status"]
    gates["connect_package_versions"] = {
        "status": "unknown", "blocking_reasons": ["PACKAGE_VERSION_COVERAGE_NOT_VERIFIED"],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "observed_at_utc": now.isoformat() + "Z",
        "window_days": int(window_days),
        "storage_profile": storage_profile,
        "connection_safety": connection_safety,
        "gates": gates,
        "destructive_steps_allowed": False,
        "note": "Every removal still needs a verified backup, restore proof and a separate approval.",
    }
