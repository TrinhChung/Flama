"""P5-08 requested Algorithm switch writer with a synthetic registered target."""

from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests import test_study_direct_note_replay as fixtures
from app.services import study_algorithm_registry as registry_module
from app.services.study_algorithm_registry import (
    AlgorithmIdentity,
    AlgorithmLifecycleState,
    LegacyAnkiAlgorithmAdapter,
    StudyAlgorithmRegistry,
)
from app.services.study_algorithm_switch_service import (
    SWITCH_RECEIPT_SCHEMA_VERSION,
    StudyAlgorithmSwitchError,
    StudyAlgorithmSwitchRequest,
    apply_study_algorithm_switch,
)
from app.services.study_authority_enrollment_service import (
    StudyAuthorityEnrollmentError,
    stage_legacy_authority_enrollment,
)
from app.services.study_authority_write_service import StudyAuthorityStateWrite
from app.services.study_progress_contract import (
    HISTORY_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_codec import (
    STATE_DECODERS,
    algorithm_state_hash,
    state_document,
)
from models import db
from models.card import Card
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_progress_subject import StudyProgressSubject

SYNTHETIC = AlgorithmIdentity("synthetic-switch", "1.0.0", STATE_SCHEMA_VERSION)
UNPROJECTABLE = AlgorithmIdentity("synthetic-wide", "1.0.0", "synthetic-wide-state.v1")


class _SyntheticAdapter(LegacyAnkiAlgorithmAdapter):
    def __init__(self, identity):
        self.identity = identity


class _Initializer:
    state_storage_codec = STORAGE_CODEC
    history_schema_version = HISTORY_SCHEMA_VERSION

    def __init__(self, identity, *, extra=None):
        self.identity = identity
        self.extra = extra or {}
        self.calls = 0

    def decode_config(self, payload):
        return payload

    def decode_history_fact(self, payload):
        return payload

    def initialize(self, *, frozen_history_cut):
        self.calls += 1
        payload = {**json.loads(frozen_history_cut.current_state_payload_bytes), **self.extra}
        document = state_document(payload)
        return StudyAuthorityStateWrite(
            algorithm_key=self.identity.key, algorithm_version=self.identity.version,
            state_schema_version=self.identity.state_schema_version, storage_codec=STORAGE_CODEC,
            state_payload=document.payload, state_payload_size=document.size,
            algorithm_state_hash=algorithm_state_hash(document.payload,
                algorithm_key=self.identity.key, algorithm_version=self.identity.version,
                state_schema_version=self.identity.state_schema_version, storage_codec=STORAGE_CODEC))


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


class StudyAlgorithmSwitchTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    def setUp(self):
        fixtures.StudyDirectNoteReplayTests.setUp(self)
        legacy_decoder = STATE_DECODERS._decoders[
            ("legacy-anki", "1.0.0", STATE_SCHEMA_VERSION, STORAGE_CODEC)]
        decoders = patch.dict(STATE_DECODERS._decoders, {
            (SYNTHETIC.key, SYNTHETIC.version, SYNTHETIC.state_schema_version, STORAGE_CODEC): legacy_decoder,
            # Decodable, but its due day cannot become the Note row's availability.
            (UNPROJECTABLE.key, UNPROJECTABLE.version, UNPROJECTABLE.state_schema_version, STORAGE_CODEC):
                lambda payload: legacy_decoder({key: (None if key == "due_day" else value)
                                                for key, value in payload.items() if key != "wide"}),
        })
        decoders.start()
        self.addCleanup(decoders.stop)
        registry = StudyAlgorithmRegistry(state_decoders=STATE_DECODERS)
        registry.register(identity=LegacyAnkiAlgorithmAdapter.identity,
            lifecycle_state=AlgorithmLifecycleState.ACTIVE, adapter=LegacyAnkiAlgorithmAdapter())
        self.initializers = {}
        for identity, extra in ((SYNTHETIC, None), (UNPROJECTABLE, {"wide": 1, "due_day": "unprojectable"})):
            registry.register(identity=identity, lifecycle_state=AlgorithmLifecycleState.ACTIVE,
                adapter=_SyntheticAdapter(identity))
            self.initializers[identity.key] = _Initializer(identity, extra=extra)
            registry.register_switch_initializer(self.initializers[identity.key])
        registry_patch = patch.object(registry_module, "_ALGORITHM_REGISTRY", registry)
        registry_patch.start()
        self.addCleanup(registry_patch.stop)
        with self.app.app_context():
            self.note_key = str(Card.query.first().note_id)

    def _switch(self, target=SYNTHETIC, *, operation_key=None, expected=None):
        request = StudyAlgorithmSwitchRequest(learner_user_id=self.user_id, logical_note_key=self.note_key,
            target_key=target.key, target_version=target.version,
            operation_key=operation_key or str(uuid4()), expected_authority_revision=expected)
        return apply_study_algorithm_switch(db.session, request=request, now_utc=_now())

    def _token(self):
        # The Note's one row is its CAS token and its state (ADR P10).
        return StudyProgressSubject.query.one()

    def test_synthetic_target_switches_atomically_replays_and_is_forward_only(self):
        with self.app.app_context():
            before = self._token().authority_revision
            result = self._switch(operation_key="switch-1", expected=before)
            db.session.commit()
            self.assertFalse(result.replayed)
            self.assertEqual(result.response["to_algorithm"], {"key": SYNTHETIC.key, "version": "1.0.0"})
            self.assertEqual(self._token().authority_revision, before + 1)
            self.assertEqual(self._token().algorithm_key, SYNTHETIC.key)
            from sqlalchemy import inspect
            self.assertFalse(inspect(db.engine).has_table("card_progress"))
            receipt = StudyAuthorityCommandReceipt.query.one()
            self.assertEqual(receipt.receipt_schema_version, SWITCH_RECEIPT_SCHEMA_VERSION)
            self.assertIsNone(receipt.review_event_id)

            replay = self._switch(operation_key="switch-1", expected=before)
            db.session.commit()
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.response, result.response)
            self.assertEqual(self.initializers[SYNTHETIC.key].calls, 1)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)

            with self.assertRaises(StudyAlgorithmSwitchError) as reused:
                self._switch(UNPROJECTABLE, operation_key="switch-1")
            self.assertEqual(reused.exception.code, "AUTHORITY_OPERATION_REUSED")
            db.session.rollback()

            with self.assertRaises(StudyAuthorityEnrollmentError) as rollback:
                stage_legacy_authority_enrollment(db.session, learner_user_id=self.user_id, now_utc=_now())
            self.assertEqual(rollback.exception.code, "LEGACY_ROLLBACK_RETIRED")
            db.session.rollback()
        # Ordinary reviews cannot silently rewrite the switched identity.
        refused = self._answer(expected=409)
        self.assertEqual(refused["error"], "ALGORITHM_IDENTITY_CHANGE_UNAUTHORIZED")

    def test_switched_note_reads_canonically_and_a_new_template_keeps_its_identity(self):
        from app.services import flashcard_content_service as content
        from app.services.scheduler_config_service import resolve_deck_options
        from app.services.study_authority_read_service import load_study_authority_card_reads
        from models.note_type import NoteType

        with self.app.app_context():
            self._switch()
            db.session.commit()
            cards = Card.query.all()
            options = resolve_deck_options(user_id=self.user_id, deck_id=self.deck_id)
            reads = load_study_authority_card_reads(db.session, learner_user_id=self.user_id, cards=cards,
                now_utc=_now(), timezone_name="UTC", deck_options_by_card_id={card.id: options for card in cards})
            self.assertEqual({read.authority_revision for read in reads.values()}, {1})
            db.session.rollback()
            # A new Card shares the row; nothing is copied that could revert it.
            content.create_template(user_id=self.user_id, note_type_id=NoteType.query.one().id,
                payload={"name": "Reverse"})
            db.session.expire_all()
            self.assertEqual(self._token().algorithm_key, SYNTHETIC.key)
            self.assertEqual(self._token().authority_revision, 1)
            self.assertEqual(Card.query.count(), 3)

    def test_unprojectable_target_is_refused_before_any_write(self):
        with self.app.app_context():
            before = self._token().authority_revision
            with self.assertRaises(StudyAlgorithmSwitchError) as failure:
                self._switch(UNPROJECTABLE)
            self.assertEqual(failure.exception.code, "SWITCH_TARGET_NOT_PROJECTABLE")
            db.session.rollback()
            self.assertEqual(self._token().authority_revision, before)
            self.assertEqual(self._token().algorithm_key, "legacy-anki")
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 0)

    def test_unknown_or_initializerless_target_fails_typed(self):
        with self.app.app_context():
            for identity, reason in ((AlgorithmIdentity("fsrs", "6.0.0", "fsrs-state.v1"), "UNKNOWN_VERSION"),):
                with self.assertRaises(StudyAlgorithmSwitchError) as failure:
                    self._switch(identity)
                self.assertEqual(failure.exception.code, "ALGORITHM_SWITCH_TARGET_UNAVAILABLE")
                self.assertEqual(failure.exception.blockers, (reason,))
                db.session.rollback()
            with self.assertRaises(StudyAlgorithmSwitchError) as same:
                self._switch(LegacyAnkiAlgorithmAdapter.identity)
            self.assertEqual(same.exception.code, "ALGORITHM_ALREADY_ACTIVE")
            db.session.rollback()
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 0)

    def test_reviewed_history_and_stale_revision_block_switch(self):
        with self.app.app_context():
            with self.assertRaises(StudyAlgorithmSwitchError) as stale:
                self._switch(expected=self._token().authority_revision + 5)
            self.assertEqual(stale.exception.code, "STALE_AUTHORITY_STATE")
            db.session.rollback()
        self._answer()
        with self.app.app_context():
            with self.assertRaises(StudyAlgorithmSwitchError) as reviewed:
                self._switch()
            self.assertEqual(reviewed.exception.code, "ALGORITHM_HISTORY_POLICY_UNAPPROVED")
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
