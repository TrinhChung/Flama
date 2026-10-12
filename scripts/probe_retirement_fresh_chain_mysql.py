"""Qualify the complete retirement chain on a generated local MySQL schema.

The configured DB is read only for its default collation. Only an unpredictable
probe-owned schema is created; a failed schema is retained for diagnosis.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa
from flask_migrate import upgrade

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_audit_app
from migrations.historical_bootstrap_core import bootstrap_empty_schema
from models import db
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

PROBE_NAME = re.compile(r'^flama_retirement_fresh_probe_[0-9]+_[a-f0-9]{12}$')
RETIRED = {'cards','card_progress','vocabulary_column_preferences','study_progress_backfill_runs',
           'study_progress_backfill_checkpoints','study_progress_backfill_dispositions'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT/'.env')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    settings = _connection_settings()
    if settings['host'] not in ('localhost','127.0.0.1','::1'):
        raise ValueError('Retirement fresh-chain probe requires loopback MySQL.')
    target = f'flama_retirement_fresh_probe_{os.getpid()}_{secrets.token_hex(6)}'
    if not PROBE_NAME.fullmatch(target) or target == os.getenv('DB_NAME'):
        raise ValueError('Unsafe generated probe name.')
    admin = pymysql.connect(**settings)
    created = False
    success = False
    started = time.monotonic()
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute('SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s', (target,))
            if cursor.fetchone():
                raise RuntimeError('Generated target exists; never overwrite an existing schema.')
            cursor.execute(f'CREATE DATABASE `{target}` CHARACTER SET utf8mb4 COLLATE {collation}')
            created = True
        app = create_audit_app({'TESTING':True, 'SQLALCHEMY_DATABASE_URI':_database_uri(settings,target),
            'REDIS_URL':'', 'DECK_COUNT_WRITE_ENABLED':False, 'REVIEW_ANALYTICS_WRITE_ENABLED':False})
        with app.app_context():
            try:
                with db.engine.begin() as connection:
                    if sa.inspect(connection).get_table_names():
                        raise RuntimeError('Fresh probe schema is not empty.')
                    bootstrap_empty_schema(connection)
                upgrade(directory=str(ROOT/'migrations'))
                tables = set(sa.inspect(db.engine).get_table_names())
                head = db.session.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one()
                if head != '20261012_000062' or tables & RETIRED:
                    raise RuntimeError('Retirement head/table contract failed.')
                if tables != set(db.metadata.tables) | {'alembic_version'}:
                    raise RuntimeError('Fresh migration schema differs from current runtime metadata.')
                users = db.session.execute(sa.text('SELECT COUNT(*) FROM users')).scalar_one()
                subjects = db.session.execute(sa.text('SELECT COUNT(*) FROM study_progress_subjects')).scalar_one()
                if users or subjects:
                    raise RuntimeError('Fresh chain unexpectedly seeded learner data.')
                report = {'database':target, 'head':head, 'mysql_version':db.session.execute(sa.text('SELECT VERSION()')).scalar_one(),
                    'runtime_tables':len(db.metadata.tables), 'physical_tables':len(tables), 'users':users, 'subjects':subjects,
                    'retired_tables_present':sorted(tables & RETIRED), 'source_database_writes':0,
                    'elapsed_seconds':round(time.monotonic()-started,3), 'result':'PASS'}
                if args.output:
                    args.output.parent.mkdir(parents=True,exist_ok=True)
                    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
                print(json.dumps(report))
                success = True
            finally:
                db.session.remove()
                db.engine.dispose()
    finally:
        if success and created:
            # The only DROP target is the same generated literal created here.
            if not PROBE_NAME.fullmatch(target) or target == os.getenv('DB_NAME'):
                raise RuntimeError('Unsafe cleanup target.')
            with admin.cursor() as cursor:
                cursor.execute(f'DROP DATABASE `{target}`')
        elif created:
            print(f'Failed fresh-chain evidence retained in isolated schema {target}', file=sys.stderr)
        admin.close()


if __name__ == '__main__':
    main()
