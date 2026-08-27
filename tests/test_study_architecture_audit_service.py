from datetime import datetime, timedelta
import unittest

from app import create_app
from app.services.study_architecture_audit_service import build_study_architecture_audit
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.note_type import NoteType
from models.study_session import StudySession
from models.template import Template
from models.user import User


class StudyArchitectureAuditServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with self.app.app_context():
            db.create_all()
            user = User(username="audit-user", email="audit@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()

            note_type_a = NoteType(user_id=user.id, name="A")
            note_type_b = NoteType(user_id=user.id, name="B")
            db.session.add_all([note_type_a, note_type_b])
            db.session.flush()

            template_a1 = Template(
                note_type_id=note_type_a.id,
                name="Basic",
                position=0,
                is_default=False,
            )
            template_a2 = Template(
                note_type_id=note_type_a.id,
                name="basic",
                position=0,
                is_default=False,
            )
            template_b = Template(
                note_type_id=note_type_b.id,
                name="Basic",
                position=0,
                is_default=True,
            )
            db.session.add_all([template_a1, template_a2, template_b])
            db.session.flush()

            note = Note(user_id=user.id, note_type_id=note_type_a.id, field_values={})
            db.session.add(note)
            db.session.flush()
            matching_card = Card(note_id=note.id, template_id=template_a1.id)
            mismatched_card = Card(note_id=note.id, template_id=template_b.id)
            db.session.add_all([matching_card, mismatched_card])
            db.session.flush()
            db.session.add_all(
                [
                    CardProgress(user_id=user.id, card_id=matching_card.id),
                    CardProgress(user_id=user.id, card_id=mismatched_card.id),
                ]
            )
            now = datetime(2026, 8, 27, 12, 0, 0)
            db.session.add(
                StudySession(
                    user_id=user.id,
                    scope_type="deck",
                    scope_id="1",
                    status="open",
                    snapshot_hash="snapshot",
                    token_hash="token",
                    config_snapshot_json="{}",
                    opened_at=now - timedelta(days=2),
                    expires_at=now - timedelta(days=1),
                )
            )
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_report_exposes_read_only_migration_gates(self):
        with self.app.app_context():
            report = build_study_architecture_audit(
                now=datetime(2026, 8, 27, 12, 0, 0)
            )

        self.assertEqual(report["schema_version"], "study-architecture-audit.v1")
        self.assertEqual(report["template_gates"]["note_types_with_multiple_templates"], 1)
        self.assertEqual(report["template_gates"]["default_count_anomalies"], 1)
        self.assertEqual(report["template_gates"]["duplicate_name_groups"], 1)
        self.assertEqual(report["template_gates"]["duplicate_position_groups"], 1)
        self.assertEqual(report["card_gates"]["cross_note_type_cards"], 1)
        self.assertEqual(report["card_gates"]["notes_with_multiple_cards"], 1)
        self.assertEqual(report["progress_gates"]["learner_note_fan_in_groups"], 1)
        self.assertEqual(report["session_gates"]["expired_open_sessions"], 1)


if __name__ == "__main__":
    unittest.main()
