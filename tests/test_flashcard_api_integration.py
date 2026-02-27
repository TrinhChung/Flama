"""Integration tests for flashcard API CRUD, preview, and study."""

import io
import re
import unittest

from app import create_app
from models import db
from models.flashcard_entries import Card, DeckInstall, DeckMarketplaceItem, Note
from models.user import User
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_progress import VocabularyProgress


class FlashcardApiIntegrationTests(unittest.TestCase):
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
            user = User(username="admin", email="admin@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = VocabularyDeck(name="Deck A")
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "admin@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_note_type(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "Japanese Vocabulary",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Reading", "field_type": "text", "position": 1, "required": False},
                    {"name": "Meaning", "field_type": "richtext", "position": 2, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}} - {{Reading}} {{{Meaning}}}</div>",
                    "shared_css": ".card{color:red;}",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def _collect_subtree_ids(self, root_deck_id: int) -> list[int]:
        seen: set[int] = set()
        frontier: set[int] = {int(root_deck_id)}
        while frontier:
            current = {deck_id for deck_id in frontier if deck_id not in seen}
            if not current:
                break
            seen.update(current)
            child_rows = (
                db.session.query(VocabularyDeck.id)
                .filter(VocabularyDeck.parent_id.in_(current))
                .all()
            )
            frontier = {int(row[0]) for row in child_rows if row and row[0] is not None}
        return sorted(seen)

    def test_crud_preview_flow(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        template_id = note_type["templates"][0]["id"]

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "<b>dog</b>",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        preview_resp = self.client.post(
            f"/api/note-types/{note_type_id}/templates/{template_id}/preview",
            json={"note_id": note_id},
        )
        self.assertEqual(preview_resp.status_code, 200)
        preview = preview_resp.get_json()
        self.assertIn("\u72ac", preview["front_html"])
        self.assertIn("\u3044\u306c", preview["back_html"])
        self.assertIn("<b>dog</b>", preview["back_html"])

    def test_preview_sample_mode_uses_field_name_dump_and_image_placeholder(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "Preview Sample",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Illustration", "field_type": "image", "position": 1, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>{{{Illustration}}}",
                    "back_html": "<div>{{Word}}</div>",
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        note_type = response.get_json()
        note_type_id = note_type["id"]
        template_id = note_type["templates"][0]["id"]

        preview_resp = self.client.post(
            f"/api/note-types/{note_type_id}/templates/{template_id}/preview",
            json={"use_sample_data": True},
        )
        self.assertEqual(preview_resp.status_code, 200)
        preview = preview_resp.get_json()
        self.assertIn("Word", preview["front_html"])
        self.assertIn("fc-preview-media-box", preview["front_html"])
        self.assertIn("[Image: Illustration]", preview["front_html"])

    def test_shared_deck_preview_uses_first_note_from_source_deck(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        template_id = note_type["templates"][0]["id"]

        first_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(first_note_resp.status_code, 201)

        second_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )
        self.assertEqual(second_note_resp.status_code, 201)

        with self.app.app_context():
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=None,
                title="Shared Deck A",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        detail_resp = self.client.get(f"/api/shared/decks/{deck_item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.get_json()
        self.assertEqual(detail_payload["source_note_type_id"], note_type_id)
        self.assertIsNotNone(detail_payload.get("source_note_type"))
        self.assertTrue((detail_payload["source_note_type"].get("templates") or []))
        test_samples = detail_payload.get("test_samples") or []
        self.assertEqual(len(test_samples), 2)
        self.assertEqual(detail_payload.get("test_sample_limit"), 5)
        sampled_words = {sample.get("word") for sample in test_samples}
        self.assertIn("\u72ac", sampled_words)
        self.assertIn("\u732b", sampled_words)

        preview_resp = self.client.post(
            f"/api/shared/decks/{deck_item_id}/templates/{template_id}/preview",
            json={},
        )
        self.assertEqual(preview_resp.status_code, 200)
        preview = preview_resp.get_json()
        self.assertIn("\u72ac", preview["front_html"])
        self.assertIn("\u3044\u306c", preview["back_html"])
        self.assertNotIn("\u306d\u3053", preview["back_html"])

        selected_cat = next((row for row in test_samples if row.get("word") == "\u732b"), None)
        self.assertIsNotNone(selected_cat)
        self.assertIsNotNone(selected_cat.get("note_id"))
        selected_preview_resp = self.client.post(
            f"/api/shared/decks/{deck_item_id}/templates/{template_id}/preview",
            json={"note_id": selected_cat.get("note_id")},
        )
        self.assertEqual(selected_preview_resp.status_code, 200)
        selected_preview = selected_preview_resp.get_json()
        self.assertIn("\u732b", selected_preview["front_html"])
        self.assertIn("\u306d\u3053", selected_preview["back_html"])

    def test_shared_deck_preview_requires_source_note_type_when_notes_missing(self):
        with self.app.app_context():
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=None,
                title="Shared Deck Entries Only",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        detail_resp = self.client.get(f"/api/shared/decks/{deck_item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.get_json()
        self.assertIsNone(detail_payload.get("source_note_type"))
        self.assertEqual(detail_payload.get("test_samples"), [])

        preview_resp = self.client.post(
            f"/api/shared/decks/{deck_item_id}/templates/unknown-template/preview",
            json={},
        )
        self.assertEqual(preview_resp.status_code, 409)
        self.assertIn("no notes", (preview_resp.get_json() or {}).get("message", "").lower())

    def test_shared_deck_install_clones_subtree_notes_and_cards(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            child_deck = VocabularyDeck(name="Installed Child", parent_id=self.deck_id)
            db.session.add(child_deck)
            db.session.flush()
            child_deck_id = child_deck.id
            db.session.commit()

        owner_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": child_deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(owner_note_resp.status_code, 201)

        with self.app.app_context():
            learner = User(username="learner", email="learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            learner_id = learner.id

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Install Clone",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "learner@example.com", "password": "password"},
            follow_redirects=True,
        )

        install_resp = learner_client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_resp.status_code, 201)
        install_payload = install_resp.get_json()
        installed_root_id = install_payload.get("installed_deck_id")
        self.assertIsNotNone(installed_root_id)

        with self.app.app_context():
            install_row = DeckInstall.query.filter_by(deck_item_id=deck_item_id, user_id=learner_id).first()
            self.assertIsNotNone(install_row)
            subtree_ids = self._collect_subtree_ids(int(installed_root_id))
            cloned_notes = Note.query.filter(
                Note.user_id == learner_id,
                Note.deck_id.in_(subtree_ids),
            ).all()
            self.assertEqual(len(cloned_notes), 1)
            cloned_note_ids = [row.id for row in cloned_notes]
            cloned_cards = Card.query.filter(Card.note_id.in_(cloned_note_ids)).all()
            self.assertTrue(cloned_cards)

        next_resp = learner_client.get(f"/api/study/next?scope=deck&scope_id={installed_root_id}")
        self.assertEqual(next_resp.status_code, 200)
        next_payload = next_resp.get_json()
        self.assertIsNotNone(next_payload.get("card_id"))
        self.assertIn("\u72ac", next_payload.get("rendered_front_html", ""))

    def test_dashboard_for_installed_deck_includes_child_deck_rows(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            child_deck = VocabularyDeck(name="Visible Child Deck", parent_id=self.deck_id)
            db.session.add(child_deck)
            db.session.flush()
            child_deck_id = child_deck.id
            db.session.commit()

        owner_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": child_deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )
        self.assertEqual(owner_note_resp.status_code, 201)

        with self.app.app_context():
            learner = User(username="viewer", email="viewer@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Dashboard Child Visibility",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        viewer_client = self.app.test_client()
        viewer_client.post(
            "/login",
            data={"email": "viewer@example.com", "password": "password"},
            follow_redirects=True,
        )
        install_resp = viewer_client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_resp.status_code, 201)

        dashboard_resp = viewer_client.get("/dashboard")
        self.assertEqual(dashboard_resp.status_code, 200)
        dashboard_html = dashboard_resp.get_data(as_text=True)
        self.assertIn("Deck A", dashboard_html)
        self.assertIn("Visible Child Deck", dashboard_html)

    def test_dashboard_counts_include_imported_note_cards(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        create_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(create_note_resp.status_code, 201)

        dashboard_resp = self.client.get("/dashboard")
        self.assertEqual(dashboard_resp.status_code, 200)
        dashboard_html = dashboard_resp.get_data(as_text=True)

        pattern = re.compile(
            r'data-node-name="Deck A".*?<span class="stat-num stat-new">(\d+)</span>\s*<span class="stat-num stat-learn">(\d+)</span>\s*<span class="stat-num stat-due">(\d+)</span>',
            re.S,
        )
        match = pattern.search(dashboard_html)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 1)

    def test_vocabulary_study_deck_renders_note_card_source(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        create_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(create_note_resp.status_code, 201)

        study_resp = self.client.get(f"/vocabulary/study/deck/{self.deck_id}")
        self.assertEqual(study_resp.status_code, 200)
        html = study_resp.get_data(as_text=True)
        self.assertIn('data-card-id="', html)
        self.assertIn('data-answer-url="', html)
        self.assertNotIn('data-entry-id="', html)

    def test_vocabulary_study_topic_route_is_removed(self):
        study_resp = self.client.get("/vocabulary/study/topic/1")
        self.assertEqual(study_resp.status_code, 410)

    def test_vocabulary_study_lesson_route_is_removed(self):
        study_resp = self.client.get("/vocabulary/study/lesson/1")
        self.assertEqual(study_resp.status_code, 410)

    def test_shared_deck_detail_returns_up_to_five_random_test_words(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        source_rows = [
            ("\u6d77", "\u3046\u307f", "bi\u1ec3n"),
            ("\u5c71", "\u3084\u307e", "n\u00fai"),
            ("\u7a7a", "\u305d\u3089", "tr\u1eddi"),
            ("\u5ddd", "\u304b\u308f", "s\u00f4ng"),
            ("\u68ee", "\u3082\u308a", "r\u1eebng"),
            ("\u96e8", "\u3042\u3081", "m\u01b0a"),
            ("\u98a8", "\u304b\u305c", "gi\u00f3"),
        ]

        for word, reading, translation_vi in source_rows:
            note_resp = self.client.post(
                "/api/notes",
                json={
                    "note_type_id": note_type_id,
                    "deck_id": self.deck_id,
                    "field_values": {
                        "Word": word,
                        "Reading": reading,
                        "Meaning": translation_vi,
                    },
                },
            )
            self.assertEqual(note_resp.status_code, 201)

        with self.app.app_context():
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Random Samples",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        detail_resp = self.client.get(f"/api/shared/decks/{deck_item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        payload = detail_resp.get_json()
        self.assertEqual(payload.get("test_sample_limit"), 5)

        samples = payload.get("test_samples") or []
        self.assertEqual(len(samples), 5)

        source_words = {row[0] for row in source_rows}
        for sample in samples:
            self.assertIn(sample.get("word"), source_words)
            self.assertIsNotNone(sample.get("note_id"))

    def test_shared_deck_detail_returns_all_test_words_when_less_than_five(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        source_rows = [
            ("\u706b", "\u3072", "l\u1eeda"),
            ("\u6c34", "\u307f\u305a", "n\u01b0\u1edbc"),
            ("\u571f", "\u3064\u3061", "\u0111\u1ea5t"),
        ]

        for word, reading, translation_vi in source_rows:
            note_resp = self.client.post(
                "/api/notes",
                json={
                    "note_type_id": note_type_id,
                    "deck_id": self.deck_id,
                    "field_values": {
                        "Word": word,
                        "Reading": reading,
                        "Meaning": translation_vi,
                    },
                },
            )
            self.assertEqual(note_resp.status_code, 201)

        with self.app.app_context():
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Small Samples",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        detail_resp = self.client.get(f"/api/shared/decks/{deck_item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        payload = detail_resp.get_json()

        samples = payload.get("test_samples") or []
        self.assertEqual(len(samples), 3)
        self.assertEqual(payload.get("test_sample_limit"), 5)

        source_words = {row[0] for row in source_rows}
        for sample in samples:
            self.assertIn(sample.get("word"), source_words)
            self.assertIsNotNone(sample.get("note_id"))

    def test_note_create_rejects_mixed_note_types_in_same_deck(self):
        note_type_a = self._create_note_type()
        note_type_a_id = note_type_a["id"]

        note_type_b_resp = self.client.post(
            "/api/note-types",
            json={
                "name": "Japanese Vocabulary Alt",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Reading", "field_type": "text", "position": 1, "required": False},
                    {"name": "Meaning", "field_type": "richtext", "position": 2, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}} - {{Reading}} {{{Meaning}}}</div>",
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(note_type_b_resp.status_code, 201)
        note_type_b_id = note_type_b_resp.get_json()["id"]

        first_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_a_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(first_note_resp.status_code, 201)

        second_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_b_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )
        self.assertEqual(second_note_resp.status_code, 400)
        self.assertIn("same template", second_note_resp.get_json().get("message", ""))

    def test_add_field_without_schema_change(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        field_resp = self.client.post(
            f"/api/note-types/{note_type_id}/fields",
            json={"name": "PitchAccent", "field_type": "text", "required": False},
        )
        self.assertEqual(field_resp.status_code, 201)

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u6a4b",
                    "Reading": "\u306f\u3057",
                    "Meaning": "bridge",
                    "PitchAccent": "L-H",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        detail_resp = self.client.get(f"/api/notes/{note_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.get_json()["field_values"]["PitchAccent"], "L-H")

    def test_study_next_and_answer(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )

        next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_resp.status_code, 200)
        payload = next_resp.get_json()
        self.assertIsNotNone(payload["card_id"])
        self.assertIn("\u732b", payload["rendered_front_html"])

        answer_resp = self.client.post(
            f"/api/study/{payload['card_id']}/answer",
            json={"rating": "good"},
        )
        self.assertEqual(answer_resp.status_code, 200)
        self.assertTrue(answer_resp.get_json()["success"])

        with self.app.app_context():
            progress = VocabularyProgress.query.filter_by(
                user_id=self.user_id,
                new_card_id=payload["card_id"],
            ).first()
            self.assertIsNotNone(progress)
            self.assertIn(progress.queue, {"learning", "review", "relearning", "new"})
            self.assertIsNotNone(progress.reps)

    def test_flashcard_import_parse_and_execute_upsert(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        parse_resp = self.client.post(
            "/api/flashcards/import/parse",
            data={
                "note_type_id": note_type_id,
                "delimiter_mode": "custom",
                "custom_delimiter": "|",
                "has_header": "1",
                "file": (
                    io.BytesIO(
                        "Word|Reading|Meaning\n犬|いぬ|dog\n猫|ねこ|cat\n".encode("utf-8")
                    ),
                    "bulk-import.txt",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(parse_resp.status_code, 200)
        parse_payload = parse_resp.get_json()
        self.assertTrue(parse_payload.get("token"))
        self.assertEqual(parse_payload.get("total_rows"), 2)

        execute_resp = self.client.post(
            "/api/flashcards/import/execute",
            json={
                "token": parse_payload["token"],
                "note_type_id": note_type_id,
                "target_deck_id": self.deck_id,
                "import_mode": "upsert",
                "uniqueness_fields": ["Word"],
                "mapping": parse_payload.get("suggested_mapping", {}),
                "dont_overwrite_empty": True,
                "confirm_column_mismatch": False,
            },
        )
        self.assertEqual(execute_resp.status_code, 200)
        result = execute_resp.get_json()
        summary = result.get("summary") or {}
        self.assertEqual(int(summary.get("inserted") or 0), 2)
        self.assertEqual(int(summary.get("updated") or 0), 0)
        self.assertEqual(int(summary.get("errors") or 0), 0)

        with self.app.app_context():
            note_count = Note.query.filter_by(user_id=self.user_id, note_type_id=note_type_id).count()
            card_count = (
                db.session.query(Card)
                .join(Note, Card.note_id == Note.id)
                .filter(Note.user_id == self.user_id, Note.note_type_id == note_type_id)
                .count()
            )
            self.assertEqual(note_count, 2)
            self.assertGreaterEqual(card_count, 2)

    def test_flashcard_import_update_only_respects_dont_overwrite_empty(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        create_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "犬",
                    "Reading": "いぬ",
                    "Meaning": "dog-old",
                },
            },
        )
        self.assertEqual(create_resp.status_code, 201)

        parse_resp = self.client.post(
            "/api/flashcards/import/parse",
            data={
                "note_type_id": note_type_id,
                "delimiter_mode": "csv",
                "has_header": "1",
                "file": (
                    io.BytesIO(
                        "Word,Reading,Meaning\n犬,,dog-new\n".encode("utf-8")
                    ),
                    "update.csv",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(parse_resp.status_code, 200)
        parse_payload = parse_resp.get_json()

        execute_resp = self.client.post(
            "/api/flashcards/import/execute",
            json={
                "token": parse_payload["token"],
                "note_type_id": note_type_id,
                "target_deck_id": self.deck_id,
                "import_mode": "update_only",
                "uniqueness_fields": ["Word"],
                "mapping": parse_payload.get("suggested_mapping", {}),
                "dont_overwrite_empty": True,
                "confirm_column_mismatch": False,
            },
        )
        self.assertEqual(execute_resp.status_code, 200)
        result = execute_resp.get_json()
        summary = result.get("summary") or {}
        self.assertEqual(int(summary.get("inserted") or 0), 0)
        self.assertEqual(int(summary.get("updated") or 0), 1)
        self.assertEqual(int(summary.get("errors") or 0), 0)

        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.user_id, note_type_id=note_type_id).first()
            self.assertIsNotNone(note)
            values = note.field_values or {}
            self.assertEqual(values.get("Word"), "犬")
            self.assertEqual(values.get("Reading"), "いぬ")
            self.assertEqual(values.get("Meaning"), "dog-new")

    def test_flashcard_import_insert_only_scoped_to_target_deck(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            deck_b = VocabularyDeck(name="Deck B")
            db.session.add(deck_b)
            db.session.commit()
            deck_b_id = deck_b.id

        existing_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "犬",
                    "Reading": "いぬ",
                    "Meaning": "dog-existing",
                },
            },
        )
        self.assertEqual(existing_note_resp.status_code, 201)

        parse_resp = self.client.post(
            "/api/flashcards/import/parse",
            data={
                "note_type_id": note_type_id,
                "delimiter_mode": "csv",
                "has_header": "1",
                "file": (
                    io.BytesIO("Word,Reading,Meaning\n犬,いぬ,dog-import\n".encode("utf-8")),
                    "insert-only.csv",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(parse_resp.status_code, 200)
        parse_payload = parse_resp.get_json()

        execute_resp = self.client.post(
            "/api/flashcards/import/execute",
            json={
                "token": parse_payload["token"],
                "note_type_id": note_type_id,
                "target_deck_id": deck_b_id,
                "import_mode": "insert_only",
                "uniqueness_fields": ["Word"],
                "mapping": parse_payload.get("suggested_mapping", {}),
                "dont_overwrite_empty": True,
                "confirm_column_mismatch": False,
            },
        )
        self.assertEqual(execute_resp.status_code, 200)
        result = execute_resp.get_json()
        summary = result.get("summary") or {}
        self.assertEqual(int(summary.get("inserted") or 0), 1)
        self.assertEqual(int(summary.get("skipped") or 0), 0)
        self.assertEqual(int(summary.get("errors") or 0), 0)

        with self.app.app_context():
            deck_a_count = Note.query.filter_by(
                user_id=self.user_id,
                note_type_id=note_type_id,
                deck_id=self.deck_id,
            ).count()
            deck_b_count = Note.query.filter_by(
                user_id=self.user_id,
                note_type_id=note_type_id,
                deck_id=deck_b_id,
            ).count()
            self.assertEqual(deck_a_count, 1)
            self.assertEqual(deck_b_count, 1)

    def test_flashcard_import_page_renders(self):
        response = self.client.get("/flashcards/import")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Step A - Upload & Parse", html)
        self.assertIn("Step D - Review & Execute", html)


if __name__ == "__main__":
    unittest.main()
