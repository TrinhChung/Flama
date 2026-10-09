"""Compare preserved audit measurements with the same SQLite-memory fixture.

No configured application database is opened. The BEFORE values are historical
measurements from the preserved audit JSON, not reruns of old runtime code.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
BASELINE = REPO / "docs/architecture/artifacts/legacy_perf_audit_20261010/results.json"
SOURCES = (
    "app/repositories/deck_tree_query.py",
    "app/repositories/marketplace_list_repository.py",
    "app/services/marketplace_list_service.py",
    "app/services/marketplace_note_type_service.py",
    "app/services/marketplace_query_service.py",
    "app/repositories/template_library_repository.py",
    "app/services/template_library_service.py",
    "app/services/connect/actions.py",
    "app/services/connect/dispatcher.py",
    "app/services/connect/identity_lookup.py",
    "app/repositories/connect_identity_repository.py",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probes():
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app import create_app
    from app.repositories.deck_tree_query import query_accessible_stats_decks
    from app.services.marketplace_note_type_service import list_shared_note_types
    from app.services.template_library_service import list_templates
    from app.services.connect.actions import _is_duplicate
    from app.services.connect.dispatcher import dispatch
    from app.services.connect.identity_lookup import NoteIdentityLookup
    from models import db
    from models.user import User
    from models.deck import Deck
    from models.note_type import NoteType
    from models.template import Template
    from models.note import Note
    from models.field_def import FieldDef

    app = create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {}, "SECRET_KEY": "synthetic-implementation-only",
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

        def measure(label, call, *, expected_checks=None, notes=None):
            db.session.remove()
            loaded, sql_tables = Counter(), Counter()
            statements = []
            def sql(_conn, _cursor, statement, _params, _ctx, _many):
                if statement.lstrip().lower().startswith("select"):
                    statements.append(statement)
                    for table in ("decks", "card_progress", "note_types", "templates", "study_applications", "notes", "field_defs"):
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
                if expected_checks is not None:
                    assert payload == expected_checks, f"Invalid Connect fixture: {label}: {payload}"
                size = len(json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8"))
                count = len(payload["items"]) if isinstance(payload, dict) and "items" in payload else len(payload)
                row = {
                    "case": label, "select_count": len(statements), "select_tables": dict(sql_tables),
                    "orm_loaded": dict(loaded), "returned_rows": count, "json_equivalent_bytes": size,
                    "elapsed_local_sqlite_ms": round(elapsed, 3),
                }
                if isinstance(payload, dict) and "pagination" in payload:
                    row["pagination"] = payload["pagination"]
                if notes:
                    row["notes"] = notes
                results.append(row)
            finally:
                event.remove(db.engine, "before_cursor_execute", sql)
                event.remove(Session, "loaded_as_persistent", hydrated)
                db.session.remove()

        measure("stats_empty_learner_1000_foreign_decks", lambda: query_accessible_stats_decks(user_id=learner_id, admin_mode=False))
        measure("legacy_market_list_no_match_600_total_100_public", lambda: list_shared_note_types(user_id=learner_id, args={"q": "no-match-unique-audit"}))
        measure("legacy_market_list_100_public", lambda: list_shared_note_types(user_id=learner_id, args={}),
                notes="Compatibility client still requests definitions; React uses compact pages below.")
        measure("compact_market_list_page_24_of_100_public", lambda: list_shared_note_types(user_id=learner_id, args={"compact": "1", "page": "1", "page_size": "24"}))
        measure("template_library_100_templates_16KiB_code_each", lambda: list_templates(user_id=publisher_id))
        measure("compact_template_library_page_24_of_100_legacy_inputs", lambda: list_templates(user_id=publisher_id, compact=True, page=1, page_size=24),
                notes="Same original pre-attachment templates: empty/null input_schema inference intentionally reads page HTML in one batch.")

        duplicate_type_id = db.session.query(NoteType.id).filter(NoteType.user_id == publisher_id).first()[0]
        duplicate_deck = Deck(name="connect-duplicate-probe", owner_user_id=publisher_id)
        db.session.add(duplicate_deck)
        db.session.flush()
        duplicate_deck_id = duplicate_deck.id
        db.session.add_all([Note(user_id=publisher_id, note_type_id=duplicate_type_id,
                                deck_id=duplicate_deck_id, field_values={"Word": f"word-{i}", "Body": "z" * 4096})
                            for i in range(1000)])
        db.session.commit()

        def duplicates(count, *, shared=False):
            prepared = SimpleNamespace(deck=SimpleNamespace(id=duplicate_deck_id),
                                       identity_field=SimpleNamespace(name="Word"),
                                       identity_value="no-match-unique-audit", clone_map=None)
            lookup = NoteIdentityLookup(publisher_id) if shared else None
            return [_is_duplicate(publisher_id, prepared, lookup=lookup) for _ in range(count)]

        measure("connect_duplicate_check_1x1000_notes", lambda: duplicates(1), expected_checks=[False])
        measure("connect_duplicate_check_50x1000_notes", lambda: duplicates(50), expected_checks=[False] * 50,
                notes="Same original helper loop without a shared request lookup: 50 identity projections, zero Note hydration.")
        measure("connect_duplicate_shared_lookup_50x1000_notes", lambda: duplicates(50, shared=True), expected_checks=[False] * 50)

        # The original audit measured only the duplicate helper, bypassing model
        # validation. Add the minimum schema/template needed for valid transport
        # checks only AFTER the directly comparable measurements above.
        db.session.add_all([
            FieldDef(note_type_id=duplicate_type_id, name="Word", field_type="text", position=0, required=True, identity_role="primary"),
            FieldDef(note_type_id=duplicate_type_id, name="Body", field_type="text", position=1),
        ])
        if not db.session.query(Template.id).filter(Template.note_type_id == duplicate_type_id).first():
            db.session.add(Template(note_type_id=duplicate_type_id, owner_user_id=publisher_id,
                                    name="connect-valid-fixture", front_html="{{Word}}", back_html="{{Word}}"))
        db.session.commit()
        raw = {"deckName": "connect-duplicate-probe", "modelName": duplicate_type_id,
               "fields": {"Word": "no-match-unique-audit"}, "tags": []}
        measure("connect_canAddNotes_actual_batch_50x1000_notes", lambda: dispatch(publisher_id, "canAddNotes", {"notes": [raw.copy() for _ in range(50)]}), expected_checks=[True] * 50,
                notes="Real dispatcher/check/parse path. Extra Word/Body FieldDef rows and possibly one template enable validation; no equivalent BEFORE transport timing exists. Includes accessible deck/model catalog resolution.")
        db.session.remove()
        db.engine.dispose()
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(Path(__file__).with_name("results.json")))
    args = parser.parse_args()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    before_labels = {
        "stats_empty_learner_1000_foreign_decks", "legacy_market_list_no_match_600_total_100_public",
        "legacy_market_list_100_public", "template_library_100_templates_16KiB_code_each",
        "connect_duplicate_check_1x1000_notes", "connect_duplicate_check_50x1000_notes",
    }
    source_hashes = {name: sha256(REPO / name) for name in SOURCES}
    after = probes()
    final_hashes = {name: sha256(REPO / name) for name in SOURCES}
    if source_hashes != final_hashes:
        raise RuntimeError("Measured source changed while this probe was running; rerun after edits finish.")
    result = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "source_is_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip()),
        "python": sys.version.split()[0],
        "scope": "SQLite-memory synthetic probe; single local timings are not production percentiles. BEFORE comes from preserved historical audit, not old-code reruns. JSON-equivalent bytes are not compressed HTTP/network bytes. No configured DB, env dump, MySQL EXPLAIN or browser timing.",
        "baseline_reference": {
            "path": BASELINE.relative_to(REPO).as_posix(), "sha256": sha256(BASELINE),
            "source_head": baseline["source_head"], "source_is_dirty": baseline["source_is_dirty"],
            "audited_source_sha256": baseline["audited_source_sha256"],
        },
        "fixture": {"foreign_decks": 1000, "note_types": 600, "public_note_types": 100,
                    "public_template_source": "{{Word}} plus 8192 x + {{Word}} plus 8192 y, CSS empty",
                    "duplicate_notes": 1000, "duplicate_body_bytes_each": 4096,
                    "connect_actual_transport_additions": "2 FieldDefs and, if absent, one matching Template, after all directly comparable probes"},
        "before": [row for row in baseline["sqlite_probes"] if row["case"] in before_labels],
        "after": after,
        "measured_source_sha256": source_hashes,
        "probe_sha256": sha256(Path(__file__)),
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_head": result["source_head"], "before": result["before"], "after": result["after"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
