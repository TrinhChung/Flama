"""Owned direct-deck freshness, publish races and additive schema contracts."""

from datetime import datetime, timedelta
import importlib
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import create_app
from app.repositories import deck_count_snapshot_repository as repository
from app.services import deck_count_snapshot_service as service
from app.services.review_analytics_policy import ReviewAnalyticsPolicy
from models import db
from models.card import Card
from tests.study_note_fixtures import attach_template, enroll_note_user
from tests.note_progress_fixtures import stage_note_state
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_count_snapshot import (
    CARD_UNIT, NOTE_UNIT, DeckCountContentRevision, DeckCountLearnerRevision, DeckStudyCountSnapshot,
)
from models.deck_install import DeckInstall
from models.note import Note
from models.note_type import NoteType
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.template import Template
from models.user import User

NOW = datetime(2026, 10, 6, 12)
DAY = NOW.date().toordinal()
CUTOFF = datetime(2026, 10, 7, 4)
migration = importlib.import_module("migrations.versions.20261006_000052_add_deck_count_snapshots")
MODELS = (DeckCountContentRevision, DeckCountLearnerRevision, DeckStudyCountSnapshot)


class DeckCountSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
            "DECK_COUNT_WRITE_ENABLED": False, "DECK_COUNT_READ_MODE": "raw",
            "REVIEW_ANALYTICS_WRITE_ENABLED": False, "REDIS_URL": "", "STUDY_NOTE_COUNT_ENABLED": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        users = [User(username=name, email=f"{name}@example.test", timezone="UTC") for name in ("counts-owner", "counts-other")]
        db.session.add_all(users)
        db.session.flush()
        for user in users:
            enroll_note_user(db.session, user)
        self.user_id, self.other_id = [int(row.id) for row in users]
        decks = [Deck(name="populated", owner_user_id=self.user_id), Deck(name="empty", owner_user_id=self.user_id), Deck(name="other", owner_user_id=self.other_id)]
        db.session.add_all(decks)
        db.session.flush()
        self.deck_id, self.empty_id, self.other_deck_id = [int(row.id) for row in decks]
        # Cards are derived per Note type (ADR P11): the first Note presents two
        # Templates, the next four one, and the empty deck's Note none.
        note_type, single_type, bare_type = [
            NoteType(user_id=self.user_id, name=name)
            for name in ("Count fixture", "Count fixture single", "Count fixture bare")
        ]
        db.session.add_all([note_type, single_type, bare_type])
        db.session.flush()
        template = attach_template(db.session, owner_user_id=self.user_id, note_type_id=note_type.id, name="Card")
        second_template = attach_template(db.session, owner_user_id=self.user_id, note_type_id=note_type.id, name="Reverse")
        db.session.add_all([template, second_template, attach_template(db.session, owner_user_id=self.user_id, note_type_id=single_type.id, name="Card")])
        db.session.flush()
        first_note = Note(user_id=self.user_id, deck_id=self.deck_id, note_type_id=note_type.id)
        db.session.add(first_note)
        db.session.flush()
        others = []
        for _index in range(4):
            note = Note(user_id=self.user_id, deck_id=self.deck_id, note_type_id=single_type.id)
            db.session.add(note)
            db.session.flush()
            others.append(note)
        self.cards = [
            str(Card.query.filter_by(note_id=first_note.id, template_id=template.id).one().id),
            str(Card.query.filter_by(note_id=first_note.id, template_id=second_template.id).one().id),
            *[str(Card.query.filter_by(note_id=note.id).one().id) for note in others],
        ]
        db.session.add(Note(user_id=self.user_id, deck_id=self.empty_id, note_type_id=bare_type.id))
        db.session.add_all([
            stage_note_state(db.session, user_id=self.user_id, card_id=self.cards[0], queue="review", due_day=DAY, due_at=CUTOFF + timedelta(days=1)),

            stage_note_state(db.session, user_id=self.user_id, card_id=self.cards[3], queue="learning", due_at=CUTOFF + timedelta(days=1)),
            stage_note_state(db.session, user_id=self.user_id, card_id=self.cards[4], queue="review", due_day=DAY, is_buried=True, buried_until_day=DAY),
            stage_note_state(db.session, user_id=self.user_id, card_id=self.cards[5], queue="review", due_day=DAY, is_suspended=True),
        ])
        db.session.commit()
        self.app.config.update(DECK_COUNT_WRITE_ENABLED=True, DECK_COUNT_READ_MODE="summary")

    def tearDown(self):
        op._proxy = None
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def args(self, **changes):
        values = dict(
            learner_user_id=self.user_id, visible_deck_ids=[self.deck_id, self.empty_id],
            today_day_index=DAY, day_cutoff_utc=CUTOFF, timezone_name="UTC",
            day_boundary_hour_local=4, is_note_mode=True, now_utc=NOW,
        )
        values.update(changes)
        return values

    def resolve(self, **changes):
        return service.resolve_cached_owned_deck_counts(db.session, **self.args(**changes))

    def prewarm(self, **changes):
        values = dict(user_id=self.user_id, now_utc=NOW)
        values.update(changes)
        db.session.remove()
        return service.prewarm_owned_deck_counts(**values)

    def test_owned_counts_match_due_priority_burial_learning_and_zero_card_rules(self):
        report = self.prewarm()
        self.assertEqual((report["eligible"], report["computed"], report["published"]), (2, 2, 2))
        cached, dirty = self.resolve(visible_deck_ids=[self.deck_id, self.empty_id, self.other_deck_id])
        self.assertEqual(cached[self.deck_id], {"total": 6, "new": 1, "learn": 1, "due": 2})
        self.assertEqual(cached[self.empty_id], {"total": 0, "new": 0, "learn": 0, "due": 0})
        self.assertEqual(dirty, [self.other_deck_id])

    def test_reader_is_read_only_even_with_pending_orm_work(self):
        self.prewarm()
        user = db.session.get(User, self.user_id)
        user.display_name = "pending change"
        statements = []
        def capture(_connection, _cursor, sql, _params, _context, _many):
            statements.append(sql.upper())
        sa.event.listen(db.engine, "before_cursor_execute", capture)
        try:
            cached, dirty = self.resolve()
        finally:
            sa.event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(len(cached), 2)
        self.assertFalse(dirty)
        self.assertFalse(any(sql.lstrip().startswith(("INSERT", "UPDATE", "DELETE")) for sql in statements))
        self.assertFalse(any("FOR UPDATE" in sql or "LOCK IN SHARE MODE" in sql for sql in statements))
        self.assertTrue(db.session.dirty)
        db.session.rollback()

    def test_read_and_write_flags_prevent_uncovered_cache_use(self):
        self.prewarm()
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = False
        self.assertEqual(self.resolve(), ({}, [self.deck_id, self.empty_id]))
        self.assertFalse(self.prewarm()["ok"])
        self.app.config.update(DECK_COUNT_WRITE_ENABLED=True, DECK_COUNT_READ_MODE="raw")
        self.assertEqual(self.resolve(), ({}, [self.deck_id, self.empty_id]))

    def test_prewarm_skips_valid_keys_and_rebuilds_only_dirty_decks(self):
        self.prewarm()
        with patch.object(service, "aggregate_deck_study_counts", side_effect=AssertionError("valid keys must skip raw")):
            report = self.prewarm()
        self.assertEqual((report["cached"], report["computed"], report["published"]), (2, 0, 0))
        repository.bump_content_revisions(db.session, [self.deck_id])
        db.session.commit()
        original = service.aggregate_deck_study_counts
        with patch.object(service, "aggregate_deck_study_counts", wraps=original) as raw:
            report = self.prewarm()
        self.assertEqual(raw.call_args.kwargs["visible_deck_ids"], [self.deck_id])
        self.assertEqual((report["cached"], report["computed"]), (1, 1))
        self.assertEqual(self.prewarm(force=True)["computed"], 2)

    def test_direct_and_global_tokens_invalidate_the_correct_scope(self):
        self.prewarm()
        repository.bump_learner_revisions(db.session, [(self.other_id, 0)])
        db.session.commit()
        self.assertFalse(self.resolve()[1])
        repository.bump_learner_revisions(db.session, [(self.user_id, self.deck_id)])
        db.session.commit()
        self.assertEqual(self.resolve()[1], [self.deck_id])
        self.prewarm()
        repository.bump_content_revisions(db.session, [0])
        db.session.commit()
        self.assertEqual(self.resolve()[1], [self.deck_id, self.empty_id])
        self.prewarm()
        repository.bump_learner_revisions(db.session, [(self.user_id, 0)])
        db.session.commit()
        self.assertEqual(self.resolve()[1], [self.deck_id, self.empty_id])

    def test_revision_bumps_deduplicate_and_rollback_without_aba_reset(self):
        self.prewarm()
        repository.bump_content_revisions(db.session, [self.deck_id, self.deck_id])
        repository.bump_learner_revisions(db.session, [(self.user_id, 0), (self.user_id, 0)])
        db.session.rollback()
        self.assertFalse(self.resolve()[1])
        repository.bump_content_revisions(db.session, [self.deck_id, self.deck_id])
        db.session.commit()
        self.assertEqual(db.session.get(DeckCountContentRevision, self.deck_id).revision, 1)
        repository.bump_content_revisions(db.session, [self.deck_id])
        db.session.commit()
        db.session.expire_all()
        self.assertEqual(db.session.get(DeckCountContentRevision, self.deck_id).revision, 2)

    def test_day_policy_implementation_and_authority_epoch_are_dependencies(self):
        self.prewarm()
        self.assertEqual(self.resolve(now_utc=CUTOFF)[1], [self.deck_id, self.empty_id])
        self.assertEqual(self.resolve(timezone_name="Asia/Tokyo")[1], [self.deck_id, self.empty_id])
        with patch.object(service, "COUNT_IMPLEMENTATION_VERSION", "dashboard-direct-counts.v2"):
            self.assertEqual(self.resolve()[1], [self.deck_id, self.empty_id])
        StudyAuthorityEnrollment.query.filter_by(learner_user_id=self.user_id).one().epoch += 1
        db.session.commit()
        self.assertEqual(self.resolve()[1], [self.deck_id, self.empty_id])

    def test_note_unit_and_card_unit_have_separate_snapshots(self):
        db.session.commit()
        self.app.config["STUDY_NOTE_COUNT_ENABLED"] = True
        report = self.prewarm()
        self.assertEqual(report["unit_code"], NOTE_UNIT)
        cached, dirty = self.resolve(count_by_note=True)
        self.assertFalse(dirty)
        self.assertEqual(cached[self.deck_id], {"total": 5, "new": 1, "learn": 1, "due": 1})
        self.assertEqual(self.resolve(count_by_note=False)[1], [self.deck_id, self.empty_id])
        self.app.config["STUDY_NOTE_COUNT_ENABLED"] = False
        self.assertEqual(self.prewarm()["unit_code"], CARD_UNIT)
        self.assertEqual(self.resolve()[0][self.deck_id]["total"], 6)

    def test_any_overlay_mapping_and_unmapped_install_descendant_remain_raw(self):
        child = Deck(name="unmapped child", owner_user_id=self.user_id, parent_id=self.deck_id)
        db.session.add(child)
        db.session.flush()
        child_id = int(child.id)
        db.session.commit()
        self.prewarm()
        install = DeckInstall(id=str(uuid4()), user_id=self.other_id, deck_item_id="fixture-item", local_deck_id=self.deck_id,
                              source_deck_id=self.other_deck_id, source_owner_user_id=self.other_id)
        db.session.add(install)
        db.session.flush()
        db.session.add(DeckCloneDeckMap(deck_install_id=install.id, local_deck_id=self.deck_id, source_deck_id=self.other_deck_id))
        db.session.commit()
        self.assertEqual(self.resolve(visible_deck_ids=[self.deck_id, child_id])[1], [self.deck_id, child_id])
        self.assertEqual(self.resolve(visible_deck_ids=[child_id], admin_mode=True)[1], [child_id])
        report = self.prewarm()
        self.assertEqual(report["eligible"], 1)

    def test_deep_owned_hierarchy_uses_linear_metadata_walk_and_bounded_sql(self):
        size = 1500
        deck_ids = list(range(10000, 10000 + size))
        db.session.execute(Deck.__table__.insert(), [
            {"id": deck_id, "name": "deep", "owner_user_id": self.user_id,
             "parent_id": None if index == 0 else deck_ids[index - 1]}
            for index, deck_id in enumerate(deck_ids)
        ])
        db.session.commit()
        inspected = [0]
        original = repository.owned_scope_rows

        class ObservedRow:
            def __init__(self, row):
                self.row = row
                self.id = row.id

            @property
            def parent_id(self):
                inspected[0] += 1
                return self.row.parent_id

        def observed(*args, **kwargs):
            return [ObservedRow(row) for row in original(*args, **kwargs)]

        statements = []
        def capture(_connection, _cursor, sql, _params, _context, _many):
            statements.append(sql.upper())

        sa.event.listen(db.engine, "before_cursor_execute", capture)
        try:
            with patch.object(repository, "owned_scope_rows", side_effect=observed):
                eligible = service._owned_eligible_scope(db.session, self.user_id, deck_ids)
        finally:
            sa.event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(eligible, tuple(deck_ids))
        self.assertLessEqual(inspected[0], size * 6)
        self.assertEqual(sum(sql.lstrip().startswith("SELECT") for sql in statements), 3)
        self.assert_no_dml(statements)

    def test_cyclic_and_unowned_ancestor_scopes_fail_closed(self):
        db.session.execute(Deck.__table__.insert(), [
            {"id": 30000, "name": "cycle A", "owner_user_id": self.user_id, "parent_id": 30001},
            {"id": 30001, "name": "cycle B", "owner_user_id": self.user_id, "parent_id": 30000},
            {"id": 30002, "name": "cycle child", "owner_user_id": self.user_id, "parent_id": 30000},
            {"id": 30003, "name": "foreign parent", "owner_user_id": self.user_id, "parent_id": self.other_deck_id},
        ])
        db.session.commit()
        self.assertEqual(service._owned_eligible_scope(db.session, self.user_id, [30000, 30001, 30002, 30003]), ())

    def test_changed_dependency_between_compute_and_publish_discards_result(self):
        original = service._publish_count_snapshots
        def changed(captured, counts, **kwargs):
            with Session(db.engine) as writer:
                repository.bump_content_revisions(writer, [self.deck_id])
                writer.commit()
            return original(captured, counts, **kwargs)
        with patch.object(service, "_publish_count_snapshots", side_effect=changed):
            report = self.prewarm()
        self.assertEqual((report["computed"], report["published"], report["discarded"]), (2, 1, 1))
        self.assertEqual(self.resolve()[1], [self.deck_id])

    def test_race_after_publish_compare_keeps_captured_old_hash_and_reader_misses(self):
        original = repository.upsert_snapshots
        def changed(session, rows):
            repository.bump_content_revisions(session, [self.deck_id])
            original(session, rows)
        with patch.object(repository, "upsert_snapshots", side_effect=changed):
            report = self.prewarm()
        self.assertEqual(report["published"], 2)
        self.assertEqual(self.resolve()[1], [self.deck_id])

    def test_fresh_session_guard_rejects_request_session_reuse(self):
        db.session.execute(sa.select(User.id))
        with self.assertRaisesRegex(RuntimeError, "fresh Session"):
            service.prewarm_owned_deck_counts(user_id=self.user_id, now_utc=NOW, session_factory=lambda: db.session())
        db.session.rollback()

    def _migration(self, step):
        db.session.remove()
        with db.engine.begin() as connection:
            op._proxy = Operations(MigrationContext.configure(connection))
            getattr(migration, step)()

    def test_migration_accepts_existing_schema_and_preserves_tokens(self):
        repository.bump_content_revisions(db.session, [0, self.deck_id])
        repository.bump_learner_revisions(db.session, [(self.user_id, 0)])
        db.session.commit()
        before = repository.read_revision_vectors(db.session, user_id=self.user_id, deck_ids=[self.deck_id])
        self._migration("upgrade")
        self._migration("upgrade")
        self.assertEqual(repository.read_revision_vectors(db.session, user_id=self.user_id, deck_ids=[self.deck_id]), before)
        with self.assertRaisesRegex(RuntimeError, "populated tokens"):
            self._migration("downgrade")

    def test_migration_fresh_creation_and_drift_preflight(self):
        db.session.remove()
        with db.engine.begin() as connection:
            for model in reversed(MODELS):
                model.__table__.drop(connection)
        self._migration("upgrade")
        self._migration("upgrade")
        self._migration("downgrade")
        self._migration("upgrade")
        with db.engine.begin() as connection:
            DeckCountContentRevision.__table__.drop(connection)
            connection.exec_driver_sql("ALTER TABLE deck_study_count_snapshots ADD COLUMN unexpected INTEGER")
        with self.assertRaisesRegex(RuntimeError, "column set differs"):
            self._migration("upgrade")
        self.assertNotIn(DeckCountContentRevision.__tablename__, sa.inspect(db.engine).get_table_names())

    def test_mysql_model_migration_parity_signed_fk_and_schema_constraints(self):
        dialect = mysql.dialect()
        for model, expected in zip(MODELS, migration._tables()):
            def ddl(table):
                return sorted(line.strip().rstrip(",") for line in str(sa.schema.CreateTable(table).compile(dialect=dialect)).splitlines())
            self.assertEqual(ddl(model.__table__), ddl(expected))
        self.assertFalse(DeckCountContentRevision.__table__.foreign_keys)
        self.assertEqual({fk.target_fullname for fk in DeckCountLearnerRevision.__table__.foreign_keys}, {"users.id"})
        repository.bump_content_revisions(db.session, [0])
        repository.bump_learner_revisions(db.session, [(self.user_id, 0)])
        db.session.commit()
        self.prewarm()
        for values in ({"new_count": -1}, {"due_count": 7}, {"contract_code": 9}, {"unit_code": 8}):
            with self.subTest(values=values):
                with self.assertRaises(IntegrityError):
                    db.session.execute(sa.update(DeckStudyCountSnapshot).where(DeckStudyCountSnapshot.effective_deck_id == self.deck_id).values(**values))
                    db.session.commit()
                db.session.rollback()

    def _cli_with_sql(self, app, arguments):
        statements = []
        with app.app_context():
            engine = db.engine
            def capture(_connection, _cursor, sql, _parameters, _context, _many):
                statements.append(sql.upper())
            sa.event.listen(engine, "before_cursor_execute", capture)
            try:
                result = app.test_cli_runner().invoke(args=arguments)
            finally:
                sa.event.remove(engine, "before_cursor_execute", capture)
        return result, statements

    def assert_no_dml(self, statements):
        self.assertFalse(any(sql.lstrip().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")) for sql in statements), statements)

    def test_audit_status_cli_is_read_only_and_write_commands_are_absent(self):
        audit = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "DECK_COUNT_WRITE_ENABLED": True, "DECK_COUNT_READ_MODE": "summary",
            "REVIEW_ANALYTICS_WRITE_ENABLED": True, "REDIS_URL": "",
        }, audit_mode=True)
        self.assertIn("deck-counts-status", audit.cli.commands)
        self.assertNotIn("deck-counts-prewarm", audit.cli.commands)
        self.assertNotIn("deck-counts-invalidate", audit.cli.commands)
        self.assertNotIn("review-analytics-backfill", audit.cli.commands)
        with audit.app_context():
            # Establish an already migrated schema outside the audited command.
            self.assertFalse(sa.inspect(db.engine).get_table_names())
            db.create_all()
        result, statements = self._cli_with_sql(audit, ["deck-counts-status", "--user-id", str(self.user_id)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output)["snapshot_rows"], 0)
        self.assert_no_dml(statements)
        with audit.app_context():
            db.session.remove()
            db.drop_all()

    def test_normal_prewarm_cli_dry_run_does_not_call_worker_or_write(self):
        with patch.object(service, "prewarm_owned_deck_counts", side_effect=AssertionError("dry-run invoked worker")) as worker:
            result, statements = self._cli_with_sql(self.app, ["deck-counts-prewarm", "--user-id", str(self.user_id), "--force"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output), {"ok": True, "dry_run": True, "user_ids": [self.user_id]})
        worker.assert_not_called()
        self.assert_no_dml(statements)

    def test_normal_prewarm_cli_rejects_apply_without_writer_coverage(self):
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = False
        with patch.object(service, "prewarm_owned_deck_counts", side_effect=AssertionError("uncovered writers invoked worker")) as worker:
            result, statements = self._cli_with_sql(self.app, ["deck-counts-prewarm", "--user-id", str(self.user_id), "--apply"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("DECK_COUNT_WRITE_ENABLED", result.output)
        worker.assert_not_called()
        self.assert_no_dml(statements)

    def test_normal_prewarm_cli_applies_only_explicit_covered_user(self):
        result, _statements = self._cli_with_sql(self.app, ["deck-counts-prewarm", "--user-id", str(self.user_id), "--apply"])
        self.assertEqual(result.exit_code, 0, result.output)
        report = json.loads(result.output)
        self.assertEqual((report["ok"], report["user_id"], report["computed"], report["published"]), (True, self.user_id, 2, 2))
        rows = db.session.execute(sa.select(DeckStudyCountSnapshot.user_id).distinct()).scalars().all()
        self.assertEqual(rows, [self.user_id])

    def test_invalidate_cli_dry_run_then_apply_on_a_fresh_session(self):
        self.prewarm()
        dry_run, statements = self._cli_with_sql(self.app, ["deck-counts-invalidate"])
        self.assertEqual(dry_run.exit_code, 0, dry_run.output)
        self.assertTrue(json.loads(dry_run.output)["dry_run"])
        self.assert_no_dml(statements)
        self.assertIsNone(db.session.get(DeckCountContentRevision, 0))
        db.session.remove()
        applied, _statements = self._cli_with_sql(self.app, ["deck-counts-invalidate", "--apply"])
        self.assertEqual(applied.exit_code, 0, applied.output)
        self.assertFalse(json.loads(applied.output)["dry_run"])
        self.assertEqual(db.session.get(DeckCountContentRevision, 0).revision, 1)
        self.assertEqual(self.resolve()[1], [self.deck_id, self.empty_id])


if __name__ == "__main__":
    unittest.main()
