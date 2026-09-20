"""Read-only full-accounting and fixed-context parity coverage for P4-10."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import unittest

from app import create_app
from app.services import study_progress_shadow_mirror_service as mirror
from app.services import study_service
from app.services.anki_scheduler import _day_index, applyAnswer
from app.services.scheduler_config_service import (
    resolve_deck_options,
    resolve_scheduler_runtime_settings,
)
from app.services.study_architecture_audit_service import build_study_architecture_audit
from app.services.study_progress_backfill_service import run_current_progress_backfill
from app.services.study_progress_reconciliation_service import (
    RECONCILIATION_SCHEMA_VERSION,
    build_study_progress_reconciliation,
)
from app.services.study_progress_shadow_codec import STATE_DECODERS
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.note_type import NoteType
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_backfill_disposition import StudyProgressBackfillDisposition
from models.study_progress_backfill_run import StudyProgressBackfillRun
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User


class StudyProgressReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
                "REDIS_URL": "",
                "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": True,
                "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED": True,
                "STUDY_PROGRESS_SHADOW_COMPARE_ENABLED": True,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(
            username="reconcile-user",
            email="reconcile@example.test",
            timezone="Asia/Tokyo",
        )
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        deck = Deck(name="Reconciliation", owner_user_id=user.id)
        note_type = NoteType(name="Reconciliation type", user_id=user.id)
        db.session.add_all((deck, note_type))
        db.session.flush()
        template = Template(
            note_type_id=note_type.id,
            name="Basic",
            position=0,
            is_default=True,
            front_html="front",
            back_html="back",
        )
        db.session.add(template)
        db.session.commit()
        self.user_id = int(user.id)
        self.deck_id = int(deck.id)
        self.note_type_id = str(note_type.id)
        self.template_id = str(template.id)
        self.now = datetime(2026, 9, 14, 12, 0, 0)
        self.review_day = _day_index(
            self.now,
            int(resolve_scheduler_runtime_settings(user_id=self.user_id).day_boundary_hour_local),
            timezone_name="Asia/Tokyo",
        ) - 1

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _card(self, *, offset: int, deck_id: int | None = None) -> Card:
        note = Note(
            user_id=self.user_id,
            note_type_id=self.note_type_id,
            deck_id=self.deck_id if deck_id is None else deck_id,
            field_values={"front": str(offset)},
            created_at=self.now - timedelta(days=10 - offset),
        )
        db.session.add(note)
        db.session.flush()
        card = Card(
            note_id=note.id,
            template_id=self.template_id,
            created_at=self.now - timedelta(days=10 - offset),
        )
        db.session.add(card)
        db.session.flush()
        return card

    def _progress(
        self,
        card: Card,
        *,
        queue: str,
        due_at: datetime | None = None,
        due_day: int | None = None,
        suspended: bool = False,
        buried: bool = False,
        buried_until_day: int | None = None,
        revision: int = 0,
        user_id: int | None = None,
    ) -> CardProgress:
        row = CardProgress(
            user_id=self.user_id if user_id is None else user_id,
            card_id=card.id,
            queue=queue,
            step_index=0,
            due_at=due_at,
            due_day=due_day,
            interval_days=3,
            interval_days_raw=3.0,
            is_suspended=suspended,
            is_buried=buried,
            buried_until_day=buried_until_day,
            review_kind="review",
            scheduler_mode="legacy",
            ease_factor=2.5,
            reps=2,
            lapses=0,
            last_leech_lapses=0,
            revision=revision,
            created_at=self.now - timedelta(days=3),
            updated_at=self.now - timedelta(days=1),
        )
        db.session.add(row)
        db.session.flush()
        return row

    def _build_full_fixture(self) -> None:
        self._card(offset=0)  # no progress remains a selectable new Card
        relearning = self._card(offset=1)
        learning = self._card(offset=2)
        review = self._card(offset=3)
        suspended = self._card(offset=4)
        buried = self._card(offset=5)
        self._progress(
            relearning,
            queue="relearning",
            due_at=self.now - timedelta(minutes=2),
        )
        self._progress(
            learning,
            queue="learning",
            due_at=self.now + timedelta(minutes=5),
        )
        self._progress(review, queue="review", due_day=self.review_day)
        self._progress(suspended, queue="new", suspended=True)
        self._progress(buried, queue="new", buried=True, buried_until_day=None)
        db.session.commit()
        completed = run_current_progress_backfill(db.session, apply=True)
        self.assertTrue(completed.complete)

    def test_full_report_is_deterministic_read_only_and_query_exact(self):
        self._build_full_fixture()
        before = {
            "progress": CardProgress.query.count(),
            "subjects": StudyProgressSubject.query.count(),
            "contributors": StudyProgressContributor.query.count(),
            "states": StudyProgressState.query.count(),
            "availability": StudyProgressAvailability.query.count(),
            "dispositions": StudyProgressBackfillDisposition.query.count(),
            "runs": StudyProgressBackfillRun.query.count(),
            "revisions": [
                (row.id, row.revision)
                for row in CardProgress.query.order_by(CardProgress.id.asc()).all()
            ],
        }

        first = build_study_progress_reconciliation(db.session, observed_at=self.now)
        second = build_study_progress_reconciliation(db.session, observed_at=self.now)

        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], RECONCILIATION_SCHEMA_VERSION)
        self.assertEqual(first["mode"], "ENFORCED")
        self.assertEqual(first["gate"], {"status": "PASS", "blockers": [], "enforced": True})
        self.assertEqual(first["unexplained"]["count"], 0)
        self.assertTrue(first["accounting"]["source_partition"])
        self.assertTrue(first["accounting"]["query_parity"])
        self.assertEqual(first["query_parity"]["quarantined_scope_count"], 0)
        self.assertGreaterEqual(first["query_parity"]["exact_parity_scope_count"], 2)
        self.assertEqual(len(first["checksum_sha256"]), 64)
        after = {
            "progress": CardProgress.query.count(),
            "subjects": StudyProgressSubject.query.count(),
            "contributors": StudyProgressContributor.query.count(),
            "states": StudyProgressState.query.count(),
            "availability": StudyProgressAvailability.query.count(),
            "dispositions": StudyProgressBackfillDisposition.query.count(),
            "runs": StudyProgressBackfillRun.query.count(),
            "revisions": [
                (row.id, row.revision)
                for row in CardProgress.query.order_by(CardProgress.id.asc()).all()
            ],
        }
        self.assertEqual(before, after)
        self.assertFalse(db.session.new)
        self.assertFalse(db.session.dirty)
        self.assertFalse(db.session.deleted)

    def test_corrupt_raw_hash_is_unexplained_and_blocks_strict_audit(self):
        card = self._card(offset=1)
        self._progress(card, queue="review", due_day=self.review_day, revision=2)
        db.session.commit()
        run_current_progress_backfill(db.session, apply=True)
        contributor = StudyProgressContributor.query.one()
        contributor.raw_progress_hash = b"x" * 32
        db.session.commit()

        report = build_study_progress_reconciliation(db.session, observed_at=self.now)

        self.assertEqual(report["gate"]["status"], "BLOCK")
        self.assertGreater(report["unexplained"]["by_code"]["CONTRIBUTOR_RAW_MISMATCH"], 0)
        self.assertIn("shadow_unexplained_mismatch", report["gate"]["blockers"])
        outer = build_study_architecture_audit(now=self.now)
        self.assertEqual(outer["schema_version"], "study-architecture-audit.v5")
        self.assertFalse(
            outer["reconciliation"]["formula_checks"]["phase4_shadow_zero_unexplained"]
        )
        self.assertEqual(outer["reconciliation"]["status"], "DRIFT_DETECTED")

    def test_review_day_and_pending_day_semantics_match_product_queries(self):
        runtime = resolve_scheduler_runtime_settings(user_id=self.user_id)
        today = _day_index(
            self.now,
            int(runtime.day_boundary_hour_local),
            timezone_name="Asia/Tokyo",
        )
        review_from_timestamp = self._card(offset=1)
        review_from_day = self._card(offset=2)
        future_learning_without_timestamp = self._card(offset=3)
        future_learning_with_timestamp = self._card(offset=4)
        self._progress(
            review_from_timestamp,
            queue="review",
            due_at=self.now + timedelta(minutes=5),
        )
        self._progress(review_from_day, queue="review", due_day=today - 1)
        self._progress(
            future_learning_without_timestamp,
            queue="learning",
            due_day=today + 1,
        )
        self._progress(
            future_learning_with_timestamp,
            queue="relearning",
            due_day=today + 1,
            due_at=self.now + timedelta(days=2),
        )
        db.session.commit()
        run_current_progress_backfill(db.session, apply=True)

        report = build_study_progress_reconciliation(db.session, observed_at=self.now)

        self.assertEqual(report["unexplained"]["count"], 0)
        self.assertEqual(report["gate"]["status"], "PASS")
        self.assertGreaterEqual(report["query_parity"]["exact_parity_scope_count"], 2)

    def test_decoded_shadow_review_state_matches_frozen_transition_goldens(self):
        card = self._card(offset=1)
        self._progress(card, queue="review", due_day=self.review_day)
        db.session.commit()
        run_current_progress_backfill(db.session, apply=True)
        state = StudyProgressState.query.one()
        decoded = STATE_DECODERS.decode(
            algorithm_key=state.algorithm_key,
            algorithm_version=state.algorithm_version,
            state_schema_version=state.state_schema_version,
            storage_codec=state.storage_codec,
            payload=state.state_payload,
            expected_size=state.state_payload_size,
            expected_hash=state.algorithm_state_hash,
        )
        options = resolve_deck_options(user_id=self.user_id, deck_id=self.deck_id)

        self.assertEqual(decoded.dueDay, self.review_day)
        self.assertEqual(decoded.intervalDays, 3.0)
        self.assertEqual(
            applyAnswer(decoded, options, self.now, "hard", timezone_name="Asia/Tokyo").intervalDays,
            4.0,
        )
        self.assertEqual(
            applyAnswer(decoded, options, self.now, "good", timezone_name="Asia/Tokyo").intervalDays,
            8.75,
        )
        self.assertEqual(
            applyAnswer(decoded, options, self.now, "easy", timezone_name="Asia/Tokyo").intervalDays,
            13.0,
        )

    def test_unsupported_product_transition_is_blocked_without_crashing_audit(self):
        card = self._card(offset=1)
        self._progress(card, queue="review", due_day=1)
        db.session.commit()
        run_current_progress_backfill(db.session, apply=True)

        report = build_study_progress_reconciliation(db.session, observed_at=self.now)

        self.assertIn("TRANSITION_EVALUATION_FAILURE", report["unexplained"]["by_code"])
        self.assertEqual(report["gate"]["status"], "BLOCK")

    def test_installed_source_child_deck_is_its_own_query_scope(self):
        installer = User(
            username="reconcile-installer",
            email="reconcile-installer@example.test",
            timezone="Asia/Tokyo",
        )
        installer.set_password("password")
        source_child = Deck(
            name="Source child",
            parent_id=self.deck_id,
            owner_user_id=self.user_id,
        )
        db.session.add_all((installer, source_child))
        db.session.flush()
        installed_type = NoteType(name="Installed type", user_id=installer.id)
        db.session.add(installed_type)
        db.session.flush()
        installed_template = Template(
            note_type_id=installed_type.id,
            name="Basic",
            position=0,
            is_default=True,
            front_html="front",
            back_html="back",
        )
        db.session.add(installed_template)
        db.session.flush()
        source_card = self._card(offset=1, deck_id=int(source_child.id))
        local_root = Deck(name="Installed root", owner_user_id=installer.id)
        db.session.add(local_root)
        db.session.flush()
        local_child = Deck(
            name="Installed child",
            parent_id=local_root.id,
            owner_user_id=installer.id,
        )
        item = DeckMarketplaceItem(
            owner_user_id=self.user_id,
            source_deck_id=self.deck_id,
            title="Reconciliation listing",
        )
        db.session.add_all((local_child, item))
        db.session.flush()
        install = DeckInstall(
            deck_item_id=item.id,
            user_id=installer.id,
            local_deck_id=local_root.id,
            source_deck_id=self.deck_id,
            source_owner_user_id=self.user_id,
            clone_mode="logical_overlay",
            base_snapshot_at=self.now + timedelta(days=1),
        )
        db.session.add(install)
        db.session.flush()
        local_note = Note(
            user_id=installer.id,
            note_type_id=installed_type.id,
            deck_id=local_child.id,
            field_values={"front": "local"},
            created_at=self.now - timedelta(days=2),
        )
        db.session.add(local_note)
        db.session.flush()
        local_card = Card(
            note_id=local_note.id,
            template_id=installed_template.id,
            created_at=self.now - timedelta(days=2),
        )
        db.session.add(local_card)
        db.session.flush()
        self._progress(source_card, queue="review", due_day=self.review_day, user_id=installer.id)
        self._progress(local_card, queue="learning", user_id=installer.id)
        db.session.add_all(
            (
                DeckCloneDeckMap(
                    deck_install_id=install.id,
                    local_deck_id=local_root.id,
                    source_deck_id=self.deck_id,
                ),
                DeckCloneDeckMap(
                    deck_install_id=install.id,
                    local_deck_id=local_child.id,
                    source_deck_id=source_child.id,
                ),
                DeckCloneAddedNote(
                    deck_install_id=install.id,
                    note_id=local_note.id,
                ),
            )
        )
        db.session.commit()
        run_current_progress_backfill(db.session, apply=True)

        report = build_study_progress_reconciliation(db.session, observed_at=self.now)

        self.assertEqual(report["unexplained"]["count"], 0)
        self.assertEqual(report["gate"]["status"], "PASS")
        self.assertGreaterEqual(report["query_parity"]["exact_parity_scope_count"], 4)

    def test_typed_quarantine_is_accounted_and_never_used_for_query(self):
        card = self._card(offset=1)
        self._progress(card, queue="future-queue")
        db.session.commit()
        run_current_progress_backfill(db.session, apply=True)

        report = build_study_progress_reconciliation(db.session, observed_at=self.now)

        self.assertEqual(report["unexplained"]["count"], 0)
        self.assertEqual(
            report["quarantines"]["by_code"],
            {"QUARANTINED_UNSUPPORTED_STATE": 1},
        )
        self.assertEqual(report["query_parity"]["comparable_scope_count"], 0)
        self.assertGreaterEqual(report["query_parity"]["quarantined_scope_count"], 2)
        self.assertEqual(StudyProgressState.query.count(), 0)
        self.assertEqual(StudyProgressAvailability.query.count(), 0)
        self.assertEqual(report["gate"]["status"], "PASS")

    def test_availability_attached_to_detached_contributor_blocks(self):
        card = self._card(offset=1)
        self._progress(card, queue="review", due_day=self.review_day)
        db.session.commit()
        run_current_progress_backfill(db.session, apply=True)
        contributor = StudyProgressContributor.query.one()
        contributor.contributor_status = "DETACHED"
        db.session.commit()

        report = build_study_progress_reconciliation(db.session, observed_at=self.now)

        self.assertIn("ORPHAN_AVAILABILITY", report["unexplained"]["by_code"])
        self.assertEqual(report["gate"]["status"], "BLOCK")

    def test_missing_completed_backfill_is_explicit_and_observe_only_is_not_authority(self):
        card = self._card(offset=1)
        self._progress(card, queue="new")
        db.session.commit()
        self.app.config["STUDY_PROGRESS_SHADOW_COMPARE_ENABLED"] = False

        report = build_study_progress_reconciliation(db.session, observed_at=self.now)

        self.assertEqual(report["mode"], "OBSERVE_ONLY")
        self.assertEqual(report["gate"]["status"], "BLOCK")
        self.assertIn("completed_current_progress_backfill_missing", report["gate"]["blockers"])
        self.assertIn("MISSING_SUBJECT", report["unexplained"]["by_code"])
        payload = json.dumps(report, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("reconcile@example.test", payload)
        outer = build_study_architecture_audit(now=self.now)
        self.assertTrue(
            outer["reconciliation"]["formula_checks"]["phase4_shadow_zero_unexplained"]
        )

    def test_native_pointer_and_provenance_drift_are_detected(self):
        card = self._card(offset=1)
        db.session.commit()
        study_service.execute_native_review_command(
            user=db.session.get(User, self.user_id),
            card=db.session.get(Card, card.id),
            action="good",
            payload={"duration_ms": 100},
            clone_scope=None,
            requested_scope_id=self.deck_id,
            timezone_name="Asia/Tokyo",
            now=self.now,
            source_path="native.rest",
        )
        run_current_progress_backfill(db.session, apply=True)
        clean = build_study_progress_reconciliation(db.session, observed_at=self.now)
        self.assertEqual(clean["unexplained"]["count"], 0)
        contributor = StudyProgressContributor.query.filter_by(
            contributor_status="ACTIVE"
        ).one()
        contributor.current_provenance_code = "NATIVE_MCP"
        db.session.commit()

        drift = build_study_progress_reconciliation(db.session, observed_at=self.now)

        self.assertIn(
            "CONTRIBUTOR_PROVENANCE_MISMATCH",
            drift["unexplained"]["by_code"],
        )
        self.assertEqual(drift["gate"]["status"], "BLOCK")

    def test_applied_connect_lineage_hashes_reconcile_and_source_drift_blocks(self):
        card = self._card(offset=1)
        progress = self._progress(card, queue="review", due_day=self.review_day, revision=7)
        source_note = ConnectSourceNoteRef(
            user_id=self.user_id,
            source_key="anki-main",
            external_note_id="note-1",
            source_model_id="model-1",
            source_deck_path="Deck",
            note_id=card.note_id,
            content_hash="b" * 64,
        )
        source_card = ConnectSourceCardRef(
            user_id=self.user_id,
            source_key="anki-main",
            external_card_id="card-1",
            external_note_id="note-1",
            source_ord=0,
            card_id=card.id,
            snapshot_hash="a" * 64,
            applied_local_revision=7,
        )
        db.session.add_all((source_note, source_card))
        db.session.flush()
        plan = mirror.prepare_native_mirror(
            db.session,
            learner_user_id=self.user_id,
            cards=(card,),
            now_utc=self.now,
        )
        mirror.finalize_external_progress_mirror(
            plan,
            applied_contexts={
                str(card.id): mirror.ExternalProgressMirrorContext(
                    provenance_code="CONNECT_PROGRESS_SNAPSHOT",
                    history_completeness_code="HISTORY_SNAPSHOT_ONLY",
                    source_card_ref=source_card,
                    source_note_ref=source_note,
                )
            },
            now_utc=self.now,
        )
        db.session.commit()
        run_current_progress_backfill(db.session, apply=True)

        clean = build_study_progress_reconciliation(db.session, observed_at=self.now)
        self.assertEqual(clean["unexplained"]["count"], 0)
        self.assertEqual(
            clean["writer_coverage"]["current_contributor_provenance"],
            {"CONNECT_PROGRESS_SNAPSHOT": 1},
        )
        source_note.content_hash = "c" * 64
        source_note.updated_at = source_note.updated_at + timedelta(seconds=1)
        db.session.commit()
        advanced_note = build_study_progress_reconciliation(
            db.session, observed_at=self.now
        )
        self.assertEqual(advanced_note["gate"]["status"], "PASS")
        self.assertEqual(
            advanced_note["understood_representations"]["by_code"]
            ["CONNECT_NOTE_CONTENT_ADVANCED_AFTER_PROGRESS"],
            1,
        )
        source_card.snapshot_hash = "c" * 64
        db.session.commit()

        drift = build_study_progress_reconciliation(db.session, observed_at=self.now)

        self.assertIn("LINEAGE_CARD_REF_MISMATCH", drift["unexplained"]["by_code"])
        self.assertEqual(drift["gate"]["status"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
