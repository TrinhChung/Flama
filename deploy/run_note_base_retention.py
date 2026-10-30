"""Daily bounded retention with an atomic restart cursor and JSON journal logs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from time import monotonic
from uuid import UUID


def _save_cursor(path, cursor):
    # The caller commits a batch before advancing the cursor. A crash before
    # this rename repeats that batch safely rather than skipping any content.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                prefix=path.name + '.', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'cursor': cursor}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_batches(run_batch, *, cursor_file, limit=200, max_batches=200, max_seconds=60,
        clock=monotonic, emit=lambda value: print(json.dumps(value), flush=True)):
    cursor = None
    if cursor_file.exists():
        value = json.loads(cursor_file.read_text(encoding='utf-8'))
        cursor = value['cursor']
        if cursor is not None:
            cursor = str(UUID(cursor))
    started = clock()
    report = {'event': 'note_base_retention_run', 'batches': 0, 'completed': False,
        'notes': 0, 'fields': 0, 'expired_overrides': 0, 'notes_retained_for_references': 0}
    for index in range(max_batches):
        if index and clock() - started >= max_seconds:
            break
        batch = run_batch(apply=True, limit=limit, after=cursor)
        next_cursor = batch['next_cursor']
        if next_cursor is not None:
            next_cursor = str(UUID(next_cursor))
            if cursor is not None and next_cursor <= cursor:
                raise RuntimeError('Retention cursor did not advance; refusing an endless sweep.')
        _save_cursor(cursor_file, next_cursor)
        cursor = next_cursor
        report['batches'] += 1
        for key in ('notes', 'fields', 'expired_overrides', 'notes_retained_for_references'):
            report[key] += batch[key]
        emit({'event': 'note_base_retention_batch', **batch})
        if cursor is None:
            report['completed'] = True
            break
    report.update(next_cursor=cursor, elapsed_seconds=round(clock() - started, 3))
    emit(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cursor-file', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=200)
    parser.add_argument('--max-batches', type=int, default=200)
    parser.add_argument('--max-seconds', type=float, default=60)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 1000 or not 1 <= args.max_batches <= 10000 or not 0 < args.max_seconds <= 3600:
        parser.error('Invalid batch/time bounds.')
    if os.getenv('NOTE_PUBLISHED_BASE_ENABLED', '').strip().lower() not in {'1', 'true', 'yes', 'on'}:
        print(json.dumps({'event': 'note_base_retention_run', 'status': 'skipped_flag_off'}))
        return 0
    if not args.cursor_file.is_absolute() or not args.cursor_file.parent.is_dir():
        parser.error('Cursor file needs an absolute path in an existing state directory.')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import create_audit_app
    from app.services.note_base_retention_service import run_retention
    # Controlled maintenance needs models/config/DB, with no WSGI startup
    # repair or legacy clone cutover even if a server environment leaks flags.
    with create_audit_app().app_context():
        run_batches(run_retention, cursor_file=args.cursor_file, limit=args.limit,
            max_batches=args.max_batches, max_seconds=args.max_seconds)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
