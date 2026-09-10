"""Run the Phase 4 audit twice with one frozen observation time.

The dedicated database URI is accepted only through the process environment and
is never copied into an artifact. The audit itself verifies the connected MySQL
principal is SELECT-only before reading application tables.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


AUDIT_URI_ENV = "STUDY_AUDIT_DATABASE_URI"
BUNDLE_SCHEMA_VERSION = "study-phase4-preflight-bundle.v1"


def _canonical_json(value: Any, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _diff_paths(left: Any, right: Any, *, prefix: str = "$", limit: int = 200) -> list[str]:
    differences: list[str] = []

    def walk(a: Any, b: Any, path: str) -> None:
        if len(differences) >= limit:
            return
        if type(a) is not type(b):
            differences.append(path)
            return
        if isinstance(a, dict):
            for key in sorted(set(a).union(b)):
                child = f"{path}.{key}"
                if key not in a or key not in b:
                    differences.append(child)
                else:
                    walk(a[key], b[key], child)
            return
        if isinstance(a, list):
            if len(a) != len(b):
                differences.append(f"{path}.length")
            for index, (a_item, b_item) in enumerate(zip(a, b)):
                walk(a_item, b_item, f"{path}[{index}]")
            return
        if a != b:
            differences.append(path)

    walk(left, right, prefix)
    return differences


def _run_once(
    *,
    repo_root: Path,
    python_executable: str,
    observed_at: str,
    child_env: dict[str, str],
) -> tuple[dict[str, Any], int, int]:
    command = [
        python_executable,
        "wsgi_audit.py",
        "--compact",
        "--observed-at",
        observed_at,
    ]
    started = time.perf_counter()
    process = subprocess.run(
        command,
        cwd=repo_root,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = round((time.perf_counter() - started) * 1000)
    try:
        report = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Audit subprocess did not emit one valid JSON document; stderr was "
            f"{len(process.stderr.encode('utf-8'))} bytes."
        ) from exc
    if not isinstance(report, dict):
        raise RuntimeError("Audit subprocess JSON root must be an object.")
    return report, int(process.returncode), duration_ms


def _safe_output_directory(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.exists() and any(resolved.iterdir()):
        raise RuntimeError("Output directory must not already contain files.")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a redacted two-run Phase 4 MySQL preflight bundle."
    )
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--observed-at",
        default=None,
        help="Frozen ISO-8601 observation time; defaults to current UTC second.",
    )
    args = parser.parse_args(argv)

    audit_uri = os.getenv(AUDIT_URI_ENV, "").strip()
    if not audit_uri:
        parser.error(f"{AUDIT_URI_ENV} must contain the dedicated SELECT-only MySQL URI")
    if not audit_uri.lower().startswith(("mysql://", "mysql+")):
        parser.error(f"{AUDIT_URI_ENV} must use a MySQL SQLAlchemy URI")

    repo_root = Path(__file__).resolve().parent.parent
    output_dir = _safe_output_directory(args.output_dir)
    if args.observed_at:
        observed_at = str(args.observed_at).strip()
    else:
        observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    child_env = dict(os.environ)
    child_env["SQLALCHEMY_DATABASE_URI"] = audit_uri
    child_env.pop(AUDIT_URI_ENV, None)

    reports: list[dict[str, Any]] = []
    exit_codes: list[int] = []
    durations_ms: list[int] = []
    try:
        for _ in range(2):
            report, exit_code, duration_ms = _run_once(
                repo_root=repo_root,
                python_executable=sys.executable,
                observed_at=observed_at,
                child_env=child_env,
            )
            reports.append(report)
            exit_codes.append(exit_code)
            durations_ms.append(duration_ms)

        for report in reports:
            safety = report.get("phase4_preflight", {}).get("connection_safety", {})
            if safety.get("current_mysql_evidence") is not True:
                raise RuntimeError(
                    "Audit report is not verified current MySQL SELECT-only evidence."
                )

        canonical_reports = [_canonical_json(report) for report in reports]
        differences = _diff_paths(reports[0], reports[1])
        comparison = {
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "observed_at_argument": observed_at,
            "command": ["python", "wsgi_audit.py", "--compact", "--observed-at", observed_at],
            "run_exit_codes": exit_codes,
            "run_durations_ms": durations_ms,
            "report_sha256": [_sha256(payload) for payload in canonical_reports],
            "deterministic_equal": not differences,
            "different_paths": differences,
            "different_paths_truncated": len(differences) >= 200,
            "phase4_gate_status": [
                report.get("phase4_preflight", {}).get("gate", {}).get("status")
                for report in reports
            ],
            "phase4_gate_blockers": [
                report.get("phase4_preflight", {}).get("gate", {}).get("blockers", [])
                for report in reports
            ],
        }

        artifact_payloads = {
            "run-1.json": _canonical_json(reports[0], pretty=True) + "\n",
            "run-2.json": _canonical_json(reports[1], pretty=True) + "\n",
            "comparison.json": _canonical_json(comparison, pretty=True) + "\n",
        }
        for name, payload in artifact_payloads.items():
            (output_dir / name).write_text(payload, encoding="utf-8")
        checksum_lines = [
            f"{_sha256(payload)}  {name}"
            for name, payload in sorted(artifact_payloads.items())
        ]
        (output_dir / "SHA256SUMS").write_text(
            "\n".join(checksum_lines) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"Phase 4 preflight bundle failed: {exc}", file=sys.stderr)
        return 2

    print(str(output_dir))
    if differences or any(
        report.get("phase4_preflight", {}).get("gate", {}).get("blockers")
        for report in reports
    ):
        return 2
    return max(exit_codes)


if __name__ == "__main__":
    raise SystemExit(main())
