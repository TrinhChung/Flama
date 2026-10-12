"""Benchmark the whole migrated /api/study/next path with a SELECT-only guard.

Unlike EXPLAIN ANALYZE, this includes count, ownership, locking reads, state
decoding and manifest creation. It compares an equivalent combined OR/CASE
picker inside the same endpoint; neither run writes database rows or schema.
Only an explicitly named loopback rehearsal database is accepted.
"""

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from time import perf_counter
from statistics import median
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--database', required=True)
    parser.add_argument('--user-id', type=int, required=True)
    parser.add_argument('--scope', choices=('deck', 'note_type'), required=True)
    parser.add_argument('--scope-id', required=True)
    parser.add_argument('--iterations', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if 'rehearsal' not in args.database or not args.database.replace('_', '').isalnum():
        raise RuntimeError('Only an explicitly named rehearsal database is accepted.')

    from dotenv import load_dotenv
    load_dotenv(args.env_file)
    from app import create_app
    from app.settings import build_app_config
    from app.repositories.study_repository import _next_day_boundary, _today_day_index
    from app.services.scheduler_config_service import resolve_scheduler_runtime_settings
    from models import db
    from models.card import Card
    from models.study_progress_subject import StudyProgressSubject
    from sqlalchemy import and_, case, event, false, or_
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import aliased

    target = make_url(build_app_config()['SQLALCHEMY_DATABASE_URI']).set(database=args.database)
    if target.host not in ('localhost', '127.0.0.1', '::1'):
        raise RuntimeError('Benchmark target must be loopback.')
    app = create_app({'SQLALCHEMY_DATABASE_URI': target.render_as_string(hide_password=False),
        'TESTING': True, 'STARTUP_RUN_MAINTENANCE': False, 'STARTUP_CHECK_DB_CONNECTIVITY': False,
        'WTF_CSRF_ENABLED': False, 'REDIS_URL': '', 'DECK_COUNT_WRITE_ENABLED': False,
        'REVIEW_ANALYTICS_WRITE_ENABLED': False})

    def combined(query, *, user_id, now, timezone_name='UTC', queue_counts=None):
        subject = aliased(StudyProgressSubject)
        runtime = resolve_scheduler_runtime_settings(user_id=user_id)
        day = _today_day_index(now=now, timezone_name=timezone_name,
                              day_boundary_hour_local=runtime.day_boundary_hour_local)
        cutoff = _next_day_boundary(now=now, timezone_name=timezone_name,
                                    day_boundary_hour_local=runtime.day_boundary_hour_local)
        current = subject.semantic_state_hash.isnot(None)
        active = or_(~current, and_(subject.is_suspended == false(),
                      or_(subject.is_buried.is_(False), subject.buried_until_day < day)))
        def due(moment, review=False):
            timestamp = subject.due_at < moment if review else subject.due_at <= moment
            return or_(subject.due_day <= day, and_(subject.due_day.is_(None),
                       or_(subject.due_at.is_(None), timestamp)))
        queue = subject.normalized_queue
        review_day = case((queue == 'review', subject.due_day), else_=None)
        time = case((queue.in_(['learning', 'relearning', 'review']), subject.due_at), else_=None)
        base = query.outerjoin(subject, and_(subject.live_note_id == Card.note_id,
                                            subject.learner_user_id == user_id)).filter(active)
        row = base.filter(or_(~current, queue == 'new',
            and_(queue.in_(['learning', 'relearning']), due(now)),
            and_(queue == 'review', due(cutoff, True)),
        )).order_by(None).order_by(
            case((queue == 'relearning', 0), (queue == 'learning', 1), (queue == 'review', 2), else_=3),
            review_day.is_(None), review_day, time.is_(None), time, Card.created_at, Card.order_key,
        ).with_entities(Card.id).first()
        if row is not None:
            return str(row[0])
        row = base.filter(queue.in_(['learning', 'relearning']), subject.due_day.is_(None),
            subject.due_at > now, subject.due_at <= now + timedelta(
                seconds=runtime.learn_ahead_seconds),
        ).order_by(None).order_by(case((queue == 'relearning', 0), else_=1),
            subject.due_at, Card.created_at, Card.order_key).with_entities(Card.id).first()
        return str(row[0]) if row else None

    statements = []
    def guard(_conn, _cursor, sql, _parameters, _context, _many):
        if sql.lstrip().split()[0].upper() not in ('SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN'):
            raise RuntimeError('Benchmark refused a non-read SQL statement.')
        statements.append(sql)

    with app.app_context():
        engine = db.engine
    event.listen(engine, 'before_cursor_execute', guard)
    result = {'database': args.database, 'user_id': args.user_id, 'scope': args.scope,
              'scope_id': args.scope_id, 'measured_utc': datetime.utcnow().isoformat(), 'runs': []}
    try:
        client = app.test_client()
        with client.session_transaction() as login:
            login['_user_id'], login['_fresh'] = str(args.user_id), True
        for iteration in range(args.iterations):
            kinds = ('combined-baseline', 'anchor-seeking')
            # Alternate order to reduce cache and concurrent-load bias.
            for kind in kinds if iteration % 2 == 0 else reversed(kinds):
                statements.clear()
                context = patch('app.routes.flashcards.study._query_next_due_card_id', side_effect=combined)
                if kind == 'anchor-seeking':
                    from contextlib import nullcontext
                    context = nullcontext()
                started = perf_counter()
                with context:
                    response = client.get('/api/study/next', query_string={
                        'scope': args.scope, 'scope_id': args.scope_id, 'render_contract': 'client_v1',
                    })
                body = response.get_json()
                result['runs'].append({'kind': kind, 'iteration': iteration,
                    'wall_ms': round((perf_counter() - started) * 1000, 3),
                    'status': response.status_code, 'card_id': body.get('card_id'),
                    'counts': {key: body.get(key) for key in ('new_count', 'learn_count', 'due_count')},
                    'error': body.get('error'), 'selects': len(statements),
                    'count_aggregates': sum('count(distinct' in sql.lower() for sql in statements)})
        snapshots = {(row['card_id'], json.dumps(row['counts'], sort_keys=True)) for row in result['runs']}
        result['same_card_and_counts'] = len(snapshots) == 1
        result['warm_medians_ms'] = {
            kind: round(median(row['wall_ms'] for row in result['runs']
                               if row['kind'] == kind and (row['iteration'] > 0 or args.iterations == 1)), 3)
            for kind in ('combined-baseline', 'anchor-seeking')
        }
    finally:
        event.remove(engine, 'before_cursor_execute', guard)
        with app.app_context():
            db.session.rollback()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('database', 'scope', 'scope_id',
                     'same_card_and_counts', 'warm_medians_ms')}))
    return 0 if result['same_card_and_counts'] and all(row['status'] == 200 for row in result['runs']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
