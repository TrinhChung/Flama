"""Adversarial challenge test suite verifying route parity, security, and SPA interception
between /store/<asset_id> and /media/proxy/<asset_id>.
"""

from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path

import app.spa
from app import create_app
from models import db
from models.deck import Deck
from models.flashcard import MediaAsset
from models.user import User
from tests.study_note_fixtures import create_note_user


_MIN_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class StoreRouteAdversarialChallengeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upload_root = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": cls.upload_root.name,
                "FLASHCARD_MEDIA_MAX_BYTES": 10 * 1024 * 1024,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )

    @classmethod
    def tearDownClass(cls):
        cls.upload_root.cleanup()

    def setUp(self):
        self.upload_tmp = tempfile.TemporaryDirectory(dir=self.upload_root.name, ignore_cleanup_errors=True)
        self.app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"] = self.upload_tmp.name
        self.app.config["FLASHCARD_MEDIA_MAX_BYTES"] = 10 * 1024 * 1024
        self.app.config["MEDIA_PROXY_USE_XACCEL"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = create_note_user(db.session, username="admin_store", email="admin-store-test@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = Deck(name="Store Security Deck")
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "admin-store-test@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.upload_tmp.cleanup()

    def _create_note_type_with_media(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "Security Note Type",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Meaning", "field_type": "richtext", "position": 1, "required": False},
                    {"name": "Picture", "field_type": "image", "position": 2, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}}</div><div>{{{Meaning}}}</div>{{{Picture}}}",
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def _create_note(self, note_type_id: str) -> str:
        response = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "Test",
                    "Meaning": "<b>test</b>",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["id"]

    def _upload_test_media(self, filename: str = "avatar.png", content: bytes = _MIN_PNG_BYTES) -> str:
        nt = self._create_note_type_with_media()
        note_id = self._create_note(nt["id"])

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Picture",
                "file": (io.BytesIO(content), filename, "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 201)
        asset_id = (upload_resp.get_json() or {}).get("asset_id")
        self.assertTrue(asset_id)
        return asset_id

    # ----------------------------------------------------------------------
    # Bug Reproduction 1: SPA Interception of /store/<asset_id>
    # ----------------------------------------------------------------------
    def test_bug_spa_intercepts_store_route_when_unpatched(self):
        """VERIFIED FIX:

        With '/store/' in app.spa._BINARY_PATH_PREFIXES, GET /store/<asset_id>
        is not intercepted by route_frontend_navigation and serves the actual media payload
        (200 OK, image/svg+xml) instead of the React SPA HTML.
        """
        resp = self.client.get("/store/sample-image")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/svg+xml")
        self.assertNotIn(b'<div id="root">', resp.data)
        self.assertIn(b"<svg", resp.data)
        resp.close()

    # ----------------------------------------------------------------------
    # Bug Reproduction 2: Bare /store returns 200 HTML instead of 404 JSON
    # ----------------------------------------------------------------------
    def test_bug_bare_store_returns_spa_html_instead_of_404_json(self):
        """VERIFIED FIX:

        Bare '/store' is properly bypassed in app/spa.py and handled by app/__init__.py
        to return 404 JSON with no-cache headers matching '/media/proxy'.
        """
        store_resp = self.client.get("/store")
        proxy_resp = self.client.get("/media/proxy")

        self.assertEqual(store_resp.status_code, 404)
        self.assertEqual(store_resp.mimetype, "application/json")

        self.assertEqual(proxy_resp.status_code, 404)
        self.assertEqual(proxy_resp.mimetype, "application/json")

        self.assertEqual(store_resp.get_json(), proxy_resp.get_json())
        self.assertEqual(
            store_resp.headers.get("Cache-Control"),
            "no-cache, no-store, must-revalidate, max-age=0",
        )

        store_resp.close()
        proxy_resp.close()

    # ----------------------------------------------------------------------
    # Route Handler Verification Under Patched SPA Binary Prefixes
    # ----------------------------------------------------------------------
    def test_store_and_proxy_parity_for_preview_samples_when_spa_bypassed(self):
        orig_prefixes = app.spa._BINARY_PATH_PREFIXES
        app.spa._BINARY_PATH_PREFIXES = (*orig_prefixes, "/store/")
        try:
            for sample_id in ["sample-image", "sample-diagram", "sample-audio"]:
                store_resp = self.client.get(f"/store/{sample_id}")
                proxy_resp = self.client.get(f"/media/proxy/{sample_id}")

                self.assertEqual(store_resp.status_code, 200)
                self.assertEqual(proxy_resp.status_code, 200)
                self.assertEqual(store_resp.mimetype, proxy_resp.mimetype)
                self.assertEqual(store_resp.data, proxy_resp.data)
                self.assertEqual(store_resp.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(store_resp.headers.get("Content-Security-Policy"), "default-src 'none'; sandbox")

                store_resp.close()
                proxy_resp.close()
        finally:
            app.spa._BINARY_PATH_PREFIXES = orig_prefixes

    def test_store_and_proxy_parity_for_database_media_assets_when_spa_bypassed(self):
        orig_prefixes = app.spa._BINARY_PATH_PREFIXES
        app.spa._BINARY_PATH_PREFIXES = (*orig_prefixes, "/store/")
        try:
            asset_id = self._upload_test_media("avatar.png", _MIN_PNG_BYTES)

            store_resp = self.client.get(f"/store/{asset_id}")
            proxy_resp = self.client.get(f"/media/proxy/{asset_id}")

            self.assertEqual(store_resp.status_code, 200)
            self.assertEqual(proxy_resp.status_code, 200)
            self.assertEqual(store_resp.data, proxy_resp.data)
            self.assertEqual(store_resp.data, _MIN_PNG_BYTES)
            self.assertEqual(store_resp.headers.get("Content-Type"), "image/png")
            self.assertEqual(store_resp.headers.get("Content-Disposition"), 'inline; filename="avatar.png"')
            self.assertEqual(store_resp.headers.get("Cache-Control"), "public, max-age=3600, s-maxage=86400")
            self.assertEqual(store_resp.headers.get("ETag"), proxy_resp.headers.get("ETag"))
            self.assertNotIn("Vary", store_resp.headers)

            store_resp.close()
            proxy_resp.close()
        finally:
            app.spa._BINARY_PATH_PREFIXES = orig_prefixes

    def test_store_and_proxy_parity_for_conditional_etag_304_when_spa_bypassed(self):
        orig_prefixes = app.spa._BINARY_PATH_PREFIXES
        app.spa._BINARY_PATH_PREFIXES = (*orig_prefixes, "/store/")
        try:
            asset_id = self._upload_test_media("test.png", _MIN_PNG_BYTES)
            sha256 = hashlib.sha256(_MIN_PNG_BYTES).hexdigest()

            store_304 = self.client.get(f"/store/{asset_id}", headers={"If-None-Match": f'"{sha256}"'})
            proxy_304 = self.client.get(f"/media/proxy/{asset_id}", headers={"If-None-Match": f'"{sha256}"'})

            self.assertEqual(store_304.status_code, 304)
            self.assertEqual(proxy_304.status_code, 304)
            self.assertEqual(store_304.data, b"")
            self.assertEqual(proxy_304.data, b"")

            store_304.close()
            proxy_304.close()
        finally:
            app.spa._BINARY_PATH_PREFIXES = orig_prefixes

    def test_store_and_proxy_parity_for_missing_and_deleted_assets_when_spa_bypassed(self):
        orig_prefixes = app.spa._BINARY_PATH_PREFIXES
        app.spa._BINARY_PATH_PREFIXES = (*orig_prefixes, "/store/")
        try:
            bad_id = "00000000-0000-0000-0000-000000000000"
            store_404 = self.client.get(f"/store/{bad_id}")
            proxy_404 = self.client.get(f"/media/proxy/{bad_id}")

            self.assertEqual(store_404.status_code, 404)
            self.assertEqual(proxy_404.status_code, 404)
            self.assertEqual(store_404.get_json(), proxy_404.get_json())
            self.assertEqual(store_404.headers.get("Cache-Control"), "no-cache, no-store, must-revalidate, max-age=0")
            self.assertEqual(proxy_404.headers.get("Cache-Control"), "no-cache, no-store, must-revalidate, max-age=0")

            store_404.close()
            proxy_404.close()
        finally:
            app.spa._BINARY_PATH_PREFIXES = orig_prefixes

    def test_store_http_method_restrictions(self):
        asset_id = "sample-image"
        for method in ("post", "put", "delete", "patch"):
            client_fn = getattr(self.client, method)
            store_resp = client_fn(f"/store/{asset_id}")
            proxy_resp = client_fn(f"/media/proxy/{asset_id}")

            self.assertIn(store_resp.status_code, (405, 410))
            self.assertIn(proxy_resp.status_code, (405, 410))

            store_resp.close()
            proxy_resp.close()

    def test_store_path_traversal_attempts_when_spa_bypassed(self):
        orig_prefixes = app.spa._BINARY_PATH_PREFIXES
        app.spa._BINARY_PATH_PREFIXES = (*orig_prefixes, "/store/")
        try:
            traversal_attempts = [
                "/store/..",
                "/store/../secret",
                "/store/..%2f..%2fetc%2fpasswd",
                "/store/nested/path",
            ]
            for path in traversal_attempts:
                resp = self.client.get(path)
                self.assertEqual(resp.status_code, 404, f"Path {path} returned {resp.status_code}")
                resp.close()
        finally:
            app.spa._BINARY_PATH_PREFIXES = orig_prefixes

    def test_store_xaccel_mode_parity_when_spa_bypassed(self):
        orig_prefixes = app.spa._BINARY_PATH_PREFIXES
        app.spa._BINARY_PATH_PREFIXES = (*orig_prefixes, "/store/")
        self.app.config["MEDIA_PROXY_USE_XACCEL"] = True
        try:
            asset_id = self._upload_test_media("accelerated.png", _MIN_PNG_BYTES)

            store_resp = self.client.get(f"/store/{asset_id}")
            proxy_resp = self.client.get(f"/media/proxy/{asset_id}")

            self.assertEqual(store_resp.status_code, 200)
            self.assertEqual(proxy_resp.status_code, 200)
            self.assertEqual(
                store_resp.headers.get("X-Accel-Redirect"),
                proxy_resp.headers.get("X-Accel-Redirect"),
            )
            self.assertEqual(store_resp.data, b"")
            self.assertEqual(proxy_resp.data, b"")

            store_resp.close()
            proxy_resp.close()
        finally:
            self.app.config["MEDIA_PROXY_USE_XACCEL"] = False
            app.spa._BINARY_PATH_PREFIXES = orig_prefixes

    def test_store_public_access_unauthenticated_when_spa_bypassed(self):
        orig_prefixes = app.spa._BINARY_PATH_PREFIXES
        app.spa._BINARY_PATH_PREFIXES = (*orig_prefixes, "/store/")
        try:
            asset_id = self._upload_test_media("public.png", _MIN_PNG_BYTES)

            anon_client = self.app.test_client()
            store_resp = anon_client.get(f"/store/{asset_id}")
            proxy_resp = anon_client.get(f"/media/proxy/{asset_id}")

            self.assertEqual(store_resp.status_code, 200)
            self.assertEqual(proxy_resp.status_code, 200)
            self.assertEqual(store_resp.data, _MIN_PNG_BYTES)

            store_resp.close()
            proxy_resp.close()
        finally:
            app.spa._BINARY_PATH_PREFIXES = orig_prefixes


if __name__ == "__main__":
    unittest.main()
