"""Serve the real SPA/API/consumer against disposable local MySQL NOTE fixtures.

Build frontend with VITE_API_BASE_URL=/api first. Pass an explicit loopback
Redis URL (an SSH tunnel is fine). Open the printed URL in an isolated browser
profile; the printed password belongs only to this disposable fixture.
Commands on stdin: inspect, stop. No production/configured application rows,
shared rate-limit keys, migrations, or service definitions are changed.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import argparse
import json
import logging
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time

from dotenv import load_dotenv
import pymysql
from werkzeug.serving import make_server

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.services.redis_state_service import redis_client
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from app.services.study_queue_namespace import study_queue_prefix
from app.services.study_worker_readiness_service import has_ready_study_worker
from app.services.user_roles import ensure_default_user_roles
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.template import Template
from models.user import User
from scripts.probe_p5_study_consumer import _validate_redis_url
from scripts.probe_phase4_shadow_schema_mysql import (
    _connection_settings, _database_uri, _source_database_collation,
)

PROBE_NAME_PATTERN = re.compile(r"^flama_p5_browser_probe_[0-9]+_[a-f0-9]{8}$")


def validate_database_target(settings, database_name):
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Browser probe requires local MySQL.")
    if not PROBE_NAME_PATTERN.fullmatch(database_name):
        raise ValueError("Refusing non-disposable browser probe database.")


def seed_browser_fixture(app):
    with app.app_context():
        db.create_all()
        roles = ensure_default_user_roles(db.session)
        password = secrets.token_urlsafe(18)
        user = User(
            username="p5-browser", email="p5-browser@example.test",
            email_verified_at=datetime.now(timezone.utc).replace(tzinfo=None), role_id=roles["regular"].id,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        note_type = NoteType(name="P5 NOTE browser probe", user_id=user.id)
        db.session.add(note_type)
        db.session.flush()
        db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
        templates = [Template(
            name=f"Browser sibling {number + 1}", note_type_id=note_type.id,
            front_html="<h1>{{Word}}</h1>", back_html="<p>Answer: {{Word}}</p>",
            is_default=number == 0,
        ) for number in range(2)]
        db.session.add_all(templates)
        db.session.flush()
        decks = {}
        for label, count in (("online", 3), ("offline", 3), ("rollover", 60)):
            deck = Deck(name=f"P5 browser {label}", owner_user_id=user.id, note_type_id=note_type.id)
            db.session.add(deck)
            db.session.flush()
            decks[label] = deck.id
            for number in range(count):
                note = Note(
                    user_id=user.id, deck_id=deck.id, note_type_id=note_type.id,
                    field_values={"Word": f"{label}-{number + 1:02}"},
                )
                db.session.add(note)
                db.session.flush()
                db.session.add_all([Card(note_id=note.id, template_id=template.id) for template in templates])
        user_id = user.id
        db.session.commit()
        stage_note_authority_enrollment(db.session, learner_user_id=user_id, now_utc=datetime.now(timezone.utc).replace(tzinfo=None))
        db.session.commit()
        return {"email": user.email, "password": password, "decks": decks}


def inspect_browser_fixture(app):
    """Read exact-once evidence with a fresh snapshot, without repairing state."""
    with app.app_context():
        try:
            projections = CardProgress.query.all()
            cards = {row.id: row for row in Card.query.all()}
            sibling_states = {}
            for row in projections:
                state = tuple(getattr(row, key) for key in (
                    "queue", "step_index", "due_at", "due_day", "interval_days", "interval_days_raw",
                    "ease_factor", "reps", "lapses", "revision", "last_reviewed_at",
                ))
                sibling_states.setdefault(cards[row.card_id].note_id, set()).add(state)
            return {
                "sessions": [{"id": row.id, "status": row.status} for row in StudySession.query.all()],
                "batches": [{
                    "session_id": row.session_id, "batch_id": row.batch_id,
                    "sequence": row.batch_sequence, "status": row.status,
                    "events": row.event_count, "attempts": row.attempt_count,
                } for row in StudySessionBatch.query.order_by(StudySessionBatch.enqueued_at).all()],
                "review_events": ReviewEvent.query.count(),
                "history_facts": StudyProgressHistoryFact.query.count(),
                "authority_receipts": StudyAuthorityCommandReceipt.query.count(),
                "authority_revision_counts": dict(Counter(row.authority_revision for row in StudyAuthoritySubjectToken.query.all())),
                "projection_revision_counts": dict(Counter(row.revision for row in projections)),
                "sibling_state_mismatches": sum(len(states) != 1 for states in sibling_states.values()),
            }
        finally:
            db.session.rollback()


def serve_probe(redis_url, port):
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    database_name = f"flama_p5_browser_probe_{os.getpid()}_{secrets.token_hex(4)}"
    validate_database_target(settings, database_name)
    redis_url = _validate_redis_url(redis_url)
    if not (ROOT_DIR / "frontend/dist/index.html").is_file():
        raise RuntimeError("Build the frontend with VITE_API_BASE_URL=/api first.")
    namespace = "p5_browser_probe_" + secrets.token_hex(16)
    admin = pymysql.connect(**settings)
    app = worker = server = server_thread = client = None
    prefix = None
    created = False
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE {collation}")
        created = True
        uri = _database_uri(settings, database_name)
        app = create_app({
            "TESTING": False, "SECRET_KEY": secrets.token_hex(32),
            "SQLALCHEMY_DATABASE_URI": uri,
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_RUN_DB_CREATE_ALL": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False,
            "STUDY_QUEUE_NAMESPACE": namespace, "REDIS_URL": redis_url,
            "STUDY_ASYNC_BATCH_ENABLED": True, "STUDY_WIRE_V4_ENABLED": True,
            "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": False,
            "RATE_LIMIT_BACKEND": "local", "MCP_PREVIEW_BACKEND": "local",
            "EMAIL_ENABLED": False, "EMAIL_PROVIDER": "disabled",
            "FRONTEND_URL": f"http://127.0.0.1:{port}",
            "SESSION_COOKIE_SECURE": False, "TRUST_PROXY": False,
            "WTF_CSRF_ENABLED": True,
        })
        fixture = seed_browser_fixture(app)
        with app.app_context():
            prefix = study_queue_prefix(require_namespace=True)
            client = redis_client()
            client.ping()
        env = dict(os.environ)
        env.update(
            SQLALCHEMY_DATABASE_URI=uri, REDIS_URL=redis_url,
            STUDY_QUEUE_NAMESPACE=namespace, STUDY_ASYNC_BATCH_ENABLED="0",
            STARTUP_RUN_MAINTENANCE="0",
        )
        worker = subprocess.Popen(
            [sys.executable, str(ROOT_DIR / "study_worker.py")], cwd=ROOT_DIR, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 25
        with app.app_context():
            while not has_ready_study_worker("study-session.v4"):
                if worker.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Disposable NOTE consumer did not become ready.")
                time.sleep(0.2)
        server = make_server("127.0.0.1", port, app, threaded=True)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print(json.dumps({"status": "READY", "url": f"http://127.0.0.1:{port}/login", **fixture}), flush=True)
        for command in sys.stdin:
            if command.strip() == "stop":
                break
            if command.strip() == "inspect":
                print(json.dumps(inspect_browser_fixture(app)), flush=True)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if server_thread is not None:
            server_thread.join(timeout=5)
        if worker is not None:
            if worker.poll() is None:
                worker.terminate()  # Only the explicitly owned child, not a service.
            worker.wait(timeout=10)
        # Cleanup attempts remain independent: a dead SSH tunnel must not keep
        # the generated MySQL database or its pooled connections alive.
        try:
            if client is not None and prefix is not None:
                keys = list(client.scan_iter(match=prefix + ":*", count=100))
                if any(not isinstance(key, str) or not key.startswith(prefix + ":") for key in keys):
                    raise RuntimeError("Refusing unexpected Redis cleanup target.")
                if keys:
                    client.delete(*keys)
                if list(client.scan_iter(match=prefix + ":*", count=100)):
                    raise RuntimeError("Disposable Redis keys remain after cleanup.")
                print(json.dumps({"isolated_redis_namespace_removed": True}), flush=True)
        finally:
            try:
                if app is not None:
                    with app.app_context():
                        db.session.remove()
                        db.engine.dispose()
            finally:
                try:
                    if created:
                        validate_database_target(settings, database_name)
                        with admin.cursor() as cursor:
                            cursor.execute(f"DROP DATABASE `{database_name}`")
                        print(json.dumps({"disposable_database_removed": True, "configured_database_modified": False}), flush=True)
                finally:
                    admin.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redis-url", required=True, type=_validate_redis_url)
    parser.add_argument("--port", type=int, default=14889)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged local port from 1024 to 65535.")
    serve_probe(args.redis_url, args.port)


if __name__ == "__main__":
    main()
