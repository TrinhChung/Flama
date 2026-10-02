"""Measure cross-learner NOTE write concurrency on disposable local MySQL.

Seeds several NOTE learners in a generated database, then runs rounds in
which every learner commits first reviews of a v4 session at the same moment,
followed by a burst of simultaneous sign-ups with new-learner NOTE enrollment
and a burst of simultaneous MCP ``create_note`` calls by one learner (agents
create Notes in parallel).
Reports HTTP statuses, the InnoDB deadlock delta and integrity checks (event,
token and lineage counts plus ``study-authority-read-audit`` per learner).

Creation and cleanup touch only a generated database on loopback MySQL; the
configured application database is never read or written.

Usage: python scripts/probe_p5_concurrency_mysql.py [--learners 6] [--notes 40]
       [--rounds 3] [--answers 12] [--signups 10] [--creates 12]
"""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import time
from uuid import uuid4

from dotenv import load_dotenv
import pymysql

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import func, select

from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from app.services.study_composition_service import make_compatibility_composition_id
from app.services.user_roles import ensure_default_user_roles
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_lineage_ref import StudyProgressLineageRef
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User
from scripts.probe_p5_direct_replay_mysql import _probe_app
from scripts.probe_phase4_shadow_schema_mysql import (
    _connection_settings, _database_uri, _source_database_collation,
)

PROBE_NAME_PATTERN = re.compile(r"^flama_p5_direct_probe_[0-9]+_[a-f0-9]{8}$")
PROBE_PASSWORD = "Probe-Password-9731!"


