"""A NOTE session commit touches marketplace install usage once per install key."""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests import test_study_direct_note_replay as fixtures
from app.services import flashcards_share_service
from models import db
from models.card import Card
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.review_event import ReviewEvent
from models.template import Template
from models.user import User


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class StudySessionInstallUsageTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup

    def _install_overlay(self, notes):
        with self.app.app_context():
            publisher = User(username="usage-publisher", email="usage-publisher@example.test")
            db.session.add(publisher)
            db.session.flush()
            source_deck = Deck(name="Shared source", owner_user_id=publisher.id)
            local_deck = Deck(name="Installed", owner_user_id=self.user_id)
            note_type = NoteType(name="Shared type", user_id=publisher.id)
            installed_copy = NoteType(name="Shared type copy", user_id=self.user_id)
            db.session.add_all([source_deck, local_deck, note_type, installed_copy])
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
            template = Template(note_type_id=note_type.id, name="Source", front_html="{{Word}}",
                back_html="{{Word}}", is_default=True)
            db.session.add(template)
            rows = [Note(user_id=publisher.id, note_type_id=note_type.id, deck_id=source_deck.id,
                field_values={"Word": f"w{index}"}, created_at=_now() - timedelta(days=1)) for index in range(notes)]
            db.session.add_all(rows)
            db.session.flush()
            item = DeckMarketplaceItem(owner_user_id=publisher.id, source_deck_id=source_deck.id,
                source_note_type_id=note_type.id, title="Shared", publish_status="published", pricing_mode="free")
            db.session.add(item)
            db.session.flush()
            install = DeckInstall(deck_item_id=item.id, user_id=self.user_id, local_deck_id=local_deck.id,
                clone_mode="logical_overlay", source_deck_id=source_deck.id, source_note_type_id=note_type.id,
                source_owner_user_id=publisher.id, base_snapshot_at=_now() + timedelta(seconds=1))
            note_type_install = NoteTypeInstall(source_note_type_id=note_type.id,
                installed_note_type_id=installed_copy.id, user_id=self.user_id)
            db.session.add_all([install, note_type_install])
            db.session.flush()
            db.session.add(DeckCloneDeckMap(deck_install_id=install.id, local_deck_id=local_deck.id,
                source_deck_id=source_deck.id))
            db.session.commit()
            self.local_deck_id, self.install_id = local_deck.id, install.id
            self.item_id, self.note_type_install_id = item.id, note_type_install.id

    def _open(self):
        compositions = self.client.get(f"/api/study/scopes/deck/{self.local_deck_id}/compositions")
        self.assertEqual(compositions.status_code, 200, compositions.get_json())
        with patch.dict(self.app.config, STUDY_WIRE_V4_ENABLED=True):
            opened = self.client.post("/api/study/sessions", json={
                "scope": "deck", "scope_id": self.local_deck_id,
                "composition_id": compositions.get_json()["compositions"][0]["composition_id"],
                "accepted_session_schema_versions": ["study-session.v4"],
                "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
            })
        self.assertEqual(opened.status_code, 201, opened.get_json())
        return opened.get_json()

    def _commit(self, snapshot, answers):
        events = []
        for sequence, card in enumerate(snapshot["cards"][:answers], start=1):
            policy = snapshot["policies"][card["policy_key"]]
            event_id = str(uuid4())
            events.append({
                "event_id": event_id, "sequence": sequence, "card_id": card["card_id"], "rating": "good",
                "policy_key": card["policy_key"], "scheduler_offset_ms": 60_000 * sequence, "duration_ms": 3000,
                "action_key": "review.good", "action_contract_version": "1",
                "trigger_key": "scheduler.review.good", "trigger_contract_version": "1",
                "algorithm_key": snapshot["scheduler_algorithm"], "algorithm_version": snapshot["algorithm_version"],
                "config_schema_version": policy["config_schema_version"], "config_hash": policy["config_hash"],
                "study_session_id": snapshot["session_id"], "operation_key": event_id,
                **{key: value for key, value in card["authority_pin"].items() if key != "schema_version"},
            })
        with patch.dict(self.app.config, STUDY_WIRE_V4_ENABLED=True):
            return self.client.post(f"/api/study/sessions/{snapshot['session_id']}/commit", json={
                "schema_version": "study-commit.v3", "commit_id": str(uuid4()),
                "session_token": snapshot["session_token"], "snapshot_hash": snapshot["snapshot_hash"],
                "commit_reason": "rollover", "events": events, "final_states": [],
            })

    def test_commit_touches_each_install_at_first_and_last_review(self):
        self._install_overlay(notes=4)
        snapshot = self._open()
        deck_touch = patch.object(flashcards_share_service, "touch_deck_install_usage",
            wraps=flashcards_share_service.touch_deck_install_usage)
        note_type_touch = patch.object(flashcards_share_service, "touch_note_type_install_usage",
            wraps=flashcards_share_service.touch_note_type_install_usage)
        with deck_touch as deck_calls, note_type_touch as note_type_calls:
            committed = self._commit(snapshot, 4)
        self.assertEqual(committed.status_code, 200, committed.get_json())
        self.assertEqual(committed.get_json()["applied_event_count"], 4)
        # Two touches per key (first and last review), not one per answer.
        self.assertEqual((deck_calls.call_count, note_type_calls.call_count), (2, 2))
        with self.app.app_context():
            times = sorted(event.reviewed_at for event in ReviewEvent.query.all())
            self.assertEqual(len(times), 4)
            self.assertLess(times[0], times[-1])
            self.assertEqual([call.kwargs["activity_at"] for call in deck_calls.call_args_list],
                [times[0], times[-1]])
            install = db.session.get(DeckInstall, self.install_id)
            self.assertEqual((install.first_use_at, install.last_activity_at), (times[0], times[-1]))
            # Four new reps cross the active threshold once: one counter increment.
            self.assertTrue(install.market_active)
            self.assertEqual(install.market_active_evaluated_at, times[-1])
            self.assertEqual(db.session.get(DeckMarketplaceItem, self.item_id).active_usage_count, 1)
            note_type_install = db.session.get(NoteTypeInstall, self.note_type_install_id)
            self.assertEqual((note_type_install.first_use_at, note_type_install.last_activity_at),
                (times[0], times[-1]))

    def test_single_answer_commit_touches_each_install_once(self):
        self._install_overlay(notes=2)
        snapshot = self._open()
        with patch.object(flashcards_share_service, "touch_deck_install_usage",
                wraps=flashcards_share_service.touch_deck_install_usage) as deck_calls:
            committed = self._commit(snapshot, 1)
        self.assertEqual(committed.status_code, 200, committed.get_json())
        self.assertEqual(deck_calls.call_count, 1)
        with self.app.app_context():
            reviewed_at = ReviewEvent.query.one().reviewed_at
            install = db.session.get(DeckInstall, self.install_id)
            self.assertEqual((install.first_use_at, install.last_activity_at), (reviewed_at, reviewed_at))
            self.assertFalse(install.market_active)
            self.assertEqual(db.session.get(DeckMarketplaceItem, self.item_id).active_usage_count, 0)

    def test_earlier_first_use_is_kept(self):
        self._install_overlay(notes=2)
        earlier = _now() - timedelta(days=5)
        with self.app.app_context():
            db.session.get(DeckInstall, self.install_id).first_use_at = earlier
            db.session.commit()
        committed = self._commit(self._open(), 2)
        self.assertEqual(committed.status_code, 200, committed.get_json())
        with self.app.app_context():
            last = max(event.reviewed_at for event in ReviewEvent.query.all())
            install = db.session.get(DeckInstall, self.install_id)
            self.assertEqual((install.first_use_at, install.last_activity_at), (earlier, last))

    def test_compositions_include_counts_for_installed_deck(self):
        self._install_overlay(3)
        response = self.client.get(
            f"/api/study/scopes/deck/{self.local_deck_id}/compositions?include_counts=1"
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(len(body["compositions"]), 1)
        composition_id = body["compositions"][0]["composition_id"]
        self.assertEqual(body["compositions"][0]["context_kind"], "installed_source")
        self.assertEqual(body["note_counts"], {composition_id: 3})


if __name__ == "__main__":
    unittest.main()
