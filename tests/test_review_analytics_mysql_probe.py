"""Prevent a local-dump probe from connecting remotely or deleting other users."""

from pathlib import Path
import tempfile
import unittest

import sqlalchemy as sa

from scripts.probe_review_analytics_mysql import assert_fixture_ownership, local_url


class ReviewAnalyticsMysqlProbeGuardTests(unittest.TestCase):
    def _url(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(text, encoding="utf-8")
            return local_url(path)

    def test_explicit_local_configuration_preserves_escaped_credentials(self):
        url = self._url("DB_USER=fixture\nDB_PASSWORD='local@fake:password'\nDB_HOST=127.0.0.1\nDB_PORT=3306\nDB_NAME=nihongo\n")
        self.assertEqual((url.host, url.database, url.password), ("127.0.0.1", "nihongo", "local@fake:password"))

    def test_remote_and_non_mysql_configuration_is_refused(self):
        for uri in ("mysql+pymysql://fixture:fake@prod.example/nihongo", "sqlite:///nihongo.db", "mysql+pymysql://fixture:fake@127.0.0.1/"):
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                self._url(f"SQLALCHEMY_DATABASE_URI={uri}\n")

    def test_cleanup_requires_all_captured_ids_and_exact_emails(self):
        engine = sa.create_engine("sqlite:///:memory:")
        metadata = sa.MetaData()
        users = sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("email", sa.String(255)))
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(users.insert(), [{"id": 1, "email": "existing@example.test"}, {"id": 9, "email": "fixture@example.invalid"}])
            self.assertEqual(assert_fixture_ownership(connection, {9: "fixture@example.invalid"}), [9])
            for inventory in ({1: "existing@example.test"}, {9: "wrong@example.invalid"}, {9: "fixture@example.invalid", 10: "missing@example.invalid"}, {}):
                with self.subTest(inventory=inventory), self.assertRaises(RuntimeError):
                    assert_fixture_ownership(connection, inventory)
            self.assertEqual(connection.execute(sa.select(sa.func.count()).select_from(users)).scalar_one(), 2)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
