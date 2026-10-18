"""Seed a disposable MySQL DB with NOTE-enrolled learners owning Anki-sized decks.

Usage (repo root): venv/bin/python seed_mysql.py <learners> <notes_per_learner> <child_decks>
Writes learners.json next to this file: [{user_id, email, root_deck_id, child_deck_ids, composition_id}]
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, ".")

from sqlalchemy import insert  # noqa: E402
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

HERE = Path(__file__).resolve().parent


def main():
    learners = int(sys.argv[1])
    notes_per = int(sys.argv[2])
    children = int(sys.argv[3])
    app = create_app()
    out = []
    started = time.perf_counter()
    pw = generate_password_hash("password", method="pbkdf2:sha256:1000")
    with app.app_context():
        for index in range(learners):
            user = User(username=f"learner{index}", email=f"learner{index}@load.test", password_hash=pw)
            db.session.add(user)
            db.session.flush()
            root = Deck(name=f"JLPT N{index % 5 + 1} Core", owner_user_id=user.id)
            db.session.add(root)
            db.session.flush()
            child_ids = []
            for c in range(children):
                child = Deck(name=f"Lesson {c + 1:02d}", owner_user_id=user.id, parent_id=root.id)
                db.session.add(child)
                db.session.flush()
                child_ids.append(child.id)
            nt = NoteType(name="Vocab (Anki)", user_id=user.id)
            db.session.add(nt)
            db.session.flush()
            for pos, name in enumerate(("Expression", "Reading", "Meaning")):
                db.session.add(FieldDef(note_type_id=nt.id, name=name, field_type="text", position=pos))
            template = Template(
                note_type_id=nt.id, name="Recognition",
                front_html="<div class=jp>{{Expression}}</div>",
                back_html="{{FrontSide}}<hr>{{Reading}}<br>{{Meaning}}", is_default=True,
            )
            db.session.add(template)
            db.session.flush()
            base = datetime.utcnow() - timedelta(days=30)
            note_rows, card_rows = [], []
            for n in range(notes_per):
                note_id = str(uuid4())
                ts = base + timedelta(seconds=n)
                note_rows.append({
                    "id": note_id, "note_type_id": nt.id, "user_id": user.id,
                    "deck_id": child_ids[n % children],
                    "field_values": {"Expression": f"語彙{n}", "Reading": f"ごい{n}", "Meaning": f"vocabulary {n}"},
                    "tags": ["anki", f"lesson{n % children}"], "created_at": ts, "updated_at": ts,
                })
                card_rows.append({"id": str(uuid4()), "note_id": note_id, "template_id": template.id,
                                  "created_at": ts, "updated_at": ts})
            for start in range(0, len(note_rows), 1000):
                db.session.execute(insert(Note), note_rows[start:start + 1000])
                db.session.execute(insert(Card), card_rows[start:start + 1000])
            db.session.commit()
            stage_note_authority_enrollment(db.session, learner_user_id=user.id, now_utc=datetime.utcnow())
            db.session.commit()
            out.append({
                "user_id": user.id, "email": user.email, "root_deck_id": root.id,
                "child_deck_ids": child_ids,
                "composition_id": make_compatibility_composition_id(nt.id, template.id),
            })
            print(f"seeded learner {index} (user {user.id}) in {time.perf_counter() - started:.1f}s", flush=True)
    (HERE / "learners.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
