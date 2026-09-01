"""Comprehensive test suite for the Backend Secure Image Ingestion & Processing Pipeline."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from werkzeug.datastructures import FileStorage

from app import create_app
from app.services import image_ingestion_service, image_queue_service, image_worker_service
from app.services.image_processor import process_image_preset
from app.services.image_security_service import ImageSecurityError, validate_image_security
from app.services.remote_image_fetcher import RemoteImagePayload
from models import db
from models.admin_security_alert import AdminSecurityAlert
from models.image_asset import ImageAsset
from models.user import User
from models.user_role import UserRole


def _create_test_image_bytes(
    format_name: str = "PNG",
    size: tuple[int, int] = (100, 100),
    color: tuple[int, int, int] = (255, 0, 0),
) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = BytesIO()
    img.save(buf, format=format_name)
    return buf.getvalue()


class SecureImagePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_root = Path(self.temp_dir.name)

        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "FLASHCARD_MEDIA_UPLOAD_ROOT": str(self.upload_root),
                "WTF_CSRF_ENABLED": False,
                "SERVER_NAME": "localhost",
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        admin_role = UserRole.query.filter_by(code="admin").first()
        regular_role = UserRole.query.filter_by(code="regular").first()

        self.admin_user = User(
            email="admin@example.com",
            username="admin",
            role_id=admin_role.id if admin_role else None,
            is_admin=True,
        )
        self.admin_user.set_password("password123")

        self.regular_user = User(
            email="user@example.com",
            username="user",
            role_id=regular_role.id if regular_role else None,
            is_admin=False,
        )
        self.regular_user.set_password("password123")

        db.session.add_all([self.admin_user, self.regular_user])
        db.session.commit()

        self.client = self.app.test_client()
        image_queue_service.clear_image_queue()

    def tearDown(self):
        image_queue_service.clear_image_queue()
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. Security & Threat Detection Tests
    # -------------------------------------------------------------------------
    def test_rejects_fake_image_file_and_creates_security_alert(self):
        fake_content = b"<html><script>alert(1)</script></html>"
        with self.assertRaises(ImageSecurityError) as ctx:
            validate_image_security(
                fake_content,
                filename="attack.jpg",
                user_id=self.regular_user.id,
                source_ip="1.2.3.4",
            )
        self.assertEqual(ctx.exception.threat_type, "disguised_file")

        # Verify AdminSecurityAlert was created
        alert = AdminSecurityAlert.query.filter_by(threat_type="disguised_file").first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.user_id, self.regular_user.id)
        self.assertEqual(alert.source_ip, "1.2.3.4")
        self.assertFalse(alert.is_resolved)

    def test_rejects_executable_header_polyglot(self):
        mz_payload = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100
        with self.assertRaises(ImageSecurityError) as ctx:
            validate_image_security(
                mz_payload,
                filename="fake.png",
                user_id=self.regular_user.id,
            )
        self.assertEqual(ctx.exception.threat_type, "disguised_file")
        alert = AdminSecurityAlert.query.filter_by(threat_type="disguised_file").first()
        self.assertIsNotNone(alert)

    def test_rejects_decompression_bomb_and_creates_alert(self):
        huge_image_bytes = _create_test_image_bytes(size=(6000, 5000))  # 30M pixels > 25M
        with self.assertRaises(ImageSecurityError) as ctx:
            validate_image_security(
                huge_image_bytes,
                filename="bomb.png",
                max_pixels=25_000_000,
                user_id=self.regular_user.id,
            )
        self.assertEqual(ctx.exception.threat_type, "decompression_bomb")
        alert = AdminSecurityAlert.query.filter_by(threat_type="decompression_bomb").first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "high")

    def test_rejects_ssrf_private_ip_and_creates_alert(self):
        with self.assertRaises(ImageSecurityError) as ctx:
            image_ingestion_service.ingest_image(
                user_id=self.regular_user.id,
                source_url="http://127.0.0.1/secret.png",
                source_ip="192.168.1.50",
            )
        self.assertEqual(ctx.exception.threat_type, "ssrf_attempt")

        alert = AdminSecurityAlert.query.filter_by(threat_type="ssrf_attempt").first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "high")
        self.assertIn("127.0.0.1", alert.source_url)

    def test_rejects_cloud_metadata_ip_ssrf(self):
        with self.assertRaises(ImageSecurityError) as ctx:
            image_ingestion_service.ingest_image(
                user_id=self.regular_user.id,
                source_url="http://169.254.169.254/latest/meta-data",
            )
        self.assertEqual(ctx.exception.threat_type, "ssrf_attempt")

    # -------------------------------------------------------------------------
    # 2. Preset Processing & Optimization Tests
    # -------------------------------------------------------------------------
    def test_avatar_preset_square_crops_and_converts_to_webp(self):
        img_bytes = _create_test_image_bytes(format_name="PNG", size=(600, 300))
        result = process_image_preset(img_bytes, preset_name="avatar")
        self.assertEqual(result.mime_type, "image/webp")
        self.assertEqual(result.width, 256)
        self.assertEqual(result.height, 256)

    def test_deck_cover_preset_cover_crops(self):
        img_bytes = _create_test_image_bytes(format_name="JPEG", size=(1600, 1200))
        result = process_image_preset(img_bytes, preset_name="deck_cover")
        self.assertEqual(result.mime_type, "image/webp")
        self.assertEqual(result.width, 1200)
        self.assertEqual(result.height, 675)

    def test_note_image_preset_fits_without_losing_aspect_ratio(self):
        img_bytes = _create_test_image_bytes(format_name="PNG", size=(3200, 1600))
        result = process_image_preset(img_bytes, preset_name="note_image")
        self.assertEqual(result.mime_type, "image/webp")
        self.assertEqual(result.width, 1600)
        self.assertEqual(result.height, 800)

    # -------------------------------------------------------------------------
    # 3. Ingestion & Temporary Display URL Flow
    # -------------------------------------------------------------------------
    def test_direct_file_upload_ingestion_creates_ready_managed_asset(self):
        raw_png = _create_test_image_bytes(format_name="PNG", size=(400, 400))
        file_storage = FileStorage(
            stream=BytesIO(raw_png),
            filename="profile_pic.png",
            content_type="image/png",
        )

        asset = image_ingestion_service.ingest_image(
            user_id=self.regular_user.id,
            source_type="upload",
            file=file_storage,
            usage_type="avatar",
            upload_root=self.upload_root,
        )

        self.assertEqual(asset.processing_status, "ready")
        self.assertEqual(asset.security_status, "safe")
        self.assertEqual(asset.output_mime_type, "image/webp")
        self.assertTrue(asset.managed_url.startswith(f"/media/asset/{asset.id}"))
        self.assertEqual(asset.display_url, asset.managed_url)
        self.assertEqual(asset.output_width, 256)
        self.assertEqual(asset.output_height, 256)

        # Check file exists on disk
        self.assertTrue((self.upload_root / asset.storage_path).exists())

    @patch("app.services.image_worker_service.fetch_remote_image")
    def test_public_url_ingestion_uses_temp_url_and_async_worker_replaces_it(self, mock_fetch):
        public_url = "https://images.unsplash.com/photo-1543466835-00a7907e9de1"
        downloaded_bytes = _create_test_image_bytes(format_name="JPEG", size=(800, 600))
        mock_fetch.return_value = RemoteImagePayload(
            content=downloaded_bytes,
            filename="photo.jpg",
            mime_type="image/jpeg",
            source_url=public_url,
        )

        # Ingest external URL without depending on real DNS availability.
        with patch(
            "app.services.remote_image_fetcher._resolve_public_addresses",
            return_value=("93.184.216.34",),
        ):
            asset = image_ingestion_service.ingest_image(
                user_id=self.regular_user.id,
                source_type="external_url",
                source_url=public_url,
                usage_type="deck_cover",
                upload_root=self.upload_root,
                async_process=True,
            )

        # Step 1: Initial state: display_url is temporary external URL
        self.assertEqual(asset.processing_status, "pending")
        self.assertEqual(asset.display_url, public_url)
        self.assertIsNone(asset.managed_url)

        # Step 2: Run worker drain
        drain_result = image_worker_service.drain_image_queue(upload_root=self.upload_root)
        self.assertEqual(drain_result["processed_count"], 1)

        # Step 3: Refresh asset from DB and verify atomic replacement
        db.session.refresh(asset)
        self.assertEqual(asset.processing_status, "ready")
        self.assertEqual(asset.managed_url, f"/media/asset/{asset.id}")
        self.assertEqual(asset.display_url, asset.managed_url)
        self.assertEqual(asset.output_mime_type, "image/webp")
        self.assertIsNotNone(asset.processed_at)
        self.assertTrue((self.upload_root / asset.storage_path).exists())

    # -------------------------------------------------------------------------
    # 4. Media Asset Serving Route Tests
    # -------------------------------------------------------------------------
    def test_serve_managed_image_asset_headers(self):
        raw_png = _create_test_image_bytes(format_name="PNG", size=(200, 200))
        asset = image_ingestion_service.ingest_image(
            user_id=self.regular_user.id,
            source_type="upload",
            file=FileStorage(stream=BytesIO(raw_png), filename="test.png"),
            upload_root=self.upload_root,
        )

        resp = self.client.get(f"/media/asset/{asset.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/webp")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("Content-Security-Policy"), "default-src 'none'; sandbox")
        self.assertIn("public, max-age=", resp.headers.get("Cache-Control", ""))

    def test_serve_nonexistent_or_unready_asset_returns_404(self):
        resp = self.client.get("/media/asset/non-existent-uuid")
        self.assertEqual(resp.status_code, 404)

    # -------------------------------------------------------------------------
    # 5. REST APIs & Admin Security Alert Endpoints
    # -------------------------------------------------------------------------
    def test_api_ingest_via_post_form_and_json(self):
        with patch(
            "app.services.remote_image_fetcher._resolve_public_addresses",
            return_value=("93.184.216.34",),
        ):
            # Test JSON URL ingest
            resp = self.client.post(
                "/api/images/ingest",
                json={
                    "source_url": "https://cdn.example.com/sample.png",
                    "usage_type": "avatar",
                },
            )
            self.assertEqual(resp.status_code, 201)
            data = resp.get_json()
            self.assertIn("asset", data)
            self.assertEqual(data["asset"]["source_type"], "external_url")
            self.assertEqual(data["asset"]["display_url"], "https://cdn.example.com/sample.png")

            asset_id = data["asset"]["id"]
            status_resp = self.client.get(f"/api/images/{asset_id}/status")
            self.assertEqual(status_resp.status_code, 200)
            self.assertEqual(status_resp.get_json()["asset"]["id"], asset_id)

    def test_admin_security_alerts_api(self):
        # Create a test alert
        alert = AdminSecurityAlert(
            user_id=self.regular_user.id,
            threat_type="ssrf_attempt",
            severity="high",
            source_ip="10.0.0.1",
            source_url="http://127.0.0.1:8080/flag",
            message="SSRF attempt detected",
            details={"ip": "127.0.0.1"},
            is_resolved=False,
        )
        db.session.add(alert)
        db.session.commit()

        # 1. Unauthenticated request -> 401
        resp = self.client.get("/api/admin/security-alerts")
        self.assertEqual(resp.status_code, 401)

        # 2. Regular user request -> 403
        self.client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )
        resp = self.client.get("/api/admin/security-alerts")
        self.assertEqual(resp.status_code, 403)

        # 3. Admin user request -> 200
        self.client.delete("/api/session")
        self.client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "password123"},
        )
        resp = self.client.get("/api/admin/security-alerts?threat_type=ssrf_attempt")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["threat_type"], "ssrf_attempt")
        self.assertFalse(data["items"][0]["is_resolved"])

        # 4. Resolve alert
        patch_resp = self.client.patch(
            f"/api/admin/security-alerts/{alert.id}",
            json={"is_resolved": True},
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertTrue(patch_resp.get_json()["item"]["is_resolved"])
        self.assertEqual(patch_resp.get_json()["item"]["resolved_by_user_id"], self.admin_user.id)
