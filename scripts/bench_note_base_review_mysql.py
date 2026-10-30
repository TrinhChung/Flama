"""Sequential latency and process-isolated load on a disposable local MySQL DB.

Does not change server settings, indexes, or the configured application DB.
Global counters include other work on the shared host. Synthetic Study measures
page reads only; these samples are not a production capacity qualification.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sys
from time import perf_counter, process_time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import bindparam, event, insert, select

from scripts import bench_note_published_base_mysql as baseline
from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from models import db
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.note_draft import NoteDraft
from app.services import browse_note_service, deck_release_service
from app.services.note_base_context import note_author_view

baseline.COUNTERS = (*baseline.COUNTERS, 'Innodb_row_lock_time', 'Innodb_row_lock_waits')


def _request(audience, operation, seed):
    if audience == 'learner':
        return baseline._request(operation, seed['contexts'][0])
    args = {'deck_id': str(seed['source_root_id']), 'per_page': '20',
        'sort_by': 'word' if operation == 'sort' else 'due'}
    if operation == 'search':
        args['q'] = 'word'
    with note_author_view(seed['owner_id']):
        value = browse_note_service.list_notes(user_id=seed['owner_id'], admin_mode=False,
            timezone_name='UTC', query_args=args)
    value = {'total': value['total'], 'items': [(row['note_id'], row['word'], row['reading'], row['meaning'])
        for row in value['items']]}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _measure(app, operation, *, admin=None, explain=False, sql_pages=False):
    """Separate DBAPI wall time, process CPU, and wall outside DBAPI calls."""
    statements = []
    first_lock = [None]
    statement_pages = []
    def before(_connection, _cursor, sql, parameters, context, many):
        if sql_pages and admin:
            context._note_bench_pages_before = baseline._status(admin)
        context._note_bench_started = perf_counter()
        if first_lock[0] is None and 'FOR UPDATE' in sql.upper():
            first_lock[0] = context._note_bench_started
    def after(_connection, _cursor, sql, parameters, context, many):
        elapsed = perf_counter() - context._note_bench_started
        statements.append((elapsed, sql, parameters, many))
        if sql_pages and admin:
            status = baseline._status(admin)
            statement_pages.append({'dbapi_wall_ms': elapsed * 1000, 'sql': sql,
                'mysql_global_counter_delta': {key: status.get(key, 0) - context._note_bench_pages_before.get(key, 0)
                    for key in baseline.COUNTERS}})
    with app.app_context():
        engine = db.engine
        db.session.remove()
        event.listen(engine, 'before_cursor_execute', before)
        event.listen(engine, 'after_cursor_execute', after)
        counters_before = baseline._status(admin) if admin else None
        cpu = process_time()
        started = perf_counter()
        try:
            with app.test_request_context('/benchmark/note-base-review'):
                signature = operation()
                db.session.rollback()
                db.session.remove()
        finally:
            finished = perf_counter()
            cpu = process_time() - cpu
            event.remove(engine, 'before_cursor_execute', before)
            event.remove(engine, 'after_cursor_execute', after)
            db.session.remove()
        counters_after = baseline._status(admin) if admin else None
        sql_time = sum(row[0] for row in statements)
        result = {'elapsed_ms': (finished - started) * 1000,
            'dbapi_wall_ms': sql_time * 1000,
            'outside_dbapi_wall_ms': (finished - started - sql_time) * 1000,
            'python_cpu_ms': cpu * 1000, 'sql_statements': len(statements), 'signature': signature}
        if counters_before is not None:
            result['mysql_global_counter_delta'] = {key: counters_after.get(key, 0) - counters_before.get(key, 0)
                for key in baseline.COUNTERS}
        if sql_pages:
            result['per_statement'] = statement_pages
            result['sql_pages_instrumented'] = True
        if first_lock[0] is not None:
            result['first_lock_query_to_return_upper_bound_ms'] = (finished - first_lock[0]) * 1000
        if explain:
            result['slowest_selects'] = []
            selects = sorted((row for row in statements if row[1].lstrip().upper().startswith(('SELECT', 'WITH'))
                and not row[3]), reverse=True, key=lambda row: row[0])[:3]
            # SQL/parameters contain synthetic fixture data only. EXPLAIN does
            # not execute the slow SELECT again or mutate application data.
            with engine.connect() as connection:
                for seconds, sql, parameters, _many in selects:
                    plan = connection.exec_driver_sql('EXPLAIN FORMAT=JSON ' + sql, parameters).scalar_one()
                    result['slowest_selects'].append({'dbapi_ms': seconds * 1000, 'sql': sql,
                        'parameters': parameters, 'explain': json.loads(plan)})
        return result


def _drafts(seed, count, label):
    with db.engine.begin() as connection:
        connection.execute(NoteDraft.__table__.delete())
        rows = [{'note_id': note_id, 'field_values_by_id': {
            seed['field_id']: {'op': 'set', 'value': f'{label}-word-{note_id[-6:]}'}}, 'updated_at': datetime.utcnow()}
            for note_id in seed['note_ids'][:count]]
        for offset in range(0, len(rows), 500):
            connection.execute(insert(NoteDraft.__table__), rows[offset:offset + 500])
        connection.execute(DeckMarketplaceItem.__table__.update().where(
            DeckMarketplaceItem.id == seed['item_id']).values(working_revision=DeckMarketplaceItem.working_revision + 1))
    db.session.remove()
    return rows


def _author_mode(app, originals, drafts, enabled):
    app.config['NOTE_PUBLISHED_BASE_ENABLED'] = enabled
    rows = []
    for draft in drafts:
        original = originals[draft['note_id']]
        values = dict(original['field_values_by_id'])
        if not enabled:
            values.update({identity: change['value'] for identity, change in draft['field_values_by_id'].items()})
        rows.append({'note_key': draft['note_id'], 'values_doc': values,
            'edited_at': original['updated_at'] if enabled else draft['updated_at']})
    if rows:
        with db.engine.begin() as connection:
            connection.execute(Note.__table__.update().where(Note.id == bindparam('note_key')).values(
                field_values_by_id=bindparam('values_doc'), updated_at=bindparam('edited_at')), rows)
    db.session.remove()


def _publish(seed, count):
    item = db.session.get(DeckMarketplaceItem, seed['item_id'])
    request = dict(deck_item_id=item.id, user_id=seed['owner_id'], version_label=f'review-{count}',
        changelog='Disposable benchmark only', expected_current_release_id=item.current_release_id,
        expected_working_revision=item.working_revision, idempotency_key=f'review-{count}')
    result = deck_release_service.publish_release_and_commit(**request)
    return str(result.release.id)


def _process_load(config, seed, iterations):
    from app import create_audit_app
    app = create_audit_app(config)
    try:
        return [_measure(app, lambda: _request('author', operation, seed))
            for _ in range(iterations) for operation in ('browse', 'search', 'sort')]
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


def run(args):
    os.environ['FLAMA_MYSQL_TESTS'] = '1'
    # dotenv must not enable unrelated study experiments in the benchmark.
    for name in ('STUDY_WIRE_V4_ENABLED', 'STUDY_ASYNC_BATCH_ENABLED', 'STUDY_NEW_LEARNER_NOTE_ENABLED',
            'STUDY_NOTE_COUNT_ENABLED', 'STUDY_PROGRESS_SHADOW_WRITE_ENABLED', 'STUDY_PROGRESS_SHADOW_READ_ENABLED',
            'STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED', 'STUDY_PROGRESS_SHADOW_COMPARE_ENABLED'):
        os.environ[name] = ''
    class Database(NoteBaseMySQLTestCase):
        APP_CONFIG = {'NOTE_PUBLISHED_BASE_ENABLED': False, 'DECK_COUNT_WRITE_ENABLED': False,
            'REVIEW_ANALYTICS_WRITE_ENABLED': False}
    Database.setUpClass()
    report = {'configured_database_modified': False, 'generated_database': Database.database_name,
        'notes': args.notes, 'samples': [], 'publish': [], 'multiprocess': [],
        'limitations': ['Synthetic data, one local host, warm cache, short qualification samples.',
            'Counter deltas are global and include concurrent host work.',
            'DBAPI time includes driver/network time; outside-DBAPI wall is not a pure Python CPU measurement.',
            'First lock-query to return is an upper bound including lock wait, not measured row lock residency.',
            'Study covers page reads only. Full 25/50/100 VU study-commit qualification remains separate.']}
    sources = sorted(path for directory in ('app', 'models') for path in (ROOT / directory).rglob('*.py'))
    report['runtime_source_sha256'] = hashlib.sha256(b''.join(
        str(path.relative_to(ROOT)).replace('\\', '/').encode() + b'\0' + path.read_bytes() for path in sources)).hexdigest()
    report['benchmark_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['started_utc'] = datetime.utcnow().isoformat() + 'Z'
    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    try:
        report.update(baseline._environment(Database.admin))
        with Database.app.app_context():
            seed = baseline._seed(args.notes, args.installs, 1, args.payload_bytes)
            # The reused source fixture creates a publisher without Study
            # state. Explicitly enroll that generated benchmark user too.
            from models.study_authority_enrollment import StudyAuthorityEnrollment
            now = datetime.utcnow()
            db.session.add(StudyAuthorityEnrollment(learner_user_id=seed['owner_id'], mode_code='NOTE', epoch=1,
                created_at=now, updated_at=now))
            db.session.commit()
            seed['source_root_id'] = db.session.get(DeckInstall, seed['contexts'][0][2]).source_deck_id
            originals = {row.id: dict(row) for row in db.session.connection().execute(select(Note.__table__)).mappings()}
            db.session.remove()
        for audience, densities in (('author', args.drafts), ('learner', args.overrides)):
            for density in densities:
                with Database.app.app_context():
                    if audience == 'author':
                        drafts = _drafts(seed, density, 'draft')
                    else:
                        _drafts(seed, 0, 'empty')
                        drafts = []
                        baseline._overlays(seed, 1, density)
                for iteration in range(args.iterations):
                    for enabled in ((False, True) if iteration % 2 == 0 else (True, False)):
                        with Database.app.app_context():
                            _author_mode(Database.app, originals, drafts, enabled)
                        operations = ('browse', 'search', 'sort') if audience == 'author' else ('browse', 'search', 'study_page_query')
                        for operation in operations:
                            sample = _measure(Database.app, lambda: _request(audience, operation, seed), admin=Database.admin,
                                sql_pages=args.sql_pages,
                                explain=iteration == 0 and (audience == 'author' and operation != 'browse'
                                    or audience == 'learner' and density == 0 and not enabled))
                            sample.update(audience=audience, density=density, iteration=iteration,
                                mode='published_base' if enabled else 'legacy', operation=operation)
                            report['samples'].append(sample)
                            save()
                            print(json.dumps({key: sample[key] for key in ('audience', 'density', 'mode', 'operation',
                                'elapsed_ms', 'sql_statements')}), flush=True)
                with Database.app.app_context():
                    _author_mode(Database.app, originals, drafts, True)
        Database.app.config['NOTE_PUBLISHED_BASE_ENABLED'] = True
        for count in args.publish:
            with Database.app.app_context():
                _drafts(seed, count, f'publish-{count}')
            sample = _measure(Database.app, lambda: _publish(seed, count), admin=Database.admin)
            sample['notes'] = count
            report['publish'].append(sample)
            save()
        if args.process_vus:
            with Database.app.app_context():
                _drafts(seed, min(2000, args.notes), 'multiprocess')
                config = {'TESTING': True, 'SECRET_KEY': 'generated-benchmark-only',
                    'SQLALCHEMY_DATABASE_URI': str(db.engine.url.render_as_string(hide_password=False)),
                    'NOTE_PUBLISHED_BASE_ENABLED': True, 'STARTUP_RUN_MAINTENANCE': False,
                    'STARTUP_CHECK_DB_CONNECTIVITY': False, 'DECK_COUNT_WRITE_ENABLED': False,
                    'REVIEW_ANALYTICS_WRITE_ENABLED': False, 'MEDIA_STORAGE_ROOT': Database.media_directory.name}
            before = baseline._status(Database.admin)
            started = perf_counter()
            with ProcessPoolExecutor(max_workers=args.process_vus, mp_context=multiprocessing.get_context('spawn')) as pool:
                futures = [pool.submit(_process_load, config, seed, args.process_iterations) for _ in range(args.process_vus)]
                report['multiprocess'] = [future.result() for future in futures]
            after = baseline._status(Database.admin)
            report['multiprocess_elapsed_ms_including_spawn'] = (perf_counter() - started) * 1000
            report['multiprocess_global_counter_delta'] = {key: after.get(key, 0) - before.get(key, 0) for key in baseline.COUNTERS}
            report['process_vus'] = args.process_vus
        parity = []
        for audience in ('author', 'learner'):
            keys = {(row['density'], row['iteration'], row['operation']) for row in report['samples'] if row['audience'] == audience}
            for density, iteration, operation in sorted(keys):
                signatures = {row['signature'] for row in report['samples'] if (row['audience'], row['density'],
                    row['iteration'], row['operation']) == (audience, density, iteration, operation)}
                parity.append({'audience': audience, 'density': density, 'iteration': iteration,
                    'operation': operation, 'pass': len(signatures) == 1})
        report['parity'] = parity
        report['status'] = 'PASS' if all(row['pass'] for row in parity) else 'FAIL'
        return report
    finally:
        Database.doClassCleanups()
        report['generated_database_dropped'] = True
        save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notes', type=int, default=10000)
    parser.add_argument('--installs', type=int, default=100)
    parser.add_argument('--drafts', type=int, nargs='+', default=[0, 200, 2000])
    parser.add_argument('--overrides', type=int, nargs='*', default=[0, 20])
    parser.add_argument('--publish', type=int, nargs='*', default=[10, 1000, 10000])
    parser.add_argument('--iterations', type=int, default=2)
    parser.add_argument('--payload-bytes', type=int, default=1800)
    parser.add_argument('--process-vus', type=int, default=4)
    parser.add_argument('--process-iterations', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sql-pages', action='store_true', help='Attribute global page deltas per statement; adds monitoring overhead.')
    args = parser.parse_args()
    if min(args.notes, args.installs, args.iterations, args.process_iterations) < 1 or args.process_vus < 0:
        parser.error('Positive counts are required; process VUs may be zero.')
    if any(count < 0 or count > args.notes for count in args.drafts + args.overrides + args.publish):
        parser.error('Densities and publish sizes must be between zero and the Note count.')
    result = run(args)
    print(json.dumps({'status': result['status'], 'output': str(args.output)}, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
