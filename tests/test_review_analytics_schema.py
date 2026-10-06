"""Historical-count schema parity, integrity and additive migration behavior."""

from __future__ import annotations

from datetime import date, datetime
import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError

from models.review_analytics import (
    BUILDING, READY, DIRTY, FAILED, RETIRED,
    DailyReviewCount, ReviewAnalyticsGeneration, ReviewAnalyticsHead,
)


migration = importlib.import_module("migrations.versions.20261005_000051_add_review_analytics_counts")
MODELS = (ReviewAnalyticsHead, ReviewAnalyticsGeneration, DailyReviewCount)
NOW = datetime(2026, 10, 5, 9, 12, 34, 123456)
DAY = date(2026, 10, 5)


class ReviewAnalyticsSchemaTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.connection = self.engine.connect()
        self.connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        self.metadata = sa.MetaData()
        self.users = sa.Table("users", self.metadata, sa.Column("id", sa.Integer, primary_key=True))
        self.tables = [model.__table__.to_metadata(self.metadata) for model in MODELS]
        self.metadata.create_all(self.connection)
        self.connection.execute(self.users.insert().values(id=1))
        self.connection.execute(self.users.insert().values(id=2))
        self.connection.commit()
        op._proxy = Operations(MigrationContext.configure(self.connection))

    def tearDown(self):
        op._proxy = None
        self.connection.close()
        self.engine.dispose()

    def _seed(self, **generation_values):
        head, generation, counts = self.tables
        self.connection.execute(head.insert().values(user_id=1, updated_at=NOW))
        self.connection.execute(generation.insert().values(
            user_id=1, generation=7, policy_hash=b"p" * 32,
            timezone_name="Asia/Tokyo", day_boundary_hour=4,
            grouping_version=1, timezone_rules_version="test-v1", status=BUILDING,
            baseline_high_water_id=20, backfill_cursor_id=10,
            applied_source_revision=4, verified_source_revision=3,
            verification_contract_version=1, verified_at=NOW, created_at=NOW,
            **generation_values,
        ))
        self.connection.execute(counts.insert().values(
            user_id=1, generation=7, scope_kind=0, scope_id=0, study_day=DAY,
            review_event_count=3, positive_duration_ms=1000, passed_review_count=2,
        ))
        self.connection.commit()

    def test_status_codes_and_model_registration(self):
        self.assertEqual((BUILDING, READY, DIRTY, FAILED, RETIRED), tuple(range(5)))
        self.assertEqual(ReviewAnalyticsGeneration.BUILDING, BUILDING)
        from app import create_app
        from models import db

        app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
        }, audit_mode=True)
        with app.app_context():
            self.assertTrue(set(migration.TABLE_NAMES) <= set(db.metadata.tables))
            self.assertFalse(set(migration.TABLE_NAMES) & set(sa.inspect(db.engine).get_table_names()))
            db.session.remove()

    def test_mysql_widths_signedness_precision_and_no_extra_indexes(self):
        dialect = mysql.dialect()
        for model, actual, expected in zip(MODELS, self.tables, migration._tables()):
            with self.subTest(table=model.__tablename__):
                self.assertEqual(
                    sorted(line.strip().rstrip(",") for line in str(sa.schema.CreateTable(actual).compile(dialect=dialect)).splitlines()),
                    sorted(line.strip().rstrip(",") for line in str(sa.schema.CreateTable(expected).compile(dialect=dialect)).splitlines()),
                )
                self.assertFalse(model.__table__.indexes)
                self.assertEqual(str(model.__table__.c.user_id.type.compile(dialect=dialect)), "INTEGER")
                self.assertNotIn("AUTO_INCREMENT", str(sa.schema.CreateTable(actual).compile(dialect=dialect)))
        self.assertEqual(str(ReviewAnalyticsHead.__table__.c.source_revision.type.compile(dialect=dialect)), "BIGINT UNSIGNED")
        self.assertEqual(str(DailyReviewCount.__table__.c.review_event_count.type.compile(dialect=dialect)), "BIGINT")
        self.assertEqual(str(ReviewAnalyticsGeneration.__table__.c.verified_at.type.compile(dialect=dialect)), "DATETIME(6)")
        self.assertEqual(str(ReviewAnalyticsGeneration.__table__.c.policy_hash.type.compile(dialect=dialect)), "BINARY(32)")

    def test_upgrade_existing_create_all_schema_preserves_values_and_proof(self):
        self._seed()
        before = [self.connection.execute(table.select()).all() for table in self.tables]
        migration.upgrade()
        migration.upgrade()
        self.assertEqual(before, [self.connection.execute(table.select()).all() for table in self.tables])
        row = self.connection.execute(self.tables[0].select()).mappings().one()
        self.assertEqual((row["next_generation"], row["source_revision"]), (1, 0))

    def test_fresh_upgrade_and_empty_downgrade_are_idempotent(self):
        for table in reversed(self.tables):
            table.drop(self.connection)
        migration.upgrade()
        migration.upgrade()
        self.assertTrue(set(migration.TABLE_NAMES) <= set(sa.inspect(self.connection).get_table_names()))
        migration.downgrade()
        migration.downgrade()
        self.assertEqual(sa.inspect(self.connection).get_table_names(), ["users"])

    def test_partial_create_all_schema_is_completed_without_resetting_head(self):
        for table in reversed(self.tables[1:]):
            table.drop(self.connection)
        self.connection.execute(self.tables[0].insert().values(user_id=1, source_revision=8, next_generation=9, updated_at=NOW))
        migration.upgrade()
        head = self.connection.execute(self.tables[0].select()).mappings().one()
        self.assertEqual((head["source_revision"], head["next_generation"]), (8, 9))

    def test_upgrade_rejects_unknown_column_drift_before_creating_missing_parent(self):
        # SQLite can preserve an existing child's declared FK while its parent
        # is absent. Preflight must reject the child before creating that parent.
        self.tables[1].drop(self.connection)
        self.connection.exec_driver_sql("ALTER TABLE daily_review_counts ADD COLUMN unexpected INTEGER")
        with self.assertRaisesRegex(RuntimeError, "daily_review_counts.*column set"):
            migration.upgrade()
        self.assertNotIn("review_analytics_generations", sa.inspect(self.connection).get_table_names())

    def test_upgrade_rejects_type_nullability_default_and_check_drift(self):
        for kind in ("type", "nullability", "default", "check"):
            with self.subTest(kind=kind):
                self.tables[2].drop(self.connection)
                table = migration._tables()[2]
                if kind == "type":
                    table.c.review_event_count.type = sa.Integer()
                elif kind == "nullability":
                    table.c.positive_duration_ms.nullable = True
                elif kind == "default":
                    table.c.review_event_count.server_default = sa.DefaultClause(sa.text("0"))
                else:
                    check = next(c for c in table.constraints if c.name == "ck_daily_review_count_scope")
                    check.sqltext = sa.text("scope_kind = 0 OR scope_kind = 1")
                table.create(self.connection)
                with self.assertRaisesRegex(RuntimeError, "schema drift"):
                    migration.upgrade()

    def test_checks_reject_invalid_scope_negative_measures_and_impossible_cursor(self):
        self._seed()
        counts = self.tables[2]
        for values in (
            {"scope_kind": 0, "scope_id": 5},
            {"scope_kind": 1, "scope_id": 0},
            {"scope_kind": 2, "scope_id": 7},
            {"review_event_count": -1},
            {"positive_duration_ms": -1},
            {"passed_review_count": -1},
            {"passed_review_count": 4},
        ):
            with self.subTest(values=values), self.connection.begin_nested():
                with self.assertRaises(IntegrityError):
                    self.connection.execute(counts.update().values(**values))
        generation = self.tables[1]
        for values in ({"status": 5}, {"day_boundary_hour": 24}, {"day_boundary_hour": -1}, {"backfill_cursor_id": 21}):
            with self.subTest(values=values), self.connection.begin_nested():
                with self.assertRaises(IntegrityError):
                    self.connection.execute(generation.update().values(**values))

    def test_upgrade_rejects_fk_delete_drift_and_unplanned_indexes(self):
        self.tables[2].drop(self.connection)
        table = migration._tables()[2]
        next(iter(table.foreign_key_constraints)).ondelete = "RESTRICT"
        table.create(self.connection)
        with self.assertRaisesRegex(RuntimeError, "foreign keys or delete behavior"):
            migration.upgrade()
        table.drop(self.connection)
        self.tables[2].create(self.connection)
        sa.Index("unexpected_day_index", self.tables[2].c.study_day).create(self.connection)
        with self.assertRaisesRegex(RuntimeError, "unexpected secondary"):
            migration.upgrade()

    def test_mysql_check_parentheses_cannot_hide_changed_scope_logic(self):
        expected = "(scope_kind = 0 AND scope_id = 0) OR (scope_kind = 1 AND scope_id > 0)"
        reflected = "(((`scope_kind` = 0) and (`scope_id` = 0)) or ((`scope_kind` = 1) and (`scope_id` > 0)))"
        changed = "scope_kind = 0 AND (scope_id = 0 OR scope_kind = 1) AND scope_id > 0"
        self.assertEqual(migration._check_sql(expected), migration._check_sql(reflected))
        self.assertNotEqual(migration._check_sql(expected), migration._check_sql(changed))

    def test_composite_user_generation_fk_and_cascade_preserve_historical_scope(self):
        self._seed()
        counts = self.tables[2]
        self.connection.execute(counts.insert().values(
            user_id=1, generation=7, scope_kind=1, scope_id=999999, study_day=DAY,
            review_event_count=1, positive_duration_ms=0, passed_review_count=0,
        ))
        # No Deck FK: historical deck attribution survives a live deck's deletion.
        self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(counts)).scalar_one(), 2)
        with self.connection.begin_nested(), self.assertRaises(IntegrityError):
            self.connection.execute(counts.insert().values(
                user_id=2, generation=7, scope_kind=0, scope_id=0, study_day=DAY,
                review_event_count=1, positive_duration_ms=0, passed_review_count=0,
            ))
        self.connection.execute(self.users.delete().where(self.users.c.id == 1))
        for table in self.tables:
            self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(table)).scalar_one(), 0)


if __name__ == "__main__":
    unittest.main()
