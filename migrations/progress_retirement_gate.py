"""Frozen, model-independent gates for contracting the old progress table."""

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path

import sqlalchemy as sa

AUDIT_ENV = 'FLAMA_PROGRESS_RETIREMENT_AUDIT'


def _json_value(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, datetime):
        return value.isoformat(timespec='microseconds')
    raise TypeError(type(value).__name__)


def snapshot_sha256(connection, name):
    table = sa.Table(name, sa.MetaData(), autoload_with=connection, resolve_fks=False)
    digest = hashlib.sha256()
    count = 0
    for row in connection.execute(sa.select(table).order_by(*table.primary_key.columns)).mappings():
        digest.update(json.dumps(dict(row), sort_keys=True, separators=(',', ':'),
                                 default=_json_value).encode('utf-8') + b'\n')
        count += 1
    return digest.hexdigest(), count


def assert_note_authority(connection):
    metadata = sa.MetaData()
    users, enrollment, profiles = [sa.Table(name, metadata, autoload_with=connection,
                                           resolve_fks=False) for name in (
        'users', 'study_authority_enrollments', 'study_authority_storage_profile')]
    user_count = int(connection.execute(sa.select(sa.func.count()).select_from(users)).scalar_one())
    if not user_count:
        return False
    incompatible = connection.execute(sa.select(sa.func.count()).select_from(
        users.outerjoin(enrollment, enrollment.c.learner_user_id == users.c.id)
    ).where(sa.or_(enrollment.c.mode_code.is_(None), enrollment.c.mode_code != 'NOTE'))).scalar_one()
    profile = connection.execute(sa.select(profiles)).mappings().all()
    if incompatible or len(profile) != 1 or profile[0]['profile_code'] != 'CONSOLIDATED_V1' or profile[0]['switched_at'] is None:
        raise RuntimeError('Legacy or unenrolled learners/storage profile prevent progress retirement')
    return True


def assert_progress_audit_matches(connection, *, audit_path=None):
    path = audit_path or os.environ.get(AUDIT_ENV)
    if not path:
        raise RuntimeError(f'Populated progress retirement requires a fresh read-only audit; set {AUDIT_ENV}')
    report = json.loads(Path(path).read_text(encoding='utf-8'))
    coverage = report.get('progress_coverage', {})
    if (report.get('schema_version') != 'legacy-progress-retirement.v1'
            or report.get('status') != 'DATA_READY' or report.get('blockers') != []
            or report.get('current_state_problems') != {}
            or report.get('frozen_mapping_failure_codes') != {}
            or coverage.get('old_rows') != coverage.get('covered_rows')
            or any(value for key, value in coverage.items() if key not in {'old_rows', 'covered_rows'})):
        raise RuntimeError('Progress retirement audit does not prove complete valid NOTE coverage')
    assert_note_authority(connection)
    profile_table = sa.Table('study_authority_storage_profile', sa.MetaData(),
                             autoload_with=connection, resolve_fks=False)
    profiles = [dict(row) for row in connection.execute(sa.select(profile_table)).mappings()]
    normalized_profiles = json.loads(json.dumps(profiles, default=_json_value))
    if report.get('storage_profiles') != normalized_profiles:
        raise RuntimeError('Storage profile changed since the progress retirement audit')
    for table, count_key in [('card_progress', 'old_rows'), ('study_progress_subjects', 'current_subjects')]:
        digest, count = snapshot_sha256(connection, table)
        expected_count = coverage.get(count_key) if table == 'card_progress' else report.get(count_key)
        if digest != report.get('snapshot_sha256', {}).get(table) or count != expected_count:
            raise RuntimeError(f'Live {table} changed since the progress retirement audit')


def initialize_empty_note_profile(connection):
    """An empty historical bootstrap has no learner state to migrate."""
    users = sa.Table('users', sa.MetaData(), autoload_with=connection, resolve_fks=False)
    subjects = sa.Table('study_progress_subjects', sa.MetaData(), autoload_with=connection, resolve_fks=False)
    if (connection.execute(sa.select(sa.func.count()).select_from(users)).scalar_one()
            or connection.execute(sa.select(sa.func.count()).select_from(subjects)).scalar_one()):
        return
    table = sa.Table('study_authority_storage_profile', sa.MetaData(), autoload_with=connection, resolve_fks=False)
    now = datetime.utcnow()
    existing = connection.execute(sa.select(table)).mappings().all()
    if not existing:
        connection.execute(table.insert().values(id=1, profile_code='CONSOLIDATED_V1', epoch=1,
                                                switched_at=now, created_at=now, updated_at=now))
    elif len(existing) == 1 and (existing[0]['profile_code'] != 'CONSOLIDATED_V1'
                                 or existing[0]['switched_at'] is None):
        connection.execute(table.update().where(table.c.id == 1).values(
            profile_code='CONSOLIDATED_V1', epoch=int(existing[0]['epoch']) + 1,
            switched_at=now, updated_at=now))
