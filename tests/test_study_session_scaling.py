"""Study request scaling while preserving complete NOTE leases and artifacts."""

from dataclasses import replace
from datetime import timedelta
import unittest
from unittest.mock import patch

from sqlalchemy import delete, event, select

from tests import test_study_note_batch as batches
from tests import test_study_session_authority_pin_service as pins
from tests import test_study_session_install_usage as installs
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_siblings,
    lock_study_authority_siblings_many,
)
from app.services import study_artifact_service, study_session_service
from app.services.scheduler_config_service import resolve_deck_options
from models import db
from models.card import Card
from models.deck import Deck
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_install import DeckInstall
from models.field_def import FieldDef
from models.note import Note
from models.scheduler_preset import SchedulerPreset
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.template import Template
from models.user import User


class StudySessionScalingTests(unittest.TestCase):
    setUpClass = classmethod(batches.StudyNoteBatchTests.setUpClass.__func__)
    _seed = batches.StudyNoteBatchTests._seed
    _cleanup = batches.StudyNoteBatchTests._cleanup
    _event = batches.StudyNoteBatchTests._event

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._seed(note_count=40)

    def _open(self):
        response = self.client.post("/api/study/sessions", json={
            "scope": "deck", "scope_id": self.deck_id,
            "composition_id": self.composition_id,
            "accepted_session_schema_versions": ["study-session.v4"],
            "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _capture_sql(self, call):
        statements = []
        def before(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)
        with self.app.app_context():
            event.listen(db.engine, "before_cursor_execute", before)
            try:
                result = call()
            finally:
                event.remove(db.engine, "before_cursor_execute", before)
        return result, statements

    def test_issuance_builds_one_artifact_and_policy_for_identical_effective_inputs(self):
        with patch.object(study_artifact_service, "build_template_artifact", wraps=study_artifact_service.build_template_artifact) as artifact, patch.object(
            study_session_service, "build_scheduler_policy", wraps=study_session_service.build_scheduler_policy,
        ) as policy:
            snapshot = self._open()
        self.assertEqual(len(snapshot["cards"]), 40)
        self.assertEqual((artifact.call_count, policy.call_count), (1, 1))
        with self.app.app_context():
            for payload in snapshot["cards"]:
                context = study_artifact_service.build_effective_study_card(
                    card=db.session.get(Card, payload["card_id"]), clone_scope=None,
                )
                self.assertEqual(snapshot["templates"][payload["template_key"]], study_artifact_service.build_template_artifact(context))
                self.assertEqual(snapshot["contents"][payload["content_key"]], study_artifact_service.build_content_artifact(context))

    def test_runtime_settings_read_once_across_decks_and_distinct_policies_stay_distinct(self):
        with self.app.app_context():
            children = [Deck(name=f"Options {i}", owner_user_id=self.user_id, parent_id=self.deck_id) for i in range(5)]
            preset = SchedulerPreset(user_id=self.user_id, name="Distinct", maximum_interval_days=37)
            db.session.add_all([*children, preset])
            db.session.flush()
            children[0].scheduler_preset_id = preset.id
            for i, note in enumerate(Note.query.filter_by(user_id=self.user_id).order_by(Note.id)):
                note.deck_id = children[i % len(children)].id
            db.session.commit()
        snapshot, statements = self._capture_sql(self._open)
        setting_reads = [s for s in statements if s.lstrip().upper().startswith("SELECT") and "FROM user_scheduler_settings" in s]
        self.assertEqual(len(setting_reads), 1)
        self.assertEqual(len(snapshot["policies"]), 2)
        self.assertEqual({p["config"]["max_interval_days"] for p in snapshot["policies"].values()}, {37, 36500})
        with self.app.app_context():
            for card in snapshot["cards"]:
                actual = study_session_service.build_scheduler_policy(
                    options=resolve_deck_options(user_id=self.user_id, deck_id=card["local_deck_id"]), timezone_name=snapshot["timezone"],
                )
                self.assertEqual(snapshot["policies"][card["policy_key"]]["config_hash"], actual["config_hash"])

    def test_status_reads_complete_siblings_set_wise_without_writing(self):
        response, statements = self._capture_sql(lambda: self.client.get(f"/api/study/sessions/{self.snapshot['session_id']}"))
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertFalse(response.get_json()["stale"])
        sibling_reads = [s for s in statements if "FROM cards" in s and "cards.note_id IN" in s]
        note_locks = [s for s in statements if "FROM notes" in s and s.split("FROM notes")[0].strip() == "SELECT notes.id" and "notes.id IN" in s]
        self.assertEqual((len(sibling_reads), len(note_locks)), (1, 1))
        self.assertFalse(any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for s in statements))

    def test_status_keeps_complete_vector_across_500_note_chunk_boundary(self):
        self._cleanup()
        self._seed(note_count=501)
        self.assertEqual(len(self.snapshot["cards"]), 501)
        response, statements = self._capture_sql(lambda: self.client.get(f"/api/study/sessions/{self.snapshot['session_id']}"))
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertFalse(response.get_json()["stale"])
        sibling_reads = [s for s in statements if "FROM cards" in s and "cards.note_id IN" in s]
        note_locks = [s for s in statements if "FROM notes" in s and s.split("FROM notes")[0].strip() == "SELECT notes.id" and "notes.id IN" in s]
        self.assertEqual((len(sibling_reads), len(note_locks)), (2, 2))
        self.assertFalse(any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for s in statements))

    def test_replay_identity_lookups_are_linear_and_updates_every_session_sibling(self):
        from app.services.study_application_service import stage_repeated_application
        from app.services.study_content_delete_service import lock_content_delete_routes
        with self.app.app_context():
            template = db.session.get(Card, self.snapshot["cards"][0]["card_id"]).template
            card_ids = tuple(db.session.execute(select(Card.id)).scalars())
            routes = lock_content_delete_routes(
                db.session, actor_user_ids=[self.user_id], card_ids=card_ids, deleted_note_ids=[],
            )
            stage_repeated_application(
                db.session, routes=routes, template=template, occurrence_key="scaling-repeat",
            )
            db.session.commit()
        self.snapshot = self._open()
        self.assertEqual(len(self.snapshot["cards"]), 80)
        with self.app.app_context():
            lease = db.session.get(StudySession, self.snapshot["session_id"])
            members = db.session.execute(select(StudySessionCard).where(StudySessionCard.session_id == lease.id).order_by(StudySessionCard.ordinal)).scalars().all()
            from app.repositories.study_authority_repository import lock_study_authority_route
            route = lock_study_authority_route(db.session, learner_user_id=self.user_id, allow_note_authority=True)
            authority_pins = study_session_service.lock_study_session_authority_pins(db.session, study_session=lease, session_cards=members, route=route)
            reads = []
            class CountingMap(dict):
                def __getitem__(self, key):
                    reads.append(key)
                    return super().__getitem__(key)
            authority_pins = replace(authority_pins, identity_by_session_card_id=CountingMap(authority_pins.identity_by_session_card_id))
            events = [self._event(i, card=card) for i,card in enumerate(self.snapshot["cards"], 1)]
            states, replayed, touched, _ids = study_session_service._replay_session_events(
                session=lease,
                payload={"selected_composition_id": self.snapshot["selected_composition_id"]},
                session_cards=members, raw_events=events, note_authority_pins=authority_pins,
                committed_at=lease.opened_at + timedelta(seconds=100),
            )
            self.assertEqual(len(replayed), 80)
            self.assertEqual(touched, {row.card_id for row in members})
            self.assertLessEqual(len(reads), len(members) + 2 * len(events))
            self.assertTrue(all(states[row.card_id].reps == 2 for row in members))


