"""Safety/inspection contracts for the disposable real-browser fixture."""

import unittest

from app import create_app
from models import db
from models.card_progress import CardProgress
from models.study_authority_enrollment import StudyAuthorityEnrollment
from scripts.serve_p5_note_browser_probe import (
    inspect_browser_fixture, seed_browser_fixture, validate_database_target,
)


class StudyBrowserProbeTests(unittest.TestCase):
    def test_only_generated_loopback_mysql_targets_are_accepted(self):
        for host in ("localhost", "127.0.0.1", "::1"):
            validate_database_target({"host": host}, "flama_p5_browser_probe_123_ab12cd34")
        for host in ("production", "192.168.1.10", "127.0.0.1.evil", ""):
            with self.subTest(host=host), self.assertRaises(ValueError):
                validate_database_target({"host": host}, "flama_p5_browser_probe_123_ab12cd34")

    def test_configured_or_unsafe_database_names_are_refused(self):
        for name in ("flama", "mysql", "flama_p5_browser_probe_", "flama_p5_browser_probe_123_ab12cd34_extra", "flama_p5_browser_probe_1_deadbeef`", "flama_p5_browser_probe_1_deadbeef\n"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_database_target({"host": "127.0.0.1"}, name)

    def test_fixture_has_one_note_authority_and_two_projections_per_note(self):
        app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
            "REDIS_URL": "", "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": False,
        })
        try:
            fixture = seed_browser_fixture(app)
            self.assertEqual(set(fixture["decks"]), {"online", "offline", "rollover"})
            with app.app_context():
                self.assertEqual(StudyAuthorityEnrollment.query.one().mode_code, "NOTE")
                db.session.rollback()
            report = inspect_browser_fixture(app)
            self.assertEqual(report["authority_revision_counts"], {0: 66})
            self.assertEqual(report["projection_revision_counts"], {0: 132})
            self.assertEqual(report["sibling_state_mismatches"], 0)
            self.assertEqual(report["review_events"], 0)
            self.assertEqual(report["history_facts"], 0)
            self.assertEqual(report["authority_receipts"], 0)
            self.assertEqual(report["sessions"], [])
            self.assertEqual(report["batches"], [])
            with app.app_context():
                CardProgress.query.first().revision = 1
                db.session.commit()
            report = inspect_browser_fixture(app)
            self.assertEqual(report["sibling_state_mismatches"], 1)
            self.assertEqual(report["projection_revision_counts"], {0: 131, 1: 1})
        finally:
            with app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
