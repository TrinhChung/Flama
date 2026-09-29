"""Single-user latency and statement counts on MySQL (in-process test client).

Scenario A: brand-new NOTE learner imports a deck of N notes, then opens the
first session (pristine materialization happens inside that request).
Scenario B: an enrolled learner from learners.json runs one SPA study cycle.

Usage: venv/bin/python single_user_mysql.py A 500 2000   |   venv/bin/python single_user_mysql.py B <learner_index>
"""
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, ".")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import event, insert  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment  # noqa: E402
from app.services.study_composition_service import make_compatibility_composition_id  # noqa: E402
from models import db  # noqa: E402
from models.card import Card  # noqa: E402
from models.deck import Deck  # noqa: E402
from models.field_def import FieldDef  # noqa: E402
from models.note import Note  # noqa: E402
from models.note_type import NoteType  # noqa: E402
from models.template import Template  # noqa: E402
from models.user import User  # noqa: E402
from driver import commit_payload  # noqa: E402

HERE = Path(__file__).resolve().parent
COUNT = {"on": False, "n": 0}


def counter(*_args):
    if COUNT["on"]:
        COUNT["n"] += 1


def timed(label, fn):
    COUNT["n"] = 0
    COUNT["on"] = True
    started = time.perf_counter()
    response = fn()
    elapsed = time.perf_counter() - started
    COUNT["on"] = False
    print(f"{label:48} {elapsed:7.2f}s {COUNT['n']:7} statements  HTTP {response.status_code}", flush=True)
    return response


def login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = str(user_id)
        s["_fresh"] = True


def open_body(root_id, composition_id):
    return {"scope": "deck", "scope_id": root_id, "composition_id": composition_id,
            "accepted_session_schema_versions": ["study-session.v4"],
            "accepted_note_storage_profiles": ["note-mysql-float-text.v1"]}


def scenario_a(app, sizes):
    for size in sizes:
        with app.app_context():
            user = User(username=f"newbie{uuid4().hex[:6]}", email=f"{uuid4().hex[:8]}@new.test",
                        password_hash=generate_password_hash("password", method="pbkdf2:sha256:1000"))
            db.session.add(user)
            db.session.flush()
            db.session.commit()
            stage_note_authority_enrollment(db.session, learner_user_id=user.id, now_utc=datetime.utcnow())
            db.session.commit()
            root = Deck(name="Imported Anki deck", owner_user_id=user.id)
            db.session.add(root)
            db.session.flush()
            nt = NoteType(name="Imported", user_id=user.id)
            db.session.add(nt)
            db.session.flush()
            db.session.add(FieldDef(note_type_id=nt.id, name="Front", field_type="text", position=0))
            tpl = Template(note_type_id=nt.id, name="Card 1", front_html="{{Front}}", back_html="{{Front}}",
                           is_default=True)
            db.session.add(tpl)
            db.session.flush()
            ts = datetime.utcnow() - timedelta(days=1)
            notes, cards = [], []
            for n in range(size):
                nid = str(uuid4())
                notes.append({"id": nid, "note_type_id": nt.id, "user_id": user.id, "deck_id": root.id,
                              "field_values": {"Front": f"w{n}"}, "tags": [], "created_at": ts, "updated_at": ts})
                cards.append({"id": str(uuid4()), "note_id": nid, "template_id": tpl.id,
                              "created_at": ts, "updated_at": ts})
            for i in range(0, size, 1000):
                db.session.execute(insert(Note), notes[i:i + 1000])
                db.session.execute(insert(Card), cards[i:i + 1000])
            db.session.commit()
            uid, rid, comp = user.id, root.id, make_compatibility_composition_id(nt.id, tpl.id)
        client = app.test_client()
        login(client, uid)
        timed(f"A: first open, new NOTE learner, {size} new notes", lambda: client.post(
            "/api/study/sessions", json=open_body(rid, comp)))
        timed(f"A: second open, same deck ({size})", lambda: client.post(
            "/api/study/sessions", json=open_body(rid, comp)))


def scenario_b(app, index):
    learner = json.loads((HERE / "learners.json").read_text())[index]
    client = app.test_client()
    login(client, learner["user_id"])
    body = open_body(learner["root_deck_id"], learner["composition_id"])
    r = timed("B: open session (2000 cards)", lambda: client.post("/api/study/sessions", json=body))
    snap = r.get_json()
    print(f"   snapshot bytes: {len(r.data):,}; cards: {len(snap['cards'])}")
    timed("B: commit 50 answers (sync NOTE)", lambda: client.post(
        f"/api/study/sessions/{snap['session_id']}/commit", json=commit_payload(snap)))
    timed("B: reopen after rollover", lambda: client.post("/api/study/sessions", json=body))
    timed("B: dashboard", lambda: client.get("/api/dashboard"))
    timed("B: statistics overview", lambda: client.get("/api/statistics/overview?year=2026&timezone=Asia/Ho_Chi_Minh"))
    timed("B: browse deck tree", lambda: client.get("/api/browse/decks/tree"))
    timed("B: browse cards (root)", lambda: client.get(f"/api/browse/cards?deck_id={learner['root_deck_id']}"))


def main():
    app = create_app({"WTF_CSRF_ENABLED": False})
    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", counter)
    if sys.argv[1] == "A":
        scenario_a(app, [int(v) for v in sys.argv[2:]])
    else:
        scenario_b(app, int(sys.argv[2]))


if __name__ == "__main__":
    main()
