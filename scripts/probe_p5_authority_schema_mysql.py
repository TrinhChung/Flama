"""Exercise the inert Phase 5 schema migration in a disposable local MySQL DB.

Only a randomly named probe database is created/dropped.  The configured
application database is consulted for its default collation, not modified.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from types import SimpleNamespace

from dotenv import load_dotenv
from flask_migrate import downgrade, stamp, upgrade
import pymysql
import sqlalchemy as sa
from sqlalchemy.orm.attributes import flag_modified

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    StudyAuthorityRoute,
    lock_study_authority_compatibility,
    lock_study_authority_route,
    lock_study_authority_siblings,
    lock_study_authority_subject,
)
from app.services.study_authority_projection_encoder import (
    PRESERVE_MATCHING_STATE,
    LegacyProjectionMetadata,
    LegacySiblingBaseline,
    encode_note_state_to_legacy_cards,
)
from app.services.study_authority_cas_service import (
    StudyAuthorityCASExpectation,
    verify_study_authority_cas,
)
from app.services.study_authority_command_service import (
    ExistingStateNoteReviewCommand,
)
from app.services.study_authority_receipt_service import (
    IdempotentExistingStateNoteReviewCommand,
    apply_idempotent_existing_state_note_review,
)
from app.services.study_authority_write_service import (
    StudyAuthorityStateWrite,
    apply_study_authority_material_write,
)
from app.services.study_progress_contract import (
    ALGORITHM_KEY,
    ALGORITHM_VERSION,
    MAPPER_VERSION,
    RAW_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_codec import (
    RAW_CARD_PROGRESS_FIELDS,
    STATE_DECODERS,
    canonical_document,
    canonical_typed_document,
    serialize_raw_card_progress,
)
from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress
from app.services.study_service import (
    NativeReviewMutationInput,
    NativeReviewProvenance,
    NativeReviewTransitionInput,
    execute_native_review_transition,
)
from app.services.anki_scheduler import default_deck_options
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_state import StudyProgressState
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lineage_ref import StudyProgressLineageRef
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User
from scripts.probe_phase4_shadow_schema_mysql import (
    _connection_settings,
    _database_uri,
    _source_database_collation,
)


PROBE_NAME_PATTERN = re.compile(r"^flama_p5_authority_probe_[0-9]+_[a-f0-9]{8}$")


def _new_progress(*, user_id: int, card_id: str, created_at: datetime) -> CardProgress:
    return CardProgress(
        user_id=user_id,
        card_id=card_id,
        queue="new",
        step_index=0,
        due_at=None,
        due_day=None,
        interval_days=0,
        interval_days_raw=0.0,
        is_suspended=False,
        is_buried=False,
        buried_until_day=None,
        review_kind="review",
        scheduler_mode="legacy",
        ease_factor=2.5,
        memory_stability=None,
        memory_difficulty=None,
        suspension_reason=None,
        last_leech_at=None,
        last_leech_lapses=0,
        last_review_event_id=None,
        reps=0,
        lapses=0,
        last_reviewed_at=None,
        revision=0,
        created_at=created_at,
        updated_at=created_at,
    )


def _target_mapping(*, card_created_at: datetime, reset: bool = False) -> MappedCardProgress:
    if reset:
        values = {
            "queue": "new",
            "step_index": 0,
            "due_at": None,
            "due_day": None,
            "interval_days": 0,
            "interval_days_raw": 0.0,
            "is_suspended": False,
            "is_buried": False,
            "buried_until_day": None,
            "review_kind": "review",
            "scheduler_mode": "legacy",
            "ease_factor": 2.5,
            "memory_stability": None,
            "memory_difficulty": None,
            "suspension_reason": None,
            "last_leech_at": None,
            "last_leech_lapses": 0,
            "reps": 0,
            "lapses": 0,
            "last_reviewed_at": None,
        }
    else:
        values = {
            "queue": "review",
            "step_index": 2,
            "due_at": datetime(2026, 9, 30, 4, 5, 6),
            "due_day": 20726,
            "interval_days": 13,
            "interval_days_raw": 12.75,
            "is_suspended": True,
            "is_buried": True,
            "buried_until_day": 20727,
            "review_kind": "manual",
            "scheduler_mode": "fsrs",
            "ease_factor": 2.5,
            "memory_stability": 10.5,
            "memory_difficulty": 4.25,
            "suspension_reason": "leech",
            "last_leech_at": datetime(2026, 9, 21, 3, 4, 5),
            "last_leech_lapses": 3,
            "reps": 14,
            "lapses": 3,
            "last_reviewed_at": datetime(2026, 9, 21, 2, 3, 4),
        }
    progress = SimpleNamespace(
        id=999999,
        user_id=1,
        card_id="p5-probe-state-only",
        last_review_event_id=None,
        revision=1,
        created_at=card_created_at,
        updated_at=card_created_at,
        **values,
    )
    mapped = map_card_progress(progress, card_created_at=card_created_at)
    if not isinstance(mapped, MappedCardProgress):
        raise AssertionError(f"Probe target state is not mappable: {mapped.code}")
    return mapped


def _baseline(
    *,
    progress: CardProgress,
    card: Card,
    disposition_code: str = "APPLY_NOTE_STATE",
) -> LegacySiblingBaseline:
    raw = serialize_raw_card_progress(progress)
    return LegacySiblingBaseline(
        card_id=str(card.id),
        expected_base_revision=int(progress.revision),
        card_created_at=card.created_at,
        raw_payload=raw.payload,
        raw_payload_size=raw.size,
        raw_payload_hash=raw.digest,
        projected_last_review_event_id=progress.last_review_event_id,
        disposition_code=disposition_code,
    )


def _encode_projection(
    *,
    user_id: int,
    target: MappedCardProgress,
    metadata: LegacyProjectionMetadata,
    baselines: tuple[LegacySiblingBaseline, ...],
):
    return encode_note_state_to_legacy_cards(
        expected_learner_user_id=user_id,
        algorithm_key=ALGORITHM_KEY,
        algorithm_version=ALGORITHM_VERSION,
        state_schema_version=STATE_SCHEMA_VERSION,
        storage_codec=STORAGE_CODEC,
        state_payload=target.state.payload,
        expected_state_payload_size=target.state.size,
        expected_algorithm_state_hash=target.algorithm_state_hash,
        metadata=metadata,
        siblings=baselines,
    )


def _apply_projection(row: CardProgress, projected: object) -> None:
    values = projected.progress.as_dict()
    immutable = {"id", "user_id", "card_id", "created_at"}
    for field_name in RAW_CARD_PROGRESS_FIELDS:
        if field_name in immutable:
            if getattr(row, field_name) != values[field_name]:
                raise AssertionError(f"Projection changed immutable {field_name}.")
            continue
        setattr(row, field_name, values[field_name])
        if field_name == "updated_at":
            # A newly flushed shell can already carry the projection timestamp.
            # Mark it explicit so SQLAlchemy's onupdate clock cannot replace the
            # encoder's exact compatibility value when another column changes.
            flag_modified(row, field_name)


def _assert_persisted_projection(expected: object) -> None:
    db.session.expire_all()
    for sibling in expected.siblings:
        row = CardProgress.query.filter_by(card_id=sibling.card_id).one()
        actual = serialize_raw_card_progress(row)
        if actual.digest != sibling.raw.digest:
            differing_fields = sorted(
                field_name
                for field_name in RAW_CARD_PROGRESS_FIELDS
                if actual.payload[field_name] != sibling.raw.payload[field_name]
            )
            raise AssertionError(
                f"MySQL round-trip changed projected Card {sibling.card_id}: "
                f"{differing_fields!r}."
            )


def _probe_projection_round_trip(user: User) -> dict[str, object]:
    """Persist 1:N exact vectors and prove rollback/new-sibling/reset behavior."""

    user_id = int(user.id)
    created_at = datetime(2026, 9, 20, 1, 2, 3)
    projected_at = datetime(2026, 9, 21, 3, 4, 5)
    note_type = NoteType(
        id="p5-probe-note-type", user_id=user_id, name="P5 projection probe"
    )
    template_a = Template(
        id="p5-probe-template-a",
        note_type=note_type,
        name="A",
        position=0,
    )
    template_b = Template(
        id="p5-probe-template-b",
        note_type=note_type,
        name="B",
        position=1,
    )
    deck = Deck(
        owner_user_id=user_id,
        note_type=note_type,
        name="P5 projection probe",
        created_at=created_at,
        updated_at=created_at,
    )
    note = Note(
        id="p5-probe-note",
        note_type=note_type,
        user_id=user_id,
        deck_id=None,
        field_values={"Front": "probe"},
        tags=[],
        created_at=created_at,
        updated_at=created_at,
    )
    card_a = Card(
        id="p5-probe-card-a",
        note=note,
        template=template_a,
        created_at=created_at,
        updated_at=created_at,
    )
    card_b = Card(
        id="p5-probe-card-b",
        note=note,
        template=template_b,
        created_at=created_at,
        updated_at=created_at,
    )
    progress_a = _new_progress(
        user_id=user_id, card_id=card_a.id, created_at=created_at
    )
    progress_b = _new_progress(
        user_id=user_id, card_id=card_b.id, created_at=created_at
    )
    db.session.add_all(
        [note_type, template_a, template_b, deck, note, card_a, card_b]
    )
    db.session.flush()
    note.deck_id = deck.id
    db.session.add_all([progress_a, progress_b])
    db.session.commit()

    with db.engine.connect() as connection:
        float_types = dict(
            connection.execute(
                sa.text(
                    "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='card_progress' "
                    "AND COLUMN_NAME IN ('interval_days_raw', 'ease_factor', "
                    "'memory_stability', 'memory_difficulty')"
                )
            ).all()
        )
        datetime_precision = dict(
            connection.execute(
                sa.text(
                    "SELECT COLUMN_NAME, DATETIME_PRECISION "
                    "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME='card_progress' AND COLUMN_NAME IN "
                    "('due_at', 'last_leech_at', 'last_reviewed_at', 'updated_at')"
                )
            ).all()
        )
    if set(float_types.values()) != {"float"}:
        raise AssertionError(f"Unexpected legacy float types: {float_types!r}")
    if set(datetime_precision.values()) != {0}:
        raise AssertionError(
            f"Unexpected legacy datetime precision: {datetime_precision!r}"
        )

    target = _target_mapping(card_created_at=created_at)
    metadata = LegacyProjectionMetadata(
        interval_days_rounded=13,
        is_buried=True,
        buried_until_day=20727,
        last_leech_at=projected_at,
        last_leech_lapses=3,
        projected_at=projected_at,
    )
    baseline_raw = {
        row.card_id: serialize_raw_card_progress(row).digest
        for row in (progress_a, progress_b)
    }
    proposed = _encode_projection(
        user_id=user_id,
        target=target,
        metadata=metadata,
        baselines=(
            _baseline(progress=progress_a, card=card_a),
            _baseline(progress=progress_b, card=card_b),
        ),
    )

    # A failure after the first sibling must leave neither row advanced.
    _apply_projection(progress_a, proposed.siblings[0])
    db.session.flush()
    db.session.rollback()
    db.session.expire_all()
    for card_id, digest in baseline_raw.items():
        row = CardProgress.query.filter_by(card_id=card_id).one()
        if serialize_raw_card_progress(row).digest != digest:
            raise AssertionError("Fault rollback left a partial Card projection.")

    progress_by_card = {
        row.card_id: row
        for row in CardProgress.query.filter(
            CardProgress.card_id.in_((card_a.id, card_b.id))
        ).all()
    }
    for sibling in proposed.siblings:
        _apply_projection(progress_by_card[sibling.card_id], sibling)
    db.session.commit()
    _assert_persisted_projection(proposed)

    # Lifecycle add: preserve matching siblings byte-for-byte and materialize
    # only the newly allocated compatibility row from the Note state.
    template_c = Template(
        id="p5-probe-template-c",
        note_type=note_type,
        name="C",
        position=2,
    )
    card_c = Card(
        id="p5-probe-card-c",
        note=note,
        template=template_c,
        created_at=projected_at,
        updated_at=projected_at,
    )
    progress_c = _new_progress(
        user_id=user_id, card_id=card_c.id, created_at=projected_at
    )
    db.session.add_all([template_c, card_c])
    db.session.flush()
    db.session.add(progress_c)
    db.session.flush()
    progress_a = CardProgress.query.filter_by(card_id=card_a.id).one()
    progress_b = CardProgress.query.filter_by(card_id=card_b.id).one()
    lifecycle = _encode_projection(
        user_id=user_id,
        target=target,
        metadata=metadata,
        baselines=(
            _baseline(
                progress=progress_a,
                card=card_a,
                disposition_code=PRESERVE_MATCHING_STATE,
            ),
            _baseline(
                progress=progress_b,
                card=card_b,
                disposition_code=PRESERVE_MATCHING_STATE,
            ),
            _baseline(progress=progress_c, card=card_c),
        ),
    )
    _apply_projection(progress_c, lifecycle.siblings[2])
    db.session.commit()
    _assert_persisted_projection(lifecycle)

    db.session.delete(card_c)
    db.session.commit()
    if CardProgress.query.filter_by(card_id=card_c.id).count() != 0:
        raise AssertionError("Deleted sibling left a compatibility progress row.")

    # Reset is another all-sibling material transition and must remain exact.
    progress_a = CardProgress.query.filter_by(card_id=card_a.id).one()
    progress_b = CardProgress.query.filter_by(card_id=card_b.id).one()
    reset_target = _target_mapping(card_created_at=created_at, reset=True)
    reset_metadata = LegacyProjectionMetadata(
        interval_days_rounded=0,
        is_buried=False,
        buried_until_day=None,
        last_leech_at=None,
        last_leech_lapses=0,
        projected_at=datetime(2026, 9, 22, 1, 2, 3),
    )
    reset = _encode_projection(
        user_id=user_id,
        target=reset_target,
        metadata=reset_metadata,
        baselines=(
            _baseline(progress=progress_a, card=card_a),
            _baseline(progress=progress_b, card=card_b),
        ),
    )
    for sibling, row in zip(reset.siblings, (progress_a, progress_b), strict=True):
        _apply_projection(row, sibling)
    db.session.commit()
    _assert_persisted_projection(reset)

    # Initialize and verify the independent authority CAS token without
    # changing learner routing. Enrollment is exercised separately.
    subject = StudyProgressSubject(
        learner_user_id=user_id,
        logical_note_key=str(note.id).encode("utf-8"),
        live_note_id=note.id,
        subject_generation=1,
        mirror_revision=1,
        status_code="MIRRORED_EQUIVALENT_FANIN",
        contributor_count=2,
        created_at=created_at,
        updated_at=projected_at,
    )
    db.session.add(subject)
    db.session.flush()
    reset_rows = (progress_a, progress_b)
    reset_cards = (card_a, card_b)
    mapped_reset = []
    absent_lineage_hash = canonical_typed_document(
        {
            "references": [
                {
                    "ref_kind": "LAST_REVIEW_EVENT",
                    "source_row_key": None,
                    "ref_status": "ABSENT",
                }
            ]
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest
    probe_contributors = []
    for progress, card in zip(reset_rows, reset_cards, strict=True):
        mapped = map_card_progress(progress, card_created_at=card.created_at)
        if not isinstance(mapped, MappedCardProgress):
            raise AssertionError("Reset projection cannot seed compatibility evidence.")
        mapped_reset.append(mapped)
        contributor = StudyProgressContributor(
            subject_id=int(subject.id),
            subject_generation=1,
            source_progress_id=int(progress.id),
            live_card_progress_id=int(progress.id),
            logical_card_key=str(card.id).encode("utf-8"),
            live_card_id=str(card.id),
            card_progress_revision=int(progress.revision),
            raw_schema_version=RAW_SCHEMA_VERSION,
            storage_codec=STORAGE_CODEC,
            raw_payload=mapped.raw.payload,
            raw_payload_size=mapped.raw.size,
            raw_progress_hash=mapped.raw.digest,
            pointer_status="ABSENT",
            history_completeness_code="HISTORY_NATIVE_COMPLETE",
            current_provenance_code="UNKNOWN_LEGACY",
            lineage_vector_hash=absent_lineage_hash,
            contributor_status="ACTIVE",
            created_at=created_at,
            updated_at=projected_at,
        )
        db.session.add(contributor)
        probe_contributors.append(contributor)
    db.session.flush()
    for mapped, contributor in zip(mapped_reset, probe_contributors, strict=True):
        availability = mapped.availability
        db.session.add(
            StudyProgressAvailability(
                contributor_id=int(contributor.id),
                subject_id=int(subject.id),
                subject_generation=1,
                projection_version=availability.projection_version,
                normalized_queue=availability.normalized_queue,
                due_at=availability.due_at,
                due_day=availability.due_day,
                is_suspended=availability.is_suspended,
                is_buried=availability.is_buried,
                buried_until_day=availability.buried_until_day,
                card_created_at=availability.card_created_at,
                card_order_key=availability.card_order_key,
                state_schema_version=availability.state_schema_version,
                semantic_state_hash=availability.semantic_state_hash,
                created_at=created_at,
                updated_at=projected_at,
            )
        )
    subject.authority_vector_hash = canonical_document(
        {
            "contributors": [
                {
                    "card_id": str(progress.card_id),
                    "progress_id": str(progress.id),
                    "raw_progress_hash": mapped.raw.digest.hex(),
                    "revision": str(progress.revision),
                }
                for progress, mapped in zip(reset_rows, mapped_reset, strict=True)
            ]
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest
    subject.lineage_vector_hash = canonical_document(
        {
            "contributors": [
                {
                    "card_id": str(progress.card_id),
                    "lineage_vector_hash": absent_lineage_hash.hex(),
                    "progress_id": str(progress.id),
                }
                for progress in reset_rows
            ]
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest
    subject.mapper_version = MAPPER_VERSION
    subject.last_mirrored_at = projected_at
    db.session.add(
        StudyProgressState(
            subject_id=subject.id,
            subject_generation=1,
            mirror_revision=1,
            algorithm_key=reset_target.algorithm_key,
            algorithm_version=reset_target.algorithm_version,
            state_schema_version=reset_target.state_schema_version,
            storage_codec=reset_target.storage_codec,
            state_payload=reset_target.state.payload,
            state_payload_size=reset_target.state.size,
            algorithm_state_hash=reset_target.algorithm_state_hash,
            semantic_state_hash=reset_target.semantic_state_hash,
            created_at=created_at,
            updated_at=projected_at,
        )
    )
    db.session.commit()
    subject = db.session.execute(
        sa.select(StudyProgressSubject)
        .where(StudyProgressSubject.id == subject.id)
        .with_for_update()
    ).scalar_one()
    cas_route = StudyAuthorityRoute(
        learner_user_id=user_id,
        mode_code="LEGACY",
        epoch=0,
        persisted=False,
    )
    locked_cas = lock_study_authority_subject(
        db.session,
        route=cas_route,
        subject=subject,
        now_utc=projected_at,
    )
    verified_cas = verify_study_authority_cas(
        route=cas_route,
        locked=locked_cas,
        expected=StudyAuthorityCASExpectation(
            enrollment_epoch=0,
            subject_generation=1,
            authority_revision=0,
            semantic_state_hash=reset_target.semantic_state_hash,
        ),
        require_note_authority=False,
    )
    if not verified_cas.has_current_state or not locked_cas.token_created:
        raise AssertionError("MySQL CAS token did not initialize from current state.")
    cas_subject_id = int(subject.id)
    db.session.commit()

    holder = db.engine.raw_connection()
    waiter = db.engine.raw_connection()
    try:
        with holder.cursor() as cursor:
            cursor.execute("START TRANSACTION")
            cursor.execute(
                "SELECT authority_revision FROM study_authority_subject_tokens "
                "WHERE subject_id=%s FOR UPDATE",
                (cas_subject_id,),
            )
            if cursor.fetchone() != (0,):
                raise AssertionError("CAS holder did not lock revision zero.")
        with waiter.cursor() as cursor:
            cursor.execute("SET SESSION innodb_lock_wait_timeout=1")
            cursor.execute("START TRANSACTION")
            try:
                cursor.execute(
                    "SELECT authority_revision "
                    "FROM study_authority_subject_tokens "
                    "WHERE subject_id=%s FOR UPDATE",
                    (cas_subject_id,),
                )
            except pymysql.err.OperationalError as exc:
                if not exc.args or exc.args[0] != 1205:
                    raise
            else:
                raise AssertionError("Concurrent CAS bypassed the locked token row.")
        waiter.rollback()
        holder.rollback()
    finally:
        waiter.rollback()
        holder.rollback()
        waiter.close()
        holder.close()

    # Exercise the no-commit NOTE material-write applicator against real
    # InnoDB rows. This uses a synthetic NOTE route only inside the disposable
    # probe; migration 40 still rejects persisted NOTE enrollment.
    authority_written_at = datetime(2026, 9, 23, 1, 2, 3)
    note_route = StudyAuthorityRoute(
        learner_user_id=user_id,
        mode_code="NOTE",
        epoch=0,
        persisted=False,
    )

    def prepare_authority_write():
        locked_subject = db.session.execute(
            sa.select(StudyProgressSubject)
            .where(StudyProgressSubject.id == cas_subject_id)
            .with_for_update()
        ).scalar_one()
        locked_authority = lock_study_authority_subject(
            db.session,
            route=note_route,
            subject=locked_subject,
            now_utc=authority_written_at,
        )
        locked_siblings = lock_study_authority_siblings(
            db.session,
            route=note_route,
            locked=locked_authority,
            requested_card_id=str(card_a.id),
        )
        locked_compatibility = lock_study_authority_compatibility(
            db.session,
            route=note_route,
            locked=locked_authority,
            siblings=locked_siblings,
        )
        rows_by_card = dict(locked_siblings.progress_by_card_id)
        encoded = _encode_projection(
            user_id=user_id,
            target=target,
            metadata=LegacyProjectionMetadata(
                interval_days_rounded=13,
                is_buried=True,
                buried_until_day=20727,
                last_leech_at=projected_at,
                last_leech_lapses=3,
                projected_at=authority_written_at,
            ),
            baselines=tuple(
                _baseline(
                    progress=rows_by_card[str(card.id)],
                    card=card,
                )
                for card in (card_a, card_b)
            ),
        )
        return locked_authority, locked_siblings, locked_compatibility, encoded

    (
        locked_authority,
        authority_siblings,
        _authority_compatibility,
        authority_projection,
    ) = prepare_authority_write()
    sibling_inserter = db.engine.raw_connection()
    try:
        with sibling_inserter.cursor() as cursor:
            cursor.execute("SET SESSION innodb_lock_wait_timeout=1")
            cursor.execute("START TRANSACTION")
            try:
                cursor.execute(
                    "INSERT INTO cards "
                    "(id, note_id, template_id, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        "p5-probe-card-concurrent",
                        str(note.id),
                        str(template_c.id),
                        authority_written_at,
                        authority_written_at,
                    ),
                )
            except pymysql.err.OperationalError as exc:
                if not exc.args or exc.args[0] != 1205:
                    raise
            else:
                raise AssertionError(
                    "Concurrent sibling insert bypassed the locked Card set."
                )
        sibling_inserter.rollback()
    finally:
        sibling_inserter.rollback()
        sibling_inserter.close()
    prewrite_raw_hashes = {
        card_id: serialize_raw_card_progress(row).digest
        for card_id, row in authority_siblings.progress_by_card_id.items()
    }
    authority_state_write = StudyAuthorityStateWrite(
        algorithm_key=target.algorithm_key,
        algorithm_version=target.algorithm_version,
        state_schema_version=target.state_schema_version,
        storage_codec=target.storage_codec,
        state_payload=target.state.payload,
        state_payload_size=target.state.size,
        algorithm_state_hash=target.algorithm_state_hash,
    )
    authority_expected = StudyAuthorityCASExpectation(
        enrollment_epoch=0,
        subject_generation=1,
        authority_revision=0,
        semantic_state_hash=reset_target.semantic_state_hash,
    )
    apply_study_authority_material_write(
        db.session,
        route=note_route,
        locked=locked_authority,
        expected=authority_expected,
        next_state=authority_state_write,
        siblings=authority_siblings,
        projection=authority_projection,
        now_utc=authority_written_at,
    )
    db.session.flush()
    db.session.rollback()
    db.session.expire_all()
    rolled_back_token = db.session.get(StudyAuthoritySubjectToken, cas_subject_id)
    rolled_back_state = db.session.get(StudyProgressState, cas_subject_id)
    if (
        rolled_back_token is None
        or int(rolled_back_token.authority_revision) != 0
        or bytes(rolled_back_token.semantic_state_hash)
        != reset_target.semantic_state_hash
        or rolled_back_state is None
        or bytes(rolled_back_state.semantic_state_hash)
        != reset_target.semantic_state_hash
    ):
        raise AssertionError("Material-write rollback changed state or CAS token.")
    for card_id, expected_hash in prewrite_raw_hashes.items():
        row = CardProgress.query.filter_by(card_id=card_id).one()
        if serialize_raw_card_progress(row).digest != expected_hash:
            raise AssertionError("Material-write rollback left a partial sibling.")
    db.session.rollback()

    (
        locked_authority,
        authority_siblings,
        authority_compatibility,
        _authority_projection_without_event,
    ) = prepare_authority_write()
    current_state_row = locked_authority.state
    if current_state_row is None:
        raise AssertionError("Existing-state command probe has no current state.")
    current_state = STATE_DECODERS.decode(
        algorithm_key=str(current_state_row.algorithm_key),
        algorithm_version=str(current_state_row.algorithm_version),
        state_schema_version=str(current_state_row.state_schema_version),
        storage_codec=str(current_state_row.storage_codec),
        payload=current_state_row.state_payload,
        expected_size=int(current_state_row.state_payload_size),
        expected_hash=bytes(current_state_row.algorithm_state_hash),
    )
    deck_options = default_deck_options()
    transition = execute_native_review_transition(
        NativeReviewTransitionInput(
            state=current_state,
            deck_options=deck_options,
            reviewed_at=authority_written_at,
            action="good",
            timezone_name="UTC",
        )
    )
    reviewed_card = next(
        card
        for card in authority_siblings.cards
        if str(card.id) == str(card_a.id)
    )
    authority_command = ExistingStateNoteReviewCommand(
        route=note_route,
        locked=locked_authority,
        expected=authority_expected,
        siblings=authority_siblings,
        compatibility=authority_compatibility,
        review=NativeReviewMutationInput(
            user_id=user_id,
            card=reviewed_card,
            current_state=current_state,
            transition=transition,
            reviewed_at=authority_written_at,
            duration_ms=321,
            payload=None,
            local_deck_id=int(deck.id),
            scheduler_preset_id=None,
            scheduler_config_hash="66" * 32,
            timezone_name="UTC",
            deck_options=deck_options,
            review_mode="deck",
            provenance=NativeReviewProvenance(
                source_path="native.rest",
                request_id="p5-mysql-authority-command",
            ),
        ),
        now_utc=authority_written_at,
    )
    authority_outcome = apply_idempotent_existing_state_note_review(
        db.session,
        command=IdempotentExistingStateNoteReviewCommand(
            operation_key="p5-mysql-authority-command",
            command=authority_command,
        ),
    )
    authority_result = authority_outcome.applied
    if (
        authority_outcome.replayed
        or authority_result is None
        or authority_result.write.authority_revision != 1
        or authority_result.evidence.mirror_revision != 2
        or not authority_result.history.inserted
    ):
        raise AssertionError("Authority command did not finalize exactly once.")
    receipt_id = int(authority_outcome.receipt.id)
    stored_response = dict(authority_outcome.response_payload)
    db.session.commit()
    _assert_persisted_projection(authority_result.projection)
    persisted_token = db.session.get(StudyAuthoritySubjectToken, cas_subject_id)
    persisted_state = db.session.get(StudyProgressState, cas_subject_id)
    if (
        persisted_token is None
        or int(persisted_token.authority_revision) != 1
        or bytes(persisted_token.semantic_state_hash)
        != authority_result.write.semantic_state_hash
        or persisted_state is None
        or bytes(persisted_state.semantic_state_hash)
        != authority_result.write.semantic_state_hash
        or int(persisted_state.mirror_revision) != 2
    ):
        raise AssertionError("Committed material write left state/token divergence.")
    if (
        StudyProgressHistoryFact.query.filter_by(
            review_event_id=int(authority_result.review_event.id)
        ).count()
        != 1
        or StudyProgressLineageRef.query.filter_by(
            contributor_id=int(
                authority_result.evidence.contributor_by_card_id[str(card_a.id)].id
            )
        ).count()
        != 1
    ):
        raise AssertionError("Committed authority write lost history or lineage evidence.")

    before_replay_counts = (
        ReviewEvent.query.count(),
        StudyProgressHistoryFact.query.count(),
        StudyAuthorityCommandReceipt.query.count(),
    )
    (
        replay_locked,
        replay_siblings,
        replay_compatibility,
        _unused_replay_projection,
    ) = prepare_authority_write()
    replay_card = next(
        card
        for card in replay_siblings.cards
        if str(card.id) == str(card_a.id)
    )
    replay_command = replace(
        authority_command,
        locked=replay_locked,
        siblings=replay_siblings,
        compatibility=replay_compatibility,
        review=replace(authority_command.review, card=replay_card),
    )
    replay_outcome = apply_idempotent_existing_state_note_review(
        db.session,
        command=IdempotentExistingStateNoteReviewCommand(
            operation_key="p5-mysql-authority-command",
            command=replay_command,
        ),
    )
    if (
        not replay_outcome.replayed
        or replay_outcome.applied is not None
        or int(replay_outcome.receipt.id) != receipt_id
        or dict(replay_outcome.response_payload) != stored_response
    ):
        raise AssertionError("Exact authority command retry did not replay its receipt.")
    after_replay_counts = (
        ReviewEvent.query.count(),
        StudyProgressHistoryFact.query.count(),
        StudyAuthorityCommandReceipt.query.count(),
    )
    if after_replay_counts != before_replay_counts:
        raise AssertionError("Authority receipt replay created duplicate evidence.")
    db.session.rollback()
    return {
        "legacy_float32_guard": "PASS",
        "legacy_datetime0_guard": "PASS",
        "projection_1_to_n_round_trip": "PASS",
        "projection_fault_rollback": "PASS",
        "projection_new_sibling_materialization": "PASS",
        "projection_deleted_sibling_cascade": "PASS",
        "projection_reset_round_trip": "PASS",
        "subject_cas_first_create": "PASS",
        "subject_cas_two_connection_lock": "PASS",
        "subject_sibling_insert_fence": "PASS",
        "subject_material_write_rollback": "PASS",
        "subject_material_write_commit": "PASS",
        "subject_compatibility_evidence_commit": "PASS",
        "subject_history_fact_commit": "PASS",
        "subject_canonical_command_commit": "PASS",
        "subject_command_receipt_commit": "PASS",
        "subject_command_receipt_replay": "PASS",
    }


def _probe_absent_enrollment_lock(settings: dict[str, object], database_name: str, user_id: int) -> None:
    """Verify a stable User row fences a switch even when enrollment is absent.

    This is a local two-connection InnoDB probe, not an enrollment implementation.
    The migration deliberately disallows NOTE rows, so the exclusive holder only
    inserts a LEGACY epoch marker after the shared holder releases its lock.
    """

    connection_options = {**settings, "database": database_name, "autocommit": False}
    writer = pymysql.connect(**connection_options)
    switcher = pymysql.connect(**connection_options)
    try:
        with writer.cursor() as cursor:
            cursor.execute("START TRANSACTION")
            cursor.execute("SELECT id FROM users WHERE id=%s FOR SHARE", (user_id,))
            if cursor.fetchone() != (user_id,):
                raise AssertionError("Shared learner fence did not find the User row.")

        # Shared readers can coexist; an exclusive mode switch must wait until
        # all progress writers holding the learner fence have committed.
        with switcher.cursor() as cursor:
            cursor.execute("START TRANSACTION")
            cursor.execute("SELECT id FROM users WHERE id=%s FOR SHARE", (user_id,))
            if cursor.fetchone() != (user_id,):
                raise AssertionError("Second shared learner fence failed.")
        switcher.rollback()

        with switcher.cursor() as cursor:
            cursor.execute("SET SESSION innodb_lock_wait_timeout=1")
            cursor.execute("START TRANSACTION")
            try:
                cursor.execute("SELECT id FROM users WHERE id=%s FOR UPDATE", (user_id,))
            except pymysql.err.OperationalError as exc:
                if not exc.args or exc.args[0] != 1205:
                    raise
            else:
                raise AssertionError("Exclusive switch bypassed an active writer fence.")
        switcher.rollback()
        writer.commit()

        with switcher.cursor() as cursor:
            cursor.execute("START TRANSACTION")
            cursor.execute("SELECT id FROM users WHERE id=%s FOR UPDATE", (user_id,))
            if cursor.fetchone() != (user_id,):
                raise AssertionError("Exclusive learner fence did not find the User row.")
            cursor.execute(
                "SELECT mode_code, epoch FROM study_authority_enrollments "
                "WHERE learner_user_id=%s FOR SHARE",
                (user_id,),
            )
            if cursor.fetchone() is not None:
                raise AssertionError("Expected an absent enrollment before the first switch.")
            cursor.execute(
                "INSERT INTO study_authority_enrollments "
                "(learner_user_id, mode_code, epoch, created_at, updated_at) "
                "VALUES (%s, 'LEGACY', 1, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6))",
                (user_id,),
            )
        switcher.commit()

        with writer.cursor() as cursor:
            cursor.execute("START TRANSACTION")
            cursor.execute("SELECT id FROM users WHERE id=%s FOR SHARE", (user_id,))
            cursor.execute(
                "SELECT mode_code, epoch FROM study_authority_enrollments "
                "WHERE learner_user_id=%s FOR SHARE",
                (user_id,),
            )
            if cursor.fetchone() != ("LEGACY", 1):
                raise AssertionError("Writer did not observe the new enrollment epoch.")
        writer.rollback()
    finally:
        writer.rollback()
        switcher.rollback()
        writer.close()
        switcher.close()


def run_probe() -> dict[str, object]:
    load_dotenv()
    settings = _connection_settings()
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("P5 schema probe requires local MySQL; refusing remote DB_HOST.")
    database_name = f"flama_p5_authority_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if not PROBE_NAME_PATTERN.fullmatch(database_name):
        raise RuntimeError("Refusing unsafe disposable database name.")

    admin = pymysql.connect(**settings)
    created = False
    app = None
    try:
        source_collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 "
                f"COLLATE {source_collation}"
            )
        created = True

        app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": _database_uri(settings, database_name),
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_RUN_DB_CREATE_ALL": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )
        foundation_migration = importlib.import_module(
            "migrations.versions.20260921_000040_add_study_authority_fence"
        )
        receipt_migration = importlib.import_module(
            "migrations.versions.20260921_000041_add_study_authority_command_receipts"
        )
        session_pin_migration = importlib.import_module(
            "migrations.versions.20260921_000042_add_study_session_authority_pins"
        )
        migrations = (
            foundation_migration,
            receipt_migration,
            session_pin_migration,
        )
        with app.app_context():
            # The original baseline predates Alembic.  Reproduce head 39
            # using metadata while excluding the additive P5 tables.
            target_names = {
                table.name
                for migration in migrations
                for table in migration.TARGET_TABLES
            }
            baseline_tables = [
                table for table in db.metadata.sorted_tables if table.name not in target_names
            ]
            db.metadata.create_all(bind=db.engine, tables=baseline_tables)
            stamp(revision="20260913_000039", directory="migrations")
            upgrade(directory="migrations")

            inspector = sa.inspect(db.engine)
            with db.engine.connect() as connection:
                for table in (
                    StudyAuthorityEnrollment.__table__,
                    StudyAuthoritySubjectToken.__table__,
                    StudyAuthorityCommandReceipt.__table__,
                    session_pin_migration.TARGET_TABLES[0],
                ):
                    if not inspector.has_table(table.name):
                        raise AssertionError(f"Missing migrated table: {table.name}")
                    foundation_migration._assert_table_contract(connection, table)

            boot_env = dict(os.environ)
            boot_env.update(
                {
                    "SQLALCHEMY_DATABASE_URI": _database_uri(settings, database_name),
                    "STARTUP_RUN_MAINTENANCE": "0",
                    "STARTUP_RUN_DB_CREATE_ALL": "0",
                    "STARTUP_RUN_USER_MANAGEMENT_SCHEMA": "0",
                    "STARTUP_RUN_BACKWARD_COMPAT_SCHEMA": "0",
                    "STARTUP_RUN_DEFAULT_USER_ROLE_SEED": "0",
                    "STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED": "0",
                    "STARTUP_RUN_CLONE_CUTOVER": "0",
                }
            )
            boot = subprocess.run(
                [sys.executable, "-c", "import wsgi; assert wsgi.app is not None"],
                cwd=ROOT_DIR,
                env=boot_env,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if boot.returncode:
                raise AssertionError(
                    "Flags-off wsgi.py boot failed in disposable MySQL "
                    f"(exit={boot.returncode}, stderr_bytes={len(boot.stderr.encode('utf-8'))})."
                )

            user = User(email="p5-probe@example.test", username="p5-probe")
            db.session.add(user)
            db.session.commit()
            now = datetime(2026, 9, 21)
            db.session.add(
                StudyAuthorityEnrollment(
                    learner_user_id=user.id,
                    mode_code="NOTE",
                    epoch=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            db.session.commit()
            try:
                lock_study_authority_route(
                    db.session,
                    learner_user_id=int(user.id),
                )
            except StudyAuthorityFenceError as exc:
                if exc.code != "NOTE_AUTHORITY_UNAVAILABLE":
                    raise
                db.session.rollback()
            else:
                raise AssertionError("Default authority routing served NOTE.")
            note_route = lock_study_authority_route(
                db.session,
                learner_user_id=int(user.id),
                allow_note_authority=True,
            )
            if note_route.mode_code != "NOTE" or note_route.epoch != 1:
                raise AssertionError("Opt-in authority routing did not serve NOTE.")
            db.session.rollback()
            db.session.delete(
                db.session.get(StudyAuthorityEnrollment, int(user.id))
            )
            db.session.commit()
            db.session.rollback()
            projection_evidence = _probe_projection_round_trip(user)
            _probe_absent_enrollment_lock(settings, database_name, user.id)
            route = lock_study_authority_route(
                db.session,
                learner_user_id=int(user.id),
            )
            if (
                route.mode_code != "LEGACY"
                or route.epoch != 1
                or not route.persisted
            ):
                raise AssertionError("Repository did not observe the fenced LEGACY route.")
            db.session.rollback()
            db.session.delete(user)
            db.session.commit()

            downgrade(revision="20260913_000039", directory="migrations")
            if any(sa.inspect(db.engine).has_table(name) for name in target_names):
                raise AssertionError("Empty-only downgrade left authority tables.")
            upgrade(directory="migrations")
            head = db.session.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
            if head != "20260921_000043":
                raise AssertionError(f"Unexpected migration head: {head}")
            return {
                "status": "PASS",
                "mysql_version": db.session.execute(sa.text("SELECT VERSION()")).scalar_one(),
                "collation": source_collation,
                "migration_head": head,
                "note_enrollment_constraint": "PASS",
                "two_connection_absent_enrollment_fence": "PASS",
                "legacy_route_repository_fence": "PASS",
                "flags_off_wsgi_boot": "PASS",
                "empty_downgrade_reupgrade": "PASS",
                "configured_database_modified": False,
                **projection_evidence,
            }
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            # The exact target was generated above and validated by regex.
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{database_name}`")
        admin.close()


if __name__ == "__main__":
    print(json.dumps(run_probe(), sort_keys=True))