def _deadlock_count(connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT `COUNT` FROM information_schema.INNODB_METRICS WHERE NAME = 'lock_deadlocks'")
        row = cursor.fetchone()
    return int(row[0]) if row else -1


def _latest_deadlock(connection) -> str | None:
    with connection.cursor() as cursor:
        cursor.execute("SHOW ENGINE INNODB STATUS")
        status = cursor.fetchone()[2]
    marker = "LATEST DETECTED DEADLOCK"
    if marker not in status:
        return None
    section = status.split(marker, 1)[1]
    return section.split("------------\nTRANSACTIONS", 1)[0][:3000]


def _seed(app, *, learners: int, notes: int) -> list[dict]:
    seeded = []
    with app.app_context():
        db.create_all()
        # Startup maintenance normally seeds the roles every sign-up needs.
        ensure_default_user_roles(db.session)
        db.session.commit()
        for index in range(learners):
            user = User(username=f"probe-learner-{index}", email=f"probe-learner-{index}@example.test")
            user.set_password(PROBE_PASSWORD)
            db.session.add(user)
            db.session.flush()
            deck = Deck(name=f"Probe deck {index}", owner_user_id=user.id)
            note_type = NoteType(name=f"Probe type {index}", user_id=user.id)
            db.session.add_all([deck, note_type])
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
            template = Template(note_type_id=note_type.id, name="Card 1",
                                front_html="{{Word}}", back_html="{{Word}}", is_default=True)
            db.session.add(template)
            db.session.flush()
            rows = [Note(user_id=user.id, deck_id=deck.id, note_type_id=note_type.id,
                         field_values={"Word": f"w-{index}-{number}"}) for number in range(notes)]
            db.session.add_all(rows)
            db.session.flush()
            db.session.add_all(Card(note_id=note.id, template_id=template.id) for note in rows)
            db.session.commit()
            stage_note_authority_enrollment(db.session, learner_user_id=int(user.id), now_utc=datetime.utcnow())
            db.session.commit()
            seeded.append({
                "user_id": int(user.id), "deck_id": deck.id,
                "composition_id": make_compatibility_composition_id(note_type.id, template.id),
            })
    return seeded


def _client(app, user_id: int):
    client = app.test_client()
    with client.session_transaction() as login:
        login["_user_id"], login["_fresh"] = str(user_id), True
    return client


def _commit_payload(snapshot: dict, answers: int) -> dict:
    events = []
    new_cards = [card for card in snapshot["cards"] if card["state"].get("type") == "new"][:answers]
    for sequence, card in enumerate(new_cards, start=1):
        policy = snapshot["policies"][card["policy_key"]]
        event_id = str(uuid4())
        events.append({
            "event_id": event_id, "sequence": sequence, "card_id": card["card_id"], "rating": "good",
            "policy_key": card["policy_key"], "scheduler_offset_ms": 1000 * sequence, "duration_ms": 3000,
            "action_key": "review.good", "action_contract_version": "1",
            "trigger_key": "scheduler.review.good", "trigger_contract_version": "1",
            "algorithm_key": snapshot["scheduler_algorithm"], "algorithm_version": snapshot["algorithm_version"],
            "config_schema_version": policy["config_schema_version"], "config_hash": policy["config_hash"],
            "study_session_id": snapshot["session_id"], "operation_key": event_id,
            **{key: value for key, value in card["authority_pin"].items() if key != "schema_version"},
        })
    return {"schema_version": "study-commit.v3", "commit_id": str(uuid4()),
            "session_token": snapshot["session_token"], "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover", "events": events, "final_states": []}


def _commit_round(app, learners: list[dict], *, answers: int) -> dict:
    snapshots = {}
    for learner in learners:  # Opens run one at a time; this round measures commits.
        response = _client(app, learner["user_id"]).post("/api/study/sessions", json={
            "scope": "deck", "scope_id": learner["deck_id"], "composition_id": learner["composition_id"],
            "accepted_session_schema_versions": ["study-session.v4"],
            "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
        })
        if response.status_code != 201:
            raise RuntimeError(f"open failed: {response.status_code} {response.get_json()}")
        snapshots[learner["user_id"]] = response.get_json()
    barrier = threading.Barrier(len(learners), timeout=60)

    def commit(learner):
        client = _client(app, learner["user_id"])
        snapshot = snapshots[learner["user_id"]]
        payload = _commit_payload(snapshot, answers)
        barrier.wait()
        started = time.perf_counter()
        response = client.post(f"/api/study/sessions/{snapshot['session_id']}/commit", json=payload)
        body = response.get_json(silent=True) or {}
        return {
            "user_id": learner["user_id"], "status": response.status_code,
            "seconds": round(time.perf_counter() - started, 3),
            "error": body.get("error"), "accepted": len(payload["events"]) if response.status_code == 200 else 0,
        }

    with ThreadPoolExecutor(max_workers=len(learners)) as executor:
        results = list(executor.map(commit, learners))
    return {"results": results, "statuses": dict(Counter(str(item["status"]) for item in results))}


def _direct_round(app, learners: list[dict], *, answers: int) -> dict:
    """Every learner answers new cards through the direct REST path at once."""

    with app.app_context():
        targets = {
            learner["user_id"]: db.session.execute(
                select(Card.id)
                .join(Note, Note.id == Card.note_id)
                .where(Note.deck_id == learner["deck_id"])
                .where(~select(ReviewEvent.id).where(ReviewEvent.card_id == Card.id).exists())
                .order_by(Card.id)
                .limit(answers)
            ).scalars().all()
            for learner in learners
        }
    barrier = threading.Barrier(len(learners), timeout=60)

    def answer_all(learner):
        client = _client(app, learner["user_id"])
        barrier.wait()
        statuses = []
        for card_id in targets[learner["user_id"]]:
            response = client.post(f"/api/study/{card_id}/answer", json={
                "rating": "good", "operation_key": str(uuid4()), "duration_ms": 900,
                "scope": "deck", "scope_id": learner["deck_id"]})
            statuses.append(response.status_code)
        return learner["user_id"], statuses

    with ThreadPoolExecutor(max_workers=len(learners)) as executor:
        results = list(executor.map(answer_all, learners))
    return {
        "statuses": dict(Counter(str(status) for _, statuses in results for status in statuses)),
        "accepted": {user_id: sum(1 for status in statuses if status == 200) for user_id, statuses in results},
    }


def _signup_burst(app, count: int) -> dict:
    barrier = threading.Barrier(count, timeout=60)
    tag = secrets.token_hex(3)

    def register(index):
        client = app.test_client()
        payload = {"email": f"signup-{tag}-{index}@example.test", "username": f"signup_{tag}_{index}",
                   "password": PROBE_PASSWORD, "confirm_password": PROBE_PASSWORD}
        barrier.wait()
        response = client.post("/api/auth/register", json=payload)
        return response.status_code, (response.get_json(silent=True) or {}).get("error")

    with ThreadPoolExecutor(max_workers=count) as executor:
        results = list(executor.map(register, range(count)))
    with app.app_context():
        emails = [f"signup-{tag}-{index}@example.test" for index in range(count)]
        created = db.session.execute(select(User.id).where(User.email.in_(emails))).scalars().all()
        enrolled = db.session.execute(
            select(func.count()).select_from(StudyAuthorityEnrollment).where(
                StudyAuthorityEnrollment.learner_user_id.in_(created),
                StudyAuthorityEnrollment.mode_code == "NOTE",
            )
        ).scalar_one()
    return {
        "statuses": dict(Counter(str(status) for status, _ in results)),
        "errors": dict(Counter(str(error) for status, error in results if status >= 400)),
        "created": len(created), "enrolled_note": int(enrolled),
    }


def _create_burst(app, learner: dict, count: int) -> dict:
    """One learner's agent creates ``count`` Notes through MCP at the same moment."""

    from app.services.mcp.note_tools import create_note

    with app.app_context():
        note_type_name = db.session.execute(
            select(NoteType.name).join(Note, Note.note_type_id == NoteType.id)
            .where(Note.deck_id == learner["deck_id"]).limit(1)
        ).scalar_one()
        before = db.session.execute(
            select(func.count()).select_from(Note).where(Note.user_id == learner["user_id"])
        ).scalar_one()
        subjects_before = db.session.execute(
            select(func.count()).select_from(StudyProgressSubject)
            .where(StudyProgressSubject.learner_user_id == learner["user_id"])
        ).scalar_one()
    barrier = threading.Barrier(count, timeout=60)
    tag = secrets.token_hex(3)

    def create(index):
        with app.app_context():
            barrier.wait()
            try:
                create_note(user_id=learner["user_id"], note_data={
                    "deck_id": learner["deck_id"], "note_type_name": note_type_name,
                    "fields": {"Word": f"mcp-{tag}-{index}"}})
                return "created"
            except Exception as exc:  # noqa: BLE001 - reported, not raised
                db.session.rollback()
                return type(exc).__name__
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=count) as executor:
        results = list(executor.map(create, range(count)))
    with app.app_context():
        after = db.session.execute(
            select(func.count()).select_from(Note).where(Note.user_id == learner["user_id"])
        ).scalar_one()
        subjects_after = db.session.execute(
            select(func.count()).select_from(StudyProgressSubject)
            .where(StudyProgressSubject.learner_user_id == learner["user_id"])
        ).scalar_one()
    return {"results": dict(Counter(results)), "notes_added": int(after - before),
            "subjects_added": int(subjects_after - subjects_before)}


