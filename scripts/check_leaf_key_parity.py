#!/usr/bin/env python3
"""
scripts/check_leaf_key_parity.py

Automated Leaf-Key Parity & Integrity Verification for Flama i18n Locales.
Checks 100% symmetric leaf keys between `vi` (Vietnamese) and `en` (English)
translation dictionaries in `frontend/src/shared/config/i18n/locales/`.

Usage:
    py scripts/check_leaf_key_parity.py                     # Checks all discovered namespaces
    py scripts/check_leaf_key_parity.py --namespace settings,mcp  # Checks specific namespaces
    py scripts/check_leaf_key_parity.py --verbose          # Detailed per-namespace breakdown
"""

import argparse
import json
import os
import re
import sys

# Ensure UTF-8 output encoding across platforms
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_LOCALES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'shared', 'config', 'i18n', 'locales')
)

INTERPOLATION_REGEX = re.compile(r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}')


def flatten_keys(data, prefix=''):
    """
    Recursively extract all leaf keys from nested dictionaries and lists.
    Returns dict mapping full dotted path to value.
    """
    items = {}
    if isinstance(data, dict):
        for k, v in data.items():
            full_k = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(flatten_keys(v, full_k))
            elif isinstance(v, list):
                for idx, item in enumerate(v):
                    list_k = f"{full_k}[{idx}]"
                    if isinstance(item, (dict, list)):
                        items.update(flatten_keys(item, list_k))
                    else:
                        items[list_k] = item
            else:
                items[full_k] = v
    return items


def discover_namespaces(locales_dir):
    """Discover all JSON namespaces available in vi and en."""
    vi_dir = os.path.join(locales_dir, 'vi')
    en_dir = os.path.join(locales_dir, 'en')

    namespaces = set()
    if os.path.isdir(vi_dir):
        for f in os.listdir(vi_dir):
            if f.endswith('.json'):
                namespaces.add(f[:-5])
    if os.path.isdir(en_dir):
        for f in os.listdir(en_dir):
            if f.endswith('.json'):
                namespaces.add(f[:-5])

    return sorted(namespaces)


def verify_namespace(ns, locales_dir, verbose=False):
    """
    Verify parity and structural integrity for a single namespace.
    Returns (passed: bool, errors: list[str], leaf_count: int).
    """
    errors = []
    vi_file = os.path.join(locales_dir, 'vi', f'{ns}.json')
    en_file = os.path.join(locales_dir, 'en', f'{ns}.json')

    if not os.path.isfile(vi_file):
        errors.append(f"[{ns}] Missing Vietnamese locale file: {vi_file}")
        return False, errors, 0
    if not os.path.isfile(en_file):
        errors.append(f"[{ns}] Missing English locale file: {en_file}")
        return False, errors, 0

    try:
        with open(vi_file, 'r', encoding='utf-8') as f:
            vi_data = json.load(f)
    except Exception as e:
        errors.append(f"[{ns}] Syntax error in vi/{ns}.json: {e}")
        return False, errors, 0

    try:
        with open(en_file, 'r', encoding='utf-8') as f:
            en_data = json.load(f)
    except Exception as e:
        errors.append(f"[{ns}] Syntax error in en/{ns}.json: {e}")
        return False, errors, 0

    vi_leaves = flatten_keys(vi_data)
    en_leaves = flatten_keys(en_data)

    vi_keys = set(vi_leaves.keys())
    en_keys = set(en_leaves.keys())

    # 1. Check leaf key parity
    missing_in_en = vi_keys - en_keys
    missing_in_vi = en_keys - vi_keys

    if missing_in_en:
        for k in sorted(missing_in_en):
            errors.append(f"[{ns}] Key present in 'vi' but missing in 'en': '{k}'")
    if missing_in_vi:
        for k in sorted(missing_in_vi):
            errors.append(f"[{ns}] Key present in 'en' but missing in 'vi': '{k}'")

    # 2. Check value integrity for vi
    for k, v in vi_leaves.items():
        if v is None:
            errors.append(f"[{ns}] vi value is null at key: '{k}'")
        elif not isinstance(v, str):
            errors.append(f"[{ns}] vi value is non-string ({type(v).__name__}) at key: '{k}'")
        elif not v.strip():
            errors.append(f"[{ns}] vi value is empty or whitespace at key: '{k}'")

    # 3. Check value integrity for en
    for k, v in en_leaves.items():
        if v is None:
            errors.append(f"[{ns}] en value is null at key: '{k}'")
        elif not isinstance(v, str):
            errors.append(f"[{ns}] en value is non-string ({type(v).__name__}) at key: '{k}'")
        elif not v.strip():
            errors.append(f"[{ns}] en value is empty or whitespace at key: '{k}'")

    # 4. Check interpolation variables symmetry
    common_keys = vi_keys & en_keys
    for k in common_keys:
        vi_val = vi_leaves[k]
        en_val = en_leaves[k]
        if isinstance(vi_val, str) and isinstance(en_val, str):
            vi_vars = set(INTERPOLATION_REGEX.findall(vi_val))
            en_vars = set(INTERPOLATION_REGEX.findall(en_val))
            if vi_vars != en_vars:
                errors.append(
                    f"[{ns}] Interpolation variable mismatch at '{k}':\n"
                    f"       vi variables: {sorted(vi_vars)} (value: \"{vi_val}\")\n"
                    f"       en variables: {sorted(en_vars)} (value: \"{en_val}\")"
                )

    passed = len(errors) == 0
    return passed, errors, len(vi_leaves)


