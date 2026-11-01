#!/usr/bin/env python3
"""Pre-commit security scanner for staged files and diffs.

Verifies that staged changes do not contain hardcoded credentials, production
IP addresses, gateway secrets, or forbidden deployment configurations.
Zero external pip dependencies required (runs on standard library).
"""

from __future__ import annotations

import re
import subprocess
import sys

# Paths exempt from secret checks (submodule, incident documentation, tests, teamwork metadata)
ALLOWLIST_PATHS: list[re.Pattern[str]] = [
    re.compile(r"^infra-vpn/"),
    re.compile(r"^\.agents/teamwork/"),
    re.compile(r"^docs/ops/incidents/"),
    re.compile(r"^docs/plans/"),
    re.compile(r"^ISSUE_PRODUCTION_CONFIG_EXPOSURE\.md$"),
    re.compile(r"^AGENTS\.md$"),
    re.compile(r"^tests/"),
    re.compile(r"^docs/reports/2026-11-01_GIT_HISTORY_LEAK_INVESTIGATION_REPORT\.md$"),
    re.compile(r"^docs/runbooks/GIT_HISTORY_SCRUB_RUNBOOK\.md$"),
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

# Sensitive content rules applied to added lines in staged diffs
RULES: list[dict[str, object]] = [
    {
        "id": "flama-gateway-secret",
        "description": "Flama Gateway Secret token (flama_gw_sec_*)",
        "pattern": re.compile(r"(?i)flama_gw_sec_[a-f0-9]{32}"),
    },
    {
        "id": "production-server-public-ip",
        "description": "Hardcoded production server public IP address (Hostinger, Oracle Gateway, Worker 212)",
        "pattern": re.compile(r"\b(?:187\.77\.131\.151|161\.33\.193\.141|132\.145\.115\.226)\b"),
    },
    {
        "id": "internal-wireguard-ip",
        "description": "Internal WireGuard mesh IP address",
        "pattern": re.compile(r"\b10\.10\.0\.[4-6]\b"),
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


def check_staged_files() -> list[str]:
    """Inspect staged files and diffs for forbidden files and sensitive data."""
    errors: list[str] = []

    # 1. Inspect staged file names
    cmd_files = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    proc_files = subprocess.run(
        cmd_files,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    staged_files = [
        normalize_path(line)
        for line in proc_files.stdout.splitlines()
        if line.strip()
    ]

    for file_path in staged_files:
        if is_allowlisted(file_path):
            continue
        for pattern, reason in FORBIDDEN_FILE_PATTERNS:
            if pattern.search(file_path):
                errors.append(f"[FORBIDDEN FILE] {file_path}: {reason}")

    # 2. Inspect staged diff additions
    diff_cmd = ["git", "diff", "--cached", "-U0"]
    diff_proc = subprocess.run(
        diff_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )

    current_file: str | None = None

    for line in diff_proc.stdout.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip().strip('"')
            if target.startswith("b/"):
                current_file = normalize_path(target[2:])
            elif target == "/dev/null":
                current_file = None
            else:
                current_file = normalize_path(target)
            continue

        if not current_file or is_allowlisted(current_file):
            continue

        # Inspect only added lines (starts with + but not +++)
        if line.startswith("+") and not line.startswith("+++"):
            added_content = line[1:]
            for rule in RULES:
                path_filter = rule.get("path_filter")
                if isinstance(path_filter, re.Pattern) and not path_filter.search(current_file):
                    continue

                pattern = rule["pattern"]
                if isinstance(pattern, re.Pattern) and pattern.search(added_content):
                    errors.append(
                        f"[LEAK DETECTED] File: {current_file} | Rule: {rule['id']} ({rule['description']})\n"
                        f"    Content snippet: {added_content.strip()[:100]}"
                    )

    return errors


def main() -> int:
    try:
        errors = check_staged_files()
    except Exception as e:
        print(f"[pre-commit-scanner] ERROR: Failed to execute git diff: {e}", file=sys.stderr)
        return 1

    if errors:
        print("\n" + "=" * 76, file=sys.stderr)
        print("❌ PRE-COMMIT SECURITY SCANNER: REJECTED SENSITIVE DATA IN COMMIT", file=sys.stderr)
        print("=" * 76, file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        print("\nRemediation Instructions:", file=sys.stderr)
        print("1. Remove all hardcoded real IPs, secrets, tokens, and private keys from the files above.", file=sys.stderr)
        print("2. For documentation, use RFC 5737 IPs (e.g. 198.51.100.141, 203.0.113.226, 192.0.2.151).", file=sys.stderr)
        print("3. Move production deployment scripts & Nginx/systemd configs to submodule: infra-vpn/flama/", file=sys.stderr)
        print("4. Store real credentials in GitHub Environment Secrets or local .env (never commit .env).", file=sys.stderr)
        print("=" * 76 + "\n", file=sys.stderr)
        return 1

    print("[pre-commit-scanner] Staged changes passed security checks (no secrets or production IPs detected).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
