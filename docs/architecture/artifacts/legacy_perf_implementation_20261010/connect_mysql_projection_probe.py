"""Bounded, read-only JSON projection parity on the configured local MySQL dump."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from sqlalchemy import event
from app import create_audit_app
from app.services.connect.base import _normalized_identity
from models import db
from models.note import Note
from scripts.probe_review_analytics_mysql import local_url


def run():
    app = create_audit_app({"SQLALCHEMY_DATABASE_URI": local_url(ROOT / ".env").render_as_string(hide_password=False), "REDIS_URL": ""})
    with app.app_context():
        engine = db.engine
        @event.listens_for(engine, "connect")
        def readonly(connection, _record):
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION TRANSACTION READ ONLY")
        @event.listens_for(engine, "before_cursor_execute")
        def guard(_connection, _cursor, statement, _params, _context, _many):
            assert statement.lstrip().split(None, 1)[0].upper() in {"SELECT", "SHOW", "EXPLAIN"}
        try:
            # Never print field names, values, IDs, user metadata or credentials.
            rows = db.session.query(Note.id, Note.field_values).filter(Note.user_id == 1).order_by(Note.id).limit(128).all()
            assert rows, "Local parity check needs at least one Note for this fixture owner"
            fields = sorted({key for row in rows for key in (row.field_values or {})})[:3]
            assert fields
            expected = {row.id: row.field_values or {} for row in rows}
            checks = 0
            for field in fields:
                projected = db.session.query(Note.id, Note.field_values[field]).filter(Note.user_id == 1, Note.id.in_(expected)).all()
                assert len(projected) == len(rows)
                for note_id, value in projected:
                    assert _normalized_identity(value) == _normalized_identity(expected[note_id].get(field))
                    checks += 1
            result = {"measured_at_utc": datetime.now(timezone.utc).isoformat(), "rows": len(rows), "fields": len(fields),
                      "normalized_identity_comparisons": checks, "json_projection_parity": True,
                      "db_transactions_read_only": True, "startup_maintenance": False,
                      "scope": "Bounded existing local data, JSON value type plus Connect Unicode/whitespace normalization. Not transport latency or production coverage.",
                      "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                                        ("app/repositories/connect_identity_repository.py", "app/services/connect/base.py")}}
            output = Path(__file__).with_name("connect_mysql_projection_results.json")
            output.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result))
        finally:
            db.session.remove()
            engine.dispose()


if __name__ == "__main__":
    run()
