"""Automated drift prevention and deployment consistency test suite."""

from __future__ import annotations

import io
from pathlib import Path
import re
import tempfile
import unittest

from app import create_app
from deploy.sync_managed_env import MANAGED_VARIABLE_DEFAULTS
from models import db
from models.deck import Deck
from models.flashcard import MediaAsset
from models.user import User
from tests.study_note_fixtures import create_note_user

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BOOTSTRAP_SCRIPT = _REPO_ROOT / "deploy" / "bootstrap_hostinger.sh"
_DEPLOY_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "deploy.yml"
_NGINX_CONF = _REPO_ROOT / "deploy" / "flama.nginx.conf"

_MIN_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class DeployEnvironmentConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upload_root = tempfile.TemporaryDirectory()
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
        self.upload_tmp = tempfile.TemporaryDirectory(dir=self.upload_root.name)
        self.app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"] = self.upload_tmp.name
        self.app.config["FLASHCARD_MEDIA_MAX_BYTES"] = 10 * 1024 * 1024
        self.app.config["MEDIA_PROXY_USE_XACCEL"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = create_note_user(db.session, username="admin", email="admin-consistency@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = Deck(name="Consistency Deck")
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "admin-consistency@example.com", "password": "password"},
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
                "name": "Consistency Note Type",
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

    def _create_note(self, note_type_id: str, *, word: str = "apple", meaning: str = "<b>fruit</b>") -> str:
        response = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": word,
                    "Meaning": meaning,
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["id"]

    def test_media_proxy_use_xaccel_defaults_to_true(self):
        """Asserts MEDIA_PROXY_USE_XACCEL defaults to true across bootstrap, sync script, and deploy workflow."""
        # 1. deploy/sync_managed_env.py
        self.assertEqual(
            MANAGED_VARIABLE_DEFAULTS.get("MEDIA_PROXY_USE_XACCEL"),
            "true",
            "MEDIA_PROXY_USE_XACCEL must default to 'true' in MANAGED_VARIABLE_DEFAULTS",
        )

        # 2. deploy/bootstrap_hostinger.sh
        bootstrap_content = _BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertRegex(
            bootstrap_content,
            r"(?m)^MEDIA_PROXY_USE_XACCEL=true$",
            "MEDIA_PROXY_USE_XACCEL must be set to 'true' in deploy/bootstrap_hostinger.sh",
        )

        # 3. .github/workflows/deploy.yml
        deploy_content = _DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "MEDIA_PROXY_USE_XACCEL: ${{ vars.MEDIA_PROXY_USE_XACCEL || 'true' }}",
            deploy_content,
            "MEDIA_PROXY_USE_XACCEL must default to 'true' in .github/workflows/deploy.yml",
        )

    def test_sync_managed_env_defaults_match_bootstrap_hostinger(self):
        """Asserts 100% equality of all shared defaults between sync_managed_env and bootstrap_hostinger."""
        bootstrap_content = _BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")

        match = re.search(r"<<ENVIRONMENT\n(.*?)\nENVIRONMENT", bootstrap_content, re.DOTALL)
        self.assertIsNotNone(match, "Could not locate ENVIRONMENT heredoc in bootstrap_hostinger.sh")
        env_lines = match.group(1).splitlines()

        bootstrap_vars: dict[str, str] = {}
        for line in env_lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                bootstrap_vars[key.strip()] = val.strip()

        shared_keys = set(MANAGED_VARIABLE_DEFAULTS.keys()) & set(bootstrap_vars.keys())
        self.assertGreaterEqual(
            len(shared_keys),
            20,
            f"Expected at least 20 shared configuration keys, found {len(shared_keys)}",
        )

        mismatches = []
        for key in sorted(shared_keys):
            bootstrap_val = bootstrap_vars[key]
            # Ignore dynamic bash expansion variables (e.g. $secret_key, $database_password)
            if bootstrap_val.startswith("$"):
                continue
            sync_val = MANAGED_VARIABLE_DEFAULTS[key]
            if bootstrap_val != sync_val:
                mismatches.append(f"{key}: bootstrap='{bootstrap_val}' vs sync='{sync_val}'")

        self.assertEqual(
            mismatches,
            [],
            f"Configuration mismatch between bootstrap_hostinger.sh and sync_managed_env.py: {mismatches}",
        )

    def test_nginx_media_proxy_allows_cache_control_headers(self):
        """Asserts proxy_hide_header Cache-Control; is removed from deploy/flama.nginx.conf while Vary and Set-Cookie are retained."""
        nginx_content = _NGINX_CONF.read_text(encoding="utf-8")

        # 1. Exact match root location = /media/proxy
        root_block_match = re.search(
            r"location\s+=\s+/media/proxy\s*\{(.*?)\}",
            nginx_content,
            re.DOTALL,
        )
        self.assertIsNotNone(root_block_match, "Could not locate location = /media/proxy block in flama.nginx.conf")
        root_block = root_block_match.group(1)
        self.assertIn("return 404;", root_block)
        self.assertIn("no-cache, no-store", root_block)

        # 2. Subpath location ^~ /media/proxy/
        proxy_block_match = re.search(
            r"location\s+\^~\s+/media/proxy/\s*\{(.*?)\}",
            nginx_content,
            re.DOTALL,
        )
        self.assertIsNotNone(proxy_block_match, "Could not locate location ^~ /media/proxy/ block in flama.nginx.conf")
        proxy_block = proxy_block_match.group(1)

        self.assertNotIn(
            "proxy_hide_header Cache-Control;",
            proxy_block,
            "proxy_hide_header Cache-Control; must be removed to allow upstream Cache-Control headers to pass through",
        )
        self.assertIn(
            "proxy_hide_header Vary;",
            proxy_block,
            "proxy_hide_header Vary; must be preserved in media proxy block",
        )
        self.assertIn(
            "proxy_hide_header Set-Cookie;",
            proxy_block,
            "proxy_hide_header Set-Cookie; must be preserved in media proxy block",
        )
        self.assertIn(
            "more_set_headers",
            proxy_block,
            "more_set_headers directive must be present in media proxy block for error status codes",
        )
        self.assertIn(
            "no-cache, no-store",
            proxy_block,
            "negative cache headers must be defined in more_set_headers for gateway/Nginx error responses",
        )
        self.assertIn("405", proxy_block, "more_set_headers -s must include 405")
        self.assertIn("410", proxy_block, "more_set_headers -s must include 410")

    def test_proxy_media_nonexistent_asset_returns_no_cache_headers(self):
        """Asserts 404 on invalid asset returns explicit no-cache, no-store headers."""
        resp = self.client.get("/media/proxy/00000000-0000-0000-0000-000000000000")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            resp.headers.get("Cache-Control"),
            "no-cache, no-store, must-revalidate, max-age=0",
        )
        self.assertEqual(resp.headers.get("Pragma"), "no-cache")

        # Verify empty asset ID /media/proxy/ falls into global 404 with negative caching
        resp_root = self.client.get("/media/proxy/")
        self.assertEqual(resp_root.status_code, 404)
        self.assertEqual(
            resp_root.headers.get("Cache-Control"),
            "no-cache, no-store, must-revalidate, max-age=0",
        )
        self.assertEqual(resp_root.headers.get("Pragma"), "no-cache")

        # Verify root path without trailing slash /media/proxy returns 404 with no-store and NO Vary: Cookie
        resp_noslash = self.client.get("/media/proxy")
        self.assertEqual(resp_noslash.status_code, 404)
        self.assertEqual(
            resp_noslash.headers.get("Cache-Control"),
            "no-cache, no-store, must-revalidate, max-age=0",
        )
        self.assertEqual(resp_noslash.headers.get("Pragma"), "no-cache")
        self.assertNotIn("Cookie", resp_noslash.headers.get("Vary", ""))
        self.assertNotIn("Vary", resp_noslash.headers)

    def test_proxy_media_unsupported_methods_return_negative_cache_headers(self):
        """Asserts POST, PUT, DELETE, PATCH to /media/proxy/<id> and /media/proxy return 405/410/404 with no-store."""
        for method in ("post", "put", "delete", "patch"):
            client_fn = getattr(self.client, method)
            # /media/proxy/123 matches route with GET only -> 405 (or 410)
            resp = client_fn("/media/proxy/123")
            self.assertIn(resp.status_code, (405, 410), f"{method.upper()} /media/proxy/123 status: {resp.status_code}")
            self.assertEqual(
                resp.headers.get("Cache-Control"),
                "no-cache, no-store, must-revalidate, max-age=0",
                f"{method.upper()} /media/proxy/123 missing Cache-Control",
            )
            self.assertEqual(
                resp.headers.get("Pragma"),
                "no-cache",
                f"{method.upper()} /media/proxy/123 missing Pragma",
            )
            self.assertNotIn("Cookie", resp.headers.get("Vary", ""), f"{method.upper()} /media/proxy/123 leaked Vary: Cookie")

            # /media/proxy without asset id -> 404 (or 410)
            resp_root = client_fn("/media/proxy")
            self.assertIn(resp_root.status_code, (404, 405, 410), f"{method.upper()} /media/proxy status: {resp_root.status_code}")
            self.assertEqual(
                resp_root.headers.get("Cache-Control"),
                "no-cache, no-store, must-revalidate, max-age=0",
                f"{method.upper()} /media/proxy missing Cache-Control",
            )
            self.assertEqual(
                resp_root.headers.get("Pragma"),
                "no-cache",
                f"{method.upper()} /media/proxy missing Pragma",
            )
            self.assertNotIn("Cookie", resp_root.headers.get("Vary", ""), f"{method.upper()} /media/proxy leaked Vary: Cookie")

    def test_proxy_media_production_mode_unsupported_methods_return_410_no_store(self):
        """Asserts production mode returns 410 Gone with negative cache headers."""
        prod_app = create_app({
            "TESTING": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False,
        })
        prod_client = prod_app.test_client()
        for method in ("post", "put", "delete", "patch"):
            client_fn = getattr(prod_client, method)
            for path in ("/media/proxy/123", "/media/proxy"):
                resp = client_fn(path)
                self.assertEqual(resp.status_code, 410, f"PROD {method.upper()} {path} status: {resp.status_code}")
                self.assertEqual(
                    resp.headers.get("Cache-Control"),
                    "no-cache, no-store, must-revalidate, max-age=0",
                )
                self.assertEqual(resp.headers.get("Pragma"), "no-cache")
                self.assertNotIn("Cookie", resp.headers.get("Vary", ""))

    def test_proxy_media_missing_disk_file_returns_no_cache_headers(self):
        """Asserts 404 on missing disk file returns explicit no-cache, no-store headers."""
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Picture",
                "file": (io.BytesIO(_MIN_PNG_BYTES), "sample.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 201)
        asset_id = (upload_resp.get_json() or {}).get("asset_id")
        self.assertTrue(asset_id)

        # Manually delete file from disk to simulate missing asset storage
        with self.app.app_context():
            asset = MediaAsset.query.filter_by(id=asset_id).first()
            self.assertIsNotNone(asset)
            upload_root = Path(self.app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
            disk_file = upload_root / asset.storage_path
            self.assertTrue(disk_file.exists())
            disk_file.unlink()

        # Request media again: must return 404 with negative cache headers
        resp = self.client.get(f"/media/proxy/{asset_id}")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            resp.headers.get("Cache-Control"),
            "no-cache, no-store, must-revalidate, max-age=0",
        )
        self.assertEqual(resp.headers.get("Pragma"), "no-cache")

    def test_proxy_media_valid_asset_preserves_public_caching(self):
        """Asserts 200 preserves public cache headers, ETag, and X-Accel-Redirect when enabled."""
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Picture",
                "file": (io.BytesIO(_MIN_PNG_BYTES), "image.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 201)
        asset_id = (upload_resp.get_json() or {}).get("asset_id")
        self.assertTrue(asset_id)

        # 1. Standard mode (direct send_file)
        self.client.post("/logout")
        resp = self.client.get(f"/media/proxy/{asset_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers.get("Cache-Control"),
            "public, max-age=3600, s-maxage=86400",
        )
        etag = resp.headers.get("ETag")
        self.assertTrue(etag)
        resp.close()

        # 2. Conditional 304 revalidation
        cond_resp = self.client.get(
            f"/media/proxy/{asset_id}",
            headers={"If-None-Match": etag},
        )
        self.assertEqual(cond_resp.status_code, 304)
        self.assertEqual(
            cond_resp.headers.get("Cache-Control"),
            "public, max-age=3600, s-maxage=86400",
        )

        # 3. X-Accel-Redirect mode
        self.app.config["MEDIA_PROXY_USE_XACCEL"] = True
        try:
            accel_resp = self.client.get(f"/media/proxy/{asset_id}")
            self.assertEqual(accel_resp.status_code, 200)
            self.assertTrue(
                accel_resp.headers.get("X-Accel-Redirect", "").startswith("/internal-media/"),
            )
            self.assertEqual(
                accel_resp.headers.get("Cache-Control"),
                "public, max-age=3600, s-maxage=86400",
            )
        finally:
            self.app.config["MEDIA_PROXY_USE_XACCEL"] = False


if __name__ == "__main__":
    unittest.main()
