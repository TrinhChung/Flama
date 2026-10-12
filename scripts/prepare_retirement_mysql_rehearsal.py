"""Back up local MySQL and restore it into new, isolated retirement schemas.

This does not migrate or alter the source database. Existing target schemas
and backup files are refused. Credentials use a temporary MySQL options file,
never command arguments, output or the backup manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.archive_retired_tables import _engine

SCHEMAS = (
    'nihongo_retirement_rehearsal_20261012',
    'nihongo_retirement_archive_restore_20261012',
    'nihongo_fresh_retirement_20261012',
)


def _option(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--mysql-bin', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--schema-suffix', default='', help='Use fresh isolated schemas for a later rehearsal.')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_]{0,12}', args.schema_suffix):
        parser.error('--schema-suffix must contain at most 12 letters, digits or underscores')
    schemas = tuple(name + args.schema_suffix for name in SCHEMAS)
    args.mysql_socket = None
    args.database = None
    engine = _engine(args)
    uri = engine.url
    if uri.host not in {'localhost', '127.0.0.1', '::1'} or engine.dialect.name != 'mysql':
        raise RuntimeError('Rehearsal source must be local MySQL')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    backup = output / 'before-retirement.sql'
    manifest = output / 'prepare-manifest.json'
    if backup.exists() or manifest.exists():
        raise RuntimeError('Refusing to overwrite rehearsal backup/evidence')
    with engine.connect() as connection:
        for name in schemas:
            exists = connection.execute(sa.text(
                'SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=:name'
            ), {'name': name}).scalar_one()
            if exists:
                raise RuntimeError(f'Rehearsal destination already exists: {name}')
        # Restoring routines/events can retain explicit source-schema names.
        # Such objects need manual review instead of executing them in a clone.
        for view, key in [('TRIGGERS', 'TRIGGER_SCHEMA'), ('EVENTS', 'EVENT_SCHEMA'),
                          ('ROUTINES', 'ROUTINE_SCHEMA'), ('VIEWS', 'TABLE_SCHEMA')]:
            count = connection.execute(sa.text(
                f'SELECT COUNT(*) FROM information_schema.{view} WHERE {key}=:name'
            ), {'name': uri.database}).scalar_one()
            if count:
                raise RuntimeError(f'Source has {view}; review isolation before restoring')
        names = sorted(sa.inspect(connection).get_table_names())
        source_counts = {name: int(connection.exec_driver_sql(
            f'SELECT COUNT(*) FROM {connection.dialect.identifier_preparer.quote(name)}'
        ).scalar_one()) for name in names}
        version = connection.exec_driver_sql('SELECT VERSION()').scalar_one()
    options_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.cnf', delete=False) as settings:
            options_path = Path(settings.name)
            settings.write('[client]\n')
            for key, value in {'user': uri.username, 'password': uri.password or '',
                               'host': uri.host, 'port': uri.port or 3306}.items():
                settings.write(f'{key}={_option(value)}\n')
        defaults = '--defaults-extra-file=' + str(options_path)
        with backup.open('xb') as destination:
            subprocess.run([str(args.mysql_bin / 'mysqldump.exe'), defaults,
                            '--single-transaction', '--skip-lock-tables', '--skip-add-locks',
                            '--no-tablespaces', '--hex-blob', '--set-gtid-purged=OFF',
                            '--default-character-set=utf8mb4', uri.database],
                           stdout=destination, stderr=subprocess.PIPE, check=True, timeout=300)
        print('Backup saved; preparing isolated schemas', flush=True)
        server = sa.create_engine(uri.set(database=None))
        try:
            with server.connect() as connection:
                for name in schemas:
                    connection.exec_driver_sql(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        finally:
            server.dispose()
        with backup.open('rb') as source:
            subprocess.run([str(args.mysql_bin / 'mysql.exe'), defaults,
                            '--default-character-set=utf8mb4', schemas[0]],
                           stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           check=True, timeout=300)
        restored = sa.create_engine(uri.set(database=schemas[0]))
        try:
            with restored.connect() as connection:
                actual = {name: int(connection.exec_driver_sql(
                    f'SELECT COUNT(*) FROM {connection.dialect.identifier_preparer.quote(name)}'
                ).scalar_one()) for name in sorted(sa.inspect(connection).get_table_names())}
            if actual != source_counts:
                raise RuntimeError('Source/restored table inventory or row counts differ')
        finally:
            restored.dispose()
        digest = hashlib.file_digest(backup.open('rb'), 'sha256').hexdigest()
        report = {'source_database': uri.database, 'mysql_version': version,
                  'backup_file': str(backup), 'backup_bytes': backup.stat().st_size,
                  'backup_sha256': digest, 'schemas': list(schemas),
                  'table_counts': source_counts, 'restore_row_counts_match': True}
        manifest.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(f'Full backup restore PASS: {len(names)} tables, SHA256={digest}', flush=True)
    finally:
        if options_path is not None:
            options_path.unlink(missing_ok=True)
        engine.dispose()


if __name__ == '__main__':
    main()
