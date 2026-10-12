"""Read-only coverage and integrity audit before retiring CardProgress.

Run against local first, then the deployed database. Existing NOTE state is
authoritative: a different frozen CardProgress state never replaces it.
Credentials come from the environment/.env, or root Unix socket authentication;
no credential is accepted on the command line or included in the report.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import sqlalchemy as sa
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.study_authority_read_service import validate_consolidated_subject
from app.services.study_algorithm_registry import STATE_DECODERS
from app.services.study_progress_shadow_codec import state_document
from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress


ARCHIVE_CANDIDATES = (
    'vocabulary_column_preferences', 'study_progress_backfill_runs',
    'study_progress_backfill_checkpoints', 'study_progress_backfill_dispositions',
)
REQUIRED = (
    'users', 'notes', 'cards', 'card_progress', 'study_progress_subjects',
    'study_authority_enrollments', 'study_authority_storage_profile',
)


def _json_value(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, datetime):
        return value.isoformat(timespec='microseconds')
    raise TypeError(type(value).__name__)


def _hash_row(digest, row):
    digest.update(json.dumps(dict(row), sort_keys=True, separators=(',', ':'),
                             default=_json_value).encode('utf-8') + b'\n')


def _mapped_frozen_progress(raw, *, card_created_at):
    values = dict(raw)
    # Reflected MySQL TINYINT(1) yields 0/1 rather than the bools supplied by
    # the ORM Boolean columns. Preserve invalid/null values for strict mapping.
    for field in ('is_suspended', 'is_buried'):
        if type(values[field]) is int and values[field] in (0, 1):
            values[field] = bool(values[field])
    return map_card_progress(SimpleNamespace(**values), card_created_at=card_created_at,
                             card_order_key=str(values['card_id']))


def audit_connection(connection):
    """Read a caller-owned consistent snapshot; do not mutate or lock rows."""
    names = set(sa.inspect(connection).get_table_names())
    missing = sorted(set(REQUIRED) - names)
    if missing:
        return {'schema_version': 'legacy-progress-retirement.v1', 'status': 'BLOCK',
                'blockers': ['REQUIRED_TABLES_MISSING'], 'missing_tables': missing}
    metadata = sa.MetaData()
    tables = {name: sa.Table(name, metadata, autoload_with=connection, resolve_fks=False)
              for name in REQUIRED}
    users, notes, cards, old, subjects, enrollment, profile = (tables[n] for n in REQUIRED)
    modes = dict(connection.execute(sa.select(users.c.id, enrollment.c.mode_code).select_from(
        users.outerjoin(enrollment, enrollment.c.learner_user_id == users.c.id))).all())
    mode_counts = Counter(mode or 'UNENROLLED' for mode in modes.values())
    profiles = [dict(r) for r in connection.execute(sa.select(profile)).mappings()]
    consolidated = len(profiles) == 1 and profiles[0]['profile_code'] == 'CONSOLIDATED_V1'
    cutoff = profiles[0]['switched_at'] if consolidated else None
    blockers = []
    if not consolidated:
        blockers.append('PROFILE_NOT_CONSOLIDATED')
    elif cutoff is None:
        blockers.append('CUTOVER_TIMESTAMP_MISSING')
    if mode_counts['LEGACY']:
        blockers.append('LEGACY_LEARNERS')
    if mode_counts['UNENROLLED']:
        blockers.append('UNENROLLED_LEARNERS')
    if set(mode_counts) - {'NOTE', 'LEGACY', 'UNENROLLED'}:
        blockers.append('INVALID_ENROLLMENT_MODE')

    state_by_identity = {}
    new_digest = hashlib.sha256()
    states = Counter()
    problems = Counter()
    samples = []
    subject_count = 0
    for row in connection.execute(sa.select(subjects).order_by(subjects.c.id)).mappings():
        subject_count += 1
        _hash_row(new_digest, row)
        states[str(row['status_code'])] += 1
        try:
            key = (int(row['learner_user_id']), bytes(row['logical_note_key']).decode('utf-8'))
        except (UnicodeError, TypeError, ValueError):
            problems['INVALID_NOTE_IDENTITY'] += 1
            if len(samples) < 10:
                samples.append({'subject_id': int(row['id']), 'code': 'INVALID_NOTE_IDENTITY'})
            continue
        if key in state_by_identity:
            problems['DUPLICATE_NOTE_IDENTITY'] += 1
        state_by_identity[key] = row
        if row['state_payload'] is None:
            continue
        try:
            document = state_document(row['state_payload'])
            STATE_DECODERS.decode(
                algorithm_key=row['algorithm_key'], algorithm_version=row['algorithm_version'],
                state_schema_version=row['state_schema_version'], storage_codec=row['storage_codec'],
                payload=document.payload, expected_size=int(row['state_payload_size']),
                expected_hash=bytes(row['algorithm_state_hash']),
            )
            validate_consolidated_subject(
                card=SimpleNamespace(id='audit-only', note_id=key[1], created_at=row['created_at']),
                subject=SimpleNamespace(**row),
            )
        except (ValueError, TypeError, RuntimeError) as exc:
            code = str(getattr(exc, 'code', type(exc).__name__))
            problems[code] += 1
            if len(samples) < 10:
                samples.append({'subject_id': int(row['id']), 'code': code})

    counts = Counter()
    comparisons = Counter()
    mapping_failures = Counter()
    old_digest = hashlib.sha256()
    fanin = Counter()
    query = sa.select(old, cards.c.note_id.label('resolved_note_id'),
                      cards.c.created_at.label('card_created_at'),
                      notes.c.id.label('resolved_note_exists')).select_from(
        old.outerjoin(cards, cards.c.id == old.c.card_id).outerjoin(notes, notes.c.id == cards.c.note_id)
    ).order_by(old.c.id)
    old_columns = [column.name for column in old.columns]
    for row in connection.execute(query).mappings():
        raw = {name: row[name] for name in old_columns}
        _hash_row(old_digest, raw)
        counts['old_rows'] += 1
        learner = int(row['user_id'])
        note_id = row['resolved_note_id']
        if note_id is None or row['resolved_note_exists'] is None or learner not in modes:
            counts['unresolved_rows'] += 1
            continue
        key = (learner, str(note_id))
        fanin[key] += 1
        if modes[learner] != 'NOTE':
            counts['rows_on_legacy_or_unenrolled_learner'] += 1
            continue
        target = state_by_identity.get(key)
        if target is None:
            counts['missing_subject_rows'] += 1
            continue
        if target['status_code'] == 'TOMBSTONED':
            counts['tombstoned_rows'] += 1
            continue
        if target['state_payload'] is None:
            counts['missing_current_state_rows'] += 1
            continue
        if target['live_note_id'] != note_id:
            counts['target_note_identity_mismatch_rows'] += 1
            continue
        counts['covered_rows'] += 1
        if cutoff is not None and row['updated_at'] >= cutoff:
            counts['old_rows_written_since_cutover'] += 1
        mapped = _mapped_frozen_progress(raw, card_created_at=row['card_created_at'])
        if not isinstance(mapped, MappedCardProgress):
            comparisons['frozen_source_mapping_failure'] += 1
            mapping_failures[mapped.code] += 1
        elif bytes(target['semantic_state_hash']) == mapped.semantic_state_hash:
            comparisons['same_semantic_state'] += 1
        else:
            # Reviews, reset, algorithm switches and import can legitimately
            # advance NOTE state after the old projection was frozen.
            comparisons['different_current_state_preserved'] += 1

    for key, code in (
        ('unresolved_rows', 'UNRESOLVED_LEGACY_PROGRESS'),
        ('rows_on_legacy_or_unenrolled_learner', 'PROGRESS_NOT_ON_NOTE_AUTHORITY'),
        ('missing_subject_rows', 'NOTE_PROGRESS_COVERAGE_GAP'),
        ('missing_current_state_rows', 'NOTE_PROGRESS_COVERAGE_GAP'),
        ('target_note_identity_mismatch_rows', 'NOTE_PROGRESS_IDENTITY_MISMATCH'),
        ('tombstoned_rows', 'TOMBSTONE_REQUIRES_HISTORICAL_DISPOSITION'),
        ('old_rows_written_since_cutover', 'LEGACY_WRITES_AFTER_CUTOVER'),
    ):
        if counts[key]:
            blockers.append(code)
    if problems:
        blockers.append('INVALID_NOTE_STATE')
    if mapping_failures:
        blockers.append('FROZEN_PROGRESS_NOT_MAPPABLE')
    archive_counts = {name: int(connection.execute(sa.text('SELECT COUNT(*) FROM ' + name)).scalar_one())
                      if name in names else None for name in ARCHIVE_CANDIDATES}
    return {
        'schema_version': 'legacy-progress-retirement.v1',
        'status': 'BLOCK' if blockers else 'DATA_READY',
        'blockers': sorted(set(blockers)),
        'authority_modes': dict(sorted(mode_counts.items())), 'storage_profiles': profiles,
        'progress_coverage': {key: counts[key] for key in (
            'old_rows', 'covered_rows', 'unresolved_rows', 'rows_on_legacy_or_unenrolled_learner',
            'missing_subject_rows', 'missing_current_state_rows', 'target_note_identity_mismatch_rows',
            'tombstoned_rows', 'old_rows_written_since_cutover')},
        'current_subjects': subject_count, 'current_subject_statuses': dict(states),
        'current_state_problems': dict(problems), 'problem_samples': samples,
        'frozen_state_comparison': dict(comparisons),
        'frozen_mapping_failure_codes': dict(mapping_failures),
        'fanin_groups': sum(count > 1 for count in fanin.values()),
        'archive_candidate_rows': archive_counts,
        'snapshot_sha256': {'card_progress': old_digest.hexdigest(),
                            'study_progress_subjects': new_digest.hexdigest()},
        'meaning': 'DATA_READY verifies coverage/current state; it does not authorize dropping runtime consumers.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--mysql-socket', help='Use local root socket authentication instead of .env.')
    parser.add_argument('--database', help='Required with --mysql-socket.')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.mysql_socket:
        if not args.database:
            parser.error('--database is required with --mysql-socket')
        uri = sa.URL.create('mysql+pymysql', username='root', database=args.database,
                            query={'unix_socket': args.mysql_socket, 'charset': 'utf8mb4'})
    else:
        load_dotenv(args.env_file)
        from app.settings import build_database_uri_from_env
        uri = sa.make_url(os.environ.get('SQLALCHEMY_DATABASE_URI') or build_database_uri_from_env())
    engine = sa.create_engine(uri, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            if connection.dialect.name == 'mysql':
                connection.exec_driver_sql('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                connection.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
                connection.commit()
                connection.exec_driver_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            elif connection.dialect.name == 'sqlite':
                connection.exec_driver_sql('PRAGMA query_only=ON')
            else:
                parser.error('Only MySQL and SQLite are supported.')
            report = audit_connection(connection)
            report['observed_at_utc'] = datetime.now(timezone.utc).isoformat()
            report['database'] = {'host': uri.host, 'port': uri.port, 'name': uri.database,
                                  'dialect': connection.dialect.name}
            if connection.dialect.name == 'mysql':
                report['database']['version'] = connection.execute(sa.text('SELECT VERSION()')).scalar_one()
            report['mode'] = 'read-only consistent snapshot; no app startup'
            connection.rollback()
    finally:
        engine.dispose()
    rendered = json.dumps(report, sort_keys=True, indent=2, default=_json_value)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    return 0 if report['status'] == 'DATA_READY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
