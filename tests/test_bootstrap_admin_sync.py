"""Tests for idempotent bootstrap-admin synchronization."""

from __future__ import annotations

import unittest

from app import create_app
from app.services.bootstrap_admin_service import (
    BootstrapAdminConflictError,
    sync_bootstrap_admin,
)
from app.utils.bootstrap_admin import BootstrapAdminCredentials
from models import db
from models.user import User
from models.user_role import UserRole


class BootstrapAdminSyncTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.credentials = BootstrapAdminCredentials(
            email="owner@example.com",
            username="owner",
            password="current-admin-password",
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_creates_missing_admin_with_login_credentials(self):
        with self.app.app_context():
            result = sync_bootstrap_admin(db.session, credentials=self.credentials)
            db.session.commit()

            user = db.session.get(User, result.user_id)
            self.assertTrue(result.created)
            self.assertIsNotNone(user)
            self.assertEqual(user.email, self.credentials.email)
            self.assertEqual(user.username, self.credentials.username)
            self.assertTrue(user.check_password(self.credentials.password))
            self.assertTrue(user.is_admin)
            self.assertTrue(user.role.is_admin)
            self.assertFalse(user.is_disabled)

    def test_repairs_existing_user_found_by_username(self):
        with self.app.app_context():
            regular_role = UserRole.query.filter_by(code="regular").first()
            user = User(
                email="old@example.com",
                username=self.credentials.username,
                password_hash="",
                is_admin=False,
                is_disabled=True,
                role_id=regular_role.id,
            )
            db.session.add(user)
            db.session.commit()

            result = sync_bootstrap_admin(db.session, credentials=self.credentials)
            db.session.commit()

            repaired = db.session.get(User, user.id)
            self.assertFalse(result.created)
            self.assertEqual(repaired.email, self.credentials.email)
            self.assertTrue(repaired.check_password(self.credentials.password))
            self.assertTrue(repaired.is_admin)
            self.assertTrue(repaired.role.is_admin)
            self.assertFalse(repaired.is_disabled)

    def test_rejects_email_and_username_owned_by_different_users(self):
        with self.app.app_context():
            email_user = User(
                email=self.credentials.email,
                username="different-owner",
                is_admin=False,
            )
            email_user.set_password("password")
            username_user = User(
                email="different@example.com",
                username=self.credentials.username,
                is_admin=False,
            )
            username_user.set_password("password")
            db.session.add_all([email_user, username_user])
            db.session.commit()

            with self.assertRaises(BootstrapAdminConflictError):
                sync_bootstrap_admin(db.session, credentials=self.credentials)


if __name__ == "__main__":
    unittest.main()