def _integrity(app, learners: list[dict], accepted_by_user: dict[int, int]) -> dict:
    report = {"learners": [], "ok": True}
    runner = app.test_cli_runner()
    with app.app_context():
        for learner in learners:
            user_id = learner["user_id"]
            events = db.session.execute(
                select(func.count()).select_from(ReviewEvent).where(ReviewEvent.user_id == user_id)
            ).scalar_one()
            revisions = db.session.execute(
                select(func.coalesce(func.sum(StudyAuthoritySubjectToken.authority_revision), 0))
                .join(StudyProgressSubject, StudyProgressSubject.id == StudyAuthoritySubjectToken.subject_id)
                .where(StudyProgressSubject.learner_user_id == user_id)
            ).scalar_one()
            duplicate_pointers = db.session.execute(
                select(func.count()).select_from(
                    select(StudyProgressLineageRef.contributor_id)
                    .join(StudyProgressContributor,
                          StudyProgressContributor.id == StudyProgressLineageRef.contributor_id)
                    .join(StudyProgressSubject, StudyProgressSubject.id == StudyProgressContributor.subject_id)
                    .where(StudyProgressSubject.learner_user_id == user_id,
                           StudyProgressLineageRef.ref_kind == "LAST_REVIEW_EVENT")
                    .group_by(StudyProgressLineageRef.contributor_id)
                    .having(func.count() > 1)
                    .subquery()
                )
            ).scalar_one()
            audit = runner.invoke(args=["study-authority-read-audit", "--user-id", str(user_id)])
            try:
                audit_status = json.loads(audit.output.strip().splitlines()[-1]).get("status")
            except (ValueError, IndexError):
                audit_status = f"UNPARSEABLE(exit={audit.exit_code})"
            row = {
                "user_id": user_id, "events": int(events), "accepted": accepted_by_user.get(user_id, 0),
                "token_revisions": int(revisions), "duplicate_pointers": int(duplicate_pointers),
                "audit": audit_status, "audit_exit": audit.exit_code,
            }
            row["ok"] = (
                row["events"] == row["accepted"] == row["token_revisions"]
                and row["duplicate_pointers"] == 0 and audit.exit_code == 0 and audit_status == "PASS"
            )
            report["ok"] = report["ok"] and row["ok"]
            report["learners"].append(row)
    return report


