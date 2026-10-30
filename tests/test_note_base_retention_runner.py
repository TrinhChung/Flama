"""Restart and failure boundaries of the scheduled retention runner."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from deploy.run_note_base_retention import run_batches


class NoteBaseRetentionRunnerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cursor_file = Path(directory.name) / 'cursor.json'

    @staticmethod
    def batch(cursor):
        return {'next_cursor': cursor, 'notes': 1, 'fields': 0, 'expired_overrides': 2,
            'notes_retained_for_references': 3, 'apply': True, 'retention_days': 90, 'limit': 200}

    def test_resumes_bounded_sweep_and_resets_when_complete(self):
        cursor = '00000000-0000-0000-0000-000000000001'
        emit = Mock()
        first = run_batches(Mock(return_value=self.batch(cursor)), cursor_file=self.cursor_file,
            max_batches=1, emit=emit)
        self.assertFalse(first['completed'])
        second_batch = Mock(return_value=self.batch(None))
        second = run_batches(second_batch, cursor_file=self.cursor_file, emit=emit)
        second_batch.assert_called_once_with(apply=True, limit=200, after=cursor)
        self.assertTrue(second['completed'])
        self.assertEqual(json.loads(self.cursor_file.read_text()), {'cursor': None})

    def test_failed_batch_leaves_last_committed_cursor(self):
        cursor = '00000000-0000-0000-0000-000000000001'
        self.cursor_file.write_text(json.dumps({'cursor': cursor}))
        with self.assertRaisesRegex(RuntimeError, 'transaction failed'):
            run_batches(Mock(side_effect=RuntimeError('transaction failed')), cursor_file=self.cursor_file, emit=Mock())
        self.assertEqual(json.loads(self.cursor_file.read_text()), {'cursor': cursor})

    def test_time_limit_stops_between_committed_batches(self):
        run = Mock(return_value=self.batch('00000000-0000-0000-0000-000000000001'))
        result = run_batches(run, cursor_file=self.cursor_file, max_seconds=1,
            clock=Mock(side_effect=[0, 2, 2]), emit=Mock())
        self.assertEqual(result['batches'], 1)
        self.assertFalse(result['completed'])

    def test_corrupt_cursor_fails_without_purging(self):
        self.cursor_file.write_text('{"cursor": "invalid"}')
        run = Mock()
        with self.assertRaises(ValueError):
            run_batches(run, cursor_file=self.cursor_file, emit=Mock())
        run.assert_not_called()

    def test_disabled_runner_exits_before_importing_or_connecting_application(self):
        environment = dict(os.environ, NOTE_PUBLISHED_BASE_ENABLED='false',
            DB_HOST='intentionally-invalid-host.invalid')
        result = subprocess.run([sys.executable, '-I', 'deploy/run_note_base_retention.py',
            '--cursor-file', str(self.cursor_file)], env=environment, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['status'], 'skipped_flag_off')
        self.assertFalse(self.cursor_file.exists())