def main():
    parser = argparse.ArgumentParser(description="Check i18n leaf-key parity between vi and en locales.")
    parser.add_argument(
        '--namespace', '-n',
        type=str,
        default=None,
        help="Comma-separated list of namespaces to check (e.g. 'settings,mcp'). If omitted, all are checked."
    )
    parser.add_argument(
        '--locales-dir',
        type=str,
        default=BASE_LOCALES_DIR,
        help="Path to locales directory containing vi/ and en/ subdirectories."
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Display detailed per-namespace info even when passing."
    )
    args = parser.parse_args()

    if not os.path.isdir(args.locales_dir):
        print(f"ERROR: Locales directory not found: {args.locales_dir}", file=sys.stderr)
        sys.exit(2)

    available = discover_namespaces(args.locales_dir)
    if not available:
        print(f"ERROR: No locale files found in {args.locales_dir}", file=sys.stderr)
        sys.exit(2)

    if args.namespace:
        target_namespaces = [n.strip() for n in args.namespace.split(',') if n.strip()]
    else:
        target_namespaces = available

    print("=================================================================")
    print(" Flama i18n Leaf-Key Parity & Integrity Verification")
    print(f" Locales Directory: {args.locales_dir}")
    print(f" Target Namespaces: {len(target_namespaces)} namespace(s)")
    print("=================================================================")

    total_keys = 0
    total_errors = 0
    passed_count = 0
    failed_count = 0

    all_error_messages = []

    for ns in target_namespaces:
        passed, errors, leaf_count = verify_namespace(ns, args.locales_dir, args.verbose)
        total_keys += leaf_count

        if passed:
            passed_count += 1
            status = "PASS"
            if args.verbose or len(target_namespaces) <= 5:
                print(f"  [OK]  {ns:<22} : {leaf_count:>4} leaf keys | Parity 100%")
        else:
            failed_count += 1
            total_errors += len(errors)
            all_error_messages.extend(errors)
            print(f"  [FAIL] {ns:<22} : {leaf_count:>4} leaf keys | {len(errors)} error(s)")

    print("-----------------------------------------------------------------")
    print(f"Total Namespaces Checked: {len(target_namespaces)}")
    print(f"Passed Namespaces:        {passed_count}")
    print(f"Failed Namespaces:        {failed_count}")
    print(f"Total Verified Leaf Keys: {total_keys}")
    print(f"Total Parity Errors:      {total_errors}")
    print("-----------------------------------------------------------------")

    if all_error_messages:
        print("\nDETAILED PARITY & INTEGRITY ERRORS:")
        for idx, err in enumerate(all_error_messages, 1):
            print(f"  {idx}. {err}")
        print("\nRESULT: FAILED (Parity discrepancies detected)")
        sys.exit(1)
    else:
        print("\nRESULT: SUCCESS (100% leaf-key parity and variable symmetry across all checked namespaces)")
        sys.exit(0)


if __name__ == '__main__':
    main()
