"""Reproduce audit observations without opening the configured application DB.

Run from the repo with .venv/Scripts/python.exe and --build pointing to a
separate Vite --manifest build. All seeded data lives in SQLite memory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
AUDITED_SOURCES = (
    "app/settings.py", "app/repositories/deck_tree_query.py", "app/services/connect/actions.py",
    "app/services/marketplace_note_type_service.py", "app/services/marketplace_query_service.py",
    "app/services/template_library_service.py", "frontend/src/features/study/session/sessionStore.ts",
    "frontend/src/features/study/session/sessionRestore.ts", "frontend/src/shared/config/i18n/index.ts",
    "frontend/src/features/marketplace/pages/MarketplacePages.tsx",
)


def inventory():
    extensions = {".py", ".ts", ".tsx", ".cs", ".json", ".js"}
    counts = {}
    for name in ("app", "models", "migrations", "frontend/src", "flama-audio/src"):
        files = [p for p in (REPO / name).rglob("*") if p.is_file()
                 and p.suffix in extensions and not {"bin", "obj", "node_modules"}.intersection(p.parts)]
        counts[name] = {"files_scanned": len(files), "bytes": sum(p.stat().st_size for p in files)}
    return counts


def bundle(build):
    build = Path(build)
    manifest = json.loads((build / ".vite/manifest.json").read_text(encoding="utf-8"))
    def closure(key):
        found = set()
        def visit(current):
            if current in found:
                return
            found.add(current)
            for other in manifest[current].get("imports", []):
                visit(other)
        visit(key)
        return found
    result = {}
    for key in manifest:
        if key == "index.html" or any(s in key for s in ("BrowsePage.tsx", "StudyPage.tsx", "MarketplacePages.tsx", "TemplateLibraryPage.tsx")):
            keys = closure(key)
            files = [manifest[k]["file"] for k in sorted(keys) if manifest[k]["file"].endswith(".js")]
            sources = []
            for f in files:
                source_map = build / (f + ".map")
                if source_map.exists():
                    sources.extend(json.loads(source_map.read_text(encoding="utf-8"))["sources"])
            result[key] = {
                "static_js_files": files,
                "static_js_raw_bytes": sum((build / f).stat().st_size for f in files),
                "static_js_gzip_bytes": sum(len(gzip.compress((build / f).read_bytes(), mtime=0)) for f in files),
                "locale_json_sources": sorted(s for s in sources if "/locales/" in s and s.endswith(".json")),
                "contains_worksheet": any(s.endswith("/components/DeckWorksheetModal.tsx") for s in sources),
                "contains_guide_page": any("GuidePage.tsx" in s for s in sources),
            }
    result["largest_js"] = sorted([
        {"file": p.name, "raw_bytes": p.stat().st_size,
         "gzip_bytes": len(gzip.compress(p.read_bytes(), mtime=0))}
        for p in (build / "assets").glob("*.js")
    ], key=lambda row: row["raw_bytes"], reverse=True)[:10]
    return result


def sqlite_probes():
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app import create_app
    from models import db
    from models.user import User
    from models.deck import Deck
    from models.note_type import NoteType
    from models.template import Template
    from models.note import Note
    from types import SimpleNamespace
    from app.services.connect.actions import _is_duplicate
    from app.repositories.deck_tree_query import query_accessible_stats_decks
    from app.services.marketplace_note_type_service import list_shared_note_types
    from app.services.marketplace.hub.builder import build_note_type_marketplace_hub, parse_marketplace_filters
    from app.services.template_library_service import list_templates

    app = create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {}, "SECRET_KEY": "synthetic-audit-only",
        "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
        "REVIEW_ANALYTICS_WRITE_ENABLED": False, "DECK_COUNT_WRITE_ENABLED": False,
        "WTF_CSRF_ENABLED": False,
    })
    results = []
    with app.app_context():
        assert db.engine.url.drivername == "sqlite" and db.engine.url.database == ":memory:"
        db.create_all()
        learner = User(username="audit-learner", email="audit-learner@example.invalid", password_hash="unused")
        publisher = User(username="audit-publisher", email="audit-publisher@example.invalid", password_hash="unused")
        db.session.add_all([learner, publisher])
        db.session.flush()
        learner_id, publisher_id = learner.id, publisher.id
        db.session.add_all([Deck(name=f"foreign-{i}", owner_user_id=publisher_id) for i in range(1000)])
        for i in range(600):
            nt = NoteType(user_id=publisher_id, name=f"audit-type-{i:04}",
                          publish_status="published" if i < 100 else "private")
            db.session.add(nt)
            db.session.flush()
            if i < 100:
                db.session.add(Template(note_type_id=nt.id, owner_user_id=publisher_id,
                                        name=f"audit-template-{i}", front_html="{{Word}}" + "x" * 8192,
                                        back_html="{{Word}}" + "y" * 8192, shared_css=""))
        db.session.commit()

        def measure(label, call):
            db.session.remove()
            loaded, sql_tables = Counter(), Counter()
            statements = []
            def sql(_conn, _cursor, statement, _params, _ctx, _many):
                if statement.lstrip().lower().startswith("select"):
                    statements.append(statement)
                    for table in ("decks", "card_progress", "note_types", "templates", "study_applications"):
                        if f"FROM {table}" in statement or f"JOIN {table}" in statement:
                            sql_tables[table] += 1
            def hydrated(_session, instance):
                loaded[type(instance).__name__] += 1
            event.listen(db.engine, "before_cursor_execute", sql)
            event.listen(Session, "loaded_as_persistent", hydrated)
            try:
                start = perf_counter()
                with app.test_request_context():
                    payload = call()
                elapsed = (perf_counter() - start) * 1000
                size = len(json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8"))
                rows = len(payload["items"]) if isinstance(payload, dict) and "items" in payload else (
                    len(payload["marketplace"]["items"]) if isinstance(payload, dict) and "marketplace" in payload else len(payload))
                results.append({"case": label, "select_count": len(statements),
                                "select_tables": dict(sql_tables), "orm_loaded": dict(loaded),
                                "returned_rows": rows, "json_equivalent_bytes": size,
                                "elapsed_local_sqlite_ms": round(elapsed, 3)})
            finally:
                event.remove(db.engine, "before_cursor_execute", sql)
                event.remove(Session, "loaded_as_persistent", hydrated)
                db.session.remove()

        measure("stats_empty_learner_1000_foreign_decks", lambda: query_accessible_stats_decks(user_id=learner_id, admin_mode=False))
        measure("legacy_market_list_no_match_600_total_100_public", lambda: list_shared_note_types(user_id=learner_id, args={"q": "no-match-unique-audit"}))
        measure("legacy_market_list_100_public", lambda: list_shared_note_types(user_id=learner_id, args={}))
        measure("canonical_market_hub_compact_100_public", lambda: build_note_type_marketplace_hub(user_id=learner_id, filters=parse_marketplace_filters({}), compact=True))
        measure("template_library_100_templates_16KiB_code_each", lambda: list_templates(user_id=publisher_id))
        db.session.add(duplicate_deck := Deck(name="connect-duplicate-probe", owner_user_id=publisher_id))
        db.session.flush()
        duplicate_deck_id = duplicate_deck.id
        duplicate_type_id = db.session.query(NoteType.id).filter(NoteType.user_id == publisher_id).first()[0]
        db.session.add_all([Note(user_id=publisher_id, note_type_id=duplicate_type_id,
                                deck_id=duplicate_deck_id, field_values={"Word": f"word-{i}", "Body": "z" * 4096})
                            for i in range(1000)])
        db.session.commit()
        def duplicates(count):
            prepared = SimpleNamespace(deck=SimpleNamespace(id=duplicate_deck_id),
                                       identity_field=SimpleNamespace(name="Word"),
                                       identity_value="no-match-unique-audit", clone_map=None)
            return [_is_duplicate(publisher_id, prepared) for _ in range(count)]
        measure("connect_duplicate_check_1x1000_notes", lambda: duplicates(1))
        measure("connect_duplicate_check_50x1000_notes", lambda: duplicates(50))
        db.session.remove()
        db.engine.dispose()
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = {
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "source_is_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip()),
        "python": sys.version.split()[0], "inventory": inventory(),
        "scope": "Current dirty working tree; SQLite synthetic cases and local build; no production DB, EXPLAIN or browser timing. gzip.compress level 9; sums are per-file, not network transfers.",
        "bundle": bundle(args.build), "sqlite_probes": sqlite_probes(),
        "audited_source_sha256": {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest()
                                  for name in AUDITED_SOURCES},
    }
    from dotenv import dotenv_values
    flags = ["STARTUP_RUN_MAINTENANCE", "STARTUP_RUN_CLONE_CUTOVER", "LEGACY_HTTP_ADAPTERS_ENABLED",
             "STUDY_WIRE_V3_ENABLED", "STUDY_WIRE_V4_ENABLED", "STUDY_NEW_LEARNER_NOTE_ENABLED",
             "STUDY_NOTE_COUNT_ENABLED", "REVIEW_ANALYTICS_WRITE_ENABLED", "REVIEW_ANALYTICS_READ_MODE",
             "DECK_COUNT_WRITE_ENABLED", "DECK_COUNT_READ_MODE", "CONNECT_LEGACY_WEB_ACTIONS_ENABLED"]
    local_env = dotenv_values(REPO / ".env")
    result["local_dotenv_flags_only_not_production"] = {key: local_env.get(key, "<unset>") for key in flags}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"inventory": result["inventory"], "sqlite_probes": result["sqlite_probes"],
                      "entry_js_gzip_bytes": result["bundle"]["index.html"]["static_js_gzip_bytes"],
                      "entry_locale_sources": len(result["bundle"]["index.html"]["locale_json_sources"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
