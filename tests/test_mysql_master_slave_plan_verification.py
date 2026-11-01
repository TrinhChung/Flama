"""Verification suite for MySQL 8.0 Master-Slave replication plan & runbook.

Validates that docs/ops/mysql_master_slave_plan.md satisfies all architectural,
configuration, and operational requirements and guards against critical failure modes.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


class MySQLMasterSlavePlanVerificationTest(unittest.TestCase):
    """Verifies docs/ops/mysql_master_slave_plan.md content and correctness."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plan_path = Path("docs/ops/mysql_master_slave_plan.md")
        cls.assertTrue(cls.plan_path.exists(), f"Plan file not found at {cls.plan_path}")
        cls.content = cls.plan_path.read_text(encoding="utf-8")

    def test_r1_document_existence_and_structure(self) -> None:
        """R1: Verify runbook exists with GTID-based Master-Slave structure."""
        self.assertIn("# Kế hoạch và Runbook Thiết lập MySQL 8.0 Master-Slave (GTID-Based)", self.content)
        self.assertIn("VPS Chính (Master)", self.content)
        self.assertIn("Máy Chủ 212 (Slave", self.content)
        self.assertIn("GTID", self.content)

    def test_r2_master_and_slave_my_cnf_configuration(self) -> None:
        """R2: Verify complete my.cnf parameters for both Master and Slave."""
        # Master configuration checks
        self.assertIn("server-id                = 1", self.content)
        self.assertIn("gtid_mode                = ON", self.content)
        self.assertIn("enforce_gtid_consistency = ON", self.content)
        self.assertIn("log_bin", self.content)
        self.assertIn("binlog_format            = ROW", self.content)
        self.assertIn("sync_binlog              = 1", self.content)
        self.assertIn("innodb_flush_log_at_trx_commit = 1", self.content)

        # Footgun guard: Master should NOT activate binlog_do_db
        self.assertIn("# binlog_do_db             = flama", self.content)
        self.assertIn("KHUYẾN NGHỊ: KHÔNG bật binlog_do_db trên Master", self.content)

        # Slave configuration checks
        self.assertIn("server-id                = 212", self.content)
        self.assertIn("read_only                = 1", self.content)
        self.assertIn("super_read_only          = 1", self.content)
        self.assertIn("relay_log", self.content)
        self.assertIn("relay_log_recovery       = ON", self.content)
        self.assertIn("replica_parallel_workers = 4", self.content)
        self.assertIn("replica_preserve_commit_order = ON", self.content)

    def test_r2_replication_user_security_and_privileges(self) -> None:
        """R2: Dedicated replication account with minimum REPLICATION SLAVE privilege."""
        self.assertIn("CREATE USER 'repl_user'@'<SLAVE_212_IP>'", self.content)
        self.assertIn("caching_sha2_password", self.content)
        self.assertIn("GRANT REPLICATION SLAVE ON *.* TO 'repl_user'@'<SLAVE_212_IP>';", self.content)
        self.assertIn("REQUIRE SSL", self.content)

    def test_r3_initial_snapshot_flags(self) -> None:
        """R3: mysqldump snapshot must contain all required non-blocking GTID flags."""
        self.assertIn("--single-transaction", self.content)
        self.assertIn("--set-gtid-purged=ON", self.content)
        self.assertIn("--quick", self.content)
        self.assertIn("--databases flama", self.content)
        self.assertIn("--max-allowed-packet=512M", self.content)

    def test_r3_change_replication_source_syntax(self) -> None:
        """R3: Modern MySQL 8.0 CHANGE REPLICATION SOURCE TO with SOURCE_AUTO_POSITION = 1."""
        self.assertIn("CHANGE REPLICATION SOURCE TO", self.content)
        self.assertIn("SOURCE_AUTO_POSITION = 1", self.content)
        self.assertIn("SOURCE_HOST = '<MASTER_VPS_IP>'", self.content)
        self.assertIn("SOURCE_USER = 'repl_user'", self.content)

    def test_r3_verification_metrics_and_checklist(self) -> None:
        """R3: SHOW REPLICA STATUS metrics definitions."""
        self.assertIn("SHOW REPLICA STATUS\\G", self.content)
        self.assertIn("Replica_IO_Running: Yes", self.content)
        self.assertIn("Replica_SQL_Running: Yes", self.content)
        self.assertIn("Seconds_Behind_Source: 0", self.content)
        self.assertIn("Last_IO_Errno: 0", self.content)
        self.assertIn("Last_SQL_Errno: 0", self.content)

    def test_r3_troubleshooting_scenarios(self) -> None:
        """R3: Troubleshooting covering at least firewall 3306, GTID drift, and replication lag."""
        # 1. Firewall / port 3306
        self.assertIn("Sự cố 1: Lỗi kết nối mạng & Firewall Port 3306", self.content)
        self.assertIn("ufw allow from <SLAVE_212_IP> to any port 3306", self.content)

        # 2. GTID conflict & Empty Transaction Injection
        self.assertIn("Sự cố 2: Bất đồng bộ GTID / Xung đột Giao dịch", self.content)
        self.assertIn("SET GTID_NEXT", self.content)
        self.assertIn("BEGIN;", self.content)
        self.assertIn("COMMIT;", self.content)
        self.assertIn("SET GTID_NEXT = 'AUTOMATIC';", self.content)

        # 3. Replication Lag & Metadata Lock
        self.assertIn("Sự cố 3: Hiện tượng Replication Lag", self.content)
        self.assertIn("Waiting for table metadata lock", self.content)
        self.assertIn("SHOW FULL PROCESSLIST;", self.content)

    def test_operational_safety_super_read_only_lifecycle(self) -> None:
        """Verify runbook correctly handles super_read_only blocks in snapshot & empty transactions."""
        # Snapshot restore must temporarily disable super_read_only
        restore_section = self.content[self.content.find("4.3. Khôi phục dữ liệu lên Máy Chủ 212"):self.content.find("4.4. Xác minh trạng thái")]
        self.assertIn("SET GLOBAL super_read_only = 0; SET GLOBAL read_only = 0;", restore_section)
        self.assertIn("SET GLOBAL read_only = 1; SET GLOBAL super_read_only = 1;", restore_section)

        # Empty transaction injection must temporarily disable super_read_only
        inject_section = self.content[self.content.find("7.2. Sự cố 2"):self.content.find("7.3. Sự cố 3")]
        self.assertIn("SET GLOBAL super_read_only = 0;", inject_section)
        self.assertIn("SET GLOBAL super_read_only = 1;", inject_section)

    def test_application_user_provisioning_on_slave(self) -> None:
        """Verify that the Flama application user (DB_USER) is explicitly provisioned on Slave 212."""
        self.assertIn("KHỞI TẠO TÀI KHOẢN ỨNG DỤNG FLAMA TRÊN MÁY CHỦ 212", self.content)
        self.assertIn("CREATE USER IF NOT EXISTS 'flama_user'@'%'", self.content)
        self.assertIn("CREATE USER IF NOT EXISTS 'flama_user'@'localhost'", self.content)
        self.assertIn("CREATE USER IF NOT EXISTS 'flama_user'@'127.0.0.1'", self.content)
        self.assertIn("GRANT SELECT, SHOW VIEW ON flama.* TO 'flama_user'@'%'", self.content)

        # Footgun guard: MUST disable sql_log_bin in session to prevent errant GTID on Slave
        restore_section = self.content[self.content.find("4.3. Khôi phục dữ liệu lên Máy Chủ 212"):self.content.find("4.4. Xác minh trạng thái")]
        self.assertIn("SET SESSION sql_log_bin = 0;", restore_section)
        self.assertIn("DROP DATABASE IF EXISTS flama;", restore_section)

    def test_failover_and_failback_safety(self) -> None:
        """Verify failover drains relay logs and failback inspects errant transactions."""
        # Failover drains relay logs
        self.assertIn("Replica_SQL_Running_State: Replica has read all relay log; waiting for more updates", self.content)
        self.assertIn("Seconds_Behind_Source: NULL", self.content)

        # Failback checks errant transactions
        self.assertIn("GTID_SUBTRACT", self.content)
        self.assertIn("SELECT GTID_SUBTRACT(@@GLOBAL.gtid_executed, '<SLAVE_212_GTID_EXECUTED>');", self.content)

        # Failback step 2 locks Master with super_read_only while acting as temporary replica
        failback_section = self.content[self.content.find("8.2. Quy trình Hoàn trả"):self.content.find("### 8.3. Tương thích")]
        self.assertIn("SET GLOBAL super_read_only = 1;\n     SET GLOBAL read_only = 1;", failback_section)

        # Failback step 4 drains relay log on Master before RESET REPLICA ALL
        self.assertIn("STOP REPLICA IO_THREAD;", failback_section)
        self.assertIn("Replica_SQL_Running_State: Replica has read all relay log; waiting for more updates", failback_section)
        self.assertIn("RESET REPLICA ALL;", failback_section)

        # Cutover resets read_only on Master
        self.assertIn("SET GLOBAL super_read_only = 0;", failback_section)
        self.assertIn("SET GLOBAL read_only = 0;", failback_section)

    def test_slave_binlog_expiration_and_capacity_guards(self) -> None:
        """Verify Slave 212 configures binlog retention and max size to avoid disk filling."""
        slave_config_section = self.content[self.content.find("2.2. Cấu hình trên Máy Chủ 212"):self.content.find("### 2.3. Bảng giải thích")]
        self.assertIn("max_binlog_size          = 500M", slave_config_section)
        self.assertIn("binlog_expire_logs_seconds = 604800", slave_config_section)
        self.assertIn("log_replica_updates      = ON", slave_config_section)

    def test_systemd_timers_lifecycle_in_failover_and_failback(self) -> None:
        """Verify the 4 high-frequency systemd timers are managed across topology changes."""
        self.assertIn("flama-analytics-counts.timer", self.content)
        self.assertIn("flama-review-analytics-worker.timer", self.content)
        self.assertIn("flama-note-base-retention.timer", self.content)
        self.assertIn("flama-study-retention.timer", self.content)

        # Timers started on Slave 212 when promoted to primary
        failover_section = self.content[self.content.find("8.1. Các bước thăng cấp"):self.content.find("### 8.2. Quy trình Hoàn trả")]
        self.assertIn("systemctl start flama-analytics-counts.timer", failover_section)

        # Timers stopped on Slave 212 and resumed on Master in failback cutover
        failback_section = self.content[self.content.find("8.2. Quy trình Hoàn trả"):self.content.find("### 8.3. Tương thích")]
        self.assertIn("systemctl stop flama-analytics-counts.timer", failback_section)
        self.assertIn("systemctl start flama-analytics-counts.timer", failback_section)

    def test_network_mtu_and_vpn_diagnostics(self) -> None:
        """Verify runbook includes MTU and packet fragment diagnostics for WireGuard/Tailscale."""
        self.assertIn("ping -c 4 -M do -s 1392 <MASTER_VPS_IP>", self.content)

    def test_repository_operational_scripts_compatibility(self) -> None:
        """Verify Section 8.3 specifies interaction rules with existing repo scripts."""
        compat_section = self.content[self.content.find("8.3. Tương thích với Scripts"):self.content.find("## 9. Checklist")]
        self.assertIn("deploy/migrate_database.py", compat_section)
        self.assertIn("scripts/run_p5_vps_preflight.py", compat_section)
        self.assertIn("scripts/probe_p9_backup_restore_mysql.py", compat_section)
        self.assertIn("scripts/reseed_db.*", compat_section)
        self.assertIn("dev-purge-data", compat_section)


if __name__ == "__main__":
    unittest.main()
