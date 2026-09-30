"""Benchmark NOTE v4 session open, commit and reads on disposable local MySQL.

Seeds one NOTE learner with a deck of N Notes (a share already studied), then
measures wall time and SQL statement counts for: the first open (pristine
Notes are materialized), a commit of a few answers, a second open, and the
remaining read endpoints. Prints JSON. Only a generated database is created
and dropped; the configured application database is untouched.

Usage: python scripts/bench_p5_session_open_mysql.py [--notes 2000] [--studied 300]
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time

from dotenv import load_dotenv
import pymysql
from sqlalchemy import event as sql_event

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from app.services.study_composition_service import make_compatibility_composition_id
from app.services.user_roles import ensure_default_user_roles
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from scripts.probe_p5_concurrency_mysql import _client, _commit_payload
from scripts.probe_p5_direct_replay_mysql import _probe_app
from scripts.probe_phase4_shadow_schema_mysql import (
    _connection_settings, _database_uri, _source_database_collation,
)

PROBE_NAME_PATTERN = re.compile(r"^flama_p5_direct_probe_[0-9]+_[a-f0-9]{8}$")


def _add_pristine_notes(app, learner: dict, count: int) -> None:
    """Notes created after enrollment are materialized by the next session open."""

    with app.app_context():
        deck = db.session.get(Deck, learner["deck_id"])
        template = db.session.execute(
            db.select(Template).order_by(Template.id)).scalars().first()
        rows = [Note(user_id=learner["user_id"], deck_id=deck.id, note_type_id=template.note_type_id,
                     field_values={"Word": f"p{i}", "Meaning": f"pm{i}", "Reading": f"pr{i}"})
                for i in range(count)]
        db.session.add_all(rows)
        db.session.flush()
        db.session.add_all(Card(note_id=note.id, template_id=template.id) for note in rows)
        db.session.commit()


def _seed_overlay(app, learner: dict, count: int) -> int:
    """Install a published deck of ``count`` Notes as a logical overlay; return the local deck."""

    from datetime import timedelta

    from models.deck_clone_deck_map import DeckCloneDeckMap
    from models.deck_install import DeckInstall
    from models.deck_marketplace_item import DeckMarketplaceItem

    with app.app_context():
        before = datetime.utcnow() - timedelta(days=1)
        publisher = User(username="bench-publisher", email="bench-publisher@example.test")
        db.session.add(publisher)
        db.session.flush()
        source_deck = Deck(name="Bench shared", owner_user_id=publisher.id)
        local_deck = Deck(name="Bench installed", owner_user_id=learner["user_id"])
        note_type = NoteType(name="Bench shared type", user_id=publisher.id)
        db.session.add_all([source_deck, local_deck, note_type])
        db.session.flush()
        db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
        template = Template(note_type_id=note_type.id, name="Shared", front_html="{{Word}}",
                            back_html="{{Word}}", is_default=True)
        db.session.add(template)
        db.session.flush()
        rows = [Note(user_id=publisher.id, note_type_id=note_type.id, deck_id=source_deck.id,
                     field_values={"Word": f"s{i}"}, created_at=before) for i in range(count)]
        db.session.add_all(rows)
        db.session.flush()
        db.session.add_all(Card(note_id=note.id, template_id=template.id, created_at=before) for note in rows)
        item = DeckMarketplaceItem(owner_user_id=publisher.id, source_deck_id=source_deck.id,
                                   source_note_type_id=note_type.id, title="Bench shared",
                                   publish_status="published", pricing_mode="free")
        db.session.add(item)
        db.session.flush()
        install = DeckInstall(deck_item_id=item.id, user_id=learner["user_id"], local_deck_id=local_deck.id,
                              clone_mode="logical_overlay", source_deck_id=source_deck.id,
                              source_note_type_id=note_type.id, source_owner_user_id=publisher.id,
                              base_snapshot_at=datetime.utcnow())
        db.session.add(install)
        db.session.flush()
        db.session.add(DeckCloneDeckMap(deck_install_id=install.id, local_deck_id=local_deck.id,
                                        source_deck_id=source_deck.id))
        db.session.commit()
        return int(local_deck.id)


def _seed(app, *, notes: int, child_decks: int = 5) -> dict:
    with app.app_context():
        db.create_all()
        ensure_default_user_roles(db.session)
        user = User(username="bench-learner", email="bench-learner@example.test")
        db.session.add(user)
        db.session.flush()
        root = Deck(name="Bench root", owner_user_id=user.id)
        db.session.add(root)
        db.session.flush()
        children = [Deck(name=f"Bench child {i}", owner_user_id=user.id, parent_id=root.id)
                    for i in range(child_decks)]
        db.session.add_all(children)
        note_type = NoteType(name="Bench type", user_id=user.id)
        db.session.add(note_type)
        db.session.flush()
        for position, name in enumerate(("Word", "Meaning", "Reading")):
            db.session.add(FieldDef(note_type_id=note_type.id, name=name, field_type="text", position=position))
        template = Template(note_type_id=note_type.id, name="Card 1",
                            front_html="{{Word}}", back_html="{{Meaning}} {{Reading}}", is_default=True)
        db.session.add(template)
        db.session.flush()
        rows = [Note(user_id=user.id, deck_id=children[i % child_decks].id, note_type_id=note_type.id,
                     field_values={"Word": f"w{i}", "Meaning": f"m{i}", "Reading": f"r{i}"})
                for i in range(notes)]
        db.session.add_all(rows)
        db.session.flush()
        db.session.add_all(Card(note_id=note.id, template_id=template.id) for note in rows)
        db.session.commit()
        stage_note_authority_enrollment(db.session, learner_user_id=int(user.id), now_utc=datetime.utcnow())
        db.session.commit()
        return {"user_id": int(user.id), "deck_id": root.id,
                "composition_id": make_compatibility_composition_id(note_type.id, template.id)}


class _Counter:
    def __init__(self, engine):
        self.engine = engine
        self.count = 0
        self.tables = Counter()

    def __enter__(self):
        sql_event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *_exc):
        sql_event.remove(self.engine, "before_cursor_execute", self._on)

    def _on(self, _conn, _cursor, statement, _params, _context, _many):
        self.count += 1
        words = statement.split()
        verb = words[0].upper() if words else "?"
        table = ""
        for keyword in ("FROM", "INTO", "UPDATE"):
            if keyword in words:
                index = words.index(keyword)
                if index + 1 < len(words):
                    table = words[index + 1]
                    break
        self.tables[f"{verb} {table}"] += 1


def _measure(app, name, fn, report):
    with app.app_context():
        engine = db.engine
    with _Counter(engine) as counter:
        started = time.perf_counter()
        response = fn()
        elapsed = time.perf_counter() - started
    report[name] = {
        "status": response.status_code, "seconds": round(elapsed, 3), "statements": counter.count,
        "top": dict(counter.tables.most_common(8)),
    }
    return response


def run(*, notes: int, studied: int, pristine: int = 0, overlay: int = 0) -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p5_direct_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("Benchmark requires a generated local MySQL database.")
    admin = pymysql.connect(**settings)
    created = False
    app = None
    report: dict = {"notes": notes, "studied": studied}
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
        app = _probe_app(_database_uri(settings, name))
        learner = _seed(app, notes=notes)
        client = _client(app, learner["user_id"])
        open_body = {
            "scope": "deck", "scope_id": learner["deck_id"], "composition_id": learner["composition_id"],
            "accepted_session_schema_versions": ["study-session.v4"],
            "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
        }
        opened = _measure(app, "open_first", lambda: client.post("/api/study/sessions", json=open_body), report)
        snapshot = opened.get_json()
        report["snapshot_bytes"] = len(opened.data)
        if studied:
            payload = _commit_payload(snapshot, studied)
            _measure(app, f"commit_{studied}", lambda: client.post(
                f"/api/study/sessions/{snapshot['session_id']}/commit", json=payload), report)
        _measure(app, "open_second", lambda: client.post("/api/study/sessions", json=open_body), report)
        if pristine:
            _add_pristine_notes(app, learner, pristine)
            _measure(app, f"open_with_{pristine}_pristine",
                     lambda: client.post("/api/study/sessions", json=open_body), report)
        if overlay:
            local_deck_id = _seed_overlay(app, learner, overlay)
            groups = client.get(f"/api/study/scopes/deck/{local_deck_id}/compositions").get_json()
            composition_id = next(
                item["composition_id"]
                for group in groups.get("groups", groups.get("composition_groups", []))
                for item in group.get("compositions", [])
            )
            overlay_body = {**open_body, "scope_id": local_deck_id, "composition_id": composition_id}
            opened = _measure(app, f"overlay_open_first_{overlay}",
                              lambda: client.post("/api/study/sessions", json=overlay_body), report)
            if opened.status_code == 201:
                overlay_snapshot = opened.get_json()
                overlay_payload = _commit_payload(overlay_snapshot, 20)
                _measure(app, "overlay_commit_20", lambda: client.post(
                    f"/api/study/sessions/{overlay_snapshot['session_id']}/commit", json=overlay_payload), report)
                _measure(app, "overlay_open_second",
                         lambda: client.post("/api/study/sessions", json=overlay_body), report)
            else:
                report["overlay_error"] = opened.get_json()
        deck = learner["deck_id"]
        for label, url in (
            ("dashboard", "/api/dashboard"),
            ("overview", "/api/statistics/overview?year=2026&timezone=Asia/Tokyo"),
            ("browse_tree", "/api/browse/decks/tree"),
            ("browse_cards", f"/api/browse/cards?deck_id={deck}&page=1&per_page=50"),
            ("study_next", f"/api/study/next?scope=deck&scope_id={deck}"),
            ("stats_today_future", "/api/statistics/today-future?timezone=Asia/Tokyo"),
        ):
            _measure(app, label, lambda url=url: client.get(url), report)
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
        admin.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--notes", type=int, default=2000)
    parser.add_argument("--studied", type=int, default=50)
    parser.add_argument("--pristine", type=int, default=0,
                        help="Notes added after enrollment, materialized by the last open.")
    parser.add_argument("--overlay", type=int, default=0,
                        help="Notes in a marketplace deck installed as a logical overlay.")
    args = parser.parse_args()
    print(json.dumps(run(notes=args.notes, studied=args.studied, pristine=args.pristine,
                         overlay=args.overlay), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
