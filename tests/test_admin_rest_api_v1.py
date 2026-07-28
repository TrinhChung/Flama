"""REST coverage for admin screens that previously used HTML forms only."""

import unittest

from app import create_app
from models import db
from models.user import User


class AdminRestApiV1Tests(unittest.TestCase):
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
            admin = User(
                username="rest-admin",
                email="rest-admin@example.com",
                is_admin=True,
            )
            admin.set_password("password")
            regular = User(
                username="rest-regular",
                email="rest-regular@example.com",
                is_admin=False,
            )
            regular.set_password("password")
            db.session.add_all([admin, regular])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, email: str = "rest-admin@example.com"):
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "password"},
        )
        self.assertEqual(response.status_code, 200)

    def test_tts_provider_crud(self):
        self._login()

        list_response = self.client.get("/api/admin/tts-providers")
        self.assertEqual(list_response.status_code, 200)
        self.assertIn("items", list_response.get_json())

        create_response = self.client.post(
            "/api/admin/tts-providers",
            json={
                "provider_name": "REST Test Provider",
                "provider_type": "rest-test",
                "base_url": "https://tts.example.com",
                "requires_api_key": False,
                "is_active": True,
                "shared_config": {},
                "provider_config": {},
                "default_settings": {},
            },
        )
        self.assertEqual(create_response.status_code, 201)
        item = create_response.get_json()["item"]
        self.assertEqual(item["provider_type"], "rest-test")
        self.assertTrue(item["is_active"])

        update_response = self.client.put(
            f"/api/admin/tts-providers/{item['id']}",
            json={
                "provider_name": "REST Test Provider Updated",
                "provider_type": "rest-test",
                "base_url": "https://tts.example.com/v2",
                "requires_api_key": True,
                "is_active": False,
                "shared_config": {"region": "test"},
                "provider_config": {},
                "default_settings": {},
            },
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.get_json()["item"]
        self.assertEqual(updated["provider_name"], "REST Test Provider Updated")
        self.assertEqual(updated["shared_config"]["region"], "test")

        delete_response = self.client.delete(
            f"/api/admin/tts-providers/{item['id']}"
        )
        self.assertEqual(delete_response.status_code, 204)

    def test_support_donation_get_and_update(self):
        self._login()

        get_response = self.client.get("/api/admin/support-donation")
        self.assertEqual(get_response.status_code, 200)
        self.assertIsNone(get_response.get_json()["item"]["id"])

        update_response = self.client.put(
            "/api/admin/support-donation",
            json={
                "title": "Support REST",
                "description": "REST donation description",
                "account_name": "FLAMA",
                "account_number": "123456789",
                "thank_you_message": "Thank you",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        item = update_response.get_json()["item"]
        self.assertEqual(item["title"], "Support REST")
        self.assertEqual(item["account_number"], "123456789")

        public_response = self.client.get("/api/support-donation")
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(public_response.get_json()["title"], "Support REST")

    def test_image_library_list_create_and_patch(self):
        self._login()

        list_response = self.client.get("/api/admin/image-library")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.get_json()["items"], [])

        create_response = self.client.post(
            "/api/admin/image-library",
            json={
                "image_key": "rest_image",
                "description": "Fileless image key",
                "is_enabled": True,
            },
        )
        self.assertEqual(create_response.status_code, 201)
        item = create_response.get_json()["item"]
        self.assertEqual(item["image_key"], "rest_image")
        self.assertFalse(item["has_file"])

        patch_response = self.client.patch(
            f"/api/admin/image-library/{item['id']}",
            json={"is_enabled": False},
        )
        self.assertEqual(patch_response.status_code, 200)
        patched = patch_response.get_json()["item"]
        self.assertFalse(patched["is_enabled"])
        self.assertEqual(patched["description"], "Fileless image key")

    def test_regular_user_is_forbidden(self):
        self._login("rest-regular@example.com")
        response = self.client.get("/api/admin/tts-providers")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
