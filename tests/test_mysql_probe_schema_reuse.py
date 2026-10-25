"""Schema reuse for MySQL probes on a generated, disposable loopback schema.

Enable with FLAMA_MYSQL_PROBE_TESTS=1 (the mysql-contract CI job sets it).
The configured development schema is read only for its default collation.
"""

import os
import re
import secrets
import unittest

import pymysql
import sqlalchemy as sa

from app import create_audit_app
from app.settings import load_environment
from models import db
from models.deck import Deck
from models.user import User
from scripts.mysql_probe_db import (
    _connection_settings,
    _database_uri,
    _source_database_collation,
    reuse_generated_schema,
)

_PROBE_NAME = re.compile(r"^flama_schema_reuse_probe_[0-9]+_[a-f0-9]{12}$")


@unittest.skipUnless(os.getenv("FLAMA_MYSQL_PROBE_TESTS") == "1", "Opt-in local MySQL qualification")
class ProbeSchemaReuseMySQLTests(unittest.TestCase):
    def setUp(self):
        load_environment()
        settings = _connection_settings()
        if settings["host"] not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Schema reuse qualification requires loopback MySQL.")
        self.schema = f"flama_schema_reuse_probe_{os.getpid()}_{secrets.token_hex(6)}"
        if not _PROBE_NAME.fullmatch(self.schema) or self.schema == os.getenv("DB_NAME"):
            raise RuntimeError("Refusing a non-generated fixture schema.")
        admin = pymysql.connect(**settings)
        self.addCleanup(admin.close)
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (self.schema,))
            if cursor.fetchone():
                raise RuntimeError("Generated schema already exists; refusing reuse.")
            cursor.execute(f"CREATE DATABASE `{self.schema}` CHARACTER SET utf8mb4 COLLATE {collation}")

        def drop_generated_schema():
            if not _PROBE_NAME.fullmatch(self.schema) or self.schema == os.getenv("DB_NAME"):
                raise RuntimeError("Refusing non-fixture cleanup.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{self.schema}`")

        self.addCleanup(drop_generated_schema)
        self.app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, self.schema),
                                     "REDIS_URL": ""})
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.engine.dispose)
        self.addCleanup(db.session.remove)
        if db.engine.url.database != self.schema:
            raise RuntimeError("Fixture ORM target escaped the generated schema.")

    def _add_user_with_deck(self, name):
        user = User(username=name, email=f"{name}@example.invalid")
        db.session.add(user)
        db.session.flush()
        db.session.add(Deck(name=name, owner_user_id=user.id))
        db.session.commit()
        return user.id

    def _tables(self):
        return set(sa.inspect(db.engine).get_table_names())

    def test_reset_empties_rows_restarts_ids_and_keeps_tables(self):
        with reuse_generated_schema(self.schema) as counters:
            db.create_all()
            tables = self._tables()
            self.assertEqual(self._add_user_with_deck("first"), 1)
            self._add_user_with_deck("second")
            db.drop_all()
            self.assertEqual(counters, {"resets": 1, "rebuilds": 0, "tables_emptied": 2})
            self.assertEqual(self._tables(), tables)
            self.assertEqual(db.session.execute(sa.select(sa.func.count()).select_from(Deck)).scalar_one(), 0)
            db.create_all()
            # A fixture that names user 1 still finds it after a reset.
            self.assertEqual(self._add_user_with_deck("again"), 1)
            # Session-level FK checks are back on for the pooled connection.
            with db.engine.connect() as connection:
                self.assertEqual(connection.exec_driver_sql("SELECT @@SESSION.foreign_key_checks").scalar_one(), 1)

    def test_changed_schema_is_dropped_and_rebuilt(self):
        with reuse_generated_schema(self.schema) as counters:
            db.create_all()
            pristine = {column["name"] for column in sa.inspect(db.engine).get_columns("decks")}
            self._add_user_with_deck("ddl")
            with db.engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE decks ADD COLUMN probe_extra INT NULL")
            db.drop_all()
            self.assertEqual(counters["rebuilds"], 1)
            self.assertEqual(self._tables(), set())
            db.create_all()
            self.assertEqual({column["name"] for column in sa.inspect(db.engine).get_columns("decks")}, pristine)
            self.assertEqual(self._add_user_with_deck("rebuilt"), 1)
            db.drop_all()
            self.assertEqual(counters, {"resets": 1, "rebuilds": 1, "tables_emptied": 2})

    def test_other_targets_keep_the_real_drop_all(self):
        with reuse_generated_schema("flama_some_other_probe_schema") as counters:
            db.create_all()
            db.drop_all()
            self.assertEqual(self._tables(), set())
        sqlite_app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "REDIS_URL": ""})
        with reuse_generated_schema(self.schema) as sqlite_counters, sqlite_app.app_context():
            db.create_all()
            db.drop_all()
            self.assertEqual(sa.inspect(db.engine).get_table_names(), [])
            db.engine.dispose()
        self.assertEqual(counters, {"resets": 0, "rebuilds": 0, "tables_emptied": 0})
        self.assertEqual(sqlite_counters, {"resets": 0, "rebuilds": 0, "tables_emptied": 0})


if __name__ == "__main__":
    unittest.main()