class StudySessionOverlayScalingTests(unittest.TestCase):
    setUpClass = classmethod(installs.StudySessionInstallUsageTests.setUpClass.__func__)
    setUp = installs.StudySessionInstallUsageTests.setUp
    _cleanup = installs.StudySessionInstallUsageTests._cleanup
    _install_overlay = installs.StudySessionInstallUsageTests._install_overlay
    _open = installs.StudySessionInstallUsageTests._open
    _capture_sql = StudySessionScalingTests._capture_sql

    def test_empty_overlay_membership_is_loaded_once_and_status_batches_it(self):
        self._install_overlay(notes=30)
        snapshot, issuance = self._capture_sql(self._open)
        self.assertEqual(len(snapshot["cards"]), 30)
        reads = [s for s in issuance if "FROM deck_clone_added_notes" in s and not "EXISTS" in s.upper()]
        self.assertEqual(len(reads), 1)
        status, statements = self._capture_sql(lambda: self.client.get(f"/api/study/sessions/{snapshot['session_id']}"))
        self.assertEqual(status.status_code, 200, status.get_json())
        self.assertFalse(status.get_json()["stale"])
        reads = [s for s in statements if "FROM deck_clone_added_notes" in s]
        self.assertEqual(len(reads), 1)

    def test_overlay_field_change_gets_a_new_artifact_in_the_next_request(self):
        self._install_overlay(notes=3)
        original = self._open()
        with self.app.app_context():
            install = db.session.get(DeckInstall, self.install_id)
            field = FieldDef.query.filter_by(note_type_id=install.source_note_type_id).one()
            db.session.add(DeckCloneFieldDefOverride(deck_install_id=install.id, source_field_def_id=field.id, properties={"name": "RenamedWord"}))
            install.overlay_revision = int(install.overlay_revision or 0) + 1
            db.session.commit()
        changed = self._open()
        old_artifact = next(iter(original["templates"].values()))
        new_artifact = next(iter(changed["templates"].values()))
        self.assertNotEqual(old_artifact["version"], new_artifact["version"])
        self.assertEqual(new_artifact["field_defs"][0]["name"], "RenamedWord")
        with self.app.app_context():
            from app.services.flashcards_share_service import resolve_clone_scope_for_local_deck
            scope = resolve_clone_scope_for_local_deck(user_id=self.user_id, local_deck_id=self.local_deck_id)
            for card_payload in changed["cards"]:
                context = study_artifact_service.build_effective_study_card(card=db.session.get(Card, card_payload["card_id"]), clone_scope=scope)
                self.assertEqual(new_artifact, study_artifact_service.build_template_artifact(context))

    def test_local_added_notes_keep_local_policy_and_batch_membership_lookup(self):
        self._install_overlay(notes=3)
        with self.app.app_context():
            install = db.session.get(DeckInstall, self.install_id)
            template = Template.query.filter_by(note_type_id=install.source_note_type_id).one()
            notes = [Note(
                user_id=self.user_id, note_type_id=install.source_note_type_id,
                deck_id=self.local_deck_id, field_values={"Word": f"local-{number}"},
            ) for number in range(30)]
            db.session.add_all(notes)
            db.session.flush()
            db.session.add_all(DeckCloneAddedNote(deck_install_id=install.id, note_id=note.id) for note in notes)
            db.session.add_all(Card(note_id=note.id, template_id=template.id) for note in notes)
            db.session.commit()
            local_note_ids = {note.id for note in notes}
        snapshot, statements = self._capture_sql(self._open)
        # Installed source and local-added Notes retain separate compositions.
        self.assertEqual(len(snapshot["cards"]), 30)
        local_cards = [card for card in snapshot["cards"] if card["note_id"] in local_note_ids]
        self.assertEqual(len(local_cards), 30)
        self.assertTrue(all(card["local_deck_id"] == self.local_deck_id for card in local_cards))
        membership_reads = [s for s in statements if "FROM deck_clone_added_notes" in s and "EXISTS" not in s.upper()]
        self.assertEqual(len(membership_reads), 1)
        status, statements = self._capture_sql(lambda: self.client.get(f"/api/study/sessions/{snapshot['session_id']}"))
        self.assertEqual(status.status_code, 200, status.get_json())
        self.assertFalse(status.get_json()["stale"])
        self.assertEqual(len([s for s in statements if "FROM deck_clone_added_notes" in s]), 1)


