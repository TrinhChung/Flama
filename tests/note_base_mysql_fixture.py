"""Disposable local MySQL fixture for Published Base integration tests.

Opt in with FLAMA_MYSQL_TESTS=1. Every class owns a generated database; the
configured application database is used only to read its default collation.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
import tempfile
import unittest

from dotenv import load_dotenv
import pymysql

from app import create_audit_app
from models import db
from scripts.mysql_probe_db import (
    _connection_settings, _database_uri, _empty_tables, _source_database_collation,
)

ROOT = Path(__file__).resolve().parents[1]
PROBE_NAME = re.compile(r"^flama_note_base_test_[0-9]+_[a-f0-9]{12}$")


class NoteBaseMySQLTestCase(unittest.TestCase):
    APP_CONFIG = {}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if os.getenv("FLAMA_MYSQL_TESTS") != "1":
            raise unittest.SkipTest("Set FLAMA_MYSQL_TESTS=1 for disposable local MySQL tests.")
        load_dotenv(ROOT / ".env")
        settings = _connection_settings()
        cls.database_name = f"flama_note_base_test_{os.getpid()}_{secrets.token_hex(6)}"
        if settings["host"] not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Published Base tests require loopback MySQL.")
        if not PROBE_NAME.fullmatch(cls.database_name) or cls.database_name == os.getenv("DB_NAME"):
            raise RuntimeError("Refusing an application or non-generated test database.")
        cls.admin = pymysql.connect(**settings)
        cls.addClassCleanup(cls.admin.close)
        with cls.admin.cursor() as cursor:
            collation = _source_database_collation(cls.admin)
            cursor.execute(f"CREATE DATABASE `{cls.database_name}` CHARACTER SET utf8mb4 COLLATE {collation}")
        cls.addClassCleanup(cls._drop_generated_database)
        cls.media_directory = tempfile.TemporaryDirectory(prefix="flama-note-base-")
        cls.addClassCleanup(cls.media_directory.cleanup)
        cls.app = create_audit_app({
            "TESTING": True,
            "SECRET_KEY": "note-base-test-only",
            "SQLALCHEMY_DATABASE_URI": _database_uri(settings, cls.database_name),
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
            "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False,
            "MEDIA_STORAGE_ROOT": cls.media_directory.name,
            "NOTE_PUBLISHED_BASE_ENABLED": False,
            **cls.APP_CONFIG,
        })
        with cls.app.app_context():
            if db.engine.dialect.name != "mysql" or db.engine.url.database != cls.database_name:
                raise RuntimeError("Test engine is not bound to its generated MySQL schema.")
            db.create_all()
            with db.engine.connect() as connection:
                cls.auto_increment_tables = {row[0] for row in connection.exec_driver_sql(
                    "SELECT TABLE_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND EXTRA LIKE '%%auto_increment%%'"
                )}

    @classmethod
    def _drop_generated_database(cls):
        if hasattr(cls, "app"):
            with cls.app.app_context():
                db.session.remove()
                db.engine.dispose()
        if not PROBE_NAME.fullmatch(cls.database_name) or cls.database_name == os.getenv("DB_NAME"):
            raise RuntimeError("Refusing cleanup of a non-generated database.")
        with cls.admin.cursor() as cursor:
            cursor.execute(f"DROP DATABASE `{cls.database_name}`")

    def setUp(self):
        super().setUp()
        self.context = self.app.app_context()
        self.context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            db.session.remove()
            if db.engine.url.database != self.database_name:
                raise RuntimeError("Refusing cleanup outside the generated database.")
            with db.engine.connect() as connection:
                _empty_tables(connection, self.auto_increment_tables)
        finally:
            self.context.pop()
            super().tearDown()


MySQLTestCase = NoteBaseMySQLTestCase
