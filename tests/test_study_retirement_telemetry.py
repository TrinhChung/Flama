from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from app.services.study_retirement_telemetry_service import (
    ENTRYPOINTS, OBSERVATION_SCHEMA, SCHEMA_VERSION, record_legacy_usage, retirement_usage_evidence,
)
from scripts.collect_study_retirement_observation import collect_observation


class StudyRetirementTelemetryTests(unittest.TestCase):
    def test_canonical_routes_do_not_log_and_legacy_log_contains_only_fixed_labels(self):
        with mock.patch("app.services.study_retirement_telemetry_service.logger.warning") as log:
            record_legacy_usage("session.commit", wire="study-session.v4")
            log.assert_not_called()
            record_legacy_usage("session.commit", wire="client-controlled-secret")
            event = json.loads(log.call_args.args[1])
            self.assertEqual(event["wire"], "unknown")
            self.assertEqual(set(event), {"schema_version", "entrypoint", "wire", "observed_at_utc"})

    def test_journal_collection_checks_metadata_and_does_not_infer_coverage(self):
        now = datetime(2026, 10, 2, 12)
        since = now - timedelta(days=30)
        coverage = {"start_utc": since.isoformat() + "Z", "end_utc": now.isoformat() + "Z",
                    "continuous": False, "gaps": [], "covered_entrypoints": sorted(set().union(*ENTRYPOINTS.values()))}
        with tempfile.TemporaryDirectory() as directory:
            journal, metadata = Path(directory) / "journal", Path(directory) / "coverage"
            journal.write_text(json.dumps({"MESSAGE": "unrelated log"}) + "\n", encoding="utf-8")
            metadata.write_text(json.dumps(coverage), encoding="utf-8")
            observation = collect_observation(journal, metadata)
            self.assertEqual(observation["schema_version"], OBSERVATION_SCHEMA)
            self.assertEqual(retirement_usage_evidence(observation, gate="old_session_wire_versions", since=since, now=now)["status"], "unknown")
            coverage["continuous"] = True
            metadata.write_text(json.dumps(coverage), encoding="utf-8")
            observation = collect_observation(journal, metadata)
            self.assertEqual(retirement_usage_evidence(observation, gate="old_session_wire_versions", since=since, now=now)["status"], "ready")
            event = {"schema_version": SCHEMA_VERSION, "entrypoint": "session.restore", "observed_at_utc": now.isoformat() + "Z"}
            journal.write_text(json.dumps({"MESSAGE": "STUDY_RETIREMENT " + json.dumps(event)}) + "\n", encoding="utf-8")
            observation = collect_observation(journal, metadata)
            self.assertEqual(retirement_usage_evidence(observation, gate="old_session_wire_versions", since=since, now=now)["status"], "waiting")
            journal.write_text('{"MESSAGE":', encoding="utf-8")
            with self.assertRaises(ValueError):
                collect_observation(journal, metadata)

    def test_stale_partial_future_and_invalid_coverage_never_pass(self):
        now = datetime(2026, 10, 2, 12)
        since = now - timedelta(days=30)
        observation = {"schema_version": OBSERVATION_SCHEMA, "start_utc": since.isoformat() + "Z",
                       "end_utc": now.isoformat() + "Z", "continuous": True, "gaps": [], "events": [],
                       "covered_entrypoints": ["session.issue"]}
        self.assertEqual(retirement_usage_evidence(observation, gate="old_session_wire_versions", since=since, now=now)["status"], "unknown")
        observation["covered_entrypoints"] = sorted(set().union(*ENTRYPOINTS.values()))
        observation["end_utc"] = (now - timedelta(minutes=1)).isoformat() + "Z"
        self.assertEqual(retirement_usage_evidence(observation, gate="old_session_wire_versions", since=since, now=now)["status"], "unknown")
        observation["end_utc"] = (now + timedelta(seconds=1)).isoformat() + "Z"
        with self.assertRaises(ValueError):
            retirement_usage_evidence(observation, gate="old_session_wire_versions", since=since, now=now)