def run_probe(*, learners: int, notes: int, rounds: int, answers: int, signups: int,
              creates: int = 0) -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p5_direct_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("Concurrency probe requires a generated local MySQL database.")
    admin = pymysql.connect(**settings)
    created = False
    app = None
    report: dict = {"schema_version": "p5-concurrency-mysql.v1", "configured_database_modified": False,
                    "learners": learners, "notes": notes, "rounds": rounds, "answers": answers}
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION(), @@transaction_isolation")
            report["mysql_version"], report["isolation"] = cursor.fetchone()
        # One process runs every simulated request thread here; production
        # runs 4 threads per process against the default pool of 4 + 1.
        os.environ["DB_POOL_SIZE"] = str(max(learners, signups, creates) + 2)
        app = _probe_app(_database_uri(settings, name))
        app.config.update(STUDY_NEW_LEARNER_NOTE_ENABLED=True, STUDY_PROGRESS_SHADOW_WRITE_ENABLED=True)
        seeded = _seed(app, learners=learners, notes=notes)

        accepted_by_user: dict[int, int] = {}
        report["rounds_detail"] = []
        deadlocks_before = _deadlock_count(admin)
        for _ in range(rounds):
            outcome = _commit_round(app, seeded, answers=answers)
            for item in outcome["results"]:
                accepted_by_user[item["user_id"]] = accepted_by_user.get(item["user_id"], 0) + item["accepted"]
            report["rounds_detail"].append(outcome)
        report["commit_deadlocks"] = _deadlock_count(admin) - deadlocks_before
        report["commit_failures"] = sum(
            1 for outcome in report["rounds_detail"] for item in outcome["results"] if item["status"] != 200
        )

        deadlocks_before = _deadlock_count(admin)
        direct = _direct_round(app, seeded, answers=max(1, answers // 2))
        for user_id, count in direct["accepted"].items():
            accepted_by_user[user_id] = accepted_by_user.get(user_id, 0) + count
        report["direct"] = direct["statuses"]
        report["direct_deadlocks"] = _deadlock_count(admin) - deadlocks_before
        report["commit_failures"] += sum(
            count for status, count in direct["statuses"].items() if status != "200"
        )

        deadlocks_before = _deadlock_count(admin)
        report["signups"] = _signup_burst(app, signups) if signups else None
        report["signup_deadlocks"] = _deadlock_count(admin) - deadlocks_before
        deadlocks_before = _deadlock_count(admin)
        report["creates"] = _create_burst(app, seeded[0], creates) if creates else None
        report["create_deadlocks"] = _deadlock_count(admin) - deadlocks_before
        if (report["commit_deadlocks"] or report["direct_deadlocks"] or report["signup_deadlocks"]
                or report["create_deadlocks"]):
            report["latest_deadlock"] = _latest_deadlock(admin)
        report["integrity"] = _integrity(app, seeded, accepted_by_user)
        report["status"] = (
            "PASS" if report["integrity"]["ok"] and report["commit_failures"] == 0
            and (not signups or report["signups"]["created"] == report["signups"]["enrolled_note"] == signups)
            and (not creates or report["creates"]["results"] == {"created": creates}
                 and report["creates"]["notes_added"] == report["creates"]["subjects_added"] == creates)
            else "FAIL"
        )
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
        admin.close()
    report["probe_database_dropped"] = created
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--learners", type=int, default=6)
    parser.add_argument("--notes", type=int, default=40)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--answers", type=int, default=12)
    parser.add_argument("--signups", type=int, default=10)
    parser.add_argument("--creates", type=int, default=12)
    args = parser.parse_args()
    report = run_probe(learners=args.learners, notes=args.notes, rounds=args.rounds,
                       answers=args.answers, signups=args.signups, creates=args.creates)
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
