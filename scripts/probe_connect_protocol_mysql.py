"""Qualify Connect concurrency on a generated, disposable loopback database.

Never reads application rows or mutates the configured application database.
Usage: .venv/Scripts/python.exe scripts/probe_connect_protocol_mysql.py
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import base64
import json
from pathlib import Path
import re
import secrets
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
import pymysql
from app.connect import create_connect_app
from app.services import user_api_token_service
from app.services.connect.mining_setup import prepare_sentence_mining
from models import db
from models.card import Card
from models.connect_note_ref import ConnectNoteRef
from models.connect_pending_media import ConnectPendingMedia
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.user import User
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

NAME = re.compile(r"^flama_c217_probe_[0-9]+_[a-f0-9]{8}$")
MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x15" + b"\x00" * 64


def main():
    load_dotenv(ROOT / ".env")
    settings = _connection_settings()
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Disposable probe requires a loopback MySQL host")
    name = f"flama_c217_probe_{int(time.time())}_{secrets.token_hex(4)}"
    assert NAME.fullmatch(name)
    admin = pymysql.connect(**settings, connect_timeout=3)
    apps = []
    created = False
    report = {}
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
        with tempfile.TemporaryDirectory(prefix="flama-c217-probe-") as media_root:
            config = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name),
                      "CONNECT_ANKI_ADAPTER_ENABLED": True, "CONNECT_ANKI_MEDIA_ENABLED": True,
                      "CONNECT_RATE_LIMIT_BACKEND": "local", "CONNECT_IP_RATE_LIMIT": 10000,
                      "CONNECT_TOKEN_RATE_LIMIT": 10000, "CONNECT_USER_RATE_LIMIT": 10000,
                      "CONNECT_ADD_NOTE_RATE_LIMIT": 10000, "CONNECT_MEDIA_RATE_LIMIT": 10000,
                      "FLASHCARD_MEDIA_UPLOAD_ROOT": media_root}
            apps = [create_connect_app(config), create_connect_app(config)]
            with apps[0].app_context():
                db.create_all()
                user = User(username="connect-probe", email="connect-probe@example.test")
                db.session.add(user)
                db.session.flush()
                prepare_sentence_mining(user.id)
                model = NoteType.query.filter_by(user_id=user.id, name="Sentence Card").one()
                db.session.add(Deck(owner_user_id=user.id, name="Second", note_type_id=model.id))
                key = user_api_token_service.issue_token(user_id=user.id, name="probe", preset="mining-media").plaintext
                db.session.commit()
                report["isolation"] = db.session.connection().get_isolation_level()

            def burst(action, params, count=8):
                gate = threading.Barrier(count)
                def send(index):
                    gate.wait(timeout=15)
                    with apps[index % 2].test_client() as client:
                        response = client.post("/v1/anki-connect", json={"action": action, "version": 6, "key": key, "params": params(index)})
                        return response.status_code, response.get_json()
                with ThreadPoolExecutor(max_workers=count) as workers:
                    return list(workers.map(send, range(count)))

            def note(index, *, duplicate=False):
                return {"note": {"deckName": "Sentences" if index % 2 else "Second",
                                 "modelName": "Sentence Card", "fields": {"Sentence": "same sentence" if duplicate else f"sentence-{index}"},
                                 "options": {"allowDuplicate": not duplicate, "duplicateScope": "collection"}}}
            results = burst("addNote", note)
            ids = [value["result"] for status, value in results if status == 200 and value["error"] is None]
            assert len(ids) == 8 and len(set(ids)) == 8, results
            report["two_workers_two_decks_unique_ids"] = True
            results = burst("addNote", lambda index: note(index, duplicate=True))
            assert sum(value["error"] is None for _, value in results) == 1, results
            assert all(status == 200 and (value["error"] is None or "duplicate" in value["error"]) for status, value in results), results
            report["collection_duplicate_serialization"] = True
            for app in apps:
                app.config["CONNECT_PENDING_MEDIA_MAX_ITEMS"] = 2
            results = burst("storeMediaFile", lambda index: {"filename": f"probe-{index}.mp3", "data": base64.b64encode(MP3).decode(), "deleteExisting": False})
            assert sum(value["error"] is None for _, value in results) == 2, results
            assert all(status == 200 for status, _ in results), results
            report["pending_quota_serialization"] = True
            with apps[0].app_context():
                from app.services.connect.media_cleanup import cleanup
                for row in ConnectPendingMedia.query.all():
                    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
                db.session.commit()
                assert cleanup()["expired_uploads"] == 2
            for app in apps:
                app.config.update(CONNECT_PENDING_MEDIA_MAX_ITEMS=20, CONNECT_ANKI_STORAGE_MAX_BYTES=len(MP3))
            results = burst("storeMediaFile", lambda index: {"filename": f"storage-{index}.mp3", "data": base64.b64encode(MP3).decode()})
            assert sum(value["error"] is None for _, value in results) == 1, results
            assert all(status == 200 for status, _ in results), results
            report["storage_admission_serialization"] = True
            with apps[0].app_context():
                assert Note.query.count() == 9
                assert Card.query.count() == 9
                assert ConnectNoteRef.query.count() == 9
                assert ConnectPendingMedia.query.count() == 1
                assert len({row.id for row in Note.query.all()}) == 9
                assert all(len(row.id) == 36 for row in Note.query.all())
            assert len([path for path in Path(media_root).rglob("*") if path.is_file()]) == 1
            report["rows_and_files_consistent"] = True
            report["passed"] = True
    finally:
        for app in apps:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            if not NAME.fullmatch(name):
                raise RuntimeError("Refusing an unsafe probe cleanup target")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
            report["disposable_database_removed"] = True
        admin.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
