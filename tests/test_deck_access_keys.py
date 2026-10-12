"""Unit and integration tests for Deck Access Keys & Classroom Licensing."""

from datetime import datetime, timedelta
import unittest

from app import create_app
from models import db
from models.creator_feature_policy import CreatorFeaturePolicy
from models.deck import Deck
from models.deck_access_key import DeckAccessKey
from models.deck_access_key_redemption import DeckAccessKeyRedemption
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from models.user_role import UserRole
from tests.study_note_fixtures import attach_template, create_note_user
from app.services import creator_key_entitlement_service, deck_access_key_service


class DeckAccessKeysTests(unittest.TestCase):
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

            creator_role = UserRole.query.filter_by(code="creator").first()

            # Create Teacher / Creator user
            creator = create_note_user(
                db.session,
                username="sensei",
                email="sensei@example.com",
                is_admin=False,
                role_id=creator_role.id if creator_role else None,
                balance_amount_minor=50000,
            )
            creator.set_password("password123")

            # Create Student 1
            student1 = create_note_user(
                db.session,
                username="student1",
                email="student1@example.com",
                is_admin=False,
            )
            student1.set_password("password123")

            # Create Student 2
            student2 = create_note_user(
                db.session,
                username="student2",
                email="student2@example.com",
                is_admin=False,
            )
            student2.set_password("password123")

            self.creator_id = creator.id
            self.student1_id = student1.id
            self.student2_id = student2.id

            # Create NoteType
            note_type = NoteType(
                name="Japanese Vocab",
                description="Standard Japanese Vocab",
                user_id=creator.id,
                publish_status="published",
            )
            db.session.add(note_type)
            db.session.flush()

            field_word = FieldDef(note_type_id=note_type.id, name="Word", position=1)
            field_meaning = FieldDef(note_type_id=note_type.id, name="Meaning", position=2)
            template = attach_template(
                db.session,
                owner_user_id=creator.id,
                note_type_id=note_type.id,
                name="Card 1",
                front_html="<div>{{Word}}</div>",
                back_html="<div>{{FrontSide}}<hr>{{Meaning}}</div>",
                position=1,
            )
            db.session.add_all([field_word, field_meaning])

            # Create Deck
            deck = Deck(
                name="Minna no Nihongo Lesson 1",
                description="Classroom deck",
                owner_user_id=creator.id,
                note_type_id=note_type.id,
            )
            db.session.add(deck)
            db.session.flush()


            # Create Note
            note = Note(
                note_type_id=note_type.id,
                user_id=creator.id,
                deck_id=deck.id,
                field_values={"Word": "私", "Meaning": "I, me"},
                tags=["N5"],
            )
            db.session.add(note)
            db.session.flush()

            # Create DeckMarketplaceItem (unlisted / classroom)
            deck_item = DeckMarketplaceItem(
                owner_user_id=creator.id,
                source_deck_id=deck.id,
                source_note_type_id=note_type.id,
                title="Minna no Nihongo Lesson 1 - N5",
                description="Exclusive classroom deck for Sensei's class",
                primary_category="Vocabulary",
                publish_status="unlisted",
                pricing_mode="free",
                version="1.0.0",
                sample_cards_count=1,
            )
            db.session.add(deck_item)
            db.session.flush()

            # Release
            release = DeckRelease(
                deck_item_id=deck_item.id,
                sequence_no=1,
                version_label="1.0.0",
                status="published",
                created_by_user_id=creator.id,
            )
            db.session.add(release)
            db.session.flush()
            deck_item.current_release_id = release.id

            db.session.commit()

            self.deck_id = deck.id
            self.deck_item_id = deck_item.id
            self.note_type_id = note_type.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, email: str):
        self.client.delete("/api/session")
        res = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(res.status_code, 200, res.get_json())



    def test_creator_create_and_list_keys(self):
        self._login("sensei@example.com")

        # Create single key
        res = self.client.post(
            f"/api/creator/decks/{self.deck_item_id}/keys",
            json={
                "count": 1,
                "label": "Lớp N5 Khóa 1",
                "max_uses": 25,
                "access_duration_days": 90,
            },
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("created_count"), 1)
        key = data["keys"][0]
        self.assertTrue(key["key_code"].startswith("FLM-"))
        self.assertEqual(key["label"], "Lớp N5 Khóa 1")
        self.assertEqual(key["max_uses"], 25)
        self.assertEqual(key["used_count"], 0)
        self.assertEqual(key["access_duration_days"], 90)
        self.assertEqual(key["status"], "active")

        # Create batch keys
        res_batch = self.client.post(
            f"/api/creator/decks/{self.deck_item_id}/keys",
            json={
                "count": 3,
                "label": "Học viên VIP",
                "max_uses": 1,
            },
        )
        self.assertEqual(res_batch.status_code, 201)
        batch_data = res_batch.get_json()
        self.assertEqual(batch_data.get("created_count"), 3)

        # List all keys for deck
        res_list = self.client.get(f"/api/creator/decks/{self.deck_item_id}/keys")
        self.assertEqual(res_list.status_code, 200)
        keys_list = res_list.get_json().get("keys", [])
        self.assertEqual(len(keys_list), 4)

    def test_creator_update_and_revoke_key(self):
        self._login("sensei@example.com")

        # Create key
        res = self.client.post(
            f"/api/creator/decks/{self.deck_item_id}/keys",
            json={"count": 1, "label": "Test Revoke", "max_uses": 5},
        )
        key_id = res.get_json()["keys"][0]["id"]

        # Revoke key
        patch_res = self.client.patch(
            f"/api/creator/keys/{key_id}",
            json={"status": "revoked", "label": "Tạm dừng lớp"},
        )
        self.assertEqual(patch_res.status_code, 200)
        updated_key = patch_res.get_json()["key"]
        self.assertEqual(updated_key["status"], "revoked")
        self.assertEqual(updated_key["label"], "Tạm dừng lớp")

        # Reactivate key
        patch_res2 = self.client.patch(
            f"/api/creator/keys/{key_id}",
            json={"status": "active"},
        )
        self.assertEqual(patch_res2.status_code, 200)
        self.assertEqual(patch_res2.get_json()["key"]["status"], "active")

    def test_validate_key_endpoint(self):
        # Create key as creator
        self._login("sensei@example.com")
        res = self.client.post(
            f"/api/creator/decks/{self.deck_item_id}/keys",
            json={"count": 1, "label": "Validation test", "max_uses": 10, "access_duration_days": 60},
        )
        key_code = res.get_json()["keys"][0]["key_code"]
        key_id = res.get_json()["keys"][0]["id"]

        # Validate as student
        self._login("student1@example.com")
        val_res = self.client.post(
            "/api/marketplace/keys/validate",
            json={"key_code": key_code},
        )
        self.assertEqual(val_res.status_code, 200)
        val_data = val_res.get_json()
        self.assertTrue(val_data.get("valid"))
        self.assertEqual(val_data.get("title"), "Minna no Nihongo Lesson 1 - N5")
        self.assertEqual(val_data.get("author"), "sensei")
        self.assertEqual(val_data.get("access_duration_days"), 60)
        self.assertFalse(val_data.get("already_installed"))

        # Revoke the key
        self._login("sensei@example.com")
        self.client.patch(f"/api/creator/keys/{key_id}", json={"status": "revoked"})

        # Validate revoked key as student
        self._login("student1@example.com")
        val_revoked = self.client.post(
            "/api/marketplace/keys/validate",
            json={"key_code": key_code},
        )
        self.assertEqual(val_revoked.status_code, 400)
        self.assertFalse(val_revoked.get_json().get("valid"))

    def test_student_redeem_key_and_install_deck(self):
        # 1. Creator generates key
        self._login("sensei@example.com")
        res = self.client.post(
            f"/api/creator/decks/{self.deck_item_id}/keys",
            json={"count": 1, "label": "Student 1 key", "max_uses": 2, "access_duration_days": 30},
        )
        key_code = res.get_json()["keys"][0]["key_code"]
        key_id = res.get_json()["keys"][0]["id"]

        # 2. Student 1 redeems key
        self._login("student1@example.com")
        redeem_res = self.client.post(
            "/api/marketplace/keys/redeem",
            json={"key_code": key_code},
        )
        self.assertEqual(redeem_res.status_code, 200, redeem_res.get_json())
        redeem_data = redeem_res.get_json()
        self.assertTrue(redeem_data.get("success"))
        self.assertFalse(redeem_data.get("already_installed"))
        self.assertIsNotNone(redeem_data.get("installed_deck_id"))

        # Check DeckInstall exists in DB for student 1
        with self.app.app_context():
            install = DeckInstall.query.filter_by(
                deck_item_id=self.deck_item_id,
                user_id=self.student1_id,
            ).first()
            self.assertIsNotNone(install)

            redemption = DeckAccessKeyRedemption.query.filter_by(
                key_id=key_id,
                user_id=self.student1_id,
            ).first()
            self.assertIsNotNone(redemption)
            self.assertEqual(redemption.status, "active")
            self.assertIsNotNone(redemption.access_expires_at)

            # Check key used_count incremented
            key_obj = db.session.get(DeckAccessKey, key_id)
            self.assertEqual(key_obj.used_count, 1)

        # 3. Creator checks redemptions list
        self._login("sensei@example.com")
        redemptions_res = self.client.get(f"/api/creator/keys/{key_id}/redemptions")
        self.assertEqual(redemptions_res.status_code, 200)
        r_data = redemptions_res.get_json()
        self.assertEqual(r_data["total_count"], 1)
        self.assertEqual(r_data["items"][0]["username"], "student1")

    def test_exhausted_max_uses_limit(self):
        # Key with max_uses = 1
        self._login("sensei@example.com")
        res = self.client.post(
            f"/api/creator/decks/{self.deck_item_id}/keys",
            json={"count": 1, "max_uses": 1},
        )
        key_code = res.get_json()["keys"][0]["key_code"]

        # Student 1 redeems successfully
        self._login("student1@example.com")
        r1 = self.client.post("/api/marketplace/keys/redeem", json={"key_code": key_code})
        self.assertEqual(r1.status_code, 200)

        # Student 2 tries to redeem the same key -> fails because max_uses reached
        self._login("student2@example.com")
        r2 = self.client.post("/api/marketplace/keys/redeem", json={"key_code": key_code})
        self.assertEqual(r2.status_code, 400)
        self.assertIn("hết lượt sử dụng", r2.get_json().get("message", ""))

    def test_owner_cannot_redeem_own_key(self):
        self._login("sensei@example.com")
        res = self.client.post(
            f"/api/creator/decks/{self.deck_item_id}/keys",
            json={"count": 1},
        )
        key_code = res.get_json()["keys"][0]["key_code"]

        # Sensei tries to redeem their own key
        r = self.client.post("/api/marketplace/keys/redeem", json={"key_code": key_code})
        self.assertEqual(r.status_code, 400)
        self.assertIn("tác giả của bộ thẻ", r.get_json().get("message", ""))

    def test_stealth_monetization_zero_fee_default_and_future_admin_switch(self):
        with self.app.app_context():
            # Default launch phase: 0 fee, allowed
            allowed, err, fee = creator_key_entitlement_service.check_creator_can_issue_keys(
                creator_user_id=self.creator_id,
                requested_count=50,
            )
            self.assertTrue(allowed)
            self.assertIsNone(err)
            self.assertEqual(fee, 0)

            # Future: Admin enables monetization (e.g. 5 free keys, 1,000 VND per key thereafter)
            creator_key_entitlement_service.update_creator_feature_policy(
                feature_code="deck_access_keys",
                is_monetized=True,
                free_quota_per_creator=5,
                price_per_key_minor=1000,
            )

            # Creator requests 3 keys (total <= 5 free quota) -> allowed with 0 fee
            allowed_quota, _, fee_quota = creator_key_entitlement_service.check_creator_can_issue_keys(
                creator_user_id=self.creator_id,
                requested_count=3,
            )
            self.assertTrue(allowed_quota)
            self.assertEqual(fee_quota, 0)

            # Creator requests 10 keys (exceeds free quota by 5) -> fee = 5,000 VND, allowed if balance sufficient
            allowed_paid, _, fee_paid = creator_key_entitlement_service.check_creator_can_issue_keys(
                creator_user_id=self.creator_id,
                requested_count=10,
            )
            self.assertTrue(allowed_paid)
            self.assertEqual(fee_paid, 5000)
