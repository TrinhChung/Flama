"""Unit and integration tests for Admin Analytics & Growth APIs."""

from datetime import datetime, timedelta, timezone
import unittest

from app import create_app
from models import db
from models.card import Card
from tests.study_note_fixtures import attach_template, archive_wire_alias
from models.study_application import StudyApplication
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.payment_order import PaymentOrder
from models.review_event import ReviewEvent
from models.user import User

UTC = timezone.utc


class AdminAnalyticsApiTests(unittest.TestCase):
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

            # Seed Admin and Regular User
            admin = User(
                username="analytics-admin",
                email="analytics-admin@example.com",
                is_admin=True,
            )
            admin.set_password("password")

            student = User(
                username="analytics-student",
                email="analytics-student@example.com",
                is_admin=False,
                created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2),
            )
            student.set_password("password")

            db.session.add_all([admin, student])
            db.session.commit()

            # Seed note type, deck, note, card
            note_type = NoteType(
                id="nt-analytics-1",
                user_id=admin.id,
                name="Basic Analytics Note",
            )
            deck = Deck(
                id=101,
                name="N5 Kanji Mastery",
                owner_user_id=admin.id,
            )
            db.session.add_all([note_type, deck])
            db.session.commit()

            from models.template import Template

            template = attach_template(db.session, owner_user_id=admin.id,
                id="tpl-analytics-1",
                note_type_id="nt-analytics-1",
                name="Card 1",
            )
            db.session.add(template)
            db.session.commit()

            note = Note(
                id="note-101",
                note_type_id="nt-analytics-1",
                user_id=student.id,
                deck_id=deck.id,
                field_values={"Front": "日", "Back": "Mặt trời, ngày"},
            )
            # Review history from before P11 names the Card by its legacy ID.
            db.session.add(note)
            db.session.flush()
            card = Card.query.filter_by(note_id=note.id).one()
            archive_wire_alias(db.session, card, "card-101")
            db.session.commit()

            # Seed Review Events for student
            now_naive = datetime.now(UTC).replace(tzinfo=None)
            rev1 = ReviewEvent(
                user_id=student.id,
                card_id="card-101",
                deck_id=deck.id,
                rating="good",
                mode="review",
                reviewed_at=now_naive - timedelta(hours=2),
                duration_ms=15000,  # 15s
            )
            rev2 = ReviewEvent(
                user_id=student.id,
                card_id="card-101",
                deck_id=deck.id,
                rating="easy",
                mode="review",
                reviewed_at=now_naive - timedelta(days=1, hours=1),
                duration_ms=25000,  # 25s
            )
            db.session.add_all([rev1, rev2])

            # Seed Payment Order
            order = PaymentOrder(
                id="order-101",
                user_id=student.id,
                merchant_order_code="FLAMA-TEST-001",
                status="paid",
                total_amount_minor=50000,
                paid_at=now_naive - timedelta(hours=5),
            )
            db.session.add(order)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, email: str = "analytics-admin@example.com"):
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "password"},
        )
        self.assertEqual(response.status_code, 200)

    def test_analytics_requires_admin(self):
        # Unauthenticated
        res = self.client.get("/api/admin/analytics/overview")
        self.assertEqual(res.status_code, 401)

        # Authenticated as regular non-admin user
        self._login("analytics-student@example.com")
        res = self.client.get("/api/admin/analytics/overview")
        self.assertEqual(res.status_code, 403)

    def test_analytics_overview(self):
        self._login()
        res = self.client.get("/api/admin/analytics/overview?range=7d")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertIn("totals", data)
        self.assertIn("period_metrics", data)
        self.assertIn("deltas", data)
        self.assertEqual(data["totals"]["users"], 2)
        self.assertEqual(data["totals"]["decks"], 1)
        self.assertEqual(data["totals"]["notes"], 1)
        self.assertEqual(data["totals"]["cards"], 1)

        metrics = data["period_metrics"]
        self.assertEqual(metrics["total_reviews"], 2)
        self.assertEqual(metrics["active_users"], 1)
        self.assertGreater(metrics["total_duration_minutes"], 0)
        self.assertEqual(metrics["revenue_minor"], 50000)

    def test_user_growth(self):
        self._login()
        res = self.client.get("/api/admin/analytics/growth?range=7d")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)
        self.assertGreaterEqual(len(data["data"]), 7)

        # Check fields in each daily entry
        item = data["data"][-1]
        self.assertIn("date", item)
        self.assertIn("new_users", item)
        self.assertIn("cumulative_users", item)
        self.assertIn("active_users", item)

    def test_study_time_breakdown(self):
        self._login()
        res = self.client.get("/api/admin/analytics/study-time?range=7d")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertIn("summary", data)
        self.assertIn("daily_time_series", data)
        self.assertIn("hourly_distribution", data)
        self.assertIn("modes_breakdown", data)

        self.assertEqual(len(data["hourly_distribution"]), 24)
        self.assertEqual(data["summary"]["total_reviews"], 2)

    def test_content_growth(self):
        self._login()
        res = self.client.get("/api/admin/analytics/content-growth?range=7d")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)
        item = data["data"][-1]
        self.assertIn("new_decks", item)
        self.assertIn("new_notes", item)
        self.assertIn("new_cards", item)

    def test_retention_cohorts(self):
        self._login()
        res = self.client.get("/api/admin/analytics/retention-cohorts?weeks=4")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertIn("cohorts", data)
        self.assertEqual(len(data["cohorts"]), 4)
        for cohort in data["cohorts"]:
            self.assertIn("cohort", cohort)
            self.assertIn("cohort_size", cohort)
            self.assertIn("d1_rate", cohort)
            self.assertIn("d7_rate", cohort)
