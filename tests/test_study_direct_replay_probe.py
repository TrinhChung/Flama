"""The MySQL replay probe cannot select a real application database."""

import unittest
from unittest.mock import patch

from scripts.probe_p5_direct_replay_mysql import _probe_app


class StudyDirectReplayProbeGuardTests(unittest.TestCase):
    def test_rejects_non_disposable_or_nonlocal_database_before_app_creation(self):
        uris = (
            "sqlite:///:memory:",
            "mysql+pymysql://localhost/nihongo",
            "mysql+pymysql://localhost/flama_p5_direct_probe_invalid",
            "mysql+pymysql://remote.example/flama_p5_direct_probe_123_1234abcd",
            "mysql+pymysql://localhost/flama_p5_direct_probe_123_1234abcd_suffix",
        )
        with patch("scripts.probe_p5_direct_replay_mysql.create_app") as create:
            for uri in uris:
                with self.subTest(uri=uri), self.assertRaises(ValueError):
                    _probe_app(uri)
            create.assert_not_called()
