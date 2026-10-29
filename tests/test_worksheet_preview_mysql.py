"""MySQL worksheet parity with rollback-only fixtures and temporary stroke files."""

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.orm import scoped_session, sessionmaker

from app import create_audit_app
from app.services.worksheets import stroke_cache, worksheet_service
from models import db
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.user import User


@unittest.skipUnless(os.getenv("FLAMA_MYSQL_TESTS") == "1", "requires opt-in loopback MySQL")
class WorksheetPreviewMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_audit_app({"TESTING": True, "REDIS_URL": ""})
        from app.api.v1.worksheets.routes import worksheets_bp
        cls.app.register_blueprint(worksheets_bp, url_prefix="/api")
        with cls.app.app_context():
            if db.engine.dialect.name != "mysql" or db.engine.url.host not in {"localhost", "127.0.0.1", "::1"}:
                raise RuntimeError("Worksheet regressions require loopback MySQL")

    def setUp(self):
        context = self.app.app_context()
        context.push()
        self.addCleanup(context.pop)
        connection = db.engine.connect()
        self.addCleanup(connection.close)
        outer = connection.begin()
        self.addCleanup(outer.rollback)

        def forbid_commit(_connection):
            raise AssertionError("Worksheet tests must never commit the outer transaction")

        event.listen(connection, "commit", forbid_commit)
        sessions = scoped_session(sessionmaker(bind=connection, join_transaction_mode="create_savepoint"))
        session_patch = patch.object(db, "session", sessions)
        session_patch.start()
        self.addCleanup(session_patch.stop)
        self.addCleanup(sessions.remove)
        files = tempfile.TemporaryDirectory()
        self.addCleanup(files.cleanup)
        self.static_root = Path(files.name) / "static"
        for locale in ("ja", "zh"):
            target = self.static_root / "strokes" / locale / "65e5.svg"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 109 109">'
                '<path id="kvg:065e5-s1" class="flama-kvg-stroke" d="M10,10 L50,50" />'
                '<path id="kvg:065e5-s2" class="flama-kvg-stroke" d="M50,10 L10,50" /></svg>', encoding="utf-8")
        original_static = self.app.static_folder
        self.app.static_folder = str(self.static_root)
        self.addCleanup(setattr, self.app, "static_folder", original_static)
        stroke_cache._read_svg.cache_clear()
        self.addCleanup(stroke_cache._read_svg.cache_clear)
        token = uuid4().hex
        self.user = User(username=f"worksheet-quickwin-{token}", email=f"{token}@example.invalid")
        db.session.add(self.user)
        db.session.flush()
        note_type = NoteType(user_id=self.user.id, name="Kanji")
        db.session.add(note_type)
        db.session.flush()
        db.session.add(FieldDef(note_type_id=note_type.id, name="Expression", field_type="array", position=0))
        self.deck = Deck(name="Kanji worksheet", owner_user_id=self.user.id, note_type_id=note_type.id)
        db.session.add(self.deck)
        db.session.flush()
        # Repeated characters across native-array notes must preserve all rows.
        db.session.add_all([Note(user_id=self.user.id, note_type_id=note_type.id, deck_id=self.deck.id,
            field_values={"Expression": ["日", ["日"]]}) for _ in range(3)])
        db.session.commit()

    def _payload(self, template="kanji_stroke", locale="ja"):
        return {"deck_id": self.deck.id, "template_id": template, "scope": "first_n", "limit": 30,
            "options": {"locale": locale, "show_step_numbers": True, "step_highlight_color": "#ab1234"}}

    def test_cached_and_uncached_preview_and_print_html_are_identical(self):
        for template in ("kanji_stroke", "kanji_compact", "kanji_step_by_step"):
            for locale in ("ja", "zh"):
                with self.subTest(template=template, locale=locale):
                    payload = self._payload(template, locale)
                    with patch.object(worksheet_service, "read_stroke_svg", side_effect=lambda path: path.read_text(encoding="utf-8")):
                        expected = worksheet_service.generate_worksheet_preview(user_id=self.user.id, payload=payload)
                    cold = worksheet_service.generate_worksheet_preview(user_id=self.user.id, payload=payload)
                    warm = worksheet_service.generate_worksheet_preview(user_id=self.user.id, payload=payload)
                    self.assertGreater(expected["total_items"], 0)
                    self.assertEqual(cold, expected)
                    self.assertEqual(warm, expected)
                    self.assertEqual(worksheet_service.render_printable_html(warm),
                        worksheet_service.render_printable_html(expected))

    def test_preview_api_contract_remains_synchronous(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.user.id)
        for _ in range(2):
            response = client.post("/api/worksheets/preview", json=self._payload())
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["template"]["id"], "kanji_compact")
            self.assertGreater(data["total_items"], 0)
            self.assertIsInstance(data["pages"], list)

    def test_cache_does_not_expose_private_deck_content(self):
        payload = self._payload()
        worksheet_service.generate_worksheet_preview(user_id=self.user.id, payload=payload)
        other = User(username=f"other-{uuid4().hex}", email=f"{uuid4().hex}@example.invalid")
        db.session.add(other)
        db.session.flush()
        with self.assertRaises(worksheet_service.WorksheetServiceError) as caught:
            worksheet_service._check_deck_access(other.id, self.deck.id)
        self.assertEqual(caught.exception.status, 403)
        # Kanji templates support a blank standalone fallback on inaccessible
        # decks. A warm file cache must not supply any of the private notes.
        preview = worksheet_service.generate_worksheet_preview(user_id=other.id, payload=payload)
        self.assertEqual(preview["deck_id"], 0)
        standalone = worksheet_service.generate_worksheet_preview(
            user_id=other.id, payload={**payload, "deck_id": 0})
        self.assertEqual(preview, standalone)


if __name__ == "__main__":
    unittest.main()
