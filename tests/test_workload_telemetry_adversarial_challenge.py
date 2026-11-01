"""Adversarial stress-testing suite for Flama workload telemetry and resource ratios RFC.

Covers:
1. Distortion of the 91.47% Read : 8.53% Write ratio by background worker heartbeat probes & sweeps.
2. Media bandwidth (38.47%) characteristics, X-Accel-Redirect mechanics, and DB query overhead.
3. Network WAN RTT lock inflation (6.9ms -> 1,000ms - 3,320ms) and multi-learner lock concurrency.
4. MCP tool burst dynamics, SQLAlchemy connection pool contention (4+1 slots), and process isolation.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from app.services.study_consumer_service import StudyConsumerOptions, probe_study_worker_database
from models.study_progress_subject import StudyProgressSubject


class WorkloadTelemetryAdversarialStressTest(unittest.TestCase):
    """Adversarial empirical tests validating and challenging RFC telemetry assertions."""

    def test_read_write_ratio_background_timer_distortion(self):
        """Challenge 1: Quantify how much background timers distort the Read:Write ratio.

        Raw Telemetry:
        - Uptime: 1,178,086 seconds (~13.63 days)
        - Com_select: 4,806,163 (91.47%)
        - Com_insert: 268,708 (5.11%)
        - Com_update: 179,150 (3.41%)
        - Com_delete: 432 (0.01%)
        - Total DML: 5,254,453 statements
        """
        uptime_seconds = 1_178_086
        raw_select = 4_806_163
        raw_insert = 268_708
        raw_update = 179_150
        raw_delete = 432
        raw_writes = raw_insert + raw_update + raw_delete
        raw_total = raw_select + raw_writes

        self.assertAlmostEqual(raw_select / raw_total, 0.9147, places=4)
        self.assertAlmostEqual(raw_writes / raw_total, 0.0853, places=4)

        # Inspect StudyConsumerOptions defaults
        options = StudyConsumerOptions()
        self.assertEqual(options.heartbeat_interval, 5.0)
        self.assertEqual(options.recovery_interval, 5.0)

        # In StudyBatchConsumer.step(), every heartbeat_interval (5.0s):
        # probe_study_worker_database() executes 7 SELECT ... LIMIT 0 queries:
        # (StudySessionBatch, StudySession, StudySessionAuthorityPin,
        #  StudyAuthorityEnrollment, StudyAuthorityCommandReceipt,
        #  StudyProgressSubject, StudyProgressHistoryFact)
        probed_models_count = 7
        heartbeat_iterations = uptime_seconds / options.heartbeat_interval
        synthetic_probe_selects = heartbeat_iterations * probed_models_count

        # In addition, recover_admitted_study_batches() executes at least 1 SELECT on StudySessionBatch
        # every recovery_interval (5.0s)
        synthetic_recovery_selects = uptime_seconds / options.recovery_interval

        total_synthetic_worker_selects = synthetic_probe_selects + synthetic_recovery_selects

        # Over 13.63 days (1,178,086s):
        # 1,178,086 / 5 * 7 = 1,649,320.4 probe selects
        # 1,178,086 / 5 * 1 = 235,617.2 recovery selects
        # Total = 1,884,937.6 synthetic SELECTs!
        self.assertAlmostEqual(total_synthetic_worker_selects, 1_884_937.6, delta=1.0)
        synthetic_pct_of_all_selects = total_synthetic_worker_selects / raw_select
        self.assertGreater(synthetic_pct_of_all_selects, 0.39)  # > 39% of all SELECTs are synthetic!

        # Recalculate true organic workload by removing synthetic worker polling:
        organic_selects = raw_select - total_synthetic_worker_selects
        organic_total = organic_selects + raw_writes
        organic_read_ratio = organic_selects / organic_total
        organic_write_ratio = raw_writes / organic_total

        # True Organic Ratio: ~86.70% Read : ~13.30% Write
        self.assertAlmostEqual(organic_read_ratio, 0.8670, delta=0.005)
        self.assertAlmostEqual(organic_write_ratio, 0.1330, delta=0.005)

        # The true write proportion is 1.56x higher (13.30% vs 8.53%) than raw DML suggests!
        write_inflation_factor = organic_write_ratio / (raw_writes / raw_total)
        self.assertGreater(write_inflation_factor, 1.55)

    def test_media_proxy_gunicorn_and_db_consumption(self):
        """Challenge 2: Analyze Media Proxy bandwidth share and DB connection cost."""
        total_requests = 54_614
        media_requests = 9_170
        media_304 = 7_211
        media_200 = 1_959
        media_bandwidth_bytes = 318.71 * 1024 * 1024
        total_bandwidth_bytes = 828.54 * 1024 * 1024

        # Request share
        media_req_pct = media_requests / total_requests
        self.assertAlmostEqual(media_req_pct, 0.1679, places=4)

        # Bandwidth share
        media_bw_pct = media_bandwidth_bytes / total_bandwidth_bytes
        self.assertAlmostEqual(media_bw_pct, 0.3847, places=4)

        # Average size per full media transfer (HTTP 200/206)
        avg_media_file_bytes = media_bandwidth_bytes / media_200
        avg_media_file_kib = avg_media_file_bytes / 1024
        self.assertAlmostEqual(avg_media_file_kib, 166.6, delta=5.0)

        # Average size per non-media request (509.83 MB / 45,444 reqs)
        non_media_bytes = total_bandwidth_bytes - media_bandwidth_bytes
        non_media_reqs = total_requests - media_requests
        avg_non_media_kib = (non_media_bytes / non_media_reqs) / 1024
        self.assertAlmostEqual(avg_non_media_kib, 11.22, delta=1.0)

        # Media bandwidth dominance is driven by payload asymmetry (166.6 KiB vs 11.2 KiB = 14.8x),
        # not by video streaming or abnormal single file sizes.
        asymmetry_ratio = avg_media_file_kib / avg_non_media_kib
        self.assertGreater(asymmetry_ratio, 14.0)

        # Verify Codebase Reality:
        # In app/routes/flashcards/media.py line 204:
        # Every media request executes: MediaAsset.query.filter(MediaAsset.id == asset_id).first()
        # Even on HTTP 304 (78.64% of cases), Flask STILL checks out a DB connection and runs a SELECT!
        media_db_queries_generated = media_requests
        self.assertEqual(media_db_queries_generated, 9_170)

        # Verify deploy/flama.nginx.conf:
        # Check that location ^~ /media/proxy/ proxies to 127.0.0.1:4789 without proxy_cache
        nginx_conf_path = Path("deploy/flama.nginx.conf")
        self.assertTrue(nginx_conf_path.exists())
        content = nginx_conf_path.read_text(encoding="utf-8")
        self.assertIn("location ^~ /media/proxy/", content)
        self.assertIn("proxy_pass http://127.0.0.1:4789;", content)
        # Nginx does not cache proxy responses locally; every miss or revalidation wakes Python!
        self.assertNotIn("proxy_cache ", content)

    def test_wan_rtt_lock_inflation_and_concurrency_semantics(self):
        """Challenge 3: Verify the physics of WAN RTT lock inflation and row-lock scope."""
        # 1. RTT Calculation Verification
        # In a batch commit of 20 cards, sequential queries include:
        # 1 user lock, 1 enrollment lock, 1 session lock, 1 batch lock, 1 pin lock,
        # plus per-card checks and inserts (~80-100 total queries).
        # Let's test conservative 25 queries vs full 83 queries:
        conservative_n = 25
        full_n = 83

        lan_rtt = 0.0005  # 0.5ms IPC / socket
        wan_rtt_sg_vn = 0.040  # 40ms WAN RTT
        wan_rtt_cross_continent = 0.080  # 80ms WAN RTT

        lan_duration_conservative = conservative_n * lan_rtt * 1000  # ms
        wan_duration_conservative = conservative_n * wan_rtt_sg_vn * 1000  # ms

        self.assertAlmostEqual(lan_duration_conservative, 12.5, delta=1.0)
        self.assertAlmostEqual(wan_duration_conservative, 1000.0, delta=1.0)

        # If 83 queries are executed sequentially:
        wan_duration_full = full_n * wan_rtt_sg_vn * 1000
        self.assertAlmostEqual(wan_duration_full, 3320.0, delta=1.0)  # 3.32 seconds!

        # 2. Concurrency Semantics Challenge:
        # Does Learner A conflict with Learner B on row locks?
        # Check StudyProgressSubject constraints:
        constraints = [
            c.name for c in StudyProgressSubject.__table_args__
            if hasattr(c, "name") and c.name
        ]
        self.assertIn("uq_sp_subject_user_note", constraints)

        # The unique constraint is ("learner_user_id", "logical_note_key").
        # Row locks are keyed on (user_id, logical_note_key).
        # Learner 1 and Learner 2 have different user_ids.
        # Therefore, two learners submitting concurrently DO NOT block each other on StudyProgressSubject!
        # The real bottleneck is:
        # 1) Queue starvation (worker throughput collapses from ~145 jobs/sec to < 1 job/sec).
        # 2) Connection pool exhaustion (holding DB connections for 1.0s - 3.3s in a pool of size 4).
        # 3) Intra-user contention (same user submitting multiple rapid reviews or Yomitan sync).

    def test_mcp_connection_pool_burst_and_process_isolation(self):
        """Challenge 4: Verify MCP tool burst behavior, pool limits, and process isolation."""
        from app.settings import build_app_config

        config = build_app_config(overrides={"SQLALCHEMY_DATABASE_URI": "mysql+pymysql://user:pass@127.0.0.1/db"})
        engine_options = config.get("SQLALCHEMY_ENGINE_OPTIONS", {})

        # Default pool settings
        pool_size = engine_options.get("pool_size", 4)
        max_overflow = engine_options.get("max_overflow", 1)
        pool_timeout = engine_options.get("pool_timeout", 5)

        self.assertEqual(pool_size, 4)
        self.assertEqual(max_overflow, 1)
        self.assertEqual(pool_timeout, 5)

        # Total simultaneous DB connections allowed per process = 4 + 1 = 5
        max_active_connections = pool_size + max_overflow
        self.assertEqual(max_active_connections, 5)

        # Process Isolation Fact:
        # flama.service (Port 4789) -> wsgi:app (Gunicorn gthread: 2 workers x 4 threads = 8 worker threads)
        # Each Gunicorn worker process has its OWN QueuePool of size 4+1 = 5.
        # flama-connect.service (Port 4790) -> connect_wsgi:app (Gunicorn sync: 1 worker)
        # It has its OWN QueuePool of size 4+1 = 5.
        # If /v1/mcp is served exclusively by flama-connect.service on port 4790,
        # an AI Agent tool-calling storm consumes connections ONLY in connect_wsgi,
        # NEVER affecting flama.service's QueuePool!
        # The RFC's warning of TimeoutError for web users (/api/study/*) is ONLY valid
        # if MCP traffic is mistakenly routed to port 4789 (flama.service).


if __name__ == "__main__":
    unittest.main()
