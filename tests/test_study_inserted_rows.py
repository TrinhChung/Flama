"""Rows remembered as inserted never outlive their transaction."""

import unittest

from app import create_app
from app.repositories.study_inserted_rows import (
    CONTRIBUTOR,
    SUBJECT,
    inserted_in_transaction,
    remember_inserted,
)
from models import db
from models.user import User


class StudyInsertedRowsTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_marks_are_per_kind_and_dropped_on_commit_and_rollback(self):
        db.session.add(User(username="rows", email="rows@example.test"))
        db.session.flush()
        remember_inserted(db.session, SUBJECT, 7)
        self.assertTrue(inserted_in_transaction(db.session, SUBJECT, 7))
        self.assertFalse(inserted_in_transaction(db.session, CONTRIBUTOR, 7))
        self.assertFalse(inserted_in_transaction(db.session, SUBJECT, None))
        db.session.commit()
        self.assertFalse(inserted_in_transaction(db.session, SUBJECT, 7))

        remember_inserted(db.session, CONTRIBUTOR, 3)
        db.session.rollback()
        self.assertFalse(inserted_in_transaction(db.session, CONTRIBUTOR, 3))

    def test_a_savepoint_does_not_drop_the_outer_marks(self):
        db.session.add(User(username="outer", email="outer@example.test"))
        db.session.flush()
        remember_inserted(db.session, SUBJECT, 11)
        with db.session.begin_nested():
            db.session.add(User(username="inner", email="inner@example.test"))
        self.assertTrue(inserted_in_transaction(db.session, SUBJECT, 11))
        db.session.rollback()
        self.assertFalse(inserted_in_transaction(db.session, SUBJECT, 11))


if __name__ == "__main__":
    unittest.main()
