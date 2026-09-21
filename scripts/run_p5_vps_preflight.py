"""Collect a P5 entry audit from the deployed read-only audit app on the VPS.

The remote half creates a random, localhost-only MySQL principal with SELECT
and SHOW VIEW on ``flama`` only, runs the existing two-run audit bundle, and
drops/verifies that exact principal in ``finally``. It never starts the serving
app or runs migrations. The root-owned audit bundle remains on the VPS for
review; this local launcher prints only a non-sensitive summary.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
from urllib.parse import quote_plus, urlencode


SSH_ALIAS = "chung_hostinger_vps"
RELEASE_ROOT = Path("/opt/flama/current")
REMOTE_PYTHON = "/opt/flama/venv/bin/python"
DATABASE_NAME = "flama"
USER_PATTERN = re.compile(r"^p5audit_[0-9a-f]{12}$")


def _mysql(sql: str) -> str:
    result = subprocess.run(
        ["mysql", "--batch", "--skip-column-names"],
        input=sql,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        # Do not echo a failed CREATE USER query or any credential-bearing SQL.
        raise RuntimeError(f"MySQL admin command failed (exit {result.returncode}).")
    return result.stdout.strip()


def _remote_main() -> int:
    if os.geteuid() != 0:
        raise RuntimeError("The remote audit launcher requires VPS root socket access.")
    if not (RELEASE_ROOT / "wsgi_audit.py").is_file() or not (
        RELEASE_ROOT / "scripts" / "run_phase4_preflight_bundle.py"
    ).is_file():
        raise RuntimeError("The deployed read-only audit entry points are missing.")

    socket_path = _mysql("SELECT @@socket;")
    if not socket_path.startswith("/"):
        raise RuntimeError("MySQL did not report an absolute Unix socket path.")
    username = f"p5audit_{secrets.token_hex(6)}"
    if not USER_PATTERN.fullmatch(username):
        raise RuntimeError("Unsafe generated audit principal name.")
    principal = f"'{username}'@'localhost'"
    existing = _mysql(
        "SELECT COUNT(*) FROM mysql.user "
        f"WHERE User='{username}' AND Host='localhost';"
    )
    if existing != "0":
        raise RuntimeError("Generated audit principal already exists; refusing reuse.")

    password = secrets.token_hex(32)
    creation_attempted = False
    try:
        creation_attempted = True
        _mysql(
            f"CREATE USER {principal} IDENTIFIED WITH mysql_native_password "
            f"BY '{password}';"
        )
        _mysql(f"GRANT SELECT, SHOW VIEW ON `{DATABASE_NAME}`.* TO {principal};")

        observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        bundle_dir = Path(tempfile.mkdtemp(prefix="p5_readonly_preflight_", dir="/root"))
        bundle_dir.chmod(0o700)
        database_uri = (
            f"mysql+pymysql://{username}:{quote_plus(password)}@localhost/"
            f"{DATABASE_NAME}?{urlencode({'unix_socket': socket_path, 'charset': 'utf8mb4'})}"
        )
        child_env = dict(os.environ)
        child_env["STUDY_AUDIT_DATABASE_URI"] = database_uri
        child_env["STARTUP_RUN_MAINTENANCE"] = "0"
        command = [
            REMOTE_PYTHON,
            "scripts/run_phase4_preflight_bundle.py",
            str(bundle_dir),
            "--observed-at",
            observed_at,
        ]
        bundle = subprocess.run(
            command,
            cwd=RELEASE_ROOT,
            env=child_env,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        comparison_file = bundle_dir / "comparison.json"
        if not comparison_file.is_file():
            raise RuntimeError(
                f"Audit bundle produced no comparison report (exit {bundle.returncode}, "
                f"stderr bytes {len(bundle.stderr.encode('utf-8'))})."
            )
        comparison = json.loads(comparison_file.read_text(encoding="utf-8"))
        report = json.loads((bundle_dir / "run-1.json").read_text(encoding="utf-8"))
        safety = report.get("phase4_preflight", {}).get("connection_safety", {})
        if safety.get("current_mysql_evidence") is not True:
            raise RuntimeError("Audit did not verify the SELECT-only principal.")
        result = {
            "observed_at": observed_at,
            "bundle_dir": str(bundle_dir),
            "bundle_exit_code": bundle.returncode,
            "select_only_verified": safety.get("select_only_verified"),
            "mysql_version": safety.get("server_version"),
            "deterministic_equal": comparison.get("deterministic_equal"),
            "different_paths": comparison.get("different_paths"),
            "run_exit_codes": comparison.get("run_exit_codes"),
            "report_sha256": comparison.get("report_sha256"),
            "phase4_gate_status": comparison.get("phase4_gate_status"),
            "phase4_gate_blockers": comparison.get("phase4_gate_blockers"),
            "audit_verdict": report.get("verdicts", {}).get("overall_status"),
            "audit_blockers": report.get("verdicts", {}).get("block", []),
        }
    finally:
        if creation_attempted:
            # A disconnected CLI can report failure after the server committed
            # CREATE USER. The generated name was checked absent beforehand.
            if _mysql(
                "SELECT COUNT(*) FROM mysql.user "
                f"WHERE User='{username}' AND Host='localhost';"
            ) == "1":
                _mysql(f"DROP USER {principal};")
            if _mysql(
                "SELECT COUNT(*) FROM mysql.user "
                f"WHERE User='{username}' AND Host='localhost';"
            ) != "0":
                raise RuntimeError("Temporary SELECT-only principal was not removed.")

    result["temporary_principal_removed"] = True
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _local_main() -> int:
    source = Path(__file__).read_text(encoding="utf-8")
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        SSH_ALIAS,
        REMOTE_PYTHON,
        "-",
        "--remote",
    ]
    result = subprocess.run(
        command,
        input=source,
        capture_output=True,
        text=True,
        check=False,
        timeout=360,
    )
    if result.returncode:
        raise RuntimeError(
            f"VPS read-only preflight failed (exit {result.returncode}; "
            f"stderr bytes {len(result.stderr.encode('utf-8'))})."
        )
    payload = json.loads(result.stdout)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--remote"]:
            sys.exit(_remote_main())
        if sys.argv[1:] == ["--production-readonly-audit"]:
            sys.exit(_local_main())
        raise RuntimeError(
            "Run explicitly with --production-readonly-audit; this creates and "
            "removes one scoped temporary MySQL principal on the VPS."
        )
    except Exception as exc:
        print(f"P5 preflight launcher: {exc}", file=sys.stderr)
        sys.exit(2)
