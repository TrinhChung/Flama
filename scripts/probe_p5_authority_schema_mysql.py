"""Exercise the inert Phase 5 schema migration in a disposable local MySQL DB.

Only a randomly named probe database is created/dropped.  The configured
application database is consulted for its default collation, not modified.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

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
from app.services.study_authority_enrollment_service import (
    StudyAuthorityEnrollmentError,
    stage_legacy_authority_enrollment,
    stage_note_authority_enrollment,
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
from app.services import (
    deck_management_service,
    flashcard_content_service,
    flashcards_share_service,
    study_progress_lifecycle_mirror_service,
)
from app.services.share.helpers import ShareControllerError
from app.services.share.cutover import cutover_clone_model_to_overlay_only
from app.services.anki_sync_service import import_progress, import_reviews
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
from models.connect_import_session import ConnectImportSession
from models.connect_review_event_ref import ConnectReviewEventRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.note_type import NoteType
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_state import StudyProgressState
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
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


def _probe_pristine_enrollment() -> dict[str, str]:
    """Prove pristine multi-sibling materialization and empty-history rollback."""

    created_at = datetime(2026, 9, 22, 1, 0, 0)
    user = User(
        email="p5-pristine-enrollment@example.test",
        username="p5-pristine-enrollment",
    )
    db.session.add(user)
    db.session.flush()
    user_id = int(user.id)
    note_type = NoteType(
        id="p5-pristine-note-type",
        user_id=user_id,
        name="P5 pristine enrollment probe",
    )
    template_a = Template(
        id="p5-pristine-template-a",
        note_type=note_type,
        name="A",
        position=0,
    )
    template_b = Template(
        id="p5-pristine-template-b",
        note_type=note_type,
        name="B",
        position=1,
    )
    deck = Deck(
        owner_user_id=user_id,
        note_type=note_type,
        name="P5 pristine enrollment probe",
        created_at=created_at,
        updated_at=created_at,
    )
    db.session.add_all([note_type, template_a, template_b, deck])
    db.session.flush()
    note = Note(
        id="p5-pristine-note",
        note_type=note_type,
        user_id=user_id,
        deck_id=int(deck.id),
        field_values={"Front": "pristine"},
        tags=[],
        created_at=created_at,
        updated_at=created_at,
    )
    cards = (
        Card(
            id="p5-pristine-card-a",
            note=note,
            template=template_a,
            created_at=created_at,
            updated_at=created_at,
        ),
        Card(
            id="p5-pristine-card-b",
            note=note,
            template=template_b,
            created_at=created_at,
            updated_at=created_at,
        ),
    )
    db.session.add_all([note, *cards])
    db.session.commit()

    pending_order = PaymentOrder(
        user_id=user_id,
        merchant_order_code="p5-pristine-pending-deck-order",
        status="pending_payment",
        grant_status="pending",
    )
    db.session.add(pending_order)
    db.session.flush()
    db.session.add(
        PaymentOrderItem(
            order_id=str(pending_order.id),
            product_type="deck_marketplace_item",
            product_ref_id="p5-pristine-paid-deck",
            title_snapshot="Pending paid deck",
        )
    )
    db.session.commit()
    try:
        stage_note_authority_enrollment(
            db.session,
            learner_user_id=user_id,
            now_utc=datetime(2026, 9, 22, 1, 0, 30),
        )
    except StudyAuthorityEnrollmentError as exc:
        if exc.code != "PENDING_DECK_ORDER":
            raise AssertionError(f"MySQL pending-order fence returned {exc.code}.") from exc
    else:
        raise AssertionError("MySQL NOTE enrollment bypassed an unsettled deck order.")
    db.session.rollback()
    db.session.get(PaymentOrder, str(pending_order.id)).status = "canceled"
    db.session.commit()

    enrolled = stage_note_authority_enrollment(
        db.session,
        learner_user_id=user_id,
        now_utc=datetime(2026, 9, 22, 1, 1, 0),
    )
    if (
        enrolled.mode_code != "NOTE"
        or enrolled.epoch != 1
        or enrolled.subject_count != 1
        or enrolled.card_count != 2
    ):
        raise AssertionError("Pristine enrollment returned incomplete coverage.")
    db.session.commit()
    db.session.expire_all()

    subject = StudyProgressSubject.query.filter_by(
        learner_user_id=user_id,
        live_note_id=str(note.id),
    ).one()
    token = db.session.get(StudyAuthoritySubjectToken, int(subject.id))
    state = db.session.get(StudyProgressState, int(subject.id))
    contributors = StudyProgressContributor.query.filter_by(
        subject_id=int(subject.id),
        contributor_status="ACTIVE",
    ).all()
    if (
        str(subject.status_code) != "MIRRORED_EQUIVALENT_FANIN"
        or int(subject.contributor_count) != 2
        or token is None
        or int(token.authority_revision) != 0
        or state is None
        or bytes(token.semantic_state_hash) != bytes(state.semantic_state_hash)
        or CardProgress.query.filter_by(user_id=user_id).count() != 2
        or len(contributors) != 2
        or any(
            row.current_provenance_code != "UNKNOWN_LEGACY"
            or row.history_completeness_code != "HISTORY_NATIVE_COMPLETE"
            for row in contributors
        )
        or StudyProgressAvailability.query.filter_by(
            subject_id=int(subject.id),
            subject_generation=1,
        ).count()
        != 2
    ):
        raise AssertionError("Pristine enrollment left MySQL authority divergence.")
    db.session.rollback()

    sync_session = ConnectImportSession(
        id="p5-connect-snapshot-session",
        user_id=user_id,
        source="anki",
        source_key=f"{user_id}:p5-connect-snapshot",
        mode="strict",
        status="uploading",
        selected_decks=[],
        note_type_bindings={},
        blockers=[],
        expires_at=datetime(2026, 10, 1, 0, 0, 0),
    )
    source_note = ConnectSourceNoteRef(
        id="p5-connect-source-note",
        user_id=user_id,
        source_key=sync_session.source_key,
        external_note_id="p5-external-note",
        source_model_id="p5-external-model",
        source_deck_path="P5 probe",
        note_id=str(note.id),
        content_hash="1" * 64,
        last_session_id=sync_session.id,
    )
    db.session.add_all([sync_session, source_note])
    db.session.commit()
    snapshot = {
        "externalNoteId": "p5-external-note",
        "sourceCardId": "p5-external-card-a",
        "ord": 0,
        "snapshotHash": "a" * 64,
        "baseSnapshotHash": None,
        "type": 2,
        "queue": 2,
        "due": 50003,
        "sourceToday": 50000,
        "interval": 14,
        "factor": 2500,
        "reps": 2,
        "lapses": 1,
        "left": 0,
    }
    applied = import_progress(user_id, sync_session, [snapshot])[0]
    if (
        applied.get("state") != "applied"
        or applied.get("code") != "PROGRESS_APPLIED"
    ):
        raise AssertionError(f"MySQL NOTE snapshot was not applied: {applied!r}")
    db.session.commit()
    db.session.expire_all()
    subject = StudyProgressSubject.query.filter_by(
        learner_user_id=user_id,
        live_note_id=str(note.id),
    ).one()
    token = db.session.get(StudyAuthoritySubjectToken, int(subject.id))
    progress_rows = CardProgress.query.filter_by(user_id=user_id).all()
    source_card = ConnectSourceCardRef.query.filter_by(
        user_id=user_id,
        external_card_id="p5-external-card-a",
    ).one()
    contributors = StudyProgressContributor.query.filter_by(
        subject_id=int(subject.id),
        contributor_status="ACTIVE",
    ).all()
    if (
        token is None
        or int(token.authority_revision) != 1
        or int(subject.mirror_revision) != 2
        or len(progress_rows) != 2
        or any(
            int(row.revision) != 1
            or row.interval_days != 14
            or row.scheduler_mode != "anki"
            for row in progress_rows
        )
        or source_card.snapshot_hash != "a" * 64
        or int(source_card.applied_local_revision or -1) != 1
        or len(contributors) != 2
        or any(
            row.current_provenance_code != "CONNECT_PROGRESS_SNAPSHOT"
            or row.history_completeness_code != "HISTORY_MIXED_PARTIAL"
            for row in contributors
        )
    ):
        raise AssertionError("MySQL NOTE snapshot left canonical/projection divergence.")
    db.session.rollback()

    first_review_ms = int(
        datetime(2026, 9, 22, 1, 30, tzinfo=timezone.utc).timestamp() * 1000
    )
    review = {
        "sourceReviewId": first_review_ms,
        "sourceCardId": "p5-external-card-a",
        "ease": 3,
        "type": 1,
        "ivl": 14,
        "lastIvl": 10,
        "factor": 2500,
        "time": 1200,
    }
    review_result = import_reviews(
        user_id,
        db.session.get(ConnectImportSession, sync_session.id),
        [review],
    )[0]
    if review_result.get("state") != "imported":
        raise AssertionError(f"MySQL NOTE revlog was not imported: {review_result!r}")
    db.session.commit()
    db.session.expire_all()
    subject = StudyProgressSubject.query.filter_by(
        learner_user_id=user_id,
        live_note_id=str(note.id),
    ).one()
    token = db.session.get(StudyAuthoritySubjectToken, int(subject.id))
    source_card = ConnectSourceCardRef.query.filter_by(
        user_id=user_id,
        external_card_id="p5-external-card-a",
    ).one()
    progress_rows = CardProgress.query.filter_by(user_id=user_id).all()
    if (
        token is None
        or int(token.authority_revision) != 1
        or int(subject.mirror_revision) != 2
        or any(int(row.revision) != 1 or row.interval_days != 14 for row in progress_rows)
        or ReviewEvent.query.filter_by(user_id=user_id).count() != 1
        or ConnectReviewEventRef.query.filter_by(user_id=user_id).count() != 1
        or StudyProgressHistoryFact.query.filter_by(learner_user_id=user_id).count()
        != 1
        or int(source_card.review_cursor or -1) != first_review_ms
    ):
        raise AssertionError("MySQL NOTE revlog changed current authority state.")
    db.session.rollback()

    second_review_ms = first_review_ms + 1000
    with patch(
        "app.services.study_progress_shadow_mirror_service.append_external_history_facts",
        side_effect=RuntimeError("MySQL NOTE revlog fault injection"),
    ):
        failed_review = import_reviews(
            user_id,
            db.session.get(ConnectImportSession, sync_session.id),
            [{**review, "sourceReviewId": second_review_ms}],
        )[0]
    if failed_review.get("state") != "failed" or not failed_review.get("cardAtomic"):
        raise AssertionError(
            f"MySQL NOTE revlog fault did not fail atomically: {failed_review!r}"
        )
    db.session.commit()
    db.session.expire_all()
    source_card = ConnectSourceCardRef.query.filter_by(
        user_id=user_id,
        external_card_id="p5-external-card-a",
    ).one()
    if (
        ReviewEvent.query.filter_by(user_id=user_id).count() != 1
        or ConnectReviewEventRef.query.filter_by(user_id=user_id).count() != 1
        or StudyProgressHistoryFact.query.filter_by(learner_user_id=user_id).count()
        != 1
        or int(source_card.review_cursor or -1) != first_review_ms
    ):
        raise AssertionError("MySQL NOTE revlog savepoint did not roll back atomically.")
    db.session.rollback()

    with patch(
        "app.services.study_progress_shadow_mirror_service.finalize_external_progress_mirror",
        side_effect=RuntimeError("MySQL NOTE snapshot fault injection"),
    ):
        failed = import_progress(
            user_id,
            db.session.get(ConnectImportSession, sync_session.id),
            [
                {
                    **snapshot,
                    "snapshotHash": "b" * 64,
                    "baseSnapshotHash": "a" * 64,
                    "interval": 20,
                }
            ],
        )[0]
    if failed.get("code") != "PROGRESS_IMPORT_FAILED":
        raise AssertionError(f"MySQL NOTE snapshot fault did not fail: {failed!r}")
    db.session.commit()
    db.session.expire_all()
    subject = StudyProgressSubject.query.filter_by(
        learner_user_id=user_id,
        live_note_id=str(note.id),
    ).one()
    token = db.session.get(StudyAuthoritySubjectToken, int(subject.id))
    source_card = ConnectSourceCardRef.query.filter_by(
        user_id=user_id,
        external_card_id="p5-external-card-a",
    ).one()
    progress_rows = CardProgress.query.filter_by(user_id=user_id).all()
    if (
        token is None
        or int(token.authority_revision) != 1
        or int(subject.mirror_revision) != 2
        or source_card.snapshot_hash != "a" * 64
        or any(int(row.revision) != 1 or row.interval_days != 14 for row in progress_rows)
    ):
        raise AssertionError("MySQL NOTE snapshot savepoint did not roll back atomically.")
    db.session.rollback()

    try:
        flashcard_content_service.delete_note_type(
            user_id=user_id,
            note_type_id=str(note_type.id),
            purge=True,
            is_admin=True,
        )
    except flashcard_content_service.ContentApiError as exc:
        if exc.error != "ADMIN_PURGE_NOT_READY":
            raise AssertionError(f"MySQL NOTE admin purge returned {exc.error}.") from exc
    else:
        raise AssertionError("MySQL NOTE admin purge bypassed the authority fence.")
    if (
        db.session.get(NoteType, str(note_type.id)) is None
        or db.session.get(Note, str(note.id)) is None
        or CardProgress.query.filter_by(user_id=user_id).count() != 2
        or StudyProgressSubject.query.filter_by(learner_user_id=user_id).count() != 1
    ):
        raise AssertionError("MySQL NOTE admin purge changed content or progress.")
    db.session.rollback()
    try:
        deck_management_service.delete_deck_subtree(
            deck_obj=db.session.get(Deck, int(deck.id)),
            user_id=user_id,
            is_admin=True,
            purge=True,
        )
    except StudyAuthorityFenceError as exc:
        if exc.code != "ADMIN_PURGE_NOT_READY":
            raise AssertionError(f"MySQL NOTE deck purge returned {exc.code}.") from exc
    else:
        raise AssertionError("MySQL NOTE deck purge bypassed the authority fence.")
    db.session.rollback()
    if db.session.get(Deck, int(deck.id)) is None:
        raise AssertionError("MySQL NOTE deck purge changed source content.")

    source_clone_deck = Deck(owner_user_id=user_id, name="P5 cutover source")
    local_clone_deck = Deck(owner_user_id=user_id, name="P5 cutover local")
    db.session.add_all([source_clone_deck, local_clone_deck])
    db.session.flush()
    clone_item = DeckMarketplaceItem(
        owner_user_id=user_id,
        source_deck_id=int(source_clone_deck.id),
        title="P5 cutover fence",
        publish_status="private",
    )
    db.session.add(clone_item)
    db.session.flush()
    clone_install = DeckInstall(
        deck_item_id=str(clone_item.id),
        user_id=user_id,
        local_deck_id=int(local_clone_deck.id),
        source_deck_id=int(source_clone_deck.id),
        source_owner_user_id=user_id,
        clone_mode="legacy_copy",
        installed_at=datetime(2026, 9, 22, 1, 1, 30),
    )
    db.session.add(clone_install)
    db.session.flush()
    cutover_summary = cutover_clone_model_to_overlay_only(fail_on_mismatch=False)
    if (
        cutover_summary["migrated"] != 0
        or cutover_summary["failed"] != 1
        or "NOTE_AUTHORITY_UNAVAILABLE" not in cutover_summary["errors"][0]["message"]
        or str(clone_install.clone_mode) != "legacy_copy"
        or DeckCloneDeckMap.query.filter_by(deck_install_id=clone_install.id).count() != 0
        or CardProgress.query.filter_by(user_id=user_id).count() != 2
    ):
        raise AssertionError("MySQL NOTE clone cutover bypassed the early learner fence.")

    other_owner = User(
        email="p5-overlay-owner@example.test", username="p5-overlay-owner"
    )
    db.session.add(other_owner)
    db.session.flush()
    other_source = Deck(owner_user_id=int(other_owner.id), name="P5 overlay source")
    db.session.add(other_source)
    db.session.flush()
    other_item = DeckMarketplaceItem(
        owner_user_id=int(other_owner.id),
        source_deck_id=int(other_source.id),
        title="P5 NOTE overlay install fence",
        publish_status="private",
    )
    db.session.add(other_item)
    db.session.flush()
    try:
        flashcards_share_service.install_shared_deck_item_for_user(
            other_item,
            user_id=user_id,
            publish_statuses_visible={"private"},
        )
    except ShareControllerError as exc:
        if exc.error != "OVERLAY_AUTHORITY_NOT_READY":
            raise AssertionError(f"MySQL NOTE overlay install returned {exc.error}.") from exc
    else:
        raise AssertionError("MySQL NOTE learner installed an unsupported overlay.")
    if DeckInstall.query.filter_by(deck_item_id=other_item.id, user_id=user_id).count():
        raise AssertionError("MySQL NOTE overlay install created an install row.")

    local_clone_child = Deck(
        owner_user_id=user_id,
        parent_id=int(local_clone_deck.id),
        name="P5 cutover local child",
    )
    db.session.add(local_clone_child)
    db.session.flush()
    db.session.add(
        DeckCloneDeckMap(
            deck_install_id=str(clone_install.id),
            local_deck_id=int(local_clone_child.id),
            source_deck_id=int(source_clone_deck.id),
        )
    )
    db.session.flush()
    for target in (local_clone_child, local_clone_deck):
        try:
            deck_management_service.delete_deck_subtree(
                deck_obj=target,
                user_id=user_id,
                is_admin=False,
            )
        except StudyAuthorityFenceError as exc:
            if exc.code != "OVERLAY_DELETE_NOT_READY":
                raise AssertionError(f"MySQL NOTE overlay delete returned {exc.code}.") from exc
        else:
            raise AssertionError("MySQL NOTE learner deleted an installed clone node.")
        if (
            db.session.get(Deck, int(target.id)) is None
            or db.session.get(DeckInstall, str(clone_install.id)) is None
        ):
            raise AssertionError("MySQL NOTE overlay delete changed clone ownership.")
    db.session.rollback()

    rolled_back = stage_legacy_authority_enrollment(
        db.session,
        learner_user_id=user_id,
        now_utc=datetime(2026, 9, 22, 1, 2, 0),
    )
    if (
        rolled_back.previous_mode != "NOTE"
        or rolled_back.mode_code != "LEGACY"
        or rolled_back.epoch != 2
        or rolled_back.subject_count != 1
        or rolled_back.card_count != 2
    ):
        raise AssertionError("Pristine enrollment rollback lost compatibility state.")
    db.session.commit()
    purged = flashcard_content_service.delete_note_type(
        user_id=user_id,
        note_type_id=str(note_type.id),
        purge=True,
        is_admin=True,
    )
    if (
        not purged.get("purged")
        or db.session.get(NoteType, str(note_type.id)) is not None
        or db.session.get(Note, str(note.id)) is not None
        or CardProgress.query.filter_by(user_id=user_id).count() != 0
        or ReviewEvent.query.filter_by(note_type_id=str(note_type.id)).count() != 0
    ):
        raise AssertionError("MySQL LEGACY admin purge did not preserve the lifecycle contract.")
    deck_purged = deck_management_service.delete_deck_subtree(
        deck_obj=db.session.get(Deck, int(deck.id)),
        user_id=user_id,
        is_admin=True,
        purge=True,
    )
    if deck_purged != "purged" or db.session.get(Deck, int(deck.id)) is not None:
        raise AssertionError("MySQL LEGACY admin deck purge did not complete.")
    db.session.delete(db.session.get(User, user_id))
    db.session.commit()
    return {
        "pristine_note_enrollment_materialization": "PASS",
        "note_enrollment_pending_deck_order_fence": "PASS",
        "note_authority_connect_snapshot": "PASS",
        "note_authority_connect_snapshot_rollback": "PASS",
        "note_authority_connect_revlog_history_only": "PASS",
        "note_authority_connect_revlog_rollback": "PASS",
        "note_authority_admin_purge_early_fence": "PASS",
        "legacy_admin_note_type_purge": "PASS",
        "note_authority_admin_deck_purge_early_fence": "PASS",
        "note_authority_clone_cutover_early_fence": "PASS",
        "note_authority_overlay_install_early_fence": "PASS",
        "note_authority_overlay_delete_early_fence": "PASS",
        "legacy_admin_deck_purge": "PASS",
        "pristine_note_enrollment_rollback": "PASS",
    }


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

    reset_plan = study_progress_lifecycle_mirror_service.prepare_note_authority_reset(
        db.session,
        route=note_route,
        removed_card_ids=(str(card_a.id), str(card_b.id)),
        now_utc=datetime(2026, 9, 23, 2, 0, 0),
    )
    if reset_plan is None:
        raise AssertionError("Reviewed NOTE state was incorrectly treated as reset-pristine.")
    deleted_count = CardProgress.query.filter(
        CardProgress.user_id == user_id,
        CardProgress.card_id.in_((str(card_a.id), str(card_b.id))),
    ).delete(synchronize_session=False)
    if deleted_count != 2:
        raise AssertionError("NOTE reset did not remove both old compatibility rows.")
    reset_result = (
        study_progress_lifecycle_mirror_service.finalize_note_authority_reset(
            reset_plan,
            source_path="deck.progress_reset",
            operation_key="p5-mysql-note-reset",
            now_utc=datetime(2026, 9, 23, 2, 0, 0),
        )
    )
    if reset_result is None or reset_result.subject_count != 1:
        raise AssertionError("NOTE reset did not rebuild one authority subject.")
    db.session.commit()
    db.session.expire_all()
    reset_subject = db.session.get(StudyProgressSubject, cas_subject_id)
    reset_token = db.session.get(StudyAuthoritySubjectToken, cas_subject_id)
    reset_state = db.session.get(StudyProgressState, cas_subject_id)
    reset_rows = CardProgress.query.filter(
        CardProgress.user_id == user_id,
        CardProgress.card_id.in_((str(card_a.id), str(card_b.id))),
    ).all()
    if (
        reset_subject is None
        or int(reset_subject.subject_generation) != 2
        or int(reset_subject.mirror_revision) != 3
        or not str(reset_subject.status_code).startswith("MIRRORED_")
        or reset_token is None
        or int(reset_token.subject_generation) != 2
        or int(reset_token.authority_revision) != 2
        or reset_state is None
        or bytes(reset_token.semantic_state_hash)
        != bytes(reset_state.semantic_state_hash)
        or len(reset_rows) != 2
        or any(str(row.queue) != "new" or int(row.revision) != 0 for row in reset_rows)
    ):
        raise AssertionError("Committed NOTE reset left state/token/projection divergence.")
    contributor_statuses = sorted(
        str(row.contributor_status)
        for row in StudyProgressContributor.query.filter_by(
            subject_id=cas_subject_id
        ).all()
    )
    if contributor_statuses != ["ACTIVE", "ACTIVE", "TOMBSTONED", "TOMBSTONED"]:
        raise AssertionError("NOTE reset did not fence prior contributor identities.")
    if StudyProgressLifecycleEvent.query.filter_by(
        subject_id=cas_subject_id,
        transition_code="TOMBSTONED_RESET",
    ).count() != 1:
        raise AssertionError("NOTE reset did not append lifecycle evidence.")
    db.session.rollback()

    expansion_plan = (
        study_progress_lifecycle_mirror_service.prepare_note_authority_sibling_expansion(
            db.session,
            route=note_route,
            note_ids=(str(note.id),),
            now_utc=datetime(2026, 9, 23, 2, 30, 0),
        )
    )
    if expansion_plan is None:
        raise AssertionError("NOTE sibling expansion did not lock its authority subject.")
    expanded_card = Card(
        id="p5-probe-card-expanded",
        note_id=str(note.id),
        template_id=str(template_c.id),
        created_at=datetime(2026, 9, 23, 2, 30, 0),
        updated_at=datetime(2026, 9, 23, 2, 30, 0),
    )
    db.session.add(expanded_card)
    db.session.flush()
    expansion_result = (
        study_progress_lifecycle_mirror_service.finalize_note_authority_sibling_expansion(
            expansion_plan,
            new_cards=(expanded_card,),
            now_utc=datetime(2026, 9, 23, 2, 30, 0),
        )
    )
    if expansion_result is None or expansion_result.subject_count != 1:
        raise AssertionError("NOTE sibling expansion did not rebuild one subject.")
    db.session.commit()
    db.session.expire_all()
    expanded_subject = db.session.get(StudyProgressSubject, cas_subject_id)
    expanded_token = db.session.get(StudyAuthoritySubjectToken, cas_subject_id)
    expanded_state = db.session.get(StudyProgressState, cas_subject_id)
    expanded_progress = CardProgress.query.filter(
        CardProgress.user_id == user_id,
        CardProgress.card_id.in_(
            (str(card_a.id), str(card_b.id), str(expanded_card.id))
        ),
    ).all()
    active_expanded_contributors = StudyProgressContributor.query.filter_by(
        subject_id=cas_subject_id,
        contributor_status="ACTIVE",
    ).count()
    if (
        expanded_subject is None
        or int(expanded_subject.subject_generation) != 3
        or int(expanded_subject.mirror_revision) != 4
        or int(expanded_subject.contributor_count) != 3
        or expanded_token is None
        or int(expanded_token.subject_generation) != 3
        or int(expanded_token.authority_revision) != 2
        or expanded_state is None
        or bytes(expanded_token.semantic_state_hash)
        != bytes(expanded_state.semantic_state_hash)
        or len(expanded_progress) != 3
        or len(
            {
                map_card_progress(
                    row,
                    card_created_at=db.session.get(Card, row.card_id).created_at,
                ).semantic_state_hash
                for row in expanded_progress
            }
        )
        != 1
        or active_expanded_contributors != 3
        or StudyProgressAvailability.query.filter_by(
            subject_id=cas_subject_id,
            subject_generation=3,
        ).count()
        != 3
    ):
        raise AssertionError("NOTE sibling expansion left state/token/projection divergence.")
    db.session.rollback()

    removal_plan = (
        study_progress_lifecycle_mirror_service.prepare_note_authority_sibling_removal(
            db.session,
            route=note_route,
            removed_card_ids=(str(expanded_card.id),),
            now_utc=datetime(2026, 9, 23, 2, 45, 0),
        )
    )
    if removal_plan is None:
        raise AssertionError("NOTE sibling removal did not lock its authority subject.")
    removed_count = CardProgress.query.filter(
        CardProgress.user_id == user_id,
        CardProgress.card_id == str(expanded_card.id),
    ).delete(synchronize_session=False)
    if removed_count != 1:
        raise AssertionError("NOTE sibling removal did not delete one projection row.")
    removal_result = (
        study_progress_lifecycle_mirror_service.finalize_note_authority_sibling_removal(
            removal_plan,
            source_path="flashcards.template_delete",
            operation_key="p5-mysql-sibling-delete",
            now_utc=datetime(2026, 9, 23, 2, 45, 0),
        )
    )
    if removal_result is None or removal_result.subject_count != 1:
        raise AssertionError("NOTE sibling removal did not rebuild one subject.")
    db.session.delete(expanded_card)
    db.session.commit()
    db.session.expire_all()
    removed_subject = db.session.get(StudyProgressSubject, cas_subject_id)
    removed_token = db.session.get(StudyAuthoritySubjectToken, cas_subject_id)
    removed_state = db.session.get(StudyProgressState, cas_subject_id)
    remaining_progress = CardProgress.query.filter(
        CardProgress.user_id == user_id,
        CardProgress.card_id.in_((str(card_a.id), str(card_b.id))),
    ).all()
    if (
        removed_subject is None
        or int(removed_subject.subject_generation) != 4
        or int(removed_subject.mirror_revision) != 5
        or int(removed_subject.contributor_count) != 2
        or removed_token is None
        or int(removed_token.subject_generation) != 4
        or int(removed_token.authority_revision) != 2
        or removed_state is None
        or bytes(removed_token.semantic_state_hash)
        != bytes(removed_state.semantic_state_hash)
        or len(remaining_progress) != 2
        or StudyProgressContributor.query.filter_by(
            subject_id=cas_subject_id,
            contributor_status="ACTIVE",
        ).count()
        != 2
        or StudyProgressAvailability.query.filter_by(
            subject_id=cas_subject_id,
            subject_generation=4,
        ).count()
        != 2
        or StudyProgressLifecycleEvent.query.filter_by(
            subject_id=cas_subject_id,
            transition_code="DETACHED_CONTRIBUTOR_DELETED",
        ).count()
        != 1
    ):
        raise AssertionError("NOTE sibling removal left state/token/projection divergence.")
    db.session.rollback()

    new_note = Note(
        id="p5-probe-new-note",
        note_type=note_type,
        user_id=user_id,
        deck_id=int(deck.id),
        field_values={"Front": "new-note"},
        tags=[],
        created_at=datetime(2026, 9, 23, 3, 0, 0),
        updated_at=datetime(2026, 9, 23, 3, 0, 0),
    )
    new_cards = (
        Card(
            id="p5-probe-new-card-a",
            note=new_note,
            template=template_a,
            created_at=datetime(2026, 9, 23, 3, 0, 0),
            updated_at=datetime(2026, 9, 23, 3, 0, 0),
        ),
        Card(
            id="p5-probe-new-card-b",
            note=new_note,
            template=template_b,
            created_at=datetime(2026, 9, 23, 3, 0, 0),
            updated_at=datetime(2026, 9, 23, 3, 0, 0),
        ),
    )
    db.session.add_all([new_note, *new_cards])
    db.session.flush()
    materialized = (
        study_progress_lifecycle_mirror_service.materialize_new_note_authority(
            db.session,
            route=note_route,
            note=new_note,
            cards=new_cards,
            now_utc=datetime(2026, 9, 23, 3, 0, 0),
        )
    )
    if materialized is None or materialized.subject_count != 1:
        raise AssertionError("New NOTE materialization did not build one subject.")
    db.session.commit()
    db.session.expire_all()
    new_subject = StudyProgressSubject.query.filter_by(
        learner_user_id=user_id,
        live_note_id=str(new_note.id),
    ).one()
    new_subject_id = int(new_subject.id)
    new_card_ids = [str(card.id) for card in new_cards]
    new_token = db.session.get(StudyAuthoritySubjectToken, int(new_subject.id))
    new_state = db.session.get(StudyProgressState, int(new_subject.id))
    if (
        int(new_subject.subject_generation) != 1
        or int(new_subject.mirror_revision) != 1
        or new_token is None
        or int(new_token.authority_revision) != 0
        or new_state is None
        or bytes(new_token.semantic_state_hash)
        != bytes(new_state.semantic_state_hash)
        or CardProgress.query.filter(
            CardProgress.user_id == user_id,
            CardProgress.card_id.in_([card.id for card in new_cards]),
        ).count()
        != 2
    ):
        raise AssertionError("New NOTE materialization left an incomplete projection.")
    db.session.rollback()

    delete_plan = study_progress_lifecycle_mirror_service.prepare_note_authority_reset(
        db.session,
        route=note_route,
        removed_card_ids=new_card_ids,
        skip_pristine=False,
        now_utc=datetime(2026, 9, 23, 4, 0, 0),
    )
    CardProgress.query.filter(
        CardProgress.user_id == user_id,
        CardProgress.card_id.in_(new_card_ids),
    ).delete(synchronize_session=False)
    deleted = study_progress_lifecycle_mirror_service.finalize_note_authority_delete(
        delete_plan,
        source_path="flashcards.note_delete",
        operation_key="p5-mysql-note-delete",
        now_utc=datetime(2026, 9, 23, 4, 0, 0),
    )
    if deleted.subject_count != 1:
        raise AssertionError("NOTE delete did not tombstone one authority subject.")
    db.session.delete(new_note)
    db.session.commit()
    db.session.expire_all()
    deleted_subject = db.session.get(StudyProgressSubject, new_subject_id)
    deleted_token = db.session.get(StudyAuthoritySubjectToken, new_subject_id)
    if (
        deleted_subject is None
        or str(deleted_subject.status_code) != "TOMBSTONED_SUBJECT_DELETED"
        or deleted_subject.live_note_id is not None
        or int(deleted_subject.subject_generation) != 2
        or int(deleted_subject.mirror_revision) != 2
        or deleted_token is None
        or int(deleted_token.subject_generation) != 2
        or int(deleted_token.authority_revision) != 1
        or deleted_token.semantic_state_hash is not None
        or db.session.get(Note, "p5-probe-new-note") is not None
        or CardProgress.query.filter(
            CardProgress.user_id == user_id,
            CardProgress.card_id.in_(new_card_ids),
        ).count()
        != 0
    ):
        raise AssertionError("NOTE delete left live content or authority state.")
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
        "subject_note_reset_reinitialization": "PASS",
        "subject_new_note_materialization": "PASS",
        "subject_new_sibling_materialization": "PASS",
        "subject_deleted_sibling_materialization": "PASS",
        "subject_owned_note_delete": "PASS",
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
            pristine_evidence = _probe_pristine_enrollment()
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
                **pristine_evidence,
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
