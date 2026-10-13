"""NOTE-only counts and forecasts after physical Card/progress retirement."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
import unittest
from uuid import uuid4

import sqlalchemy as sa

from app import create_audit_app
from app.repositories.stats_query_repository import learner_presentation_scope
from app.repositories.vocabulary_repository import build_browse_deck_tree_payload
from app.services.deck_aggregation_service import aggregate_deck_study_counts
from app.services.stats_overview import _canonical_future_due_day_counts
from app.services.stats_today_future import _aggregate_future_due_python, _consolidated_due_rows_and_load
from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress
from migrations.retired_card_tables import CardProgress as FrozenProgress
from models import db
from models.card import Card, PresentationAlias, cutover_applications, cutover_notes
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_template_pin import DeckReleaseTemplatePin
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.template_release import TemplateRelease
from models.template_version import TemplateVersion
from models.user import User

NOW = datetime(2026, 10, 12, 1)
DAY = date(2026, 10, 12).toordinal()


class NoteStatsRetirementTests(unittest.TestCase):
    def setUp(self):
        self.app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                                     "REDIS_URL": "", "DECK_COUNT_WRITE_ENABLED": False,
                                     "REVIEW_ANALYTICS_WRITE_ENABLED": False, "STUDY_NOTE_COUNT_ENABLED": True})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        for identifier in (1, 2):
            self._insert(User, id=identifier, username=f"learner{identifier}", email=f"learner{identifier}@example.test")
        self._insert(StudyAuthorityEnrollment, learner_user_id=1, mode_code="NOTE", epoch=1, created_at=NOW, updated_at=NOW)
        self._insert(StudyAuthorityStorageProfile, id=1, profile_code="CONSOLIDATED_V1", epoch=3,
                     switched_at=NOW, created_at=NOW, updated_at=NOW)
        self.own_type = str(uuid4())
        self._insert(NoteType, id=self.own_type, user_id=1, name="Owned")
        self._insert(Deck, id=1, name="Owned", owner_user_id=1, note_type_id=self.own_type)
        self.own_app, self.own_template = self._application(1, self.own_type)
        self.own_note = self._note(1, self.own_type, 1)
        self._state(self.own_note, due_day=DAY)
        db.session.commit()
        self.trace = []
        sa.event.listen(db.engine, "before_cursor_execute", self._capture)

    def tearDown(self):
        sa.event.remove(db.engine, "before_cursor_execute", self._capture)
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _capture(self, connection, cursor, statement, parameters, context, executemany):
        self.trace.append(statement)

    @staticmethod
    def _insert(model, **values):
        db.session.execute(sa.insert(model).values(**values))

    def _application(self, owner, note_type, status="ACTIVE"):
        template, app = str(uuid4()), str(uuid4())
        self._insert(Template, id=template, owner_user_id=owner, name="Front", front_html="{{Word}}")
        self._insert(StudyApplication, id=app, note_type_id=note_type, template_id=template,
                     occurrence_key=app, status_code=status, created_at=NOW - timedelta(days=30), updated_at=NOW)
        return app, template

    def _note(self, owner, note_type, deck):
        identifier = str(uuid4())
        self._insert(Note, id=identifier, user_id=owner, note_type_id=note_type, deck_id=deck,
                     field_values={"Word": "test"}, created_at=NOW - timedelta(days=30), updated_at=NOW)
        return identifier

    def _state(self, note, due_day=DAY, due_at=None, queue="review", suspended=False):
        values = {}
        for column in FrozenProgress.__table__.columns:
            default = column.default
            values[column.name] = default.arg(None) if default is not None and default.is_callable else (default.arg if default is not None else None)
        values.update(id=1, user_id=1, card_id=str(uuid4()), queue=queue, due_day=due_day, due_at=due_at,
                      interval_days=10, interval_days_raw=10.0, is_suspended=suspended, revision=3)
        mapped = map_card_progress(SimpleNamespace(**values), card_created_at=NOW, card_order_key=values["card_id"])
        self.assertIsInstance(mapped, MappedCardProgress)
        payload = {"learner_user_id": 1, "logical_note_key": note.encode(), "live_note_id": note,
                   "status_code": "MIRRORED_SINGLE", "authority_revision": 3, "contributor_count": 1,
                   "created_at": NOW, "updated_at": NOW, "history_completeness_code": "HISTORY_IMPORTED_PARTIAL",
                   "current_provenance_code": "UNKNOWN_LEGACY", "state_payload": mapped.state.payload,
                   "state_payload_size": mapped.state.size}
        payload.update({key: getattr(mapped, key) for key in ("algorithm_key", "algorithm_version", "state_schema_version",
                                                             "storage_codec", "algorithm_state_hash", "semantic_state_hash")})
        payload.update({key: getattr(mapped.availability, key) for key in ("projection_version", "normalized_queue", "due_at",
                                                                         "due_day", "is_suspended", "is_buried", "buried_until_day")})
        self._insert(StudyProgressSubject, **payload)

    def _aggregate(self, decks, by_note=True):
        return aggregate_deck_study_counts(db.session, learner_user_id=1, visible_deck_ids=decks,
                                          today_day_index=DAY, day_cutoff_utc=NOW.replace(hour=0) + timedelta(days=1),
                                          count_by_note=by_note, include_note_types=False)[0]

    def _clone(self, local_deck=3, duplicate=False):
        if not duplicate:
            self.source_type = str(uuid4())
            self._insert(NoteType, id=self.source_type, user_id=2, name="Source")
            self._insert(Deck, id=2, name="Source", owner_user_id=2, note_type_id=self.source_type)
            self.source_app, self.source_template = self._application(2, self.source_type, status="RETIRED")
            self.source_note = self._note(2, self.source_type, 2)
            self._state(self.source_note, due_day=DAY + 1)
            self.item, self.release = str(uuid4()), str(uuid4())
            self._insert(DeckMarketplaceItem, id=self.item, owner_user_id=2, source_deck_id=2,
                         source_note_type_id=self.source_type, title="Source")
            self._insert(DeckRelease, id=self.release, deck_item_id=self.item, sequence_no=1,
                         version_label="v1", status="published", template_pins_initialized=True)
            version, publication = str(uuid4()), str(uuid4())
            self._insert(TemplateVersion, id=version, template_id=self.source_template, version_no=1,
                         content_hash="a" * 64, origin="authored")
            self._insert(TemplateRelease, id=publication, template_id=self.source_template, version_id=version,
                         sequence_no=1, version_label="v1")
            self._insert(DeckReleaseTemplatePin, deck_release_id=self.release, source_template_id=self.source_template,
                         template_release_id=publication, applications_json={self.source_app: {"id": self.source_app}})
            self._insert(DeckReleaseEntityMembership, deck_item_id=self.item, entity_kind="note",
                         entity_id=self.source_note, source_deck_id=2, introduced_sequence=1)
        item, release = self.item, self.release
        source_root = 2
        if duplicate:
            # One item publishes a subtree, another publishes its ancestor:
            # the same source Note can legitimately reach two distinct installs.
            source_root = 5
            self._insert(Deck, id=source_root, name="Source ancestor", owner_user_id=2)
            db.session.execute(sa.update(Deck).where(Deck.id == 2).values(parent_id=source_root))
            item, release = str(uuid4()), str(uuid4())
            self._insert(DeckMarketplaceItem, id=item, owner_user_id=2, source_deck_id=source_root,
                         source_note_type_id=self.source_type, title="Ancestor source")
            self._insert(DeckRelease, id=release, deck_item_id=item, sequence_no=1,
                         version_label="v1", status="published", template_pins_initialized=True)
            published = db.session.execute(sa.select(DeckReleaseTemplatePin.template_release_id).where(
                DeckReleaseTemplatePin.deck_release_id == self.release)).scalar_one()
            self._insert(DeckReleaseTemplatePin, deck_release_id=release, source_template_id=self.source_template,
                         template_release_id=published, applications_json={self.source_app: {"id": self.source_app}})
            self._insert(DeckReleaseEntityMembership, deck_item_id=item, entity_kind="note",
                         entity_id=self.source_note, source_deck_id=2, introduced_sequence=1)
        self._insert(Deck, id=local_deck, name=f"Local{local_deck}", owner_user_id=1)
        install = str(uuid4())
        self._insert(DeckInstall, id=install, deck_item_id=item, user_id=1, local_deck_id=local_deck,
                     clone_mode="logical_overlay", source_deck_id=source_root, source_note_type_id=self.source_type,
                     source_owner_user_id=2, version_mode="release", applied_release_id=release,
                     installed_at=NOW, base_snapshot_at=NOW)
        self._insert(DeckCloneDeckMap, deck_install_id=install, local_deck_id=local_deck, source_deck_id=2)
        db.session.commit()

    def test_note_units_and_presentation_units_share_current_subject_state(self):
        self._application(1, self.own_type)
        db.session.commit()
        self.assertEqual(self._aggregate([1])[1], {"total": 1, "new": 0, "learn": 0, "due": 1})
        self.assertEqual(self._aggregate([1], by_note=False)[1], {"total": 2, "new": 0, "learn": 0, "due": 2})

    def test_owner_retired_application_does_not_appear_in_forecasts_or_counts(self):
        self._application(1, self.own_type, status="RETIRED")
        db.session.commit()
        self.assertEqual(self._aggregate([1], by_note=False)[1]["total"], 1)
        rows, load = _consolidated_due_rows_and_load(user_id=1, scope_deck_ids=[1])
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(load, 0.1)

    def test_pinned_retired_source_and_local_added_note_both_count_in_local_deck(self):
        self._clone()
        local_note = self._note(1, self.own_type, 3)
        self._state(local_note, due_day=DAY + 2)
        db.session.commit()
        self.assertEqual(self._aggregate([3])[3], {"total": 2, "new": 0, "learn": 0, "due": 0})
        rows, load = _consolidated_due_rows_and_load(user_id=1, scope_deck_ids=[3])
        self.assertEqual(sorted(row[1] for row in rows), [DAY + 1, DAY + 2])
        self.assertAlmostEqual(load, 0.2)

    def test_multiple_installs_count_per_local_deck_but_collection_forecast_deduplicates(self):
        self._clone()
        self._clone(local_deck=4, duplicate=True)
        counts = self._aggregate([3, 4])
        self.assertEqual((counts[3]["total"], counts[4]["total"]), (1, 1))
        rows, load = _consolidated_due_rows_and_load(user_id=1, scope_deck_ids=None)
        self.assertEqual(len(rows), 2)  # owned Note + shared source presentation
        self.assertAlmostEqual(load, 0.2)

    def test_due_day_overrides_timestamp_and_timezone_boundary_is_preserved(self):
        by_offset, _ = _aggregate_future_due_python(rows=[
            (NOW + timedelta(days=100), DAY + 1, "review"),
            (datetime(2026, 10, 12, 18), None, "learning"),
        ], timezone_name="Asia/Tokyo", today_local=date.fromordinal(DAY), backlog=False,
            end_offset=29, day_boundary_hour_local=4)
        self.assertEqual(by_offset[1]["review"], 1)
        self.assertEqual(by_offset[0]["learning"], 1)  # 03:00 Tokyo is still prior study day

    def test_tree_skeleton_skips_progress_and_default_tree_uses_note_counts(self):
        self._application(1, self.own_type)
        db.session.commit()
        skeleton = build_browse_deck_tree_payload(user_id=1, admin_mode=False, progress_counts=False)
        self.assertEqual(skeleton[0]["counts"]["total"], 0)
        tree = build_browse_deck_tree_payload(user_id=1, admin_mode=False)
        self.assertEqual(tree[0]["counts"]["total"], 1)

    def test_overview_includes_pinned_retired_source_once(self):
        self._clone()
        self._clone(local_deck=4, duplicate=True)
        counts = _canonical_future_due_day_counts(user_id=1, timezone_name="UTC", timezone_obj=None,
                                                 start_utc=NOW.replace(hour=0), end_utc=NOW + timedelta(days=30),
                                                 day_boundary_hour_local=0, storage_profile="CONSOLIDATED_V1")
        self.assertEqual(counts, {date.fromordinal(DAY): 1, date.fromordinal(DAY + 1): 1})

    def test_forecast_identity_drift_fails_closed_and_no_retired_table_is_queried(self):
        db.session.execute(sa.update(StudyProgressSubject).values(live_note_id=None))
        db.session.commit()
        from app.services.study_authority_read_service import StudyAuthorityReadError
        with self.assertRaises(StudyAuthorityReadError):
            _consolidated_due_rows_and_load(user_id=1, scope_deck_ids=[1])
        self.assertFalse(any("card_progress" in sql.lower() for sql in self.trace))
        self.assertNotIn("cards", set(sa.inspect(db.engine).get_table_names()))

    def _assert_collection_scope_parity(self, deck_ids=None):
        """Reference actual Card membership, independently of Note-weight algebra."""
        from app.repositories.note_analytics_scope_repository import collection_note_scope

        old = learner_presentation_scope(learner_user_id=1, scope_deck_ids=deck_ids)
        presentations = sa.select(old.c.note_id, old.c.card_id).distinct().subquery()
        expected = dict(db.session.execute(sa.select(
            presentations.c.note_id, sa.func.count(),
        ).group_by(presentations.c.note_id).execution_options(include_retired_cards=True)).all())
        scope = collection_note_scope(db.session, learner_user_id=1, deck_ids=deck_ids)
        actual = dict(db.session.execute(sa.select(
            scope.c.note_id, scope.c.card_count,
        ).execution_options(include_retired_cards=True)).all())
        self.assertEqual(actual, expected)
        return actual

    def test_note_scope_preserves_original_absent_pairs_and_new_applications(self):
        db.session.execute(sa.insert(cutover_notes).values(note_id=self.own_note))
        db.session.execute(sa.insert(cutover_applications).values(application_id=self.own_app))
        db.session.commit()
        self.assertEqual(self._assert_collection_scope_parity(), {})

        self._insert(PresentationAlias.__table__, id=str(uuid4()), note_id=self.own_note,
                     application_id=self.own_app, template_id=self.own_template,
                     created_at=NOW, updated_at=NOW)
        self._application(1, self.own_type)
        missing_app, _ = self._application(1, self.own_type)
        db.session.execute(sa.insert(cutover_applications).values(application_id=missing_app))
        new_note = self._note(1, self.own_type, 1)
        retired, template = self._application(1, self.own_type, status="RETIRED")
        self._insert(PresentationAlias.__table__, id=str(uuid4()), note_id=self.own_note,
                     application_id=retired, template_id=template, created_at=NOW, updated_at=NOW)
        db.session.commit()

        self.assertEqual(self._assert_collection_scope_parity([1]), {self.own_note: 2, new_note: 3})
        self.assertEqual(self._aggregate([1])[1], {"total": 2, "new": 1, "learn": 0, "due": 1})
        self.assertEqual(self._aggregate([1], by_note=False)[1], {"total": 5, "new": 3, "learn": 0, "due": 2})

    def test_note_scope_ignores_aliases_for_a_different_application_note_type(self):
        other_type = str(uuid4())
        self._insert(NoteType, id=other_type, user_id=1, name="Other")
        application, template = self._application(1, other_type)
        db.session.execute(sa.insert(cutover_notes).values(note_id=self.own_note))
        db.session.execute(sa.insert(cutover_applications), [
            {"application_id": self.own_app}, {"application_id": application},
        ])
        self._insert(PresentationAlias.__table__, id=str(uuid4()), note_id=self.own_note,
                     application_id=application, template_id=template, created_at=NOW, updated_at=NOW)
        db.session.commit()
        self.assertEqual(self._assert_collection_scope_parity(), {})

    def test_forecast_reads_one_row_for_many_occurrences_and_preserves_card_units(self):
        from app.repositories.stats_query_repository import query_consolidated_forecast_rows
        for _ in range(20):
            self._insert(StudyApplication, id=str(uuid4()), note_type_id=self.own_type,
                         template_id=self.own_template, occurrence_key=str(uuid4()),
                         status_code="ACTIVE", created_at=NOW, updated_at=NOW)
        db.session.commit()
        self.assertEqual(self._assert_collection_scope_parity()[self.own_note], 21)
        fetched = query_consolidated_forecast_rows(user_id=1, scope_deck_ids=[1])
        self.assertEqual(len(fetched), 1)
        self.assertEqual(fetched[0][-1], 21)
        rows, load = _consolidated_due_rows_and_load(user_id=1, scope_deck_ids=[1])
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(load, 2.1)
        by_day, _ = _aggregate_future_due_python(rows=rows, timezone_name="UTC",
            today_local=date.fromordinal(DAY), backlog=False, end_offset=29, day_boundary_hour_local=0)
        self.assertEqual(by_day[0]["due_count"], 21)
        due = _canonical_future_due_day_counts(user_id=1, timezone_name="UTC", timezone_obj=None,
            start_utc=NOW.replace(hour=0), end_utc=NOW + timedelta(days=30),
            day_boundary_hour_local=0, storage_profile="CONSOLIDATED_V1")
        self.assertEqual(due, {date.fromordinal(DAY): 21})

    def test_collection_unions_disjoint_release_pins_instead_of_max_or_sum(self):
        self._clone()
        self._clone(local_deck=4, duplicate=True)
        other = str(uuid4())
        self._insert(StudyApplication, id=other, note_type_id=self.source_type,
                     template_id=self.source_template, occurrence_key=other, status_code="RETIRED",
                     created_at=NOW - timedelta(days=30), updated_at=NOW)
        install = db.session.execute(sa.select(DeckInstall).where(DeckInstall.local_deck_id == 4)).scalar_one()
        db.session.execute(sa.update(DeckReleaseTemplatePin).where(
            DeckReleaseTemplatePin.deck_release_id == install.applied_release_id,
        ).values(applications_json={other: {"id": other}}))
        db.session.commit()
        self.assertEqual(self._assert_collection_scope_parity()[self.source_note], 2)
        self.assertEqual(self._assert_collection_scope_parity([3])[self.source_note], 1)
        self.assertEqual(self._assert_collection_scope_parity([4])[self.source_note], 1)
        self.assertEqual(self._aggregate([3, 4], by_note=False)[3]["total"], 1)

    def test_collection_deduplicates_owned_and_installed_active_presentations(self):
        self._clone()
        db.session.execute(sa.update(Note).where(Note.id == self.source_note).values(user_id=1))
        db.session.execute(sa.update(StudyApplication).where(StudyApplication.id == self.source_app).values(status_code="ACTIVE"))
        db.session.execute(sa.update(DeckInstall).values(source_owner_user_id=1))
        db.session.commit()
        self.assertEqual(self._assert_collection_scope_parity()[self.source_note], 1)
        self.assertEqual(self._assert_collection_scope_parity([3])[self.source_note], 1)
        self.assertEqual(self._assert_collection_scope_parity([2])[self.source_note], 1)

        # A malformed/self install mapping back to its physical deck still
        # shares the old COUNT(DISTINCT Card) semantics in both badge units.
        db.session.execute(sa.update(DeckCloneDeckMap).values(local_deck_id=2))
        db.session.execute(sa.update(DeckInstall).values(local_deck_id=2))
        db.session.commit()
        self.assertEqual(self._aggregate([2], by_note=False)[2]["total"], 1)
        self.assertEqual(self._aggregate([2], by_note=True)[2]["total"], 1)

    def test_empty_deck_scope_and_notes_without_applications_have_no_weight(self):
        other_type = str(uuid4())
        self._insert(NoteType, id=other_type, user_id=1, name="Unattached")
        self._note(1, other_type, 1)
        db.session.commit()
        self.assertEqual(self._assert_collection_scope_parity([]), {})
        self.assertEqual(self._assert_collection_scope_parity([1]), {self.own_note: 1})


if __name__ == "__main__":
    unittest.main()
