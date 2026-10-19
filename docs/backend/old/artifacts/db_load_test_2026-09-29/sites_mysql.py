import json, re, sys, traceback
from collections import Counter
from pathlib import Path
sys.path.insert(0, ".")
from sqlalchemy import event
from app import create_app
from models import db
HERE = Path(__file__).resolve().parent
rows = []; on = {"v": False}
def rec(conn, cursor, statement, params, ctx, many):
    if not on["v"]: return
    frames = [f for f in traceback.extract_stack() if "/Flama/app/" in f.filename]
    sites = [f"{f.filename.split('/Flama/')[1]}:{f.lineno} {f.name}" for f in frames[-3:]]
    m = re.search(r"(FROM|INTO|UPDATE)\s+`?(\w+)", statement)
    rows.append((f"{statement.split()[0]} {m.group(2) if m else '?'}", " <- ".join(reversed(sites))))
app = create_app({"WTF_CSRF_ENABLED": False})
with app.app_context():
    event.listen(db.engine, "before_cursor_execute", rec)
learner = json.loads((HERE / "learners.json").read_text())[int(sys.argv[1])]
c = app.test_client()
with c.session_transaction() as s:
    s["_user_id"] = str(learner["user_id"]); s["_fresh"] = True
for label, url in (("DASHBOARD", "/api/dashboard"), ("STATS", "/api/statistics/overview?year=2026&timezone=Asia/Ho_Chi_Minh")):
    rows.clear(); on["v"] = True; r = c.get(url); on["v"] = False
    print(f"\n== {label}: {len(rows)} statements, HTTP {r.status_code}")
    for (k, site), n in Counter(rows).most_common(6):
        print(f"  x{n:<5} {k:34} {site}")
rows.clear(); on["v"] = True
r = c.post("/api/study/sessions", json={"scope": "deck", "scope_id": learner["root_deck_id"], "composition_id": learner["composition_id"], "accepted_session_schema_versions": ["study-session.v4"], "accepted_note_storage_profiles": ["note-mysql-float-text.v1"]})
on["v"] = False
print(f"\n== OPEN: {len(rows)} statements, HTTP {r.status_code}")
for (k, site), n in Counter(rows).most_common(10):
    print(f"  x{n:<5} {k:34} {site}")
