"""Concurrent learner load driver against a running Gunicorn (production flags).

Each virtual learner repeats the SPA study loop: open a v4 NOTE session on the
root deck, answer 50 new cards client-side, commit them (study-commit.v3), then
refetch dashboard and statistics (the SPA invalidates both after a commit).
A bystander thread probes GET /api/health to show what other users experience.

Usage: venv/bin/python driver.py <virtual_learners> <cycles> [label]
"""
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

import requests

BASE = "http://127.0.0.1:4789"
HERE = Path(__file__).resolve().parent
SOCK = os.environ.get("MYSQL_SOCKET", "/var/run/mysqld/mysqld.sock")
ANSWERS = 50

lock = threading.Lock()
results = defaultdict(list)  # endpoint -> [(seconds, status)]


def record(name, started, response=None, error=None):
    elapsed = time.perf_counter() - started
    status = response.status_code if response is not None else f"EXC:{type(error).__name__}"
    with lock:
        results[name].append((elapsed, status))
    return elapsed


def mysql_status():
    sql = ("SELECT variable_name, variable_value FROM performance_schema.global_status WHERE variable_name IN "
           "('Innodb_row_lock_waits','Innodb_row_lock_time','Innodb_row_lock_time_max','Questions',"
           "'Threads_connected','Max_used_connections','Innodb_rows_inserted','Innodb_rows_updated','Innodb_rows_read')"
           " UNION ALL SELECT name, count FROM information_schema.innodb_metrics WHERE name='lock_deadlocks'")
    out = subprocess.run(["mysql", f"--socket={SOCK}", "-uroot", "-N", "-e", sql], capture_output=True, text=True).stdout
    return {k: int(v) for k, v in (line.split("\t") for line in out.strip().splitlines())}


def login(session, email):
    token = session.get(f"{BASE}/api/session", timeout=60).json()["csrf_token"]
    session.post(f"{BASE}/api/auth/login", json={"email": email, "password": "password"},
                 headers={"X-CSRF-Token": token}, timeout=60)
    after = session.get(f"{BASE}/api/session", timeout=60).json()
    assert after["authenticated"], "login failed"
    return {"X-CSRF-Token": after["csrf_token"]}


def commit_payload(snapshot):
    events = []
    new_cards = [c for c in snapshot["cards"] if c["state"].get("type") == "new"][:ANSWERS]
    for seq, card in enumerate(new_cards, start=1):
        policy = snapshot["policies"][card["policy_key"]]
        pin = card["authority_pin"]
        event_id = str(uuid4())
        events.append({
            "event_id": event_id, "sequence": seq, "card_id": card["card_id"], "rating": "good",
            "policy_key": card["policy_key"], "scheduler_offset_ms": 1000 * seq, "duration_ms": 4000,
            "action_key": "review.good", "action_contract_version": "1",
            "trigger_key": "scheduler.review.good", "trigger_contract_version": "1",
            "algorithm_key": snapshot["scheduler_algorithm"], "algorithm_version": snapshot["algorithm_version"],
            "config_schema_version": policy["config_schema_version"], "config_hash": policy["config_hash"],
            "study_session_id": snapshot["session_id"], "authority_mode": "NOTE",
            "enrollment_epoch": pin["enrollment_epoch"], "logical_note_key": pin["logical_note_key"],
            "subject_generation": pin["subject_generation"], "base_authority_revision": pin["base_authority_revision"],
            "base_authority_state_hash": pin["base_authority_state_hash"], "operation_key": event_id,
        })
    return {"schema_version": "study-commit.v3", "commit_id": str(uuid4()),
            "session_token": snapshot["session_token"], "snapshot_hash": snapshot["snapshot_hash"],
            "events": events, "final_states": []}


def learner_loop(learner, cycles):
    s = requests.Session()
    try:
        headers = login(s, learner["email"])
    except Exception as exc:  # noqa: BLE001
        record("login", time.perf_counter(), error=exc)
        return
    for _ in range(cycles):
        t = time.perf_counter()
        try:
            r = s.post(f"{BASE}/api/study/sessions", headers=headers, timeout=180, json={
                "scope": "deck", "scope_id": learner["root_deck_id"], "composition_id": learner["composition_id"],
                "accepted_session_schema_versions": ["study-session.v4"],
                "accepted_note_storage_profiles": ["note-mysql-float-text.v1"]})
        except Exception as exc:  # noqa: BLE001
            record("open_session", t, error=exc)
            continue
        record("open_session", t, r)
        if r.status_code != 201:
            continue
        snapshot = r.json()
        t = time.perf_counter()
        try:
            r = s.post(f"{BASE}/api/study/sessions/{snapshot['session_id']}/commit", headers=headers,
                       json=commit_payload(snapshot), timeout=180)
            record("commit_50", t, r)
            if r.status_code >= 400:
                with lock:
                    results["_errors"].append((0, r.text[:200]))
        except Exception as exc:  # noqa: BLE001
            record("commit_50", t, error=exc)
        for name, url in (("dashboard", "/api/dashboard"),
                          ("statistics", "/api/statistics/overview?year=2026&timezone=Asia/Ho_Chi_Minh")):
            t = time.perf_counter()
            try:
                record(name, t, s.get(f"{BASE}{url}", timeout=180))
            except Exception as exc:  # noqa: BLE001
                record(name, t, error=exc)


def bystander(stop):
    s = requests.Session()
    while not stop.is_set():
        t = time.perf_counter()
        try:
            record("bystander_health", t, s.get(f"{BASE}/api/health", timeout=180))
        except Exception as exc:  # noqa: BLE001
            record("bystander_health", t, error=exc)
        stop.wait(0.5)


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


def main():
    vus, cycles = int(sys.argv[1]), int(sys.argv[2])
    label = sys.argv[3] if len(sys.argv) > 3 else f"{vus}vu"
    offset = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    learners = json.loads((HERE / "learners.json").read_text())[offset:offset + vus]
    before = mysql_status()
    stop = threading.Event()
    probe = threading.Thread(target=bystander, args=(stop,), daemon=True)
    probe.start()
    started = time.perf_counter()
    threads = [threading.Thread(target=learner_loop, args=(learner, cycles)) for learner in learners]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    wall = time.perf_counter() - started
    stop.set()
    probe.join()
    after = mysql_status()
    summary = {"label": label, "vus": len(learners), "cycles": cycles, "wall_s": round(wall, 1), "endpoints": {}}
    for name, rows in sorted(results.items()):
        if name == "_errors":
            continue
        lat = [r[0] for r in rows]
        statuses = defaultdict(int)
        for _, st in rows:
            statuses[str(st)] += 1
        summary["endpoints"][name] = {
            "n": len(rows), "p50": round(statistics.median(lat), 2), "p95": round(pct(lat, 95), 2),
            "max": round(max(lat), 2), "status": dict(statuses)}
    summary["mysql_delta"] = {k: after.get(k, 0) - before.get(k, 0) for k in after
                              if k not in ("Threads_connected", "Max_used_connections", "Innodb_row_lock_time_max")}
    summary["mysql_delta"]["Max_used_connections"] = after.get("Max_used_connections")
    summary["mysql_delta"]["Innodb_row_lock_time_max_ms"] = after.get("Innodb_row_lock_time_max")
    summary["errors_sample"] = [e[1] for e in results.get("_errors", [])[:3]]
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    with open(HERE / "results.jsonl", "a") as fh:
        fh.write(json.dumps(summary, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
