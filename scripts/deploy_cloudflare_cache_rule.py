#!/usr/bin/env python3
"""One-shot script to create a Cloudflare Cache Rule for /media/proxy/* via Rulesets API.

Usage:
    python scripts/deploy_cloudflare_cache_rule.py

Reads CLOUDFLARE_API_TOKEN (or legacy CLOUD_FLARE_TOKEN) and CLOUDFLARE_ZONE_ID
from .env or environment. Set CLOUDFLARE_ZONE_ID to the flama.vn zone ID.
Requires the token to have Zone > Cache Rules > Edit permission. Prefix purge
uses CLOUDFLARE_GLOBAL_API_KEY with CLOUDFLARE_EMAIL (or EMAIL_SMTP_USER) when
available, otherwise the API token must also have Cache Purge permission.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError

PHASE = "http_request_cache_settings"
RULE_DESCRIPTION = "Cache media proxy assets at edge (bounded audio/image TTL)"
LEGACY_RULE_DESCRIPTION = "Cache media proxy assets at edge (immutable audio/image)"
MATCH_EXPRESSION = (
    '(http.host eq "api.flama.vn"'
    ' and (http.request.uri.path eq "/media/proxy"'
    ' or starts_with(http.request.uri.path, "/media/proxy/")))'
)
MEDIA_CACHE_PREFIX = "api.flama.vn/media/proxy/"


def _load_optional_setting(keys: tuple[str, ...]) -> str:
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            for key in keys:
                if line.startswith(f"{key}="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value
    return ""


def _load_token() -> str:
    token = _load_optional_setting(("CLOUDFLARE_API_TOKEN", "CLOUD_FLARE_TOKEN"))
    if token:
        return token
    print("ERROR: CLOUDFLARE_API_TOKEN not found in environment or .env", file=sys.stderr)
    sys.exit(1)


def _load_global_auth() -> tuple[str, str] | None:
    api_key = _load_optional_setting(("CLOUDFLARE_GLOBAL_API_KEY",))
    email = _load_optional_setting(("CLOUDFLARE_EMAIL", "EMAIL_SMTP_USER"))
    return (email, api_key) if email and api_key else None


def _cf_api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    return _cf_api_with_headers(method, path, {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }, body)


def _cf_api_with_headers(
    method: str,
    path: str,
    headers: dict[str, str],
    body: dict | None = None,
) -> dict:
    url = f"https://api.cloudflare.com/client/v4{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib_request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib_request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as exc:
        error_body = exc.read().decode(errors="replace")
        print(f"HTTP {exc.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


def _build_cache_rule() -> dict:
    return {
        "expression": MATCH_EXPRESSION,
        "description": RULE_DESCRIPTION,
        "action": "set_cache_settings",
        "action_parameters": {
            "cache": True,
            "edge_ttl": {
                "mode": "override_origin",
                "default": 86400,
                "status_code_ttl": [
                    {
                        "status_code": 200,
                        "value": 86400,
                    },
                    {
                        "status_code": 206,
                        "value": 86400,
                    },
                    {
                        "status_code_range": {
                            "from": 400,
                            "to": 499,
                        },
                        "value": 0,
                    },
                    {
                        "status_code_range": {
                            "from": 500,
                            "to": 599,
                        },
                        "value": 0,
                    },
                ],
            },
            "browser_ttl": {
                "mode": "override_origin",
                "default": 3600,
            },
        },
    }


def main(*, purge_existing: bool = False) -> None:
    zone_id = _load_optional_setting(("CLOUDFLARE_ZONE_ID",))
    if not zone_id:
        print("ERROR: Set CLOUDFLARE_ZONE_ID to the flama.vn zone ID in environment or .env", file=sys.stderr)
        sys.exit(1)
    token = _load_token()
    print(f"Zone: {zone_id}")
    print(f"Phase: {PHASE}")

    # Check for existing ruleset in this phase
    rulesets = _cf_api("GET", f"/zones/{zone_id}/rulesets", token)
    existing_ruleset_id = None
    for rs in rulesets.get("result") or []:
        if rs.get("phase") == PHASE and rs.get("kind") == "zone":
            existing_ruleset_id = rs["id"]
            break

    cache_rule = _build_cache_rule()

    if existing_ruleset_id:
        print(f"Found existing ruleset: {existing_ruleset_id}")
        # Fetch current rules
        current = _cf_api("GET", f"/zones/{zone_id}/rulesets/{existing_ruleset_id}", token)
        rules = list(current.get("result", {}).get("rules") or [])
        existing_rule = next(
            (
                rule
                for rule in rules
                if rule.get("description") in {RULE_DESCRIPTION, LEGACY_RULE_DESCRIPTION}
            ),
            None,
        )
        if existing_rule:
            print("Found existing media cache rule. Reconciling settings...")
            result = _cf_api(
                "PATCH",
                f"/zones/{zone_id}/rulesets/{existing_ruleset_id}/rules/{existing_rule['id']}",
                token,
                cache_rule,
            )
        else:
            rules.append(cache_rule)
            result = _cf_api(
                "PUT",
                f"/zones/{zone_id}/rulesets/{existing_ruleset_id}",
                token,
                {"rules": rules},
            )
    else:
        print("No existing cache ruleset found. Creating new one...")
        result = _cf_api(
            "POST",
            f"/zones/{zone_id}/rulesets",
            token,
            {
                "name": "Flama Media Cache Rules",
                "kind": "zone",
                "phase": PHASE,
                "rules": [cache_rule],
            },
        )

    if result.get("success"):
        print("Cache rule created/updated successfully!")
        ruleset_id = result.get("result", {}).get("id", "unknown")
        print(f"Ruleset ID: {ruleset_id}")
    else:
        print(f"Failed: {json.dumps(result, indent=2)}", file=sys.stderr)
        sys.exit(1)

    if purge_existing:
        purge_body = {"prefixes": [MEDIA_CACHE_PREFIX]}
        global_auth = _load_global_auth()
        if global_auth:
            email, api_key = global_auth
            purge_result = _cf_api_with_headers(
                "POST",
                f"/zones/{zone_id}/purge_cache",
                {
                    "X-Auth-Email": email,
                    "X-Auth-Key": api_key,
                    "Content-Type": "application/json",
                },
                purge_body,
            )
        else:
            purge_result = _cf_api(
                "POST",
                f"/zones/{zone_id}/purge_cache",
                token,
                purge_body,
            )
        if not purge_result.get("success"):
            print(f"Cache purge failed: {json.dumps(purge_result, indent=2)}", file=sys.stderr)
            sys.exit(1)
        print(f"Purged cached responses under: {MEDIA_CACHE_PREFIX}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--purge-existing",
        action="store_true",
        help="Purge existing /media/proxy/ edge objects after reconciling the rule.",
    )
    args = parser.parse_args()
    main(purge_existing=args.purge_existing)
