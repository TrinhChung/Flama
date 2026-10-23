#!/usr/bin/env python3
"""Run independent MySQL contract probes concurrently and fail if any fails.

Only pass probes that create, guard and drop their own generated schema and
touch no server-wide state; the PR-C inventory in
docs/plans/TEST_CICD_UPGRADE_IMPLEMENTATION_PLAN_2026-10-23.md lists them.
Each probe keeps its exact command line and environment. Output is spooled per
probe and printed whole when it finishes, followed by a timing summary. A probe
running longer than --timeout seconds is killed and fails the run.

Usage:
  python scripts/run_mysql_probes.py --jobs 2 \
      --probe "scripts/probe_forecast_snapshots_mysql.py --output output/forecast.json" \
      --probe "scripts/probe_p7_session_retention_mysql.py"
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

ROOT_DIR = Path(__file__).resolve().parent.parent


def run_probe(command: list[str], timeout: float | None = None) -> tuple[int, float, str]:
    start = time.time()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    note = ""
    with tempfile.TemporaryFile() as spool:
        try:
            returncode = subprocess.run(
                [sys.executable, *command],
                cwd=str(ROOT_DIR),
                env=env,
                stdout=spool,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            ).returncode
        except subprocess.TimeoutExpired:
            # subprocess.run kills the probe before raising.
            returncode = 124
            note = f"\n[TIMEOUT] probe stopped after {timeout:.0f}s"
        except OSError as exc:
            return 1, time.time() - start, f"[PROBE ERROR] {exc!r}"
        spool.seek(0)
        output = spool.read().decode("utf-8", errors="replace") + note
    return returncode, time.time() - start, output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=2, help="Probes run at the same time.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=0,
        help="Kill and fail a probe running longer than this many seconds (0 = no limit).",
    )
    parser.add_argument(
        "--probe",
        action="append",
        required=True,
        help="Probe script and arguments, relative to the repository root.",
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.timeout < 0:
        parser.error("--timeout must not be negative")
    # POSIX splitting treats a backslash as an escape; accept Windows paths.
    commands = [shlex.split(probe.replace("\\", "/")) for probe in args.probe]
    for command in commands:
        if not command or not (ROOT_DIR / command[0]).is_file():
            parser.error(f"probe script not found: {command[0] if command else ''!r}")

    start = time.time()
    timings: list[tuple[str, int, float]] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {
            executor.submit(run_probe, command, args.timeout or None): command for command in commands
        }
        for future in as_completed(futures):
            command = futures[future]
            returncode, elapsed, output = future.result()
            label = "PASS" if returncode == 0 else f"FAIL (exit {returncode})"
            print(f"::group::{command[0]} {label} in {elapsed:.1f}s")
            print(output.rstrip())
            print("::endgroup::")
            sys.stdout.flush()
            timings.append((" ".join(command), returncode, elapsed))

    print(f"\nProbe timings ({args.jobs} at a time, {time.time() - start:.1f}s wall):")
    for name, returncode, elapsed in sorted(timings, key=lambda item: -item[2]):
        print(f"  {elapsed:7.1f}s  {'ok  ' if returncode == 0 else 'FAIL'}  {name}")
    return 0 if all(returncode == 0 for _, returncode, _ in timings) else 1


if __name__ == "__main__":
    sys.exit(main())
