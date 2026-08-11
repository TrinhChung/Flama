"""Integration tests for the reusable shared image library."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from app.services.remote_image_fetcher import RemoteImagePayload
from models import db
from models.shared_image_asset import SharedImageAsset
from models.user import User
from models.user_role import UserRole


def _make_png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (24, 18), (245, 105, 24, 255)).save(output, format="PNG")
    return output.getvalue()


_MIN_PNG_BYTES = _make_png_bytes()

_SAFE_SVG_BYTES = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    b'<rect width="10" height="10" fill="#2563eb"/></svg>'
)


class ImageLibraryTests(unittest.TestCase):
    def setUp(self):
        self.upload_tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": self.upload_tmp.name,
                "IMAGE_LIBRARY_MAX_BYTES": 1024 * 1024,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            admin_role = UserRole.query.filter_by(code="admin").first()
            regular_role = UserRole.query.filter_by(code="regular").first()
            assert admin_role is not None
            assert regular_role is not None

            admin = User(
                username="image-admin",
                email="image-admin@example.com",
                is_admin=True,
                role_id=admin_role.id,
            )
            admin.set_password("password")
            regular = User(
                username="image-user",
                email="image-user@example.com",
                is_admin=False,
                role_id=regular_role.id,
            )
            regular.set_password("password")
            db.session.add_all([admin, regular])
            db.session.commit()
            self.admin_id = admin.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.upload_tmp.cleanup()

    def _login(self, email: str = "image-admin@example.com"):
        return self.client.post(
            "/login",
            data={"email": email, "password": "password"},
            follow_redirects=True,
        )

    def _create_asset(
        self,
        *,
        image_key: str = "dog",
        description: str = "A friendly dog",
        content: bytes | None = _MIN_PNG_BYTES,
        filename: str = "dog.png",
        mime_type: str = "image/png",
        enabled: bool = True,
    ):
        data: dict[str, object] = {
            "action": "create",
            "image_key": image_key,
            "description": description,
        }
        if enabled:
            data["is_enabled"] = "1"
        if content is not None:
            data["image"] = (io.BytesIO(content), filename, mime_type)
        return self.client.post(
            "/admin/image-library",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    def test_admin_can_create_normalized_key_and_search_it(self):
        self._login()
        response = self._create_asset(image_key="School Bus")
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            row = SharedImageAsset.query.one()
            self.assertEqual(row.image_key, "school_bus")
            self.assertTrue(row.is_enabled)
            self.assertEqual(row.created_by_user_id, self.admin_id)
            self.assertTrue(row.storage_path.startswith("image_library/school_bus/"))
            self.assertTrue(row.storage_path.endswith(".webp"))
            self.assertEqual(row.mime_type, "image/webp")
            stored_path = Path(self.upload_tmp.name) / row.storage_path
            self.assertTrue(stored_path.is_file())
            stored_content = stored_path.read_bytes()
            self.assertNotEqual(stored_content, _MIN_PNG_BYTES)
            self.assertEqual(stored_content[:4], b"RIFF")
            self.assertEqual(stored_content[8:12], b"WEBP")

        page = self.client.get("/admin/image-library?q=school_bus")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"id=\"root\"", page.data)

        api_res = self.client.get("/api/admin/image-library?q=school_bus")
        self.assertEqual(api_res.status_code, 200)
        self.assertIn("school_bus", api_res.get_json()["items"][0]["image_key"])

    def test_non_admin_cannot_manage_or_preview_assets(self):
        self._login("image-user@example.com")
        page = self.client.get("/admin/image-library", follow_redirects=False)
        self.assertEqual(page.status_code, 200)
        api_page = self.client.get("/api/admin/image-library")
        self.assertEqual(api_page.status_code, 403)

        create = self._create_asset()
        self.assertEqual(create.status_code, 302)
        with self.app.app_context():
            self.assertEqual(SharedImageAsset.query.count(), 0)

            row = SharedImageAsset(
                image_key="cat",
                is_enabled=True,
                created_by_user_id=self.admin_id,
                updated_by_user_id=self.admin_id,
            )
            db.session.add(row)
            db.session.commit()
            asset_id = row.id

        preview = self.client.get(f"/admin/image-library/{asset_id}/preview")
        self.assertEqual(preview.status_code, 403)

    def test_key_url_and_metadata_api_resolve_uploaded_image(self):
        self._login()
        self.assertEqual(self._create_asset().status_code, 302)

        metadata = self.client.get("/api/image-library/dog")
        self.assertEqual(metadata.status_code, 200)
        payload = metadata.get_json()
        self.assertEqual(payload["image_key"], "dog")
        self.assertEqual(payload["url"], "/media/library/dog")
        self.assertFalse(payload["is_fallback"])
        self.assertIsNone(payload["fallback_reason"])
        self.assertEqual(payload["mime_type"], "image/webp")

        image = self.client.get(payload["url"])
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.data[:4], b"RIFF")
        self.assertEqual(image.data[8:12], b"WEBP")
        self.assertEqual(image.content_type, "image/webp")
        self.assertEqual(image.headers["X-Flama-Image-Key"], "dog")
        self.assertEqual(image.headers["X-Flama-Image-Fallback"], "0")
        self.assertEqual(image.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-cache", image.headers["Cache-Control"])

    def test_replacing_file_keeps_stable_url_and_removes_old_file(self):
        self._login()
        self.assertEqual(self._create_asset().status_code, 302)
        with self.app.app_context():
            row = SharedImageAsset.query.filter_by(image_key="dog").one()
            asset_id = row.id
            old_storage_path = row.storage_path
            old_sha256 = row.sha256

        update = self.client.post(
            "/admin/image-library",
            data={
                "action": "update",
                "asset_id": asset_id,
                "image_key": "cat",
                "description": "Updated dog",
                "is_enabled": "1",
                "image": (
                    io.BytesIO(_SAFE_SVG_BYTES),
                    "dog-new.svg",
                    "image/svg+xml",
                ),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(update.status_code, 302)

        with self.app.app_context():
            row = db.session.get(SharedImageAsset, asset_id)
            self.assertEqual(row.image_key, "dog")
            self.assertEqual(row.description, "Updated dog")
            self.assertNotEqual(row.storage_path, old_storage_path)
            self.assertNotEqual(row.sha256, old_sha256)
            self.assertFalse((Path(self.upload_tmp.name) / old_storage_path).exists())
            self.assertTrue((Path(self.upload_tmp.name) / row.storage_path).exists())

        image = self.client.get("/media/library/dog")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.data, _SAFE_SVG_BYTES)
        self.assertEqual(image.content_type, "image/svg+xml; charset=utf-8")

    def test_disabled_missing_and_fileless_keys_use_fallback(self):
        self._login()
        self.assertEqual(self._create_asset().status_code, 302)
        with self.app.app_context():
            row = SharedImageAsset.query.filter_by(image_key="dog").one()
            asset_id = row.id

        toggle = self.client.post(
            "/admin/image-library",
            data={"action": "toggle", "asset_id": asset_id},
            follow_redirects=False,
        )
        self.assertEqual(toggle.status_code, 302)

        disabled_meta = self.client.get("/api/image-library/dog").get_json()
        self.assertTrue(disabled_meta["is_fallback"])
        self.assertEqual(disabled_meta["fallback_reason"], "disabled")
        self.assertFalse(disabled_meta["is_enabled"])
        self.assertEqual(disabled_meta["asset_id"], asset_id)

        disabled_image = self.client.get("/media/library/dog")
        self.assertEqual(disabled_image.status_code, 200)
        self.assertEqual(disabled_image.content_type, "image/svg+xml; charset=utf-8")
        self.assertEqual(disabled_image.headers["X-Flama-Image-Fallback"], "1")
        self.assertEqual(
            disabled_image.headers["X-Flama-Image-Fallback-Reason"],
            "disabled",
        )

        missing_meta = self.client.get("/api/image-library/not_created").get_json()
        self.assertTrue(missing_meta["is_fallback"])
        self.assertEqual(missing_meta["fallback_reason"], "missing")
        missing_image = self.client.get("/media/library/not_created")
        self.assertEqual(missing_image.status_code, 200)
        self.assertEqual(missing_image.headers["X-Flama-Image-Fallback"], "1")

        fileless_create = self._create_asset(image_key="apple", content=None)
        self.assertEqual(fileless_create.status_code, 302)
        fileless_meta = self.client.get("/api/image-library/apple").get_json()
        self.assertTrue(fileless_meta["is_fallback"])
        self.assertEqual(fileless_meta["fallback_reason"], "missing_file")

    def test_admin_preview_shows_real_file_even_when_key_is_disabled(self):
        self._login()
        self.assertEqual(self._create_asset(enabled=False).status_code, 302)
        with self.app.app_context():
            asset_id = SharedImageAsset.query.filter_by(image_key="dog").one().id

        public_image = self.client.get("/media/library/dog")
        self.assertEqual(public_image.headers["X-Flama-Image-Fallback"], "1")

        preview = self.client.get(f"/admin/image-library/{asset_id}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data[:4], b"RIFF")
        self.assertEqual(preview.data[8:12], b"WEBP")
        self.assertEqual(preview.headers["X-Flama-Image-Fallback"], "0")

    def test_duplicate_and_invalid_upload_do_not_create_extra_rows(self):
        self._login()
        self.assertEqual(self._create_asset().status_code, 302)

        duplicate = self._create_asset(image_key="DOG")
        self.assertEqual(duplicate.status_code, 302)

        invalid = self._create_asset(
            image_key="cat",
            content=b"this is not an image",
            filename="cat.png",
            mime_type="image/png",
        )
        self.assertEqual(invalid.status_code, 302)

        with self.app.app_context():
            self.assertEqual(SharedImageAsset.query.count(), 1)
            self.assertIsNone(SharedImageAsset.query.filter_by(image_key="cat").first())

    def test_invalid_key_api_returns_validation_error(self):
        self._login()
        response = self.client.get("/api/image-library/bad$key")
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["field"], "image_key")

    def test_raster_reencoding_strips_appended_payload(self):
        self._login()
        marker = b"MZ-TROJAN-PAYLOAD-SHOULD-NOT-SURVIVE"
        response = self._create_asset(
            image_key="clean_dog",
            content=_MIN_PNG_BYTES + marker,
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            row = SharedImageAsset.query.filter_by(image_key="clean_dog").one()
            stored_content = (Path(self.upload_tmp.name) / row.storage_path).read_bytes()
            self.assertEqual(row.mime_type, "image/webp")
            self.assertNotIn(marker, stored_content)
            self.assertEqual(stored_content[:4], b"RIFF")
            self.assertEqual(stored_content[8:12], b"WEBP")

    def test_raster_dimensions_are_bounded_before_storage(self):
        self._login()
        self.app.config["IMAGE_LIBRARY_MAX_PIXELS"] = 100

        response = self._create_asset(image_key="too_many_pixels")
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            self.assertIsNone(
                SharedImageAsset.query.filter_by(
                    image_key="too_many_pixels"
                ).first()
            )

    def test_admin_can_import_public_image_url_through_safe_fetcher(self):
        self._login()
        remote_payload = RemoteImagePayload(
            content=_MIN_PNG_BYTES,
            filename="remote-dog.png",
            mime_type="image/png",
            source_url="https://cdn.example.com/remote-dog.png",
        )
        with patch(
            "app.services.image_library_service.fetch_remote_image",
            return_value=remote_payload,
        ) as fetch_mock:
            response = self.client.post(
                "/admin/image-library",
                data={
                    "action": "create",
                    "image_key": "remote_dog",
                    "description": "Downloaded safely",
                    "is_enabled": "1",
                    "source_url": remote_payload.source_url,
                },
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        fetch_mock.assert_called_once()

        with self.app.app_context():
            row = SharedImageAsset.query.filter_by(image_key="remote_dog").one()
            self.assertEqual(row.mime_type, "image/webp")
            self.assertEqual(row.filename, "remote-dog.webp")
            stored_content = (Path(self.upload_tmp.name) / row.storage_path).read_bytes()
            self.assertNotEqual(stored_content, _MIN_PNG_BYTES)

    def test_private_remote_url_and_two_sources_are_rejected(self):
        self._login()
        private_response = self.client.post(
            "/admin/image-library",
            data={
                "action": "create",
                "image_key": "internal",
                "is_enabled": "1",
                "source_url": "http://127.0.0.1/internal.png",
            },
            follow_redirects=False,
        )
        self.assertEqual(private_response.status_code, 302)

        two_sources = self.client.post(
            "/admin/image-library",
            data={
                "action": "create",
                "image_key": "ambiguous",
                "is_enabled": "1",
                "source_url": "https://example.com/image.png",
                "image": (io.BytesIO(_MIN_PNG_BYTES), "image.png", "image/png"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(two_sources.status_code, 302)
        with self.app.app_context():
            self.assertEqual(SharedImageAsset.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
