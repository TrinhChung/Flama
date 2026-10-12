"""Read-only MySQL plans for the NOTE picker after the retirement migrations.

Example:
  python scripts/probe_note_queue_queries.py --env-file .env --user-id 1 --analyze

The probe does not run migrations or startup maintenance. It opens one READ
ONLY snapshot, explains disjoint due-anchor branches with LIMIT 1, then rolls
back. Output contains plans and SQL shape, never credentials or Note content.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--user-id', type=int, required=True)
    parser.add_argument('--database', help='Use a migrated disposable clone on the same loopback server')
    parser.add_argument('--deck-id', type=int)
    parser.add_argument('--timezone', default='UTC')
    parser.add_argument('--analyze', action='store_true', help='Execute read-only EXPLAIN ANALYZE (MySQL8.0.18+)')
    parser.add_argument('--compare-combined', action='store_true', help='Also explain an equivalent combined OR/CASE picker')
    parser.add_argument('--serving', action='store_true', help='Explain actual anchor seeks executed by the serving picker')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(args.env_file)
    from app import create_audit_app
    from app.settings import build_app_config
    from app.repositories.study_repository import (
        _next_day_boundary, _ordered_study_card_queries, _today_day_index,
        query_next_due_card_id,
    )
    from app.services.scheduler_config_service import resolve_scheduler_runtime_settings
    from models import db
    from models.card import Card
    from models.note import Note
    from models.study_progress_subject import StudyProgressSubject
    from sqlalchemy import and_, case, event, false, or_
    from sqlalchemy.orm import aliased
    from sqlalchemy.engine import make_url

    target = make_url(build_app_config()['SQLALCHEMY_DATABASE_URI'])
    if args.database is not None:
        if not args.database.replace('_', '').isalnum():
            raise RuntimeError('Invalid clone database name.')
        target = target.set(database=args.database)
    if target.host not in ('localhost', '127.0.0.1', '::1'):
        raise RuntimeError('The probe only accepts a loopback MySQL target.')
    app = create_audit_app({'REDIS_URL': '',
                          'SQLALCHEMY_DATABASE_URI': target.render_as_string(hide_password=False)})
    with app.app_context():
        connection = db.session.connection()
        if connection.dialect.name != 'mysql':
            raise RuntimeError('This probe requires a migrated MySQL database.')
        connection.exec_driver_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            scope = Card.query.join(Note, Note.id == Card.note_id).filter(
                Note.user_id == args.user_id, Card.application_status == 'ACTIVE',
            )
            if args.deck_id is not None:
                scope = scope.filter(Note.deck_id == args.deck_id)
            due, ahead = _ordered_study_card_queries(scope, user_id=args.user_id,
                                                    now=now, timezone_name=args.timezone)
            result = {'scope': 'owned-active', 'user_id': args.user_id,
                      'deck_id': args.deck_id, 'timezone': args.timezone,
                      'snapshot_utc': now.isoformat(), 'analyze': args.analyze, 'plans': []}
            def explain(branch, *, kind, queue_index=None, anchor_index=None):
                compiled = branch.limit(1).statement.compile(
                    dialect=connection.dialect, compile_kwargs={'render_postcompile': True},
                )
                sql = str(compiled)
                prefix = 'EXPLAIN ANALYZE ' if args.analyze else 'EXPLAIN FORMAT=JSON '
                rows = connection.exec_driver_sql(prefix + sql, compiled.params).all()
                result['plans'].append({
                    'kind': kind, 'queue_index': queue_index, 'anchor_index': anchor_index,
                    'sql': sql, 'plan': [str(row[0]) for row in rows],
                })

            if args.compare_combined:
                # Same NOTE anchors and exact ordering, but the former combined
                # queue predicate/sort shape. This is a measurement baseline,
                # never a serving path or a CardProgress persistence fallback.
                subject = aliased(StudyProgressSubject)
                runtime = resolve_scheduler_runtime_settings(user_id=args.user_id)
                day = _today_day_index(now=now, timezone_name=args.timezone,
                                      day_boundary_hour_local=runtime.day_boundary_hour_local)
                cutoff = _next_day_boundary(now=now, timezone_name=args.timezone,
                                            day_boundary_hour_local=runtime.day_boundary_hour_local)
                current = subject.semantic_state_hash.isnot(None)
                active = or_(~current, and_(subject.is_suspended == false(),
                    or_(subject.is_buried.is_(False), subject.buried_until_day < day)))
                def anchored(time_cutoff, *, review=False):
                    timestamp = subject.due_at < time_cutoff if review else subject.due_at <= time_cutoff
                    return or_(subject.due_day <= day, and_(subject.due_day.is_(None),
                        or_(subject.due_at.is_(None), timestamp)))
                queue = subject.normalized_queue
                review_day = case((queue == 'review', subject.due_day), else_=None)
                due_at = case((queue.in_(['learning', 'relearning', 'review']), subject.due_at), else_=None)
                combined = scope.outerjoin(subject, and_(
                    subject.live_note_id == Card.note_id, subject.learner_user_id == args.user_id,
                )).filter(active, or_(
                    ~current, queue == 'new',
                    and_(queue.in_(['learning', 'relearning']), anchored(now)),
                    and_(queue == 'review', anchored(cutoff, review=True)),
                )).order_by(
                    case((queue == 'relearning', 0), (queue == 'learning', 1),
                         (queue == 'review', 2), else_=3),
                    review_day.is_(None), review_day, due_at.is_(None), due_at,
                    Card.created_at, Card.id,
                ).with_entities(Card.id)
                explain(combined, kind='combined-baseline')
            if args.serving:
                captured = []
                def capture(_conn, _cursor, statement, parameters, context, _many):
                    if statement.lstrip().upper().startswith('SELECT') and 'study_progress_subjects' in statement:
                        captured.append((statement, parameters, dict(context.execution_options)))
                event.listen(connection, 'before_cursor_execute', capture)
                try:
                    result['selected_card_id'] = query_next_due_card_id(
                        scope, user_id=args.user_id, now=now, timezone_name=args.timezone,
                    )
                finally:
                    event.remove(connection, 'before_cursor_execute', capture)
                for sql, parameters, options in captured:
                    prefix = 'EXPLAIN ANALYZE ' if args.analyze else 'EXPLAIN FORMAT=JSON '
                    rows = connection.exec_driver_sql(prefix + sql, parameters).all()
                    result['plans'].append({
                        'kind': 'serving', 'queue_index': options.get('note_queue_code'),
                        'anchor_index': options.get('note_anchor_index'), 'sql': sql,
                        'plan': [str(row[0]) for row in rows],
                    })
            for kind, groups in (('due', due), ('ahead', ahead)):
                for queue_index, branches in enumerate(groups):
                    for anchor_index, branch in enumerate(branches):
                        explain(branch, kind=kind, queue_index=queue_index, anchor_index=anchor_index)
            encoded = json.dumps(result, ensure_ascii=False, indent=2)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(encoded + '\n', encoding='utf-8')
            else:
                print(encoded)
        finally:
            db.session.rollback()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
