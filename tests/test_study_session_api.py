"""Integration coverage for frontend-driven study sessions."""

import unittest
from datetime import datetime, timedelta
from uuid import uuid4

from app import create_app
from app.services.anki_scheduler import _day_index, applyAnswer
from app.services.study_session_service import (
    deserialize_card_state,
    deserialize_deck_options,
    serialize_card_state,
)
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_session import StudySession
from models.template import Template
from models.user import User


class StudySessionApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User(username="student", email="student@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id
            deck = Deck(name="Session Deck", owner_user_id=user.id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "student@example.com", "password": "password"},
            follow_redirects=True,
        )
        note_type_response = self.client.post(
            "/api/note-types",
            json={
                "name": "Session Type",
                "field_defs": [
                    {
                        "name": "Word",
                        "field_type": "text",
                        "position": 0,
                        "required": True,
                    }
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "{{Word}}",
                    "back_html": "{{Word}}",
                },
            },
        )
        self.assertEqual(note_type_response.status_code, 201)
        self.note_type_id = note_type_response.get_json()["id"]
        note_response = self.client.post(
            "/api/notes",
            json={
                "note_type_id": self.note_type_id,
                "deck_id": self.deck_id,
                "field_values": {"Word": "猫"},
            },
        )
        self.assertEqual(note_response.status_code, 201)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _open_session(self):
        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    @staticmethod
    def _commit_payload(snapshot, *, commit_id=None):
        card = snapshot["cards"][0]
        return {
            "schema_version": "study-commit.v1",
            "commit_id": commit_id or str(uuid4()),
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "events": [
                {
                    "event_id": str(uuid4()),
                    "sequence": 1,
                    "card_id": card["card_id"],
                    "rating": "good",
                    "policy_key": card["policy_key"],
                    "scheduler_offset_ms": 1000,
                    "duration_ms": 500,
                }
            ],
            "final_states": [],
        }

    def test_open_returns_self_contained_snapshot(self):
        snapshot = self._open_session()
        self.assertEqual(snapshot["schema_version"], "study-session.v2")
        self.assertTrue(snapshot["server_now_utc"].endswith(".000Z"))
        self.assertEqual(snapshot["scope"]["id"], str(self.deck_id))
        self.assertEqual(len(snapshot["cards"]), 1)
        card = snapshot["cards"][0]
        self.assertIn(card["policy_key"], snapshot["policies"])
        self.assertIn(card["template_key"], snapshot["templates"])
        self.assertIn(card["content_key"], snapshot["contents"])
        self.assertEqual(card["base_revision"], 0)

        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            self.assertIsNotNone(session)
            self.assertEqual(session.status, "open")

    def test_empty_owned_deck_can_open_and_commit(self):
        with self.app.app_context():
            empty_deck = Deck(
                name="Empty Deck",
                owner_user_id=self.user_id,
            )
            db.session.add(empty_deck)
            db.session.commit()
            empty_deck_id = empty_deck.id
        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": empty_deck_id},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        snapshot = response.get_json()
        self.assertEqual(snapshot["cards"], [])
        commit = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json={
                "schema_version": "study-commit.v1",
                "commit_id": str(uuid4()),
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": [],
                "final_states": [],
            },
        )
        self.assertEqual(commit.status_code, 200, commit.get_json())
        self.assertEqual(commit.get_json()["applied_event_count"], 0)

    def test_commit_replays_events_and_is_idempotent(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        receipt = response.get_json()
        self.assertEqual(receipt["applied_event_count"], 1)

        retry = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(retry.status_code, 200, retry.get_json())
        self.assertEqual(retry.get_json(), receipt)

        card_id = snapshot["cards"][0]["card_id"]
        with self.app.app_context():
            progress = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=card_id,
            ).one()
            self.assertEqual(progress.reps, 1)
            self.assertEqual(progress.revision, 1)
            events = ReviewEvent.query.filter_by(
                user_id=self.user_id,
                card_id=card_id,
            ).all()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].study_session_id, snapshot["session_id"])
            self.assertEqual(events[0].sequence_no, 1)
            self.assertEqual(events[0].algorithm_version, "1.0.0")

    def test_committed_batch_can_roll_into_fresh_session(self):
        first = self._open_session()
        response = self.client.post(
            f"/api/study/sessions/{first['session_id']}/commit",
            json=self._commit_payload(first),
        )
        self.assertEqual(response.status_code, 200, response.get_json())

        second = self._open_session()

        self.assertNotEqual(second["session_id"], first["session_id"])
        card = second["cards"][0]
        self.assertEqual(card["base_revision"], 1)
        self.assertEqual(card["state"]["reps"], 1)

    def test_commit_preserves_repeated_answers_for_one_card(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        second_event = dict(payload["events"][0])
        second_event.update(
            {
                "event_id": str(uuid4()),
                "sequence": 2,
                "rating": "good",
                "scheduler_offset_ms": 2000,
            }
        )
        payload["events"].append(second_event)
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["applied_event_count"], 2)

        card_id = snapshot["cards"][0]["card_id"]
        with self.app.app_context():
            events = (
                ReviewEvent.query.filter_by(
                    study_session_id=snapshot["session_id"],
                    card_id=card_id,
                )
                .order_by(ReviewEvent.sequence_no.asc())
                .all()
            )
            self.assertEqual([row.sequence_no for row in events], [1, 2])
            progress = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=card_id,
            ).one()
            self.assertEqual(progress.reps, 2)

    def test_second_session_detects_progress_conflict(self):
        first = self._open_session()
        second = self._open_session()
        first_commit = self.client.post(
            f"/api/study/sessions/{first['session_id']}/commit",
            json=self._commit_payload(first),
        )
        self.assertEqual(first_commit.status_code, 200)

        second_commit = self.client.post(
            f"/api/study/sessions/{second['session_id']}/commit",
            json=self._commit_payload(second),
        )
        self.assertEqual(second_commit.status_code, 409)
        self.assertEqual(
            second_commit.get_json()["error"],
            "CARD_PROGRESS_CONFLICT",
        )

    def test_legacy_answer_invalidates_open_batch_session(self):
        snapshot = self._open_session()
        card_id = snapshot["cards"][0]["card_id"]
        legacy = self.client.post(
            f"/api/study/{card_id}/answer",
            json={"rating": "good"},
        )
        self.assertEqual(legacy.status_code, 200, legacy.get_json())
        batch = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=self._commit_payload(snapshot),
        )
        self.assertEqual(batch.status_code, 409)
        self.assertEqual(
            batch.get_json()["error"],
            "CARD_PROGRESS_CONFLICT",
        )

    def test_commit_rejects_tampered_final_state(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        card = snapshot["cards"][0]
        payload["final_states"] = [
            {
                "card_id": card["card_id"],
                "base_revision": card["base_revision"],
                "state": card["state"],
            }
        ]
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"], "FINAL_STATE_MISMATCH")

    def test_commit_tolerates_mysql_datetime_precision_in_final_state(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        card = snapshot["cards"][0]
        policy = snapshot["policies"][card["policy_key"]]
        opened_at = datetime.fromisoformat(
            snapshot["server_now_utc"].replace("Z", "+00:00")
        ).replace(tzinfo=None)
        # Reproduce a session opened before the precision fix: the browser
        # retained milliseconds while MySQL DATETIME replayed from .000.
        browser_answer_at = opened_at + timedelta(milliseconds=1289)
        browser_state = applyAnswer(
            deserialize_card_state(card["state"]),
            deserialize_deck_options(policy["config"]),
            browser_answer_at,
            "good",
            timezone_name=snapshot["timezone"],
        )
        payload["events"][0]["scheduler_offset_ms"] = 500
        payload["final_states"] = [
            {
                "card_id": card["card_id"],
                "base_revision": card["base_revision"],
                "state": serialize_card_state(browser_state),
            }
        ]

        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["applied_event_count"], 1)

    def test_clone_session_uses_local_scope_without_mutating_source_note(self):
        with self.app.app_context():
            source_user = User(
                username="source-owner",
                email="source@example.com",
            )
            source_user.set_password("password")
            db.session.add(source_user)
            db.session.flush()
            source_deck = Deck(
                name="Source Deck",
                owner_user_id=source_user.id,
            )
            local_deck = Deck(
                name="Installed Deck",
                owner_user_id=self.user_id,
            )
            note_type = NoteType(
                user_id=source_user.id,
                name="Shared Type",
            )
            db.session.add_all([source_deck, local_deck, note_type])
            db.session.flush()
            field = FieldDef(
                note_type_id=note_type.id,
                name="Word",
                field_type="text",
                position=0,
            )
            template = Template(
                note_type_id=note_type.id,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{Word}}",
                is_default=True,
            )
            db.session.add_all([field, template])
            db.session.flush()
            note = Note(
                note_type_id=note_type.id,
                user_id=source_user.id,
                deck_id=source_deck.id,
                field_values={"Word": "共有"},
                tags=[],
            )
            db.session.add(note)
            db.session.flush()
            card = Card(note_id=note.id, template_id=template.id)
            db.session.add(card)
            db.session.flush()
            marketplace_item = DeckMarketplaceItem(
                owner_user_id=source_user.id,
                source_deck_id=source_deck.id,
                source_note_type_id=note_type.id,
                title="Shared Deck",
                publish_status="published",
                pricing_mode="free",
            )
            db.session.add(marketplace_item)
            db.session.flush()
            install = DeckInstall(
                deck_item_id=marketplace_item.id,
                user_id=self.user_id,
                local_deck_id=local_deck.id,
                clone_mode="logical_overlay",
                source_deck_id=source_deck.id,
                source_note_type_id=note_type.id,
                source_owner_user_id=source_user.id,
                base_snapshot_at=datetime.utcnow() + timedelta(seconds=1),
            )
            db.session.add(install)
            db.session.flush()
            db.session.add(
                DeckCloneDeckMap(
                    deck_install_id=install.id,
                    local_deck_id=local_deck.id,
                    source_deck_id=source_deck.id,
                )
            )
            db.session.add(
                CardProgress(
                    user_id=self.user_id,
                    card_id=card.id,
                    queue="review",
                    due_day=_day_index(datetime.utcnow(), 4),
                    interval_days=5,
                    ease_factor=2.5,
                    lapses=7,
                    revision=0,
                )
            )
            db.session.commit()
            local_deck_id = local_deck.id
            source_card_id = card.id
            source_note_id = note.id

        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": local_deck_id},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        snapshot = response.get_json()
        self.assertEqual(snapshot["cards"][0]["card_id"], source_card_id)
        self.assertEqual(
            snapshot["cards"][0]["local_deck_id"],
            local_deck_id,
        )
        payload = self._commit_payload(snapshot)
        payload["events"][0]["rating"] = "again"
        commit = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(commit.status_code, 200, commit.get_json())

        with self.app.app_context():
            source_note = db.session.get(Note, source_note_id)
            self.assertEqual(source_note.tags, [])
            event = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).one()
            self.assertEqual(event.deck_id, local_deck_id)
            progress = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=source_card_id,
            ).one()
            self.assertTrue(progress.is_suspended)


if __name__ == "__main__":
    unittest.main()
