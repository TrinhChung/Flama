#!/usr/bin/env python3
"""Block a frontend release until production runs the backend it calls.

Cloudflare Pages publishes the SPA within seconds, while the VPS backend
release runs migrations and readiness checks first and can fail or roll
back. A SPA published ahead of its backend calls endpoints that do not exist
yet. This gate reads the commit the live backend reports on /api/health and
passes only when that release already contains every backend runtime change
up to the frontend commit about to be published.

Usage:
    python scripts/check_backend_release.py \\
        --health-url https://be-flama.stmtp.com/api/health \\
        --target-sha "$GITHUB_SHA"
"""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib import request as urllib_request

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.run_tests import DEPLOY_RUNTIME_SOURCE_PATTERNS  # noqa: E402

MAX_LISTED_FILES = 20


class GateError(RuntimeError):
    """The live backend cannot serve the frontend commit being published."""

    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.details = details or []


def fetch_live_release(
    health_url: str,
    *,
    attempts: int,
    delay_seconds: float,
    opener=urllib_request.urlopen,
) -> str:
    """Return the commit /api/health reports, retrying a restarting backend."""
    last_problem = "no attempt made"
    for attempt in range(1, attempts + 1):
        request = urllib_request.Request(
            health_url,
            headers={"Accept": "application/json", "Cache-Control": "no-cache"},
        )
        try:
            with opener(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            # HTTPError/URLError are OSError; a non-JSON body is ValueError.
            last_problem = str(exc)
        else:
            if isinstance(payload, dict) and payload.get("status") == "ok":
                release = payload.get("release")
                if isinstance(release, str) and release:
                    return release
            last_problem = f"health payload has no release: {payload!r}"
        if attempt < attempts:
            print(
                f"Live backend release not readable yet "
                f"(attempt {attempt}/{attempts}): {last_problem}",
                file=sys.stderr,
            )
            time.sleep(delay_seconds)
    raise GateError(
        f"Could not read the live backend release from {health_url}: {last_problem}"
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _resolve_commit(repo: Path, sha: str, label: str) -> str:
    result = _git(repo, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
    if result.returncode != 0:
        raise GateError(
            f"The {label} commit {sha} is not in this checkout's history. "
            "Checkout needs fetch-depth: 0, and the backend must be deployed "
            "from master."
        )
    return result.stdout.strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = _git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    if result.returncode not in (0, 1):
        raise GateError(f"git merge-base failed: {result.stderr.strip()}")
    return result.returncode == 0


def backend_runtime_changes(paths: list[str]) -> list[str]:
    """Keep the paths that only reach users through a backend deploy."""
    return [
        path
        for path in paths
        if any(
            fnmatch.fnmatch(path, pattern)
            for pattern in DEPLOY_RUNTIME_SOURCE_PATTERNS
        )
    ]


def evaluate(repo: Path, live_sha: str, target_sha: str) -> str:
    """Explain why the live backend can serve target_sha, or raise GateError."""
    live = _resolve_commit(repo, live_sha, "live backend")
    target = _resolve_commit(repo, target_sha, "frontend")

    if live == target:
        return f"Live backend already runs {target}."
    if _is_ancestor(repo, target, live):
        return (
            f"Live backend runs {live}, which is newer than frontend {target}; "
            "backend changes must stay compatible with the previous SPA."
        )
    if not _is_ancestor(repo, live, target):
        raise GateError(
            f"Live backend {live} is not on the history of frontend {target}. "
            "Redeploy the backend from master before publishing the frontend."
        )

    diff = _git(repo, "diff", "--name-only", "--no-renames", live, target)
    if diff.returncode != 0:
        raise GateError(f"git diff failed: {diff.stderr.strip()}")
    pending = backend_runtime_changes(diff.stdout.split())
    if pending:
        listed = pending[:MAX_LISTED_FILES]
        if len(pending) > len(listed):
            listed.append(f"... and {len(pending) - len(listed)} more")
        raise GateError(
            f"Live backend {live} is missing {len(pending)} backend runtime "
            f"change(s) that frontend {target} may call. Run 'Deploy Flama "
            "Backend to Hostinger VPS' for master first, then re-run this job.",
            listed,
        )
    return (
        f"Live backend {live} has no backend runtime changes pending before "
        f"frontend {target}."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--health-url", required=True)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--attempts", type=int, default=10)
    parser.add_argument("--delay-seconds", type=float, default=6.0)
    args = parser.parse_args(argv)

    try:
        live = fetch_live_release(
            args.health_url,
            attempts=args.attempts,
            delay_seconds=args.delay_seconds,
        )
        summary = evaluate(ROOT_DIR, live, args.target_sha)
    except GateError as exc:
        print(f"::error title=Backend release gate::{exc}")
        for detail in exc.details:
            print(f"  {detail}")
        return 1

    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
