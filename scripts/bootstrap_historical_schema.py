"""Explicit pre-39 bootstrap for an isolated fresh database, then use db upgrade.

The historical Alembic root adds payments to a db.create_all core schema.
Retired runtime models no longer recreate that baseline. This command restores
the frozen empty historical schema independently of current app metadata.
It never repairs an existing database or runs during application startup.
"""

import argparse
from pathlib import Path
import sys

import sqlalchemy as sa
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from migrations.historical_bootstrap_core import HISTORICAL_BOOTSTRAP_METADATA, SOURCE_COMMIT, bootstrap_empty_schema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--database", help="Explicit isolated MySQL database name; it must already exist and be empty")
    destination.add_argument("--sqlite-path", type=Path, help="New SQLite file for a fresh-chain rehearsal")
    parser.add_argument("--mysql-socket", help="Local root authentication on an explicitly named MySQL schema")
    args = parser.parse_args()
    if args.sqlite_path:
        if args.mysql_socket or args.sqlite_path.exists():
            parser.error("SQLite rehearsal requires a new file and no MySQL socket option")
        uri = sa.URL.create("sqlite", database=str(args.sqlite_path.resolve()))
    else:
        settings = dotenv_values(args.env_file)
        source_name = settings.get("DB_NAME", "nihongo")
        if args.database in (source_name, "nihongo", "flama", "mysql", "sys", "information_schema", "performance_schema"):
            parser.error("Historical bootstrap requires an isolated database name, distinct from application/system databases")
        if args.mysql_socket:
            uri = sa.URL.create("mysql+pymysql", username="root", database=args.database,
                                query={"unix_socket": args.mysql_socket, "charset": "utf8mb4"})
        else:
            host = settings.get("DB_HOST", "localhost")
            if host not in ("localhost", "127.0.0.1", "::1"):
                parser.error("Fresh-schema rehearsal must target loopback MySQL or an explicit local socket")
            uri = sa.URL.create("mysql+pymysql", username=settings.get("DB_USER", "root"),
                                password=settings.get("DB_PASSWORD", ""), host=host,
                                port=int(settings.get("DB_PORT", "3306")), database=args.database,
                                query={"charset": "utf8mb4"})
    engine = sa.create_engine(uri)
    with engine.begin() as connection:
        bootstrap_empty_schema(connection)
    engine.dispose()
    print(f"Created {len(HISTORICAL_BOOTSTRAP_METADATA.tables)} historical empty tables from {SOURCE_COMMIT}; now run Flask db upgrade on this isolated database.")


if __name__ == "__main__":
    main()
