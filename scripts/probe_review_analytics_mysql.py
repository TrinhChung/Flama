"""Exercise historical counters on the configured local MySQL dump.

No databases/tables are created, reset or dropped. Only captured fixture Users
with exact generated emails may be deleted. The existing User 1 is read only.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values
from sqlalchemy import delete, event, func, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app import create_app
from app.repositories.review_event_repository import create_review_event_record
from app.repositories.study_authority_repository import lock_study_authority_route
from app.services import review_analytics_backfill_service as backfill
from app.services.review_analytics_policy import policy_from_generation
from app.services.review_analytics_projection_service import (
    ReviewAnalyticsFenceError, flush_review_analytics_deltas, invalidate_review_analytics,
)
from app.services.study_analytics_read_service import analytics_read_transaction
from models import db
from models.review_analytics import DailyReviewCount, ReviewAnalyticsGeneration, ReviewAnalyticsHead
from models.review_event import ReviewEvent
from models.user import User

NOW = datetime(2026, 1, 1, 12)


def local_url(env_file: Path):
    if not env_file.is_file():
        raise ValueError("The configured local environment file is absent.")
    values = dotenv_values(env_file)
    if values.get("SQLALCHEMY_DATABASE_URI"):
        url = make_url(values["SQLALCHEMY_DATABASE_URI"])
    else:
        url = URL.create(
            "mysql+pymysql", username=values.get("DB_USER"),
            password=values.get("DB_PASSWORD", ""), host=values.get("DB_HOST", "localhost"),
            port=int(values.get("DB_PORT", "3306")), database=values.get("DB_NAME"),
            query={"charset": "utf8mb4"},
        )
    if (url.drivername != "mysql+pymysql"
            or url.host not in {"localhost", "127.0.0.1", "::1"}
            or not url.database or not url.username):
        raise ValueError("Refusing a database other than the configured loopback MySQL dump.")
    return url


def assert_fixture_ownership(connection, fixtures):
    """Authorize cleanup by both captured numeric identity and exact email."""
    if not fixtures or any(not isinstance(key, int) or key <= 1 for key in fixtures):
        raise RuntimeError("Invalid fixture identity inventory.")
    users = User.__table__
    rows = dict(connection.execute(select(users.c.id, users.c.email).where(users.c.id.in_(sorted(fixtures)))).all())
    if rows != fixtures:
        raise RuntimeError("Fixture ownership changed; refusing cleanup.")
    return sorted(fixtures)


def _fingerprint(engine):
    # Bounded SQL result: checksum covers every projected source column rather
    # than transferring historical JSON payloads to the probe process.
    with engine.connect() as connection:
        source = dict(connection.execute(text(
            "SELECT COUNT(*) AS events, COALESCE(MIN(id),0) AS first_id, "
            "COALESCE(MAX(id),0) AS last_id, COALESCE(SUM(id),0) AS sum_ids, "
            "COALESCE(SUM(CRC32(CONCAT_WS('|', id, user_id, reviewed_at, "
            "COALESCE(deck_id,'NULL'), COALESCE(duration_ms,'NULL'), rating))),0) AS projected_checksum "
            "FROM review_events WHERE user_id = 1"
        )).mappings().one())
        projection = {}
        for model in (ReviewAnalyticsHead, ReviewAnalyticsGeneration, DailyReviewCount):
            rows = connection.execute(select(model.__table__).where(model.user_id == 1)).all()
            encoded = json.dumps(sorted([list(row) for row in rows], key=str), default=str, sort_keys=True).encode()
            projection[model.__tablename__] = {"rows": len(rows), "sha256": hashlib.sha256(encoded).hexdigest()}
        return {"source": {key: int(value) for key, value in source.items()}, "projection": projection}


class Probe:
    def __init__(self, app):
        self.app = app
        self.engine = db.engine
        self.fixtures = {}
        self.users = {}
        self.checks = {}
        self.details = {}

    def check(self, name, condition, **details):
        self.checks[name] = bool(condition)
        if details:
            self.details[name] = details
        if not condition:
            raise AssertionError(name)

    def session(self):
        session = Session(self.engine, expire_on_commit=False)
        session.info["review_analytics_write_enabled"] = True
        session.execute(text("SET SESSION innodb_lock_wait_timeout=5"))
        # SET creates SQLAlchemy's transaction envelope; roll it back before
        # returning a fresh Session to the backfill service.
        session.rollback()
        return session

    def seed_users(self):
        prefix = "analytics-probe-" + uuid4().hex
        with self.session() as session:
            for label in ("basic", "guards", "same-day", "admission", "chunk", "purge"):
                email = f"{prefix}-{label}@example.invalid"
                user = User(username=f"{prefix}-{label}", email=email, timezone="UTC")
                session.add(user)
                session.flush()
                from app.services.study_authority_enrollment_service import enroll_new_learner_note_authority
                enroll_new_learner_note_authority(session, user=user)
                self.fixtures[int(user.id)] = email
                self.users[label] = int(user.id)
            session.commit()

    def fence(self, session, user_id):
        return lock_study_authority_route(session, learner_user_id=user_id, allow_note_authority=True)

    def fact(self, session, user_id, *, duration=100, rating="good", client_id=None, deck_id=991337):
        return create_review_event_record(
            session=session, user_id=user_id, card_id=str(uuid4()), reviewed_at=NOW,
            duration_ms=duration, rating=rating, mode="review", deck_id=deck_id, note_type_id=None,
            client_event_id=client_id or str(uuid4()),
        )

    def write(self, user_id, facts):
        with self.session() as session:
            self.fence(session, user_id)
            rows = [self.fact(session, user_id, **values) for values in facts]
            flush_review_analytics_deltas(session)
            session.commit()
            return [int(row.id) for row in rows]

    def state(self, user_id):
        with self.session() as session:
            head = session.get(ReviewAnalyticsHead, user_id)
            generation = None
            if head is not None:
                generation_id = head.building_generation or head.active_generation
                if generation_id is not None:
                    generation = session.get(ReviewAnalyticsGeneration, (user_id, generation_id))
            raw = int(session.execute(select(func.count()).select_from(ReviewEvent).where(ReviewEvent.user_id == user_id)).scalar_one())
            totals = session.execute(select(
                func.coalesce(func.sum(DailyReviewCount.review_event_count), 0),
                func.coalesce(func.sum(DailyReviewCount.positive_duration_ms), 0),
                func.coalesce(func.sum(DailyReviewCount.passed_review_count), 0),
            ).where(DailyReviewCount.user_id == user_id, DailyReviewCount.scope_kind == 0,
                    DailyReviewCount.generation == (generation.generation if generation else 0))).one()
            return {
                "raw": raw, "measures": tuple(int(value) for value in totals),
                "revision": int(head.source_revision) if head is not None else None,
                "status": int(generation.status) if generation is not None else None,
                "cursor": int(generation.backfill_cursor_id) if generation is not None else None,
                "high_water": int(generation.baseline_high_water_id) if generation is not None else None,
                "verified": generation.verified_at is not None if generation is not None else False,
            }

    def ready(self, user_id):
        report = backfill.run_review_analytics_backfill(
            user_id=user_id, writer_coverage_enabled=True, session_factory=self.session, chunk_size=2,
        )
        self.check(f"ready_{user_id}", report["ok"] and report["status"] == "READY")

    def transaction_checks(self):
        user_id = self.users["basic"]
        self.ready(user_id)
        client_id = str(uuid4())
        self.write(user_id, [{"client_id": client_id}])
        baseline = self.state(user_id)
        self.check("source_counter_atomic_commit", baseline["raw"] == 1 and baseline["measures"] == (1, 100, 1))
        with self.session() as session:
            self.fence(session, user_id)
            self.fact(session, user_id, duration=9999)
            flush_review_analytics_deltas(session)
            session.rollback()
        self.check("outer_rollback_reverts_raw_counter_revision", self.state(user_id) == baseline)
        with self.session() as session:
            self.fence(session, user_id)
            self.fact(session, user_id, client_id=client_id)
            try:
                flush_review_analytics_deltas(session)
            except IntegrityError:
                session.rollback()
            else:
                raise AssertionError("duplicate_client_id_must_fail")
        self.check("duplicate_rollback_does_not_increment", self.state(user_id) == baseline)
        with self.session() as session:
            self.fence(session, user_id)
            self.fact(session, user_id, duration=300)
            session.flush()
            child = session.begin_nested()
            self.fact(session, user_id, duration=500)
            session.flush()
            child.rollback()
            enclosing = session.begin_nested()
            released = session.begin_nested()
            self.fact(session, user_id, duration=600)
            session.flush()
            released.commit()
            enclosing.rollback()
            with session.begin_nested():
                self.fact(session, user_id, duration=700)
                session.flush()
            flush_review_analytics_deltas(session)
            session.commit()
        state = self.state(user_id)
        self.check("savepoint_rollback_and_released_descendant_discard", state["raw"] == 3 and state["measures"] == (3, 1100, 3))
        with self.session() as session:
            self.fence(session, user_id)
            child = session.begin_nested()
            self.fact(session, user_id)
            session.flush()
            try:
                flush_review_analytics_deltas(session)
            except ReviewAnalyticsFenceError:
                child.rollback()
                session.rollback()
            else:
                raise AssertionError("savepoint_finalizer_must_fail")
        self.check("nested_finalizer_refused", self.state(user_id) == state)

    def guard_checks(self):
        user_id = self.users["guards"]
        for missing in ("fence", "finalizer"):
            with self.session() as session:
                if missing != "fence":
                    self.fence(session, user_id)
                self.fact(session, user_id)
                try:
                    if missing == "fence":
                        flush_review_analytics_deltas(session)
                    else:
                        session.flush()
                        session.commit()
                except ReviewAnalyticsFenceError:
                    session.rollback()
                else:
                    raise AssertionError(f"missing_{missing}_must_fail")
            self.check(f"missing_{missing}_guard", self.state(user_id)["raw"] == 0)

    def concurrent_same_day(self):
        user_id = self.users["same-day"]
        self.ready(user_id)
        barrier = threading.Barrier(2)
        def writer(duration, rating):
            with self.app.app_context(), self.session() as session:
                self.fence(session, user_id)
                self.fact(session, user_id, duration=duration, rating=rating)
                session.flush()
                barrier.wait(timeout=5)
                flush_review_analytics_deltas(session)
                session.commit()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(writer, 1000, "good"), pool.submit(writer, 2000, "again")]
            for future in futures:
                future.result(timeout=10)
        state = self.state(user_id)
        self.check("concurrent_same_day_no_lost_updates", state["raw"] == 2 and state["measures"] == (2, 3000, 1) and state["revision"] == 2)

    def admission_out_of_order(self):
        user_id = self.users["admission"]
        entered_exclusive = threading.Event()
        def capture(_connection, _cursor, sql, _parameters, _context, _many):
            if "FROM users" in sql and "FOR UPDATE" in sql:
                entered_exclusive.set()
        def admit():
            with self.app.app_context():
                return backfill.admit_review_analytics_backfill(
                    user_id=user_id, writer_coverage_enabled=True, session_factory=self.session,
                )
        with self.session() as older:
            self.fence(older, user_id)
            low = self.fact(older, user_id, duration=10)
            older.flush()
            high_id = self.write(user_id, [{"duration": 20}])[0]
            self.check("out_of_order_higher_id_committed_first", int(low.id) < high_id)
            event.listen(self.engine, "before_cursor_execute", capture)
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(admit)
                    if not entered_exclusive.wait(timeout=3):
                        raise AssertionError("admission_exclusive_query_not_observed")
                    time.sleep(0.15)
                    blocked = not future.done()
                    flush_review_analytics_deltas(older)
                    older.commit()
                    report = future.result(timeout=5)
            finally:
                event.remove(self.engine, "before_cursor_execute", capture)
        self.check("admission_drains_lower_id_uncommitted_writer", blocked and report["ok"] and report["baseline_high_water_id"] == high_id)
        while not report["complete"]:
            report = backfill.copy_review_analytics_backfill_chunk(
                user_id=user_id, writer_coverage_enabled=True, session_factory=self.session, chunk_size=1,
            )
            if not report["ok"]:
                raise AssertionError("out_of_order_backfill_failed")
        published = backfill.verify_and_publish_review_analytics_backfill(
            user_id=user_id, writer_coverage_enabled=True, session_factory=self.session,
        )
        state = self.state(user_id)
        self.check("out_of_order_baseline_exact_publication", published["ok"] and state["raw"] == 2 and state["measures"] == (2, 30, 2))

    def chunk_crash_retry(self):
        user_id = self.users["chunk"]
        self.write(user_id, [
            {"duration": -30, "rating": "good"}, {"duration": None, "rating": "easy"},
            {"duration": 0, "rating": "again"}, {"duration": 900, "rating": "hard"},
            {"duration": 1500, "rating": "3"},
        ])
        report = backfill.admit_review_analytics_backfill(user_id=user_id, writer_coverage_enabled=True, session_factory=self.session)
        self.check("chunk_baseline_admitted", report["ok"])
        self.write(user_id, [{"duration": 500, "rating": "easy", "deck_id": None}])
        baseline = self.state(user_id)
        original = backfill.add_grouped_deltas
        class InjectedCrash(RuntimeError):
            pass
        def crash(*args, **kwargs):
            original(*args, **kwargs)
            raise InjectedCrash("after counter SQL, before chunk commit")
        with patch.object(backfill, "add_grouped_deltas", side_effect=crash):
            try:
                backfill.copy_review_analytics_backfill_chunk(user_id=user_id, writer_coverage_enabled=True, session_factory=self.session, chunk_size=2)
            except InjectedCrash:
                pass
            else:
                raise AssertionError("crash_injection_not_reached")
        self.check("chunk_crash_rolls_back_counts_and_cursor", self.state(user_id) == baseline and baseline["measures"][0] == 1)
        report = backfill.copy_review_analytics_backfill_chunk(user_id=user_id, writer_coverage_enabled=True, session_factory=self.session, chunk_size=2)
        self.check("chunk_retry_counts_baseline_once", report["ok"] and report["rows_copied"] == 2 and self.state(user_id)["measures"][0] == 3)
        while report["ok"] and not report["complete"]:
            report = backfill.copy_review_analytics_backfill_chunk(user_id=user_id, writer_coverage_enabled=True, session_factory=self.session, chunk_size=2)
        published = backfill.verify_and_publish_review_analytics_backfill(user_id=user_id, writer_coverage_enabled=True, session_factory=self.session)
        self.check("baseline_and_live_tail_exact_parity", published["ok"] and self.state(user_id)["measures"] == (6, 2900, 4))

    def purge_dirty(self):
        user_id = self.users["purge"]
        self.write(user_id, [{}, {}, {}])
        self.ready(user_id)
        with self.session() as session:
            self.fence(session, user_id)
            invalidate_review_analytics(session, [user_id])
            session.execute(delete(ReviewEvent).where(ReviewEvent.user_id == user_id))
            flush_review_analytics_deltas(session)
            session.commit()
        state = self.state(user_id)
        self.check("projected_purge_marks_dirty_and_clears_proof", state["raw"] == 0 and state["status"] == 2 and not state["verified"] and state["measures"][0] == 3)

    def readonly_summary(self):
        from app.repositories import stats_query_repository as stats

        user_id = self.users["basic"]
        with self.session() as session:
            head = session.get(ReviewAnalyticsHead, user_id)
            generation = session.get(ReviewAnalyticsGeneration, (user_id, head.active_generation))
            policy = policy_from_generation(generation)
        start = NOW.replace(hour=policy.day_boundary_hour, minute=0, second=0, microsecond=0)
        statements = []
        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)
        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            with analytics_read_transaction():
                result = stats.query_daily_review_aggregates(
                    user_id=user_id, timezone_name=policy.timezone_name, timezone_obj=timezone.utc,
                    start_utc=start, end_utc=start + timedelta(days=1), day_boundary_hour_local=policy.day_boundary_hour,
                )
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        upper = [sql.upper() for sql in statements]
        values = list(result.values())
        self.check("readonly_summary_uses_counts_without_raw_scan", len(values) == 1 and values[0] == {"cards": 3, "duration_ms": 1100}
                   and any("DAILY_REVIEW_COUNTS" in sql for sql in upper)
                   and not any("REVIEW_EVENTS" in sql for sql in upper)
                   and not any("FOR UPDATE" in sql or "LOCK IN SHARE MODE" in sql for sql in upper), statement_count=len(statements))
        rejected = False
        try:
            with analytics_read_transaction():
                db.session.execute(DailyReviewCount.__table__.update().where(DailyReviewCount.user_id == user_id).values(review_event_count=4))
        except OperationalError as exc:
            rejected = getattr(exc.orig, "args", (None,))[0] == 1792
        self.check("mysql_readonly_snapshot_rejects_write", rejected)
        purge_id = self.users["purge"]
        with analytics_read_transaction():
            result = stats.query_daily_review_aggregates(
                user_id=purge_id, timezone_name=policy.timezone_name, timezone_obj=timezone.utc,
                start_utc=start, end_utc=start + timedelta(days=1), day_boundary_hour_local=policy.day_boundary_hour,
            )
        self.check("dirty_generation_reader_falls_back_to_raw", result == {})

    def cleanup(self):
        db.session.remove()
        if self.fixtures:
            with self.engine.begin() as connection:
                ids = assert_fixture_ownership(connection, self.fixtures)
                connection.execute(User.__table__.delete().where(User.id.in_(ids)))
            with self.engine.connect() as connection:
                remaining = sum(int(connection.execute(select(func.count()).select_from(model).where(model.user_id.in_(ids))).scalar_one())
                                for model in (ReviewEvent, ReviewAnalyticsHead, ReviewAnalyticsGeneration, DailyReviewCount))
                self.check("fixture_user_cascade_cleanup", remaining == 0)


def _write_result(path, result):
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")


def run_probe(url, output_path=None):
    app = create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
        "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 5, "max_overflow": 3},
        "REVIEW_ANALYTICS_WRITE_ENABLED": True, "REVIEW_ANALYTICS_READ_MODE": "summary",
        "REVIEW_ANALYTICS_READ_USER_IDS": [], "REDIS_URL": "", "WTF_CSRF_ENABLED": False,
    }, audit_mode=True)
    with app.app_context():
        probe = Probe(app)
        before = _fingerprint(db.engine)
        result = {"database": url.database, "host": url.host, "user1_before": before, "passed": False}
        errors = []
        _write_result(output_path, result)
        try:
            from alembic import op
            from alembic.migration import MigrationContext
            from alembic.operations import Operations

            migration = importlib.import_module("migrations.versions.20261005_000051_add_review_analytics_counts")
            prior_proxy = getattr(op, "_proxy", None)
            try:
                with db.engine.begin() as connection:
                    op._proxy = Operations(MigrationContext.configure(connection))
                    migration.upgrade()
            finally:
                op._proxy = prior_proxy
            probe.check("existing_mysql_schema_migration_idempotent", True)
            for model in (ReviewEvent, ReviewAnalyticsHead):
                keys = inspect(db.engine).get_foreign_keys(model.__tablename__)
                probe.check(f"cascade_preflight_{model.__tablename__}", any(
                    key["constrained_columns"] == ["user_id"] and key["referred_table"] == "users"
                    and key.get("options", {}).get("ondelete", "").upper() == "CASCADE" for key in keys
                ))
            probe.seed_users()
            # Keep exact ownership recoverable if the process is interrupted.
            result["fixture_users"] = probe.fixtures
            _write_result(output_path, result)
            probe.transaction_checks()
            probe.guard_checks()
            probe.concurrent_same_day()
            probe.admission_out_of_order()
            probe.chunk_crash_retry()
            probe.purge_dirty()
            probe.readonly_summary()
        except Exception as exc:
            errors.append({"type": type(exc).__name__, "message": str(exc)})
        finally:
            try:
                probe.cleanup()
            except Exception as exc:
                errors.append({"type": type(exc).__name__, "message": str(exc), "phase": "cleanup"})
            after = _fingerprint(db.engine)
            probe.checks["user1_source_and_projection_preserved"] = after == before
            result.update({"checks": probe.checks, "details": probe.details, "user1_after": after,
                           "fixture_user_ids": sorted(probe.fixtures), "errors": errors,
                           "passed": not errors and all(probe.checks.values())})
            _write_result(output_path, result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "output/review_analytics_mysql_probe_20261005.json")
    arguments = parser.parse_args()
    result = run_probe(local_url(arguments.env_file.resolve()), arguments.output)
    print(json.dumps({"passed": result["passed"], "checks": len(result["checks"]),
                      "errors": result["errors"], "output": str(arguments.output)}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
