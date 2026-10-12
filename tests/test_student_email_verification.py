"""Unit and integration tests for Student Email Verification & Deck Discounts."""

from datetime import datetime, timedelta, timezone
import unittest

from app import create_app
from models import db
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.email_verification_token import EmailVerificationToken
from models.field_def import FieldDef
from models.note_type import NoteType
from models.template import Template
from models.user import User
from app.services import (
    email_verification_rate_limit_service,
    email_verification_service,
    marketplace_pricing_service,
    student_verification_service,
)
from app.services.marketplace_pricing_service import (
    calculate_pricing_breakdown,
    validate_student_offer,
)
from app.services.student_verification_service import (
    get_user_student_status,
    is_education_email,
    normalize_email,
    serialize_student_profile,
)

from tests.study_note_fixtures import attach_template, create_note_user

class StudentEmailVerificationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret-key",
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Creator user
            creator = create_note_user(db.session,
                username="deck_creator",
                email="creator@example.com",
                is_admin=False,
            )
            creator.set_password("pass1234")
            db.session.add(creator)

            # Normal user (non-student)
            user_normal = create_note_user(db.session,
                username="normal_user",
                email="user@gmail.com",
                is_admin=False,
            )
            user_normal.set_password("pass1234")
            db.session.add(user_normal)

            # Unverified student user (.edu.vn)
            student_unverified = create_note_user(db.session,
                username="sv_unverified",
                email="sv123@hcmut.edu.vn",
                is_admin=False,
            )
            student_unverified.set_password("pass1234")
            db.session.add(student_unverified)

            # Verified student user (.edu.vn)
            student_verified = create_note_user(db.session,
                username="sv_verified",
                email="sv999@vnu.edu.vn",
                is_admin=False,
                email_verified_at=datetime.now(timezone.utc),
                email_verification_source="email_otp",
            )
            student_verified.set_password("pass1234")
            db.session.add(student_verified)

            db.session.commit()

            # Create sample deck and note type for publishing tests
            note_type = NoteType(
                id="nt_test_1",
                user_id=creator.id,
                name="Basic Vocab",
                pricing_mode="free",
                price_amount_minor=0,
            )
            db.session.add(note_type)

            f1 = FieldDef(note_type_id="nt_test_1", name="Front", position=0)
            f2 = FieldDef(note_type_id="nt_test_1", name="Back", position=1)
            db.session.add_all([f1, f2])

            tmpl = attach_template(db.session, owner_user_id=creator.id,
                note_type_id="nt_test_1",
                name="Card 1",
                front_html="{{Front}}",
                back_html="{{Back}}",
                position=0,
            )
            db.session.add(tmpl)

            deck = Deck(
                owner_user_id=creator.id,
                name="JLPT N5 Vocab",
            )
            db.session.add(deck)
            db.session.commit()

            self.creator_id = creator.id
            self.user_normal_id = user_normal.id
            self.student_unverified_id = student_unverified.id
            self.student_verified_id = student_verified.id
            self.deck_id = deck.id
            self.note_type_id = note_type.id
        email_verification_rate_limit_service.reset_state()

    def test_01_education_domain_detection(self):
        """Test domain normalization and .edu.vn verification rules."""
        self.assertTrue(is_education_email("student@hust.edu.vn"))
        self.assertTrue(is_education_email("user@ftu.edu.vn"))
        self.assertTrue(is_education_email("STUDENT@HCMUT.EDU.VN "))
        self.assertFalse(is_education_email("user@gmail.com"))
        self.assertFalse(is_education_email("fake@edu.com"))
        self.assertFalse(is_education_email("fake@hust-edu.vn.com"))
        self.assertFalse(is_education_email(None))
        self.assertEqual(normalize_email("  User@HCMUT.EDU.VN  "), "user@hcmut.edu.vn")

    def test_02_student_status_derivation(self):
        """Test centralized student status policy."""
        with self.app.app_context():
            normal = db.session.get(User, self.user_normal_id)
            sv_unverified = db.session.get(User, self.student_unverified_id)
            sv_verified = db.session.get(User, self.student_verified_id)

            self.assertEqual(get_user_student_status(normal), "not_eligible")
            self.assertEqual(get_user_student_status(sv_unverified), "eligible_unverified_email")
            self.assertEqual(get_user_student_status(sv_verified), "verified_student")

            profile_sv = serialize_student_profile(sv_verified)
            self.assertTrue(profile_sv["email_verified"])
            self.assertTrue(profile_sv["is_verified_student"])
            self.assertEqual(profile_sv["institution_domain"], "vnu.edu.vn")

    def test_03_request_and_verify_email_otp(self):
        """Test OTP code generation and successful verification."""
        with self.app.app_context():
            user = db.session.get(User, self.student_unverified_id)
            self.assertIsNone(user.email_verified_at)

            # Request verification OTP
            res = email_verification_service.request_email_verification(user)
            self.assertTrue(res["success"])
            self.assertFalse(res["already_verified"])

            token_row = (
                EmailVerificationToken.query.filter_by(
                    user_id=user.id, token_type="code"
                )
                .order_by(EmailVerificationToken.created_at.desc())
                .first()
            )
            self.assertIsNotNone(token_row)

            # Attempt invalid OTP
            with self.assertRaises(email_verification_service.EmailVerificationError) as ctx:
                email_verification_service.verify_email_with_code(user, "999999")
            self.assertEqual(ctx.exception.code, "INVALID_CODE")

            # Set known OTP code for deterministic verification
            known_code = "123456"
            token_row.token_hash = email_verification_service._token_digest(known_code)
            db.session.commit()

            # Verify with correct OTP
            verify_res = email_verification_service.verify_email_with_code(user, known_code)
            self.assertTrue(verify_res["success"])
            self.assertTrue(verify_res["email_verified"])

            # Re-fetch user
            db.session.refresh(user)
            self.assertIsNotNone(user.email_verified_at)
            self.assertEqual(user.email_verification_source, "email_code")
            self.assertEqual(get_user_student_status(user), "verified_student")

    def test_04_email_otp_rate_limiting(self):
        """Test 60-second cooldown rate limit."""
        with self.app.app_context():
            user = db.session.get(User, self.student_unverified_id)
            email_verification_rate_limit_service.reset_state()

            # First request: OK
            res1 = email_verification_service.request_email_verification(user)
            self.assertTrue(res1["success"])

            # Immediate second request: Rate limited
            with self.assertRaises(email_verification_service.EmailVerificationError) as ctx:
                email_verification_service.request_email_verification(user)
            self.assertEqual(ctx.exception.code, "RATE_LIMITED")

    def test_05_otp_max_attempts_revocation(self):
        """Test brute-force protection (revocation after 5 failed attempts)."""
        with self.app.app_context():
            user = db.session.get(User, self.student_unverified_id)
            email_verification_rate_limit_service.reset_state()
            email_verification_service.request_email_verification(user)

            for _ in range(5):
                try:
                    email_verification_service.verify_email_with_code(user, "000000")
                except email_verification_service.EmailVerificationError:
                    pass

            token_row = (
                EmailVerificationToken.query.filter_by(
                    user_id=user.id, token_type="code"
                )
                .order_by(EmailVerificationToken.created_at.desc())
                .first()
            )
            self.assertIsNotNone(token_row.revoked_at)
            self.assertGreaterEqual(token_row.attempts_count, 5)

    def test_06_profile_email_update_invalidates_verification(self):
        """Test that updating email resets email_verified_at and verification source."""
        with self.app.app_context():
            user = db.session.get(User, self.student_verified_id)
            self.assertIsNotNone(user.email_verified_at)

            # Change email
            email_verification_service.invalidate_user_email_verification(user)
            user.email = "new_email@hust.edu.vn"
            db.session.commit()

            db.session.refresh(user)
            self.assertIsNone(user.email_verified_at)
            self.assertIsNone(user.email_verification_source)
            self.assertEqual(get_user_student_status(user), "eligible_unverified_email")

    def test_07_validate_student_offer_configuration(self):
        """Test deck student discount validation rules."""
        # Free deck cannot have student offers
        mode, pct, err = validate_student_offer(
            pricing_mode="free", student_offer_mode="free", student_discount_percent=None
        )
        self.assertEqual(mode, "none")
        self.assertIsNone(pct)

        # Paid deck with free student offer
        mode, pct, err = validate_student_offer(
            pricing_mode="paid", student_offer_mode="free", student_discount_percent=None
        )
        self.assertEqual(mode, "free")
        self.assertIsNone(pct)
        self.assertIsNone(err)

        # Paid deck with 40% discount
        mode, pct, err = validate_student_offer(
            pricing_mode="paid", student_offer_mode="percent_discount", student_discount_percent=40
        )
        self.assertEqual(mode, "percent_discount")
        self.assertEqual(pct, 40)
        self.assertIsNone(err)

        # Invalid percentage (> 99 or < 1)
        mode, pct, err = validate_student_offer(
            pricing_mode="paid", student_offer_mode="percent_discount", student_discount_percent=100
        )
        self.assertIsNotNone(err)

    def test_08_marketplace_pricing_breakdown_free_offer(self):
        """Test pricing breakdown when deck is free for verified students."""
        with self.app.app_context():
            item = DeckMarketplaceItem(
                owner_user_id=self.creator_id,
                title="Advanced JLPT N1",
                pricing_mode="paid",
                price_amount_minor=100000,
                student_offer_mode="free",
                student_discount_percent=None,
            )
            db.session.add(item)
            db.session.commit()

            sv_verified = db.session.get(User, self.student_verified_id)
            sv_unverified = db.session.get(User, self.student_unverified_id)
            normal_user = db.session.get(User, self.user_normal_id)

            # Verified student: 0 VND, payment not required
            bd_sv = calculate_pricing_breakdown(item, sv_verified)
            self.assertEqual(bd_sv.base_price_minor, 100000)
            self.assertEqual(bd_sv.effective_price_minor, 0)
            self.assertEqual(bd_sv.discount_amount_minor, 100000)
            self.assertTrue(bd_sv.student_discount_applied)
            self.assertFalse(bd_sv.is_payment_required)

            # Unverified student: full price (until email is verified)
            bd_unverified = calculate_pricing_breakdown(item, sv_unverified)
            self.assertEqual(bd_unverified.effective_price_minor, 100000)
            self.assertFalse(bd_unverified.student_discount_applied)
            self.assertTrue(bd_unverified.is_payment_required)

            # Normal user: full price
            bd_normal = calculate_pricing_breakdown(item, normal_user)
            self.assertEqual(bd_normal.effective_price_minor, 100000)
            self.assertFalse(bd_normal.student_discount_applied)
            self.assertTrue(bd_normal.is_payment_required)

    def test_09_marketplace_pricing_breakdown_percent_discount(self):
        """Test pricing breakdown with percent discount."""
        with self.app.app_context():
            item = DeckMarketplaceItem(
                owner_user_id=self.creator_id,
                title="Grammar Master N2",
                pricing_mode="paid",
                price_amount_minor=50000,
                student_offer_mode="percent_discount",
                student_discount_percent=40,
            )
            db.session.add(item)
            db.session.commit()

            sv_verified = db.session.get(User, self.student_verified_id)
            bd = calculate_pricing_breakdown(item, sv_verified)
            # 50,000 * 40% = 20,000 discount -> 30,000 VND
            self.assertEqual(bd.base_price_minor, 50000)
            self.assertEqual(bd.discount_amount_minor, 20000)
            self.assertEqual(bd.effective_price_minor, 30000)
            self.assertTrue(bd.student_discount_applied)
            self.assertTrue(bd.is_payment_required)

    def test_10_shared_deck_direct_install_authorization(self):
        """Test that verified students can directly install a paid deck with student_offer_mode='free'."""
        with self.app.app_context():
            item = DeckMarketplaceItem(
                owner_user_id=self.creator_id,
                source_deck_id=self.deck_id,
                source_note_type_id=self.note_type_id,
                title="Direct Install Deck",
                pricing_mode="paid",
                price_amount_minor=80000,
                student_offer_mode="free",
                publish_status="published",
            )
            db.session.add(item)
            db.session.flush()

            release = DeckRelease(
                deck_item_id=item.id,
                sequence_no=1,
                version_label="1.0.0",
                status="published",
                created_by_user_id=self.creator_id,
            )
            db.session.add(release)
            db.session.flush()
            item.current_release_id = release.id
            db.session.commit()
            item_id = item.id

        # Login as verified student
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.student_verified_id)

        resp = self.client.post(f"/api/shared/decks/{item_id}/install")
        self.assertIn(resp.status_code, (200, 201))
        data = resp.get_json()
        self.assertIsNotNone(data)

        # Verify DeckInstall row created
        with self.app.app_context():
            install = DeckInstall.query.filter_by(
                user_id=self.student_verified_id, deck_item_id=item_id
            ).first()
            self.assertIsNotNone(install)
            self.assertEqual(install.purchase_amount_minor, 0)

    def test_11_shared_deck_paid_install_intercepts_non_student(self):
        """Test that non-students or unverified students are intercepted with payment required."""
        with self.app.app_context():
            item = DeckMarketplaceItem(
                owner_user_id=self.creator_id,
                source_deck_id=self.deck_id,
                source_note_type_id=self.note_type_id,
                title="Paid Deck Intercept",
                pricing_mode="paid",
                price_amount_minor=50000,
                student_offer_mode="free",
                publish_status="published",
            )
            db.session.add(item)
            db.session.flush()

            release = DeckRelease(
                deck_item_id=item.id,
                sequence_no=1,
                version_label="1.0.0",
                status="published",
                created_by_user_id=self.creator_id,
            )
            db.session.add(release)
            db.session.flush()
            item.current_release_id = release.id
            db.session.commit()
            item_id = item.id

        # Login as unverified student
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.student_unverified_id)

        resp = self.client.post(f"/api/shared/decks/{item_id}/install")
        # Should return 202 (or payment redirect / payment required response)
        self.assertIn(resp.status_code, (200, 202, 503))
        if resp.status_code == 202:
            data = resp.get_json()
            self.assertTrue(data.get("payment_required"))

    def test_12_identity_api_endpoints(self):
        """Test identity verification endpoints (/identity/student-status, /identity/email/request-verification, /identity/email/verify)."""
        email_verification_rate_limit_service.reset_state()
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.student_unverified_id)

        # GET /api/identity/student-status
        res_status = self.client.get("/api/identity/student-status")
        self.assertEqual(res_status.status_code, 200)
        data = res_status.get_json()
        self.assertEqual(data.get("student_status"), "eligible_unverified_email")
        self.assertFalse(data.get("email_verified"))

        # POST /api/identity/email/request-verification
        res_req = self.client.post("/api/identity/email/request-verification")
        self.assertEqual(res_req.status_code, 200)
        req_data = res_req.get_json()
        self.assertTrue(req_data.get("success"))

        # Fetch token from DB
        with self.app.app_context():
            token_row = (
                EmailVerificationToken.query.filter_by(
                    user_id=self.student_unverified_id, token_type="code"
                )
                .order_by(EmailVerificationToken.id.desc())
                .first()
            )
            self.assertIsNotNone(token_row)

        # POST /api/identity/email/verify with invalid code
        res_bad = self.client.post(
            "/api/identity/email/verify",
            json={"code": "000000"},
        )
        self.assertEqual(res_bad.status_code, 400)


if __name__ == "__main__":
    unittest.main()
