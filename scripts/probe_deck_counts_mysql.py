"""Prove deck snapshot freshness on the configured loopback MySQL dump."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
import sys
import threading
import statistics
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import bindparam, event, inspect, select, update
from app import create_audit_app
from app.repositories.deck_count_snapshot_repository import read_revision_vectors
from app.repositories.study_repository import _today_day_index
from app.services.anki_scheduler import _day_index_to_datetime
from app.services.deck_aggregation_service import aggregate_deck_study_counts
from app.services.deck_count_snapshot_service import prewarm_owned_deck_counts, resolve_cached_owned_deck_counts
from app.services.study_analytics_read_service import analytics_read_transaction
from models import db
from models.card import Card
from tests.study_note_fixtures import attach_template, enroll_note_user
from tests.note_progress_fixtures import stage_note_state, subject_values
from models.study_progress_subject import StudyProgressSubject
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.deck import Deck
from models.deck_count_snapshot import DeckCountContentRevision
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from scripts.probe_review_analytics_mysql import Probe, _fingerprint, _write_result, local_url

NOW = datetime(2026, 10, 6, 12)
DAY = _today_day_index(now=NOW, timezone_name="UTC", day_boundary_hour_local=4)
CUTOFF = _day_index_to_datetime(DAY + 1, 4, timezone_name="UTC")


def run(url, output):
    app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
        "DECK_COUNT_WRITE_ENABLED": True, "DECK_COUNT_READ_MODE": "summary", "REDIS_URL": "", "STUDY_NOTE_COUNT_ENABLED": False})
    result = {"host": url.host, "database": url.database, "passed": False}
    with app.app_context():
        probe = Probe(app)
        before = _fingerprint(db.engine)["source"]
        decks = []
        try:
            required = {"deck_count_content_revisions", "deck_count_learner_revisions", "deck_study_count_snapshots"}
            if not required.issubset(inspect(db.engine).get_table_names()):
                raise RuntimeError("Apply migration52 before running the deck probe")
            probe.seed_users()
            result["fixture_users"] = probe.fixtures
            _write_result(output, result)
            user_id = probe.users["basic"]
            # Summary reads cover only the learners the prewarm worker refreshes.
            app.config["DECK_COUNT_PREWARM_USER_IDS"] = (str(user_id),)
            fixture_tag = probe.fixtures[user_id].split("@")[0]
            with probe.session() as session:
                for fixture_user_id in probe.users.values():
                    if session.get(StudyAuthorityEnrollment, fixture_user_id) is None:
                        enroll_note_user(session, session.get(User, fixture_user_id))
                first = Deck(name=f"Count fixture {fixture_tag} A", owner_user_id=user_id)
                second = Deck(name=f"Count fixture {fixture_tag} B", owner_user_id=user_id)
                nt = NoteType(name="Count fixture", user_id=user_id)
                session.add_all([first, second, nt])
                session.flush()
                decks = [int(first.id), int(second.id)]
                result["fixture_decks"] = {deck_id: user_id for deck_id in decks}
                _write_result(output, result)
                templates = [attach_template(session, owner_user_id=user_id, note_type_id=nt.id, name=f"Fixture {index}", front_html="x", back_html="y") for index in range(2)]
                session.add_all(templates)
                session.flush()
                cards = []
                note_ids = []
                # Siblings on the first Note share one state. The concurrent
                # second-deck writers target two distinct Notes in that deck.
                for index, deck_id in enumerate((decks[0], decks[1], decks[1])):
                    note = Note(user_id=user_id, deck_id=deck_id, note_type_id=nt.id, field_values={})
                    session.add(note)
                    session.flush()
                    presentations = session.query(Card).filter_by(note_id=note.id).order_by(Card.template_id).all()
                    cards.extend(str(card.id) for card in (presentations if index == 0 else presentations[:1]))
                    note_ids.append(str(note.id))
                session.commit()

            def set_fixture_suspension(suspended):
                columns = ('algorithm_key','algorithm_version','state_schema_version','storage_codec','state_payload',
                    'state_payload_size','algorithm_state_hash','semantic_state_hash','projection_version','normalized_queue',
                    'due_at','due_day','is_suspended','is_buried','buried_until_day')
                parameters = []
                for index, note_id in enumerate(note_ids):
                    values = subject_values(user_id=user_id, note_id=note_id, now=NOW,
                        queue='review' if index == 0 else 'learn', due_day=DAY if index == 0 else None,
                        is_suspended=suspended)
                    parameters.append({'fixture_key':values['logical_note_key'], **{key:values[key] for key in columns}})
                table = StudyProgressSubject.__table__
                statement = update(table).where(table.c.learner_user_id == user_id,
                    table.c.logical_note_key == bindparam('fixture_key')).values({key:bindparam(key) for key in columns})
                with probe.session() as session:
                    session.execute(statement, parameters)
                    session.commit()

            def vector():
                with probe.session() as session:
                    return read_revision_vectors(session, user_id=user_id, deck_ids=decks)

            def cached():
                with analytics_read_transaction():
                    return resolve_cached_owned_deck_counts(db.session, learner_user_id=user_id,
                        visible_deck_ids=decks, today_day_index=DAY, day_cutoff_utc=CUTOFF,
                        timezone_name="UTC", day_boundary_hour_local=4, is_note_mode=True, now_utc=NOW)

            def raw():
                with analytics_read_transaction():
                    return aggregate_deck_study_counts(db.session, learner_user_id=user_id,
                        visible_deck_ids=decks, today_day_index=DAY, day_cutoff_utc=CUTOFF,
                        include_note_types=False)[0]

            warm = prewarm_owned_deck_counts(user_id=user_id, now_utc=NOW)
            hits, misses = cached()
            probe.check("fresh_mysql_snapshot_exact_parity", warm["published"] == 2 and not misses and hits == raw())
            probe.check("valid_prewarm_skips_raw_work", prewarm_owned_deck_counts(user_id=user_id, now_utc=NOW)["computed"] == 0)
            initial = vector()
            with probe.session() as session:
                session.add(stage_note_state(session, user_id=user_id, card_id=cards[0], queue="review", due_day=DAY))
                session.commit()
            hits, misses = cached()
            probe.check("orm_progress_invalidates_only_affected_deck", misses == [decks[0]] and list(hits) == [decks[1]]
                and vector()[decks[0]][3] == initial[decks[0]][3] + 1)
            probe.check("dirty_prewarm_is_bounded_to_one_deck", prewarm_owned_deck_counts(user_id=user_id, now_utc=NOW)["computed"] == 1)
            probe.check("post_review_snapshot_exact_parity", cached()[0] == raw())
            baseline = vector()
            with probe.session() as session:
                session.add(stage_note_state(session, user_id=user_id, card_id=cards[1], queue="learn"))
                session.flush()
                session.rollback()
            probe.check("outer_rollback_preserves_tokens", vector() == baseline)
            with probe.session() as session:
                outer = session.begin_nested()
                child = session.begin_nested()
                stage_note_state(session, user_id=user_id, card_id=cards[0], queue="learn")
                session.flush()
                child.commit()
                outer.rollback()
                session.commit()
            probe.check("released_descendant_rollback_preserves_tokens", vector() == baseline)

            barrier = threading.Barrier(2)
            def writer(card_id):
                with app.app_context(), probe.session() as session:
                    session.add(stage_note_state(session, user_id=user_id, card_id=card_id, queue="learn"))
                    session.flush()
                    barrier.wait(timeout=5)
                    session.commit()
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(writer, card_id) for card_id in cards[2:]]
                for future in futures:
                    future.result(timeout=10)
            probe.check("concurrent_same_deck_no_lost_revision", vector()[decks[1]][3] == baseline[decks[1]][3] + 2)
            prewarm_owned_deck_counts(user_id=user_id, now_utc=NOW)
            probe.check("concurrent_updates_snapshot_exact_parity", cached()[0] == raw())
            db.session.remove()
            set_fixture_suspension(True)
            probe.check("first_statement_bulk_invalidates_global_epoch", cached()[1] == decks)
            prewarm_owned_deck_counts(user_id=user_id, now_utc=NOW)
            probe.check("bulk_refresh_exact_parity", cached()[0] == raw())
            statements = []
            def capture(_conn, _cursor, sql, _parameters, _context, _many):
                statements.append(sql.lower())
            event.listen(db.engine, "before_cursor_execute", capture)
            try:
                cached()
            finally:
                event.remove(db.engine, "before_cursor_execute", capture)
            probe.check("mysql_cache_hit_is_readonly_and_does_not_scan_cards", bool(statements)
                and not any("from cards" in sql or "join cards" in sql or "for update" in sql
                            or "lock in share mode" in sql or sql.startswith(("insert", "update", "delete")) for sql in statements))
            # Measure the actual native transaction, rather than timing only
            # one counter UPSERT. These writes affect the captured fixture only.
            from app.services.study_service import execute_native_review_command
            from app.services.review_analytics_backfill_service import run_review_analytics_backfill
            from app.services.deck_count_projection_service import invalidate_all_deck_counts
            set_fixture_suspension(False)
            write_metrics = {}
            for mode, history_enabled, deck_enabled in (
                    ("disabled", False, False), ("history_only", True, False),
                    ("deck_only", False, True), ("both", True, True)):
                app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = history_enabled
                app.config["DECK_COUNT_WRITE_ENABLED"] = deck_enabled
                if history_enabled:
                    run_review_analytics_backfill(user_id=user_id, writer_coverage_enabled=True)
                if deck_enabled:
                    invalidate_all_deck_counts(db.session)
                    db.session.commit()
                durations = []
                for iteration in range(12):
                    db.session.remove()
                    user = db.session.get(User, user_id)
                    card = db.session.get(Card, cards[0])
                    started = time.perf_counter()
                    execute_native_review_command(user=user, card=card, action="good",
                        payload={"duration_ms": 100}, clone_scope=None, requested_scope_id=decks[0],
                        timezone_name="UTC", now=NOW, client_event_id=str(uuid4()))
                    if iteration >= 2:
                        durations.append((time.perf_counter() - started) * 1000)
                ordered = sorted(durations)
                def percentile(value):
                    position = (len(ordered) - 1) * value / 100
                    lower = int(position)
                    upper = min(lower + 1, len(ordered) - 1)
                    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
                write_metrics[mode] = {
                    "history_write_enabled": history_enabled, "deck_write_enabled": deck_enabled,
                    "median_ms": round(statistics.median(durations), 2),
                    "p95_ms": round(percentile(95), 2), "p99_ms": round(percentile(99), 2),
                    "samples_ms": [round(value, 2) for value in durations],
                }
                if history_enabled:
                    # Projection runs outside the native write timing. Drain
                    # before changing coverage or admitting another backfill.
                    probe.drain(user_id)
            result["native_review_write_metrics"] = write_metrics
            baseline_p95 = write_metrics["disabled"]["p95_ms"]
            for mode, metrics in write_metrics.items():
                metrics["p95_added_ms"] = round(metrics["p95_ms"] - baseline_p95, 2)
                metrics["p95_added_percent"] = round((metrics["p95_ms"] / baseline_p95 - 1) * 100, 2)
                metrics["proposed_write_budget_met"] = metrics["p95_added_ms"] <= 5 and metrics["p95_added_percent"] <= 10
            result["write_qualification_scope"] = "Sequential NOTE fixture samples; concurrency/cold-cache qualification still required"
            state = probe.state(user_id)
            probe.check("native_write_benchmark_counters_match_accepted_facts", state["raw"] == 48
                        and state["measures"] == (48, 4800, 48) and state["revision"] == 24)
        except Exception as exc:
            result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            try:
                if decks:
                    with db.engine.begin() as connection:
                        ownership = dict(connection.execute(select(Deck.__table__.c.id, Deck.__table__.c.owner_user_id).where(
                            Deck.__table__.c.id.in_(decks))).all())
                        if not set(ownership).issubset(decks) or any(owner != probe.users["basic"] for owner in ownership.values()):
                            raise RuntimeError("Fixture deck ownership changed; refusing cleanup")
                        # Deck.owner_user_id is SET NULL on User deletion,
                        # so explicit captured-deck cleanup must happen first.
                        connection.execute(Deck.__table__.delete().where(Deck.__table__.c.id.in_(decks)))
                        connection.execute(DeckCountContentRevision.__table__.delete().where(
                            DeckCountContentRevision.physical_deck_id.in_(decks)))
                probe.cleanup()
            except Exception as exc:
                result["cleanup_error"] = {"type": type(exc).__name__, "message": str(exc)}
            result.update({"checks": probe.checks, "source_before": before,
                           "source_after": _fingerprint(db.engine)["source"]})
            result["checks"]["user1_source_preserved"] = result["source_before"] == result["source_after"]
            result["passed"] = all(result["checks"].values()) and not result.get("error") and not result.get("cleanup_error")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "output/deck_counts_mysql_probe_20261006.json")
    arguments = parser.parse_args()
    result = run(local_url(arguments.env_file.resolve()), arguments.output)
    print(json.dumps({"passed": result["passed"], "checks": len(result["checks"]),
                      "error": result.get("error"), "cleanup_error": result.get("cleanup_error")}))
    raise SystemExit(0 if result["passed"] else 1)
