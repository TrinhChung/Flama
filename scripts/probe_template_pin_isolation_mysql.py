"""Regression checks in generated loopback MySQL schemas; never writes DB_NAME."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import secrets
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
import pymysql
from sqlalchemy import event

from app import create_audit_app
from app.repositories import template_library_repository as library
from app.repositories import template_release_repository as releases
from app.repositories.note_type_summary_repository import list_summaries
from app.services import template_release_service as service
from app.services import flashcards_share_service as share
from models import db
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.study_application import StudyApplication
from models.template import Template
from tests import test_template_pinned_new_install as fixture
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

EVIDENCE = {}
NAME = re.compile(r"^flama_pin_isolation_probe_[0-9]+_[a-f0-9]{12}$")


class PinIsolationMySQLTests(fixture.PinnedNewInstallTests):
    settings = None

    def setUp(self):
        print(f"MySQL: {self._testMethodName}", file=sys.stderr, flush=True)
        self.schema = f"flama_pin_isolation_probe_{os.getpid()}_{secrets.token_hex(6)}"
        self.admin = pymysql.connect(**self.settings)
        self.created = False
        self.addCleanup(self._cleanup_schema)
        self._guard()
        collation = _source_database_collation(self.admin)
        with self.admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (self.schema,))
            if cursor.fetchone():
                raise RuntimeError("Generated schema exists; refusing reuse.")
            cursor.execute(f"CREATE DATABASE `{self.schema}` CHARACTER SET utf8mb4 COLLATE {collation}")
            self.created = True
        def mysql_app(config):
            return create_audit_app({**config, "SQLALCHEMY_DATABASE_URI": _database_uri(self.settings, self.schema)})
        with patch.object(fixture, "create_audit_app", side_effect=mysql_app):
            super().setUp()
        if db.engine.url.database != self.schema or set(db.engines) != {None}:
            raise RuntimeError("Probe engine outside generated schema.")

    def _guard(self):
        if self.settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not NAME.fullmatch(self.schema) or self.schema == os.getenv("DB_NAME", "").strip():
            raise RuntimeError("Probe requires a unique generated loopback schema.")

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()

    def _cleanup_schema(self):
        if self.created:
            self._guard()
            with self.admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{self.schema}`")
        self.admin.close()

    def _second_install(self):
        second_deck = Deck(name="Second source", owner_user_id=self.author.id, note_type_id=self.nt.id)
        db.session.add(second_deck)
        db.session.flush()
        item = DeckMarketplaceItem(owner_user_id=self.author.id, source_deck_id=second_deck.id,
            source_note_type_id=self.nt.id, title="Second source", publish_status="published", pricing_mode="free")
        db.session.add(item)
        db.session.flush()
        release = DeckRelease(deck_item_id=item.id, sequence_no=1, version_label="1", status="published")
        db.session.add(release)
        db.session.flush()
        service.capture_deck_release_template_pins(db.session, release, actor_user_id=self.author.id)
        item.current_release_id = release.id
        db.session.commit()
        result = share.install_shared_deck_item_for_user(item, user_id=self.learner.id)
        self.assertTrue(result["created"])
        db.session.commit()
        return release

    def _effective(self, release):
        return releases.load_effective_template_overrides(db.session, user_id=self.learner.id,
            source_template_ids=[self.template.id], release_pins=releases.deck_pins(db.session, release.id))[self.template.id]

    def test_another_install_preserves_old_pin_and_projects_only_personal_edits(self):
        old = self._publish()
        install, _ = self._install(share.install_shared_deck_item_for_user)
        self.template.front_html = "second {{term}}"
        db.session.commit()
        new = self._second_install()
        self.assertEqual(self._effective(old).front_html, "frozen {{term}}")
        self.assertEqual(self._effective(new).front_html, "second {{term}}")
        sub = releases.subscription(db.session, user_id=self.learner.id, source_template_id=self.template.id)
        local = db.session.get(Template, sub["local_template_id"])
        local.shared_css = ".personal {color: red}"
        db.session.commit()
        self.assertEqual(self._effective(old).front_html, "frozen {{term}}")
        self.assertEqual(self._effective(new).front_html, "second {{term}}")
        self.assertEqual(self._effective(old).shared_css, local.shared_css)
        self.assertEqual(self.template.shared_css or "", "")
        dto = service.list_install_templates(user_id=self.learner.id, install_id=install.id)
        self.assertEqual(dto["deck_release"]["id"], old.id)
        self.assertEqual(dto["items"][0]["pinned_release"]["id"], releases.deck_pins(db.session, old.id)[self.template.id]["template_release_id"])
        with self.assertRaises(service.TemplateReleaseError) as error:
            service.list_install_templates(user_id=self.author.id, install_id=install.id)
        self.assertEqual(error.exception.status, 404)
        EVIDENCE["pins_and_personal_edits"] = "two deck releases stay distinct; CSS edits stay personal; ownership enforced"

    def test_repeated_occurrences_and_removal_keep_identity(self):
        extra = StudyApplication(note_type_id=self.nt.id, template_id=self.template.id,
            occurrence_key="reverse", source_ord=12, position=7, input_bindings={"term": self.field.id}, status_code="ACTIVE")
        db.session.add(extra)
        db.session.commit()
        old = self._publish()
        install, local_nt = self._install(share.install_shared_deck_item_for_user)
        apps = library.applications(db.session, local_nt.id)
        self.assertEqual({a.occurrence_key for a in apps}, {"compat", "reverse"})
        self.assertEqual({a.source_ord for a in apps}, {8, 12})
        original = {a.occurrence_key: a.id for a in apps}
        extra.status_code = "RETIRED"
        release = DeckRelease(deck_item_id=self.item.id, sequence_no=2, version_label="2", status="published", parent_release_id=old.id)
        db.session.add(release)
        db.session.flush()
        service.capture_deck_release_template_pins(db.session, release, actor_user_id=self.author.id)
        install.applied_release_id = release.id
        db.session.flush()
        service.stage_install_template_subscriptions(db.session, install_id=install.id, user_id=self.learner.id, from_release_id=old.id)
        db.session.commit()
        active = library.applications(db.session, local_nt.id)
        self.assertEqual([(a.occurrence_key, a.id) for a in active], [("compat", original["compat"])])
        EVIDENCE["occurrences"] = "both occurrences received; removing one retires only its identity"

    def test_summary_is_one_small_scoped_query(self):
        for number in range(9):
            db.session.add(NoteType(name=f"Summary {number}", user_id=self.author.id))
        db.session.commit()
        author_id = self.author.id
        statements = []
        def record(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)
        event.listen(db.engine, "before_cursor_execute", record)
        try:
            rows = list_summaries(user_id=author_id)
        finally:
            event.remove(db.engine, "before_cursor_execute", record)
        self.assertEqual(len(statements), 1)
        self.assertEqual(len(rows), 10)
        self.assertNotIn("front_html", json.dumps(rows))
        self.assertNotIn("frozen", json.dumps(rows))
        own = next(row for row in rows if row["id"] == self.nt.id)
        self.assertEqual((own["field_count"], own["template_count"]), (1, 1))
        self.assertEqual(list_summaries(user_id=self.learner.id), [])
        EVIDENCE["manager_summary"] = {"note_types": 10, "sql_statements": len(statements), "payload_bytes": len(json.dumps(rows).encode())}

    def test_deck_after_standalone_receipt_preserves_frozen_note_type(self):
        from app.services.note_type_release_service import stage_publication, stage_receipt
        release = stage_publication(db.session, note_type=self.nt, actor_user_id=self.author.id)
        db.session.commit()
        receipt = stage_receipt(db.session, source_note_type=self.nt, user_id=self.learner.id)
        db.session.commit()
        nt_install = db.session.query(NoteTypeInstall).filter_by(user_id=self.learner.id, source_note_type_id=self.nt.id).one()
        before = [row.id for row in library.applications(db.session, nt_install.installed_note_type_id)]
        self.template.front_html = "later deck {{term}}"
        db.session.commit()
        self._publish()
        self._install(share.install_shared_deck_item_for_user)
        after = library.applications(db.session, nt_install.installed_note_type_id)
        self.assertEqual([row.id for row in after], before)
        self.assertEqual(after[0].template.front_html, "frozen {{term}}")
        self.assertEqual(nt_install.applied_release_id, release.id)
        EVIDENCE["standalone_then_deck"] = "no duplicate or overwritten frozen NoteType application"


def run():
    load_dotenv(ROOT / ".env", override=False)
    PinIsolationMySQLTests.settings = _connection_settings()
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(PinIsolationMySQLTests))
    return {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests_run": result.testsRun,
        "configured_database_modified": False, "evidence": EVIDENCE,
        "failures": [trace for _, trace in result.failures + result.errors]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve-fixture", action="store_true", help="Serve disposable browser data on loopback:4789 until stopped.")
    args = parser.parse_args()
    if args.serve_fixture:
        load_dotenv(ROOT / ".env", override=False)
        PinIsolationMySQLTests.settings = _connection_settings()
        case = PinIsolationMySQLTests("test_summary_is_one_small_scoped_query")
        try:
            case.setUp()
            first = case._publish()
            install, local_nt = case._install(share.install_shared_deck_item_for_user)
            case.template.front_html = "second {{term}}"
            db.session.commit()
            case._second_install()
            password = secrets.token_urlsafe(24)
            case.learner.set_password(password)
            db.session.commit()
            output = ROOT / "output" / "playwright" / "template-stability-fixture.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({"username": case.learner.username, "password": password,
                "install_id": install.id, "note_type_id": local_nt.id,
                "template_id": case.template.id, "schema": case.schema, "backend": "http://127.0.0.1:4789"}), encoding="utf-8")
            print("Disposable browser fixture ready; local credentials in output/playwright/template-stability-fixture.json", flush=True)
            from app.routes import register_blueprints
            register_blueprints(case.app)
            case.app.run(host="127.0.0.1", port=4789, use_reloader=False)
        finally:
            if hasattr(case, "context"):
                case.tearDown()
            case.doCleanups()
        raise SystemExit(0)
    report = run()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