class StudySessionSiblingLockTests(unittest.TestCase):
    setUp = pins.StudySessionAuthorityPinServiceTests.setUp
    tearDown = pins.StudySessionAuthorityPinServiceTests.tearDown
    _route = pins.StudySessionAuthorityPinServiceTests._route
    _session_context = pins.StudySessionAuthorityPinServiceTests._session_context

    def test_many_returns_exact_single_helper_vector_including_unselected_siblings(self):
        _lease, _members, locked = self._session_context()
        single = lock_study_authority_siblings(db.session, route=self._route(), locked=locked)
        many = lock_study_authority_siblings_many(db.session, route=self._route(), locked_by_logical_note_key={self.note_id: locked})
        self.assertEqual(many[self.note_id], single)
        self.assertEqual(len(many[self.note_id].cards), 2)

    def test_publisher_owned_note_remains_valid_for_learners_subject(self):
        _lease, _members, locked = self._session_context()
        publisher = User(username="publisher", email="publisher@example.invalid")
        db.session.add(publisher)
        db.session.flush()
        db.session.get(Note, self.note_id).user_id = publisher.id
        db.session.flush()
        many = lock_study_authority_siblings_many(db.session, route=self._route(), locked_by_logical_note_key={self.note_id: locked})
        self.assertEqual(len(many[self.note_id].cards), 2)

    def test_detached_and_drifted_subject_fail_closed(self):
        _lease, _members, locked = self._session_context()
        with db.session.no_autoflush:
            locked.subject.live_note_id = None
            with self.assertRaises(StudyAuthorityFenceError) as detached:
                lock_study_authority_siblings_many(db.session, route=self._route(), locked_by_logical_note_key={self.note_id: locked})
            self.assertEqual(detached.exception.code, "DETACHED_AUTHORITY_SUBJECT")
            locked.subject.live_note_id = self.note_id
            locked.subject.logical_note_key = b"another-note"
            with self.assertRaises(StudyAuthorityFenceError) as drift:
                lock_study_authority_siblings_many(db.session, route=self._route(), locked_by_logical_note_key={self.note_id: locked})
            self.assertEqual(drift.exception.code, "UNSUPPORTED_AUTHORITY_IDENTITY")

    def test_wrong_learner_and_missing_siblings_fail_closed(self):
        _lease, _members, locked = self._session_context()
        with self.assertRaises(StudyAuthorityFenceError) as wrong:
            lock_study_authority_siblings_many(db.session, route=replace(self._route(), learner_user_id=self.user_id+1), locked_by_logical_note_key={self.note_id: locked})
        self.assertEqual(wrong.exception.code, "WRONG_LEARNER")
        db.session.execute(delete(Card).where(Card.note_id == self.note_id))
        with self.assertRaises(StudyAuthorityFenceError) as missing:
            lock_study_authority_siblings_many(db.session, route=self._route(), locked_by_logical_note_key={self.note_id: locked})
        self.assertEqual(missing.exception.code, "AUTHORITY_SIBLINGS_EMPTY")

    def test_invalid_route_or_missing_locked_subject_fail_closed(self):
        _lease, _members, locked = self._session_context()
        with self.assertRaises(StudyAuthorityFenceError) as route_error:
            lock_study_authority_siblings_many(db.session, route=replace(self._route(), mode_code="LEGACY"), locked_by_logical_note_key={self.note_id: locked})
        self.assertEqual(route_error.exception.code, "AUTHORITY_MODE_CONFLICT")
        with self.assertRaises(StudyAuthorityFenceError) as subject_error:
            lock_study_authority_siblings_many(db.session, route=self._route(), locked_by_logical_note_key={self.note_id: None})
        self.assertEqual(subject_error.exception.code, "INVALID_AUTHORITY_SUBJECT")

    def test_missing_note_fails_closed(self):
        _lease, _members, locked = self._session_context()
        db.session.execute(delete(Note).where(Note.id == self.note_id))
        with self.assertRaises(StudyAuthorityFenceError) as missing:
            lock_study_authority_siblings_many(db.session, route=self._route(), locked_by_logical_note_key={self.note_id: locked})
        self.assertEqual(missing.exception.code, "AUTHORITY_NOTE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
