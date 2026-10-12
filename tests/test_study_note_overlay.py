"""NOTE authority for logical-overlay installs and never-studied (pristine) Notes."""

from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests import test_study_direct_note_replay as fixtures
from tests.study_note_fixtures import attach_template, enroll_note_user, assert_retired_progress_absent
from app.services import browse_card_service, deck_management_service
from app.services.study_authority_enrollment_service import (
    StudyAuthorityEnrollmentError,
    stage_note_authority_enrollment,
)
from app.services.study_authority_read_service import load_study_authority_card_reads
from app.services.study_artifact_service import pristine_note_review_state_version
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_progress_shadow_codec import decode_float
from models import db
from models.card import Card
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_progress_subject import StudyProgressSubject
from models.study_session_authority_pin import StudySessionAuthorityPin
from models.template import Template
from models.user import User


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class StudyNoteOverlayTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup

    def _install_overlay(self, learner_id=None, *, clone_mode="logical_overlay"):
        learner_id = learner_id or self.user_id
        with self.app.app_context():
            publisher = User(username=f"publisher-{learner_id}", email=f"publisher-{learner_id}@example.test")
            db.session.add(publisher)
            db.session.flush()
            source_deck = Deck(name="Shared source", owner_user_id=publisher.id)
            local_deck = Deck(name="Installed", owner_user_id=learner_id)
            note_type = NoteType(name="Shared type", user_id=publisher.id)
            db.session.add_all([source_deck, local_deck, note_type])
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
            templates = [attach_template(db.session, note_type_id=note_type.id, owner_user_id=note_type.user_id, name=f"Source {index}", front_html="{{Word}}",
                back_html="{{Word}}", is_default=index == 0) for index in range(2)]
            db.session.add_all(templates)
            note = Note(user_id=publisher.id, note_type_id=note_type.id, deck_id=source_deck.id,
                field_values={"Word": "共有"}, created_at=_now() - timedelta(days=1))
            db.session.add(note)
            db.session.flush()
            cards = [Card.query.filter_by(note_id=note.id, template_id=template.id).one()
                for template in templates]
            item = DeckMarketplaceItem(owner_user_id=publisher.id, source_deck_id=source_deck.id,
                source_note_type_id=note_type.id, title="Shared", publish_status="published", pricing_mode="free")
            db.session.add(item)
            db.session.flush()
            install = DeckInstall(deck_item_id=item.id, user_id=learner_id, local_deck_id=local_deck.id,
                clone_mode=clone_mode, source_deck_id=source_deck.id, source_note_type_id=note_type.id,
                source_owner_user_id=publisher.id, base_snapshot_at=_now() + timedelta(seconds=1))
            db.session.add(install)
            db.session.flush()
            db.session.add(DeckCloneDeckMap(deck_install_id=install.id, local_deck_id=local_deck.id,
                source_deck_id=source_deck.id))
            db.session.commit()
            self.local_deck_id, self.source_note_id = local_deck.id, note.id
            self.source_card_ids = [card.id for card in cards]
            self.install_id = install.id

    def _answer_source(self, **extra):
        payload = {"rating": "good", "operation_key": str(uuid4()), "duration_ms": 400,
            "scope": "deck", "scope_id": self.local_deck_id, **extra}
        response = self.client.post(f"/api/study/{self.source_card_ids[0]}/answer", json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        return payload, response.get_json()

    def _source_subject(self):
        return StudyProgressSubject.query.filter_by(
            learner_user_id=self.user_id, logical_note_key=self.source_note_id.encode()).one_or_none()

    def _reader_view(self):
        """Mode-independent view of every overlay/owned reader under test."""
        from app.services.dashboard_service import build_dashboard_data

        def flatten(nodes):
            for node in nodes:
                yield node
                yield from flatten(node.children if hasattr(node, "children") else node.get("children", []))

        user = db.session.get(User, self.user_id)
        with self.app.test_request_context():
            dashboard = build_dashboard_data(user)[0]
        tree = browse_card_service.build_browse_deck_tree(user_id=self.user_id, admin_mode=False,
            timezone_name="UTC")["tree"]
        listing = browse_card_service.list_browse_cards(user_id=self.user_id, admin_mode=False,
            timezone_name="UTC", query_args={"deck_id": str(self.local_deck_id)})
        db.session.rollback()
        return {
            "dashboard": sorted((node.deck_id, node.new_count, node.learn_count, node.due_count)
                for node in flatten(dashboard)),
            "tree": sorted((node["id"], json.dumps(node["counts"], sort_keys=True)) for node in flatten(tree)),
            "list": [(row["card_id"], row["queue"], row["due_at"], row["status"], row["deck_name"], row["word"])
                for row in listing["items"]],
            "list_total": listing["total"],
        }

    def _assert_readers_share_the_note_row(self, queue):
        view = self._reader_view()
        self.assertEqual(view["list_total"], 2)
        # Both source Cards read their Note's one state.
        self.assertEqual({row[1] for row in view["list"]}, {queue})
        dashboard = {deck_id: counts for deck_id, *counts in view["dashboard"]}
        tree = {deck_id: json.loads(counts) for deck_id, counts in view["tree"]}
        new, learn, due = dashboard[self.local_deck_id]
        self.assertEqual((tree[self.local_deck_id]["new"], tree[self.local_deck_id]["learn"],
                          tree[self.local_deck_id]["due"]), (new, learn, due))
        return view

    def test_pristine_overlay_card_reads_new_without_writing(self):
        self._install_overlay()
        with self.app.app_context():
            cards = Card.query.filter(Card.id.in_(self.source_card_ids)).all()
            options = resolve_deck_options(user_id=self.user_id, deck_id=self.local_deck_id)
            reads = load_study_authority_card_reads(db.session, learner_user_id=self.user_id, cards=cards,
                now_utc=_now(), timezone_name="UTC", deck_options_by_card_id={card.id: options for card in cards})
            self.assertEqual({read.state.type for read in reads.values()}, {"new"})
            self.assertEqual({read.authority_revision for read in reads.values()}, {0})
            enrollment = StudyProgressSubject.query.count()
            self.assertEqual(reads[self.source_card_ids[0]].state_version, pristine_note_review_state_version(
                enrollment_epoch=1, logical_note_key=self.source_note_id, deck_options=options, timezone_name="UTC"))
            db.session.rollback()
            self.assertIsNone(self._source_subject())
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(StudyProgressSubject.query.count(), enrollment)

    def test_first_overlay_answer_materializes_learner_state_without_touching_source(self):
        self._install_overlay()
        _payload, result = self._answer_source()
        self.assertFalse(result["authority"]["replayed"])
        with self.app.app_context():
            subject = self._source_subject()
            self.assertIsNotNone(subject)
            self.assertTrue(subject.status_code.startswith("MIRRORED_"))
            self.assertEqual(subject.authority_revision, 1)
            # The learner's state is the Note's one row; no Card carries progress.
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(ReviewEvent.query.filter_by(card_id=self.source_card_ids[0]).count(), 1)
            source = db.session.get(Note, self.source_note_id)
            self.assertEqual(source.field_values, {"Word": "共有"})
            self.assertNotEqual(source.user_id, self.user_id)

    def test_pristine_manifest_version_is_accepted_once_and_retry_replays(self):
        self._install_overlay()
        card_id = self.source_card_ids[0]
        preview = self.client.get(f"/api/study/cards/{card_id}/intervals-preview",
            query_string={"install_id": self.install_id})
        self.assertEqual(preview.status_code, 200, preview.get_json())
        version = preview.get_json()["review_state_version"]
        payload = {"rating": "easy", "operation_key": str(uuid4()), "duration_ms": 300, "scope": "deck",
            "scope_id": self.local_deck_id, "render_contract": "client_v1", "review_state_version": version}
        path = f"/api/study/cards/{card_id}/answer"
        first = self.client.post(path, json=payload)
        self.assertEqual(first.status_code, 200, first.get_json())
        repeated = self.client.post(path, json=payload)
        self.assertEqual(repeated.status_code, 200, repeated.get_json())
        self.assertTrue(repeated.get_json()["authority"]["replayed"])
        stale = self.client.post(path, json={**payload, "operation_key": str(uuid4())})
        self.assertEqual(stale.status_code, 409, stale.get_json())
        self.assertEqual(stale.get_json()["error"], "STALE_REVIEW_STATE")
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.filter_by(card_id=card_id).count(), 1)

    def test_v4_session_open_materializes_pristine_overlay_notes(self):
        self._install_overlay()
        compositions = self.client.get(f"/api/study/scopes/deck/{self.local_deck_id}/compositions")
        self.assertEqual(compositions.status_code, 200, compositions.get_json())
        composition_id = compositions.get_json()["compositions"][0]["composition_id"]
        with patch.dict(self.app.config, STUDY_WIRE_V4_ENABLED=True):
            opened = self.client.post("/api/study/sessions", json={"scope": "deck", "scope_id": self.local_deck_id,
                "composition_id": composition_id,
                "accepted_session_schema_versions": ["study-session.v4"]})
        self.assertEqual(opened.status_code, 201, opened.get_json())
        with self.app.app_context():
            subject = self._source_subject()
            self.assertIsNotNone(subject)
            self.assertEqual(subject.authority_revision, 0)
            self.assertIsNotNone(subject.state_payload)
            self.assertEqual(StudySessionAuthorityPin.query.filter_by(subject_id=subject.id).count(), 1)
            assert_retired_progress_absent(self, db.session)

    def test_readers_share_the_note_row_for_pristine_and_studied_overlay(self):
        self._install_overlay()
        with self.app.app_context():
            self._assert_readers_share_the_note_row("new")
        self._answer_source()
        with self.app.app_context():
            self._assert_readers_share_the_note_row(self._source_subject().normalized_queue)

    def test_admin_wide_browse_serves_the_note_row(self):
        self._install_overlay()
        self._answer_source()

        def admin_view():
            tree = browse_card_service.build_browse_deck_tree(user_id=self.user_id, admin_mode=True,
                timezone_name="UTC")["tree"]
            listing = browse_card_service.list_browse_cards(user_id=self.user_id, admin_mode=True,
                timezone_name="UTC", query_args={"per_page": "500"})
            detail = browse_card_service.get_browse_card_detail(user_id=self.user_id, admin_mode=True,
                timezone_name="UTC", card_id=self.source_card_ids[0])
            db.session.rollback()
            return (json.dumps(tree, sort_keys=True, default=str),
                [(row["card_id"], row["queue"], row["due_at"], row["status"]) for row in listing["items"]],
                json.dumps(detail.get("card", detail), sort_keys=True, default=str))

        with self.app.app_context():
            view = admin_view()
            # The installed source Card's detail reads the learner's Note row;
            # the admin-wide listing of owned pristine Cards reads NEW.
            self.assertEqual(json.loads(view[2])["queue"], self._source_subject().normalized_queue)
            self.assertEqual({row[1] for row in view[1]}, {"new"})
            self.assertEqual(admin_view(), view)

    def test_read_audit_covers_overlay_state_and_owned_pristine_notes(self):
        self._install_overlay()
        self._answer_source()
        with self.app.app_context():
            result = self.app.test_cli_runner().invoke(args=["study-authority-read-audit",
                "--user-id", str(self.user_id)])
            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["card_count"], 4)

    def test_overlay_deck_reset_restarts_note_state_with_local_options(self):
        self._install_overlay()
        self._answer_source()
        with self.app.app_context():
            subject = self._source_subject()
            revision = subject.authority_revision
            deleted = deck_management_service.reset_deck_progress(
                deck_obj=db.session.get(Deck, self.local_deck_id), user_id=self.user_id)
            self.assertEqual(deleted, 2)
            db.session.expire_all()
            subject = self._source_subject()
            self.assertGreater(subject.authority_revision, revision)
            self.assertEqual(subject.normalized_queue, "new")
            expected_ease = resolve_deck_options(user_id=self.user_id, deck_id=self.local_deck_id).startingEase
            self.assertEqual(decode_float(subject.state_payload["ease"], field_name="ease"), float(expected_ease))

    def test_uninstall_keeps_overlay_state(self):
        self._install_overlay()
        self._answer_source()
        with self.app.app_context():
            self.assertEqual(deck_management_service.delete_deck_subtree(
                deck_obj=db.session.get(Deck, self.local_deck_id), user_id=self.user_id, is_admin=False), "deleted")
            self.assertIsNone(db.session.get(DeckInstall, self.install_id))
            subject = self._source_subject()
            self.assertTrue(subject.status_code.startswith("MIRRORED_"))
            self.assertEqual(subject.authority_revision, 1)
            self.assertIsNotNone(subject.state_payload)

    def test_enrollment_accepts_overlay_and_rejects_pending_clone_cutover(self):
        with self.app.app_context():
            overlay_learner = User(username="overlay-learner", email="overlay-learner@example.test")
            copy_learner = User(username="copy-learner", email="copy-learner@example.test")
            db.session.add_all([overlay_learner, copy_learner])
            db.session.commit()
            overlay_id, copy_id = overlay_learner.id, copy_learner.id
        self._install_overlay(overlay_id)
        self._install_overlay(copy_id, clone_mode="legacy_copy")
        with self.app.app_context():
            result = stage_note_authority_enrollment(db.session, learner_user_id=overlay_id, now_utc=_now())
            db.session.commit()
            self.assertEqual(result.mode_code, "NOTE")
            with self.assertRaises(StudyAuthorityEnrollmentError) as failure:
                stage_note_authority_enrollment(db.session, learner_user_id=copy_id, now_utc=_now())
            self.assertEqual(failure.exception.code, "CLONE_CUTOVER_PENDING")
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
