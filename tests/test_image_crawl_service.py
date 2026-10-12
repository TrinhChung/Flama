"""Unit and integration tests for the Image Crawl Service and endpoints."""

from __future__ import annotations

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from app import create_app
from app.services import image_crawl_service
from app.services.remote_image_fetcher import RemoteImagePayload
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.deck import Deck
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from models.user_role import UserRole


def _make_test_png(color: tuple[int, int, int, int] = (255, 0, 0, 255)) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (32, 32), color).save(output, format="PNG")
    return output.getvalue()


_PNG_BYTES = _make_test_png()
_SAFE_SVG_BYTES = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50">'
    b'<rect width="50" height="50" fill="green"/></svg>'
)

from tests.study_note_fixtures import attach_template, create_note_user

class ImageCrawlServiceTests(unittest.TestCase):
    def setUp(self):
        self.upload_tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": self.upload_tmp.name,
                "FLASHCARD_MEDIA_MAX_BYTES": 2 * 1024 * 1024,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            role = UserRole.query.filter_by(code="regular").first()
            if not role:
                role = UserRole(code="regular", name="Regular User")
                db.session.add(role)
                db.session.commit()

            user1 = create_note_user(db.session,
                username="crawler-user1",
                email="user1@example.com",
                is_admin=False,
                role_id=role.id,
            )
            user1.set_password("password")
            user2 = create_note_user(db.session,
                username="crawler-user2",
                email="user2@example.com",
                is_admin=False,
                role_id=role.id,
            )
            user2.set_password("password")
            db.session.add_all([user1, user2])
            db.session.commit()

            self.user1_id = user1.id
            self.user2_id = user2.id

            # Create NoteType with image and markdown fields
            note_type = NoteType(
                name="Vocab Note Type",
                user_id=user1.id,
            )
            db.session.add(note_type)
            db.session.flush()

            field_front = FieldDef(
                note_type_id=note_type.id,
                name="Word",
                field_type="text",
                position=0,
            )
            field_img = FieldDef(
                note_type_id=note_type.id,
                name="Illustration",
                field_type="image",
                position=1,
            )
            field_md = FieldDef(
                note_type_id=note_type.id,
                name="NotesMD",
                field_type="markdown",
                position=2,
            )
            db.session.add_all([field_front, field_img, field_md])

            template = attach_template(db.session, owner_user_id=user1.id,
                note_type_id=note_type.id,
                name="Card 1",
                front_html="<div>{{Word}}</div>",
                back_html="<div>{{Word}}<br><img src=\"{{Illustration}}\"><br>{{{NotesMD}}}</div>",
            )
            db.session.add(template)
            db.session.flush()

            deck = Deck(name="Japanese Vocab", owner_user_id=user1.id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id

            note1 = Note(
                user_id=user1.id,
                deck_id=deck.id,
                note_type_id=note_type.id,
                field_values={"Word": "Neko", "Illustration": "", "NotesMD": ""},
            )
            db.session.add(note1)
            db.session.commit()

            self.note_type_id = note_type.id
            self.note1_id = note1.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.upload_tmp.cleanup()

    def _login(self, email: str = "user1@example.com"):
        return self.client.post(
            "/login",
            data={"email": email, "password": "password"},
            follow_redirects=True,
        )

    @patch("app.services.image_crawl_service.fetch_remote_image")
    def test_crawl_remote_image_success(self, mock_fetch):
        mock_fetch.return_value = RemoteImagePayload(
            content=_PNG_BYTES,
            filename="cat.png",
            mime_type="image/png",
            source_url="https://example.com/cat.png",
        )

        with self.app.app_context():
            result = image_crawl_service.crawl_remote_image(
                "https://example.com/cat.png",
                max_bytes=1024 * 1024,
                field_name="Illustration",
            )
            self.assertEqual(result.mime_type, "image/webp")
            self.assertTrue(result.safe_original_filename.endswith(".webp"))
            self.assertGreater(result.size_bytes, 0)
            self.assertTrue(len(result.sha256) == 64)

    def test_crawl_remote_image_ssrf_blocked(self):
        with self.app.app_context():
            # Localhost / IP forbidden
            with self.assertRaises(image_crawl_service.ImageCrawlError) as cm:
                image_crawl_service.crawl_remote_image("http://127.0.0.1:8000/bad.png")
            self.assertEqual(cm.exception.error, "IMAGE_REMOTE_HOST_NOT_ALLOWED")

            with self.assertRaises(image_crawl_service.ImageCrawlError) as cm:
                image_crawl_service.crawl_remote_image("http://localhost/bad.png")
            self.assertEqual(cm.exception.error, "IMAGE_REMOTE_HOST_NOT_ALLOWED")

            # Non-http scheme
            with self.assertRaises(image_crawl_service.ImageCrawlError) as cm:
                image_crawl_service.crawl_remote_image("ftp://example.com/bad.png")
            self.assertEqual(cm.exception.error, "IMAGE_SCHEME_NOT_ALLOWED")

    @patch("app.services.image_crawl_service.fetch_remote_image")
    def test_crawl_and_save_note_media(self, mock_fetch):
        mock_fetch.return_value = RemoteImagePayload(
            content=_PNG_BYTES,
            filename="flower.png",
            mime_type="image/png",
            source_url="https://cdn.example.com/flower.png",
        )

        with self.app.app_context():
            payload, status = image_crawl_service.crawl_and_save_note_media(
                user_id=self.user1_id,
                note_id=self.note1_id,
                field_name="Illustration",
                url="https://cdn.example.com/flower.png",
                upload_root=Path(self.upload_tmp.name),
                max_bytes=2 * 1024 * 1024,
            )
            self.assertEqual(status, 201)
            self.assertTrue(payload["url"].startswith("/media/proxy/"))
            self.assertEqual(payload["field_name"], "Illustration")
            self.assertEqual(payload["source_url"], "https://cdn.example.com/flower.png")

            # Check Note field was updated
            note = Note.query.get(self.note1_id)
            self.assertEqual(
                note.field_values.get("Illustration"),
                f"/media/proxy/{payload['asset_id']}",
            )

            # Verify file exists on disk
            asset = MediaAsset.query.get(payload["asset_id"])
            full_path = Path(self.upload_tmp.name) / asset.storage_path
            self.assertTrue(full_path.exists())

            # Crawling same image again should deduplicate (HTTP 200)
            payload2, status2 = image_crawl_service.crawl_and_save_note_media(
                user_id=self.user1_id,
                note_id=self.note1_id,
                field_name="Illustration",
                url="https://cdn.example.com/flower.png",
                upload_root=Path(self.upload_tmp.name),
                max_bytes=2 * 1024 * 1024,
            )
            self.assertEqual(status2, 200)
            self.assertEqual(payload2["asset_id"], payload["asset_id"])

    @patch("app.services.image_crawl_service.fetch_remote_image")
    def test_crawl_and_save_note_media_unauthorized_note(self, mock_fetch):
        with self.app.app_context():
            # User 2 cannot crawl media into User 1's note
            with self.assertRaises(image_crawl_service.ImageCrawlError) as cm:
                image_crawl_service.crawl_and_save_note_media(
                    user_id=self.user2_id,
                    note_id=self.note1_id,
                    field_name="Illustration",
                    url="https://cdn.example.com/flower.png",
                    upload_root=Path(self.upload_tmp.name),
                    max_bytes=2 * 1024 * 1024,
                )
            self.assertEqual(cm.exception.status, 404)

    @patch("app.services.image_crawl_service.fetch_remote_image")
    def test_crawl_note_media_batch(self, mock_fetch):
        mock_fetch.return_value = RemoteImagePayload(
            content=_PNG_BYTES,
            filename="badge.png",
            mime_type="image/png",
            source_url="https://cdn.example.com/badge.png",
        )

        with self.app.app_context():
            items = [
                {
                    "item_id": "item_1",
                    "note_id": self.note1_id,
                    "field_name": "Illustration",
                    "url": "https://cdn.example.com/badge.png",
                },
                {
                    "item_id": "item_2",
                    "note_id": self.note1_id,
                    "field_name": "InvalidField",
                    "url": "https://cdn.example.com/badge.png",
                },
            ]
            result = image_crawl_service.crawl_note_media_batch(
                user_id=self.user1_id,
                items=items,
                upload_root=Path(self.upload_tmp.name),
                max_bytes=2 * 1024 * 1024,
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["success_count"], 1)
            self.assertEqual(result["failed_count"], 1)
            self.assertEqual(result["items"][0]["status"], "success")
            self.assertEqual(result["items"][1]["status"], "failed")

    @patch("app.services.image_crawl_service.fetch_remote_image")
    def test_crawl_and_rewrite_markdown_media(self, mock_fetch):
        mock_fetch.return_value = RemoteImagePayload(
            content=_PNG_BYTES,
            filename="diagram.png",
            mime_type="image/png",
            source_url="https://cdn.example.com/diagram.png",
        )

        with self.app.app_context():
            md_text = (
                "# Lesson 1\n"
                "Here is an image: ![Kanji Tree](https://cdn.example.com/diagram.png)\n"
                "And an HTML image: <img src=\"https://cdn.example.com/diagram.png\" alt=\"Kanji\" />"
            )

            result = image_crawl_service.crawl_and_rewrite_markdown_media(
                user_id=self.user1_id,
                note_id=self.note1_id,
                markdown_text=md_text,
                field_name="NotesMD",
                upload_root=Path(self.upload_tmp.name),
                max_bytes=2 * 1024 * 1024,
            )
            self.assertEqual(result["crawled_count"], 1)
            rewritten = result["rewritten_markdown"]
            self.assertNotIn("https://cdn.example.com/diagram.png", rewritten)
            self.assertIn("/media/proxy/", rewritten)

    @patch("app.services.image_crawl_service.fetch_remote_html")
    def test_extract_images_from_page(self, mock_html):
        mock_html.return_value = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Japanese Grammar Guide</title>
            <meta property="og:image" content="https://example.com/hero.jpg" />
            <meta name="twitter:image" content="/images/twitter-card.png" />
        </head>
        <body>
            <h1>Welcome</h1>
            <img src="/static/chart.png" alt="Grammar Chart" />
            <img src="https://cdn.example.com/kanji.png" alt="Kanji Table" />
            <img src="data:image/png;base64,iVBORw0KGgo..." alt="Inline data" />
        </body>
        </html>
        """

        result = image_crawl_service.extract_images_from_page(
            "https://example.com/grammar",
            max_images=10,
        )
        self.assertEqual(result["title"], "Japanese Grammar Guide")
        self.assertEqual(len(result["images"]), 4)
        urls = [img["url"] for img in result["images"]]
        self.assertIn("https://example.com/hero.jpg", urls)
        self.assertIn("https://example.com/images/twitter-card.png", urls)
        self.assertIn("https://example.com/static/chart.png", urls)
        self.assertIn("https://cdn.example.com/kanji.png", urls)

    @patch("app.services.image_crawl_service.fetch_remote_image")
    def test_api_crawl_note_media_endpoint(self, mock_fetch):
        mock_fetch.return_value = RemoteImagePayload(
            content=_PNG_BYTES,
            filename="sky.png",
            mime_type="image/png",
            source_url="https://images.example.com/sky.png",
        )

        self._login("user1@example.com")
        res = self.client.post(
            f"/api/notes/{self.note1_id}/media/crawl",
            json={
                "field_name": "Illustration",
                "url": "https://images.example.com/sky.png",
            },
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertIn("asset_id", data)
        self.assertTrue(data["url"].startswith("/media/proxy/"))

    @patch("app.services.image_crawl_service.fetch_remote_image")
    def test_api_crawl_markdown_images_endpoint(self, mock_fetch):
        mock_fetch.return_value = RemoteImagePayload(
            content=_PNG_BYTES,
            filename="sample.png",
            mime_type="image/png",
            source_url="https://images.example.com/sample.png",
        )

        self._login("user1@example.com")
        res = self.client.post(
            f"/api/notes/{self.note1_id}/markdown/crawl-images",
            json={
                "field_name": "NotesMD",
                "markdown": "Look at ![photo](https://images.example.com/sample.png)",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["crawled_count"], 1)
        self.assertIn("/media/proxy/", data["rewritten_markdown"])

    @patch("app.services.image_crawl_service.fetch_remote_html")
    def test_api_crawl_page_endpoint(self, mock_html):
        mock_html.return_value = """
        <html>
        <head><meta property="og:image" content="https://example.com/cover.png"></head>
        <body><img src="/pic.png"></body>
        </html>
        """
        self._login("user1@example.com")
        res = self.client.post(
            "/api/media/crawl-page",
            json={"page_url": "https://example.com/article"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data["images"]), 2)

    @patch("app.services.image_crawl_service.fetch_remote_image")
    def test_mcp_create_note_auto_crawl_image(self, mock_fetch):
        from app.services import mcp_tool_service

        mock_fetch.return_value = RemoteImagePayload(
            content=_PNG_BYTES,
            filename="dog.png",
            mime_type="image/png",
            source_url="https://images.example.com/dog.png",
        )

        with self.app.app_context():
            result = mcp_tool_service.create_note(
                user_id=self.user1_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {
                        "Word": "Inu",
                        "Illustration": "https://images.example.com/dog.png",
                        "NotesMD": "Markdown with ![dog](https://images.example.com/dog.png)",
                    },
                },
            )
            note_id = result["note_id"]
            note = Note.query.get(note_id)
            # Illustration field should be converted to the canonical proxy URL.
            self.assertNotEqual(note.field_values.get("Illustration"), "https://images.example.com/dog.png")
            self.assertTrue(note.field_values.get("Illustration", "").startswith("/media/proxy/"))
            # NotesMD should be rewritten with /media/proxy/
            self.assertNotIn("https://images.example.com/dog.png", note.field_values.get("NotesMD"))
            self.assertIn("/media/proxy/", note.field_values.get("NotesMD"))

    @patch("app.services.image_crawl_service.fetch_remote_image")
    def test_mcp_crawl_note_media_tool(self, mock_fetch):
        from app.services.mcp_tool_registry import call_mcp_tool

        mock_fetch.return_value = RemoteImagePayload(
            content=_PNG_BYTES,
            filename="mountain.png",
            mime_type="image/png",
            source_url="https://images.example.com/mountain.png",
        )

        with self.app.app_context():
            res = call_mcp_tool(
                tool_name="crawl_note_media",
                user_id=self.user1_id,
                arguments={
                    "note_id": self.note1_id,
                    "field_name": "Illustration",
                    "url": "https://images.example.com/mountain.png",
                },
            )
            self.assertFalse(res.get("isError", False))
            struct = res.get("structuredContent", {})
            self.assertTrue(struct.get("success"))
            self.assertTrue(struct.get("url", "").startswith("/media/proxy/"))

    @patch("app.services.image_crawl_service.fetch_remote_html")
    def test_mcp_extract_page_images_tool(self, mock_html):
        from app.services.mcp_tool_registry import call_mcp_tool

        mock_html.return_value = """
        <html>
        <head><meta property="og:image" content="https://example.com/banner.png"></head>
        <body><img src="/article-img.png"></body>
        </html>
        """

        with self.app.app_context():
            res = call_mcp_tool(
                tool_name="extract_page_images",
                user_id=self.user1_id,
                arguments={
                    "page_url": "https://example.com/post",
                    "max_images": 5,
                },
            )
            self.assertFalse(res.get("isError", False))
            struct = res.get("structuredContent", {})
            self.assertEqual(len(struct.get("images", [])), 2)


