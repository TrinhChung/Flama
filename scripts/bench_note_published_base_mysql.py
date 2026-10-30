"""Bounded legacy/Base comparison on a generated local MySQL database.

No configured application data is modified, no MySQL settings are changed.
The full matrix is opt-in; defaults are a short qualification, not a capacity
claim. Study measurements cover the effective page query, not session commits.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import sys
from threading import Lock
from time import perf_counter, process_time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import bindparam, event, insert, select
from sqlalchemy.orm import contains_eager

from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import create_note_user
from tests import test_browse_query_bounds as fixtures
from models import db
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.user import User
from app.services import browse_note_service, deck_release_service
from app.services.note_base_context import base_maintenance
from app.services.share.overlay import (
    apply_clone_note_field_overrides, build_clone_schema_view,
    query_clone_scope_cards, resolve_clone_scope_for_local_deck,
)


COUNTERS = ("Innodb_buffer_pool_read_requests", "Innodb_buffer_pool_reads",
    "Innodb_rows_read", "Created_tmp_tables", "Created_tmp_disk_tables", "Rows_sent")


def _status(admin):
    with admin.cursor() as cursor:
        cursor.execute("SHOW GLOBAL STATUS WHERE Variable_name IN (" + ",".join(["%s"] * len(COUNTERS)) + ")", COUNTERS)
        return {key: int(value) for key, value in cursor.fetchall()}


def _environment(admin):
    with admin.cursor() as cursor:
        cursor.execute("SELECT VERSION(), @@innodb_buffer_pool_size, @@innodb_buffer_pool_instances, @@innodb_buffer_pool_chunk_size")
        version, size, instances, chunk = cursor.fetchone()
        cursor.execute("SELECT VARIABLE_NAME, VARIABLE_VALUE FROM performance_schema.persisted_variables WHERE VARIABLE_NAME LIKE 'innodb_buffer_pool%'")
        persisted = dict(cursor.fetchall())
    ini = Path("C:/ProgramData/MySQL/MySQL Server 8.0/my.ini")
    configured = [line.strip() for line in ini.read_text(encoding="utf-8-sig").splitlines()
        if line.strip().lower().startswith("innodb_buffer_pool")] if ini.exists() else []
    return {"mysql_version": version, "buffer_pool_bytes": int(size), "buffer_pool_instances": int(instances),
        "buffer_pool_chunk_bytes": int(chunk), "persisted_buffer_pool": persisted,
        "configured_buffer_pool_lines": configured, "mysql_settings_changed": False}


def _seed(notes, subscribers, active_users, payload_bytes):
    users = []
    for index in range(subscribers):
        values = {"username": f"load-learner-{index}", "email": f"load-{index}@example.invalid"}
        if index < active_users:
            user = create_note_user(db.session, **values)
        else:
            user = User(**values)
            db.session.add(user)
        users.append(user)
    db.session.flush()
    ids = fixtures.seed_clone_install(users[0].id, count=notes, release=True,
        override_every=0, stateful_every=notes + 1)
    first = db.session.get(DeckInstall, ids["install_id"])
    item = first.deck_item
    definitions = FieldDef.query.filter_by(note_type_id=first.source_note_type_id).all()
    field_ids = {field.name: field.id for field in definitions}
    # A synthetic cutover fixture with exact old/new value parity. The source
    # table and historical checkpoint describe the same published content.
    rows = []
    from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
    checkpoints = DeckReleaseNoteCheckpoint.query.filter_by(release_id=first.applied_release_id).all()
    for checkpoint in checkpoints:
        values = {name: f"pinned-{name.lower()}-{checkpoint.source_note_id[-6:]}" for name in field_ids}
        values["Meaning"] += " " + ("synthetic text " * ((payload_bytes + 14) // 15))[:payload_bytes]
        checkpoint.field_values = values
        rows.append({"note_key": checkpoint.source_note_id, "values_doc": {field_ids[name]: value for name, value in values.items()}})
    with base_maintenance("Generated benchmark fixture only"):
        connection = db.session.connection()
        table = Note.__table__
        statement = table.update().where(table.c.id == bindparam("note_key")).values(
            field_values_by_id=bindparam("values_doc"), published_at=datetime.utcnow())
        for offset in range(0, len(rows), 500):
            connection.execute(statement, rows[offset:offset + 500])
    item.published_schema_json = {field.id: {"name": field.name, "field_type": field.field_type,
        "position": field.position, "required": bool(field.required), "identity_role": field.identity_role}
        for field in definitions}
    contexts = [(users[0].id, ids["local_root_id"], first.id)]
    for index, user in enumerate(users[1:], 1):
        root = Deck(name="Installed", owner_user_id=user.id)
        db.session.add(root)
        db.session.flush()
        child = Deck(name="Installed child", owner_user_id=user.id, parent_id=root.id)
        install = DeckInstall(deck_item_id=item.id, user_id=user.id, local_deck_id=root.id,
            source_deck_id=first.source_deck_id, source_note_type_id=first.source_note_type_id,
            source_owner_user_id=first.source_owner_user_id, clone_mode="logical_overlay",
            version_mode="release", applied_release_id=first.applied_release_id)
        db.session.add_all([child, install])
        db.session.flush()
        db.session.add_all([DeckCloneDeckMap(deck_install_id=install.id,
            source_deck_id=ids["source_root_id"], local_deck_id=root.id),
            DeckCloneDeckMap(deck_install_id=install.id,
            source_deck_id=ids["source_child_id"], local_deck_id=child.id)])
        contexts.append((user.id, root.id, install.id))
    db.session.commit()
    result = {"contexts": contexts, "note_ids": ids["note_ids"], "field_id": ids["word_field_id"],
        "item_id": item.id, "owner_id": item.owner_user_id}
    db.session.remove()
    return result


def _overlays(seed, active, amount):
    table = DeckCloneNoteFieldOverride.__table__
    connection = db.session.connection()
    connection.execute(table.delete())
    for _user, _deck, install_id in seed["contexts"][:active]:
        rows = [{"deck_install_id": install_id, "source_note_id": note_id,
            "source_field_def_id": seed["field_id"], "field_identity_key": seed["field_id"],
            "field_name": "Word", "operation": "set", "value": f"personal-{note_id[-6:]}"}
            for note_id in seed["note_ids"][:amount]]
        for offset in range(0, len(rows), 500):
            connection.execute(insert(table), rows[offset:offset + 500])
    connection.execute(DeckInstall.__table__.update().values(overlay_revision=amount))
    db.session.commit()
    db.session.remove()


def _request(operation, context):
    user_id, deck_id, _install_id = context
    if operation == "study_page_query":
        from app.services.effective_note_reader import base_note_values_for_ids
        from app.repositories import flashcards_share_repository
        scope = resolve_clone_scope_for_local_deck(user_id=user_id, local_deck_id=deck_id)
        from models.card import Card
        cards = query_clone_scope_cards(scope).options(contains_eager(Card.note)).order_by(Note.id).limit(20).all()
        schema = build_clone_schema_view(install=scope.install, source_note_type_id=scope.install.source_note_type_id)
        ids = [card.note_id for card in cards]
        values = base_note_values_for_ids(scope.install, ids)
        overrides = flashcards_share_repository.get_clone_note_field_overrides_batch([scope.install.id], ids)
        result = [(card.note_id, apply_clone_note_field_overrides(install=scope.install, source_note=card.note,
            schema_view=schema, base_field_values=values.get(card.note_id, {}),
            note_override_rows=overrides.get((str(scope.install.id), str(card.note_id)), []))) for card in cards]
    else:
        args = {"deck_id": str(deck_id), "per_page": "20"}
        if operation == "search":
            args.update(q="pinned-word", sort_by="word")
        payload = browse_note_service.list_notes(user_id=user_id, admin_mode=False, timezone_name="UTC", query_args=args)
        result = {"total": payload["total"], "items": [(row["note_id"], row["word"], row["reading"], row["meaning"])
            for row in payload["items"]]}
    return hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _process_rss_bytes():
    """Current process working set without adding dependencies to the venv."""
    import os
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return int(counters.WorkingSetSize)
        return None
    try:
        import psutil
        return int(psutil.Process().memory_info().rss)
    except ImportError:
        return None


def _measure(app, admin, seed, *, mode, vus, iterations):
    app.config["NOTE_PUBLISHED_BASE_ENABLED"] = mode == "published_base"
    samples, errors, hashes = defaultdict(list), [], defaultdict(set)
    mutex, sql_counts = Lock(), [0]
    cpu_before = process_time()
    rss = []
    initial_rss = _process_rss_bytes()
    if initial_rss is not None:
        rss.append(initial_rss)
    def capture(*_args):
        with mutex:
            sql_counts[0] += 1
    def worker(index):
        context = seed["contexts"][index % len(seed["contexts"])]
        for _ in range(iterations):
            for operation in ("browse", "search", "study_page_query"):
                start = perf_counter()
                try:
                    with app.test_request_context("/benchmark/note-base"):
                        signature = _request(operation, context)
                        db.session.rollback()
                        db.session.remove()
                    with mutex:
                        hashes[operation].add(signature)
                except Exception as exc:
                    with mutex:
                        errors.append({"operation": operation, "type": type(exc).__name__, "message": str(exc).splitlines()[0][:160]})
                finally:
                    with mutex:
                        samples[operation].append((perf_counter() - start) * 1000)
                        current_rss = _process_rss_bytes()
                        if current_rss is not None:
                            rss.append(current_rss)
    with app.app_context():
        db.session.remove()
        engine = db.engine
        event.listen(engine, "before_cursor_execute", capture)
    before = _status(admin)
    start = perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=vus) as pool:
            list(pool.map(worker, range(vus)))
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    elapsed = perf_counter() - start
    after = _status(admin)
    metrics = {}
    for operation, values in samples.items():
        ordered = sorted(values)
        metrics[operation] = {"requests": len(values), "p50_ms": statistics.median(values),
            "p95_ms": ordered[min(len(ordered) - 1, max(0, int(len(ordered) * .95 + .999) - 1))],
            "max_ms": max(values)}
    cpu_after = process_time()
    return {"mode": mode, "vus": vus, "iterations_per_vu": iterations, "elapsed_seconds": elapsed,
        "throughput_requests_per_second": sum(map(len, samples.values())) / elapsed,
        "operations": metrics, "sql_statements": sql_counts[0], "errors": errors,
        "mysql_global_counter_delta": {key: after.get(key, 0) - before.get(key, 0) for key in COUNTERS},
        "python_rss_peak_sampled_bytes": max(rss) if rss else None,
        "python_cpu_seconds": cpu_after - cpu_before,
        "response_signatures": {key: sorted(value) for key, value in hashes.items()}}


def _publish_probe(app, seed, label):
    app.config["NOTE_PUBLISHED_BASE_ENABLED"] = True
    with app.app_context():
        note = db.session.get(Note, seed["note_ids"][0])
        note.field_values = {**note.field_values, "Word": label}
        db.session.commit()
        item = db.session.get(DeckMarketplaceItem, seed["item_id"])
        sql = []
        def capture(_conn, _cursor, statement, *_args):
            sql.append(statement)
        event.listen(db.engine, "before_cursor_execute", capture)
        start = perf_counter()
        try:
            deck_release_service.publish_release_and_commit(deck_item_id=item.id, user_id=seed["owner_id"],
                version_label=label, changelog="Synthetic benchmark", expected_current_release_id=item.current_release_id,
                expected_working_revision=item.working_revision, idempotency_key=label)
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        return {"elapsed_ms": (perf_counter() - start) * 1000, "sql_statements": len(sql),
            "install_table_statements": sum("deck_installs" in statement.lower() for statement in sql),
            "changed_notes": 1}


def run(args):
    import os
    os.environ["FLAMA_MYSQL_TESTS"] = "1"
    class BenchmarkDatabase(NoteBaseMySQLTestCase):
        APP_CONFIG = {"NOTE_PUBLISHED_BASE_ENABLED": False,
            "DECK_COUNT_WRITE_ENABLED": False, "REVIEW_ANALYTICS_WRITE_ENABLED": False,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True, "pool_size": min(20, max(args.vus)), "max_overflow": 0}}
    BenchmarkDatabase.setUpClass()
    report = {"configured_database_modified": False, "generated_database": BenchmarkDatabase.database_name,
        "notes": args.notes, "payload_padding_bytes": args.payload_bytes, "measurements": [],
        "limitations": ["Synthetic content and generated users; no production traffic claim.",
            "Study covers effective page reads, not session creation/review commits.",
            "Global MySQL counters include any concurrent work on the shared server.",
            "Only the runtime buffer pool is measured; no 128 MiB/2 GiB comparison unless independently configured.",
            "Short runs are qualification samples, not sustained capacity measurements."]}
    try:
        report.update(_environment(BenchmarkDatabase.admin))
        for subscribers in args.installs:
            BenchmarkDatabase.app.config["NOTE_PUBLISHED_BASE_ENABLED"] = False
            if subscribers < max(args.vus):
                raise ValueError("Subscriber count must be at least the maximum VU count")
            with BenchmarkDatabase.app.app_context():
                if report["measurements"]:
                    from scripts.mysql_probe_db import _empty_tables
                    with db.engine.connect() as connection:
                        _empty_tables(connection, BenchmarkDatabase.auto_increment_tables)
                seed = _seed(args.notes, subscribers, max(args.vus), args.payload_bytes)
            for overrides in args.overrides:
                with BenchmarkDatabase.app.app_context():
                    _overlays(seed, max(args.vus), min(overrides, args.notes))
                for vus in args.vus:
                    results = []
                    for mode in ("legacy", "published_base"):
                        result = _measure(BenchmarkDatabase.app, BenchmarkDatabase.admin, seed,
                            mode=mode, vus=vus, iterations=args.iterations)
                        result.update(installs=subscribers, overrides_per_active_install=min(overrides, args.notes))
                        results.append(result)
                        report["measurements"].append(result)
                    results[-1]["legacy_response_signature_parity"] = (results[0]["response_signatures"] == results[1]["response_signatures"])
            report.setdefault("publish", []).append({"installs": subscribers,
                **_publish_probe(BenchmarkDatabase.app, seed, f"bench-{subscribers}")})
        report["status"] = "PASS" if all(not row["errors"] and row.get("legacy_response_signature_parity", True)
            for row in report["measurements"]) and all(not row["install_table_statements"] for row in report["publish"]) else "FAIL"
        return report
    finally:
        BenchmarkDatabase.doClassCleanups()
        report["generated_database_dropped"] = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notes", type=int, default=10000)
    parser.add_argument("--installs", nargs="+", type=int, default=[100])
    parser.add_argument("--overrides", nargs="+", type=int, default=[20])
    parser.add_argument("--vus", nargs="+", type=int, default=[10])
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--payload-bytes", type=int, default=1800)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    if options.notes < 1 or options.iterations < 1 or min(options.installs + options.vus) < 1 or min(options.overrides) < 0:
        parser.error("Counts must be positive; overrides may be zero")
    result = run(options)
    serialized = json.dumps(result, indent=2, sort_keys=True)
    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(serialized, encoding="utf-8")
    print(serialized)
    sys.exit(0 if result["status"] == "PASS" else 1)
