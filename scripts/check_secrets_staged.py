#!/usr/bin/env python3
"""Security scanner for staged changes (pre-commit) or the whole tracked tree (CI).

Verifies that changes do not contain hardcoded credentials, production IP
addresses, gateway secrets, or forbidden deployment configurations.
Zero external pip dependencies required (runs on standard library).

Real production values (server IPs, retired secrets) are never written in this
public file. They are read at runtime from the FLAMA_FORBIDDEN_LITERALS
environment variable (CI secret) and from the private submodule file
infra-vpn/flama/security/forbidden_literals.txt (one value per line).

Findings report file and line only, never the matched content, so CI logs of
this public repository cannot repeat a leaked value.

Usage:
    python scripts/check_secrets_staged.py          # staged diff (pre-commit)
    python scripts/check_secrets_staged.py --all    # every tracked file (CI)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_LITERALS_ENV = "FLAMA_FORBIDDEN_LITERALS"
FORBIDDEN_LITERALS_FILE = Path("infra-vpn/flama/security/forbidden_literals.txt")

# Paths exempt from secret checks: the private submodule and the scanner rule files themselves.
ALLOWLIST_PATHS: list[re.Pattern[str]] = [
    re.compile(r"^infra-vpn/"),
    re.compile(r"^\.gitleaks\.toml$"),
    re.compile(r"^scripts/check_secrets_staged\.py$"),
]

# Forbidden file patterns (must not be committed directly to public repo)
FORBIDDEN_FILE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(?:^|/).*nginx\.conf$"),
        "Production Nginx configuration belongs in infra-vpn/flama/nginx/ (generic public templates must end with .nginx.conf.example)",
    ),
    (
        re.compile(r".*\.service$"),
        "Production systemd service units belong in infra-vpn/flama/systemd/ (generic public templates must end with .service.example)",
    ),
    (
        re.compile(r"(?:^|/)\.env(?:$|\.(?!example).*$)"),
        "Environment secret file must never be committed to repository (use .env_example or .env.example)",
    ),
    (
        re.compile(r".*\.(?:key|pem|pfx|p12)$"),
        "Cryptographic private keys or certificate bundles must not be committed to repository",
    ),
]

# Sensitive content rules applied to added lines (staged mode) or every line (--all mode)
RULES: list[dict[str, object]] = [
    {
        "id": "flama-gateway-secret",
        "description": "Flama Gateway Secret token (flama_gw_sec_*)",
        "pattern": re.compile(r"(?i)flama_gw_sec_[a-f0-9]{32}"),
    },
    {
        "id": "flama-internal-secret",
        "description": "Flama internal service secret (flama_int_sec_*)",
        "pattern": re.compile(r"(?i)flama_int_sec_[a-f0-9]{32}"),
    },
    {
        "id": "internal-wireguard-ip",
        "description": "Internal WireGuard mesh host address (use wg-app-server, wg-gateway, wg-worker212)",
        "pattern": re.compile(r"\b10\.10\.0\.(?:25[0-4]|2[0-4]\d|1\d\d|[1-9]\d?)\b"),
    },
    {
        "id": "flama-private-key",
        "description": "Unencrypted Private Key header",
        "pattern": re.compile(r"(?i)-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----"),
    },
    {
        "id": "personal-admin-email",
        "description": "Personal admin email in deployment or workflow files",
        "pattern": re.compile(r"\b[a-zA-Z0-9._%+-]+@gmail\.com\b"),
        "path_filter": re.compile(r"^(?:\.github/workflows/|deploy/)"),
    },
    {
        "id": "production-ssl-cert-path",
        "description": "Production SSL private key path in configs",
        "pattern": re.compile(r"/etc/letsencrypt/live/[a-zA-Z0-9._-]+/privkey\.pem"),
    },
]

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def normalize_path(path: str) -> str:
    """Normalize file path to forward slashes with quotes stripped."""
    p = path.strip().strip('"').replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return p


def is_allowlisted(path: str) -> bool:
    """Check whether a path is exempt from secret scanning."""
    norm = normalize_path(path)
    return any(pattern.search(norm) for pattern in ALLOWLIST_PATHS)


def load_forbidden_literals() -> list[re.Pattern[str]]:
    """Build matchers for real production values supplied outside the public repository."""
    values = re.split(r"[\s,]+", os.environ.get(FORBIDDEN_LITERALS_ENV, ""))
    if FORBIDDEN_LITERALS_FILE.is_file():
        for line in FORBIDDEN_LITERALS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                values.append(line)
    patterns = []
    for value in sorted({v for v in values if len(v) >= 7}):
        # Also catch regex-escaped IPs such as 192\.0\.2\.1 inside scanner or nginx rules.
        body = re.escape(value).replace(r"\.", r"\\?\.")
        patterns.append(re.compile(r"(?<![0-9A-Za-z_.])" + body + r"(?![0-9A-Za-z_])"))
    return patterns


def _run_git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout


def scan_line(path: str, line_no: int, content: str, literals: list[re.Pattern[str]]) -> list[str]:
    """Return findings for one line without echoing the matched content."""
    findings: list[str] = []
    for rule in RULES:
        path_filter = rule.get("path_filter")
        if isinstance(path_filter, re.Pattern) and not path_filter.search(path):
            continue
        pattern = rule["pattern"]
        if isinstance(pattern, re.Pattern) and pattern.search(content):
            findings.append(f"[LEAK DETECTED] {path}:{line_no} | Rule: {rule['id']} ({rule['description']})")
    if any(pattern.search(content) for pattern in literals):
        findings.append(f"[LEAK DETECTED] {path}:{line_no} | Rule: forbidden-production-literal (real server IP or retired secret)")
    return findings


def check_staged_files(literals: list[re.Pattern[str]]) -> list[str]:
    """Inspect staged files and diffs for forbidden files and sensitive data."""
    errors: list[str] = []

    staged_files = [
        normalize_path(line)
        for line in _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"]).splitlines()
        if line.strip()
    ]
    for file_path in staged_files:
        if is_allowlisted(file_path):
            continue
        for pattern, reason in FORBIDDEN_FILE_PATTERNS:
            if pattern.search(file_path):
                errors.append(f"[FORBIDDEN FILE] {file_path}: {reason}")

    current_file: str | None = None
    line_no = 0
    for line in _run_git(["diff", "--cached", "-U0"]).splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip().strip('"')
            if target.startswith("b/"):
                current_file = normalize_path(target[2:])
            elif target == "/dev/null":
                current_file = None
            else:
                current_file = normalize_path(target)
            continue
        hunk = _HUNK_RE.match(line)
        if hunk:
            line_no = int(hunk.group(1))
            continue
        if not current_file or is_allowlisted(current_file):
            continue
        # Inspect only added lines (starts with + but not +++)
        if line.startswith("+") and not line.startswith("+++"):
            errors.extend(scan_line(current_file, line_no, line[1:], literals))
            line_no += 1

    return errors


def check_tracked_tree(literals: list[re.Pattern[str]]) -> list[str]:
    """Inspect every tracked text file (CI mode)."""
    errors: list[str] = []
    for raw_path in _run_git(["-c", "core.quotepath=off", "ls-files", "-z"]).split("\0"):
        path = normalize_path(raw_path)
        if not path or is_allowlisted(path):
            continue
        try:
            data = Path(path).read_bytes()
        except OSError:
            continue
        if b"\0" in data:
            continue
        for line_no, content in enumerate(data.decode("utf-8", errors="replace").splitlines(), start=1):
            errors.extend(scan_line(path, line_no, content, literals))
    return errors


def main() -> int:
    scan_all = "--all" in sys.argv[1:]
    literals = load_forbidden_literals()
    if not literals:
        print(
            f"[secret-scanner] WARNING: no {FORBIDDEN_LITERALS_ENV} and no {FORBIDDEN_LITERALS_FILE}; "
            "real server IPs and retired secrets are not checked.",
            file=sys.stderr,
        )
    try:
        errors = check_tracked_tree(literals) if scan_all else check_staged_files(literals)
    except Exception as e:
        print(f"[secret-scanner] ERROR: Failed to read git data: {e}", file=sys.stderr)
        return 1

    if errors:
        print("\n" + "=" * 76, file=sys.stderr)
        print("❌ SECURITY SCANNER: REJECTED SENSITIVE DATA", file=sys.stderr)
        print("=" * 76, file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        print("\nRemediation Instructions:", file=sys.stderr)
        print("1. Remove all hardcoded real IPs, secrets, tokens, and private keys from the lines above.", file=sys.stderr)
        print("2. For documentation, use RFC 5737 IPs (e.g. 198.51.100.141, 203.0.113.226, 192.0.2.151).", file=sys.stderr)
        print("3. Refer to WireGuard hosts by name: wg-app-server, wg-gateway, wg-worker212.", file=sys.stderr)
        print("4. Move production deployment scripts & Nginx/systemd configs to submodule: infra-vpn/flama/", file=sys.stderr)
        print("5. Store real credentials in GitHub Environment Secrets or local .env (never commit .env).", file=sys.stderr)
        print("=" * 76 + "\n", file=sys.stderr)
        return 1

    scope = "Tracked files" if scan_all else "Staged changes"
    print(f"[secret-scanner] {scope} passed security checks (no secrets or production IPs detected).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
