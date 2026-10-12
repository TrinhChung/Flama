"""Archive retired tables and verify evidence in an isolated database.

Examples:
  python scripts/archive_retired_tables.py archive --output C:/backup/backfill.json
  python scripts/archive_retired_tables.py verify-restore --bundle C:/backup/backfill.json --restore-sqlite C:/backup/restore.sqlite
  python scripts/archive_retired_tables.py verify-restore --bundle C:/backup/backfill.json --restore-database nihongo_retirement_restore

MySQL contraction requires a MySQL restore marker, in addition to a complete
backup/restore deployment rehearsal. Database credentials are read from the
env file and never printed or included in bundles.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import sqlalchemy as sa
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from migrations.retirement_archive import DEAD_MODEL_TABLES, verify_restore, write_bundle


def _engine(args, database=None):
    settings = dotenv_values(args.env_file)
    if args.mysql_socket:
        url = sa.URL.create("mysql+pymysql", username="root", database=database or args.database,
                            query={"unix_socket": args.mysql_socket, "charset": "utf8mb4"})
    else:
        uri = settings.get("DATABASE_URL") or settings.get("SQLALCHEMY_DATABASE_URI")
        if uri:
            url = sa.make_url(uri)
        else:
            url = sa.URL.create("mysql+pymysql", username=settings.get("DB_USER", "root"),
                                password=settings.get("DB_PASSWORD", ""), host=settings.get("DB_HOST", "localhost"),
                                port=int(settings.get("DB_PORT", "3306")), database=args.database or settings.get("DB_NAME", "nihongo"),
                                query={"charset": "utf8mb4"})
        if database or args.database:
            url = url.set(database=database or args.database)
    return sa.create_engine(url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--mysql-socket")
    parser.add_argument("--database")
    commands = parser.add_subparsers(dest="command", required=True)
    archive = commands.add_parser("archive")
    archive.add_argument("--output", type=Path, required=True)
    archive.add_argument("--tables", nargs="+", default=list(DEAD_MODEL_TABLES))
    restore = commands.add_parser("verify-restore")
    restore.add_argument("--bundle", type=Path, required=True)
    destination = restore.add_mutually_exclusive_group(required=True)
    destination.add_argument("--restore-sqlite", type=Path)
    destination.add_argument("--restore-database")
    args = parser.parse_args()
    if args.command == "archive":
        engine = _engine(args)
        with engine.connect() as connection:
            if engine.dialect.name == "mysql":
                connection.exec_driver_sql("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                connection.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
                connection.commit()
                connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            elif engine.dialect.name == "sqlite":
                connection.exec_driver_sql("PRAGMA query_only=ON")
            bundle = write_bundle(connection, args.output, args.tables)
            connection.rollback()
        print(f"Archived {len(bundle['tables'])} tables; SHA256={bundle['bundle_sha256']}")
    else:
        if args.restore_sqlite:
            if args.restore_sqlite.exists():
                raise RuntimeError("Restore SQLite file must not already exist")
            engine = sa.create_engine(sa.URL.create("sqlite", database=str(args.restore_sqlite)))
        else:
            engine = _engine(args, database=args.restore_database)
        with engine.connect() as connection:
            result = verify_restore(connection, args.bundle)
        print(f"Restore verified on {result['dialect']}; SHA256={result['bundle_sha256']}")
    engine.dispose()


if __name__ == "__main__":
    main()
