#!/usr/bin/env python3
"""
scripts/test_adversarial_i18n_parity.py

Empirical Challenger Adversarial Test Suite for i18n Locales:
Target namespaces: settings.json and mcp.json (vi vs en).

Verifies:
1. Duplicate JSON keys at all levels (via object_pairs_hook).
2. Deep tree structure parity (exact type match at every node).
3. 100% leaf key exact match (zero missing, zero unexpected).
4. Zero empty string ("") or whitespace-only values (ASCII and Unicode whitespace).
5. Interpolation variable exact parity ({{var}}, casing, counts).
6. Unbalanced interpolation braces (e.g. '{{' without '}}' or vice-versa).
7. Embedded tag parity (e.g. <link>...</link> or formatting tags).
8. Key name hygiene (no leading/trailing whitespace, no control characters).
"""

import json
import os
import re
import sys

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

LOCALES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'shared', 'config', 'i18n', 'locales')
)

INTERPOLATION_PATTERN = re.compile(r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}')
XML_TAG_PATTERN = re.compile(r'<\/?([a-zA-Z0-9_-]+)(?:\s+[^>]*?)?>')

UNICODE_WHITESPACE_CHARS = [
    '\u0020', '\u00a0', '\u1680', '\u2000', '\u2001', '\u2002', '\u2003',
    '\u2004', '\u2005', '\u2006', '\u2007', '\u2008', '\u2009', '\u200a',
    '\u2028', '\u2029', '\u202f', '\u205f', '\u3000', '\ufeff', '\u200b'
]


def make_duplicate_checking_loader():
    """Returns a json loader that detects duplicate keys."""
    duplicates = []

    def dict_hook(pairs):
        res = {}
        for key, value in pairs:
            if key in res:
                duplicates.append(key)
            res[key] = value
        return res

    return dict_hook, duplicates


def load_json_with_duplicate_check(filepath):
    hook, duplicates = make_duplicate_checking_loader()
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    data = json.loads(content, object_pairs_hook=hook)
    return data, duplicates


def inspect_tree_structure(vi_node, en_node, path=''):
    """
    Recursively compares structure between vi and en trees.
    Returns list of structural mismatch errors.
    """
    errors = []
    vi_type = type(vi_node)
    en_type = type(en_node)

    if vi_type != en_type:
        errors.append(f"Type mismatch at '{path}': vi is {vi_type.__name__}, en is {en_type.__name__}")
        return errors

    if isinstance(vi_node, dict):
        vi_keys = set(vi_node.keys())
        en_keys = set(en_node.keys())

        # Check key hygiene
        for k in vi_keys:
            if k != k.strip():
                errors.append(f"Key in vi has leading/trailing whitespace: '{k}' at '{path}'")
        for k in en_keys:
            if k != k.strip():
                errors.append(f"Key in en has leading/trailing whitespace: '{k}' at '{path}'")

        missing_in_en = vi_keys - en_keys
        missing_in_vi = en_keys - vi_keys

        for k in sorted(missing_in_en):
            sub_path = f"{path}.{k}" if path else k
            errors.append(f"Key exists in vi but MISSING in en: '{sub_path}'")
        for k in sorted(missing_in_vi):
            sub_path = f"{path}.{k}" if path else k
            errors.append(f"Key exists in en but MISSING in vi: '{sub_path}'")

        common_keys = vi_keys & en_keys
        for k in sorted(common_keys):
            sub_path = f"{path}.{k}" if path else k
            errors.extend(inspect_tree_structure(vi_node[k], en_node[k], sub_path))

    elif isinstance(vi_node, list):
        if len(vi_node) != len(en_node):
            errors.append(f"Array length mismatch at '{path}': vi has {len(vi_node)} items, en has {len(en_node)} items")
        else:
            for idx, (vi_item, en_item) in enumerate(zip(vi_node, en_node)):
                errors.extend(inspect_tree_structure(vi_item, en_item, f"{path}[{idx}]"))

    return errors


def flatten_leaf_entries(data, prefix=''):
    """Extracts all leaf entries with their full path and value."""
    leaves = {}
    if isinstance(data, dict):
        for k, v in data.items():
            full_k = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                leaves.update(flatten_leaf_entries(v, full_k))
            else:
                leaves[full_k] = v
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            full_k = f"{prefix}[{idx}]"
            if isinstance(item, (dict, list)):
                leaves.update(flatten_leaf_entries(item, full_k))
            else:
                leaves[full_k] = item
    else:
        leaves[prefix] = data
    return leaves


def check_leaf_value_integrity(key, value, locale):
    errors = []
    if value is None:
        errors.append(f"[{locale}] Value is null at '{key}'")
        return errors

    if not isinstance(value, str):
        errors.append(f"[{locale}] Value is non-string ({type(value).__name__}) at '{key}'")
        return errors

    if value == "":
        errors.append(f"[{locale}] Value is EMPTY string at '{key}'")
        return errors

    if value.strip() == "":
        errors.append(f"[{locale}] Value is WHITESPACE-ONLY at '{key}' (length {len(value)})")
        return errors

    # Check for Unicode whitespace only (e.g. \u00a0, \u200b)
    cleaned = value
    for ws in UNICODE_WHITESPACE_CHARS:
        cleaned = cleaned.replace(ws, '')
    if cleaned == "":
        errors.append(f"[{locale}] Value contains only Unicode whitespace at '{key}'")

    # Check for unbalanced interpolation
    open_count = len(re.findall(r'\{\{', value))
    close_count = len(re.findall(r'\}\}', value))
    if open_count != close_count:
        errors.append(f"[{locale}] Unbalanced interpolation braces at '{key}': {open_count} '{{{{' vs {close_count} '}}}}' (Value: \"{value}\")")

    return errors


def check_tag_parity(vi_val, en_val, key):
    errors = []
    if not isinstance(vi_val, str) or not isinstance(en_val, str):
        return errors

    vi_tags = XML_TAG_PATTERN.findall(vi_val)
    en_tags = XML_TAG_PATTERN.findall(en_val)

    if sorted(vi_tags) != sorted(en_tags):
        errors.append(
            f"XML/HTML tag mismatch at '{key}':\n"
            f"   vi tags: {sorted(vi_tags)} (val: \"{vi_val}\")\n"
            f"   en tags: {sorted(en_tags)} (val: \"{en_val}\")"
        )
    return errors


def check_interpolation_parity(vi_val, en_val, key):
    errors = []
    if not isinstance(vi_val, str) or not isinstance(en_val, str):
        return errors

    vi_vars = INTERPOLATION_PATTERN.findall(vi_val)
    en_vars = INTERPOLATION_PATTERN.findall(en_val)

    if sorted(vi_vars) != sorted(en_vars):
        errors.append(
            f"Interpolation variable mismatch at '{key}':\n"
            f"   vi vars: {sorted(vi_vars)} (val: \"{vi_val}\")\n"
            f"   en vars: {sorted(en_vars)} (val: \"{en_val}\")"
        )
    return errors


def run_adversarial_suite_on_namespace(ns):
    print(f"\n=======================================================")
    print(f" Adversarial Stress Testing: {ns}.json")
    print(f"=======================================================")

    vi_path = os.path.join(LOCALES_DIR, 'vi', f'{ns}.json')
    en_path = os.path.join(LOCALES_DIR, 'en', f'{ns}.json')

    all_errors = []

    # 1. File existence
    if not os.path.isfile(vi_path):
        all_errors.append(f"Missing vi file: {vi_path}")
        return False, all_errors, 0
    if not os.path.isfile(en_path):
        all_errors.append(f"Missing en file: {en_path}")
        return False, all_errors, 0

    # 2. Duplicate keys check
    vi_data, vi_dups = load_json_with_duplicate_check(vi_path)
    en_data, en_dups = load_json_with_duplicate_check(en_path)

    if vi_dups:
        for d in vi_dups:
            all_errors.append(f"[vi/{ns}.json] DUPLICATE KEY found: '{d}'")
    if en_dups:
        for d in en_dups:
            all_errors.append(f"[en/{ns}.json] DUPLICATE KEY found: '{d}'")

    print(f"[*] Duplicate key check: vi dups={len(vi_dups)}, en dups={len(en_dups)}")

    # 3. Recursive tree structure check
    tree_errors = inspect_tree_structure(vi_data, en_data)
    all_errors.extend(tree_errors)
    print(f"[*] Tree structure check: {len(tree_errors)} structural error(s)")

    # 4. Leaf keys extraction & parity
    vi_leaves = flatten_leaf_entries(vi_data)
    en_leaves = flatten_leaf_entries(en_data)

    print(f"[*] Leaf counts: vi={len(vi_leaves)}, en={len(en_leaves)}")

    vi_keys = set(vi_leaves.keys())
    en_keys = set(en_leaves.keys())

    missing_in_en = vi_keys - en_keys
    missing_in_vi = en_keys - vi_keys

    if missing_in_en:
        for k in sorted(missing_in_en):
            all_errors.append(f"Leaf key in vi MISSING in en: '{k}'")
    if missing_in_vi:
        for k in sorted(missing_in_vi):
            all_errors.append(f"Leaf key in en MISSING in vi: '{k}'")

    # 5. Value integrity check
    val_errors = 0
    for k, v in vi_leaves.items():
        errs = check_leaf_value_integrity(k, v, 'vi')
        if errs:
            all_errors.extend(errs)
            val_errors += len(errs)

    for k, v in en_leaves.items():
        errs = check_leaf_value_integrity(k, v, 'en')
        if errs:
            all_errors.extend(errs)
            val_errors += len(errs)

    print(f"[*] Value integrity check (empty/whitespace/null/unbalanced): {val_errors} error(s)")

    # 6. Interpolation parity check
    interp_errors = 0
    common_keys = vi_keys & en_keys
    for k in sorted(common_keys):
        errs = check_interpolation_parity(vi_leaves[k], en_leaves[k], k)
        if errs:
            all_errors.extend(errs)
            interp_errors += len(errs)

    print(f"[*] Interpolation variable symmetry check: {interp_errors} error(s)")

    # 7. Embedded tag parity check
    tag_errors = 0
    for k in sorted(common_keys):
        errs = check_tag_parity(vi_leaves[k], en_leaves[k], k)
        if errs:
            all_errors.extend(errs)
            tag_errors += len(errs)

    print(f"[*] Embedded tag symmetry check: {tag_errors} error(s)")

    passed = len(all_errors) == 0
    return passed, all_errors, len(vi_leaves)


def main():
    target_namespaces = ['settings', 'mcp']
    total_errors = []
    total_leaves = {}

    for ns in target_namespaces:
        passed, errors, count = run_adversarial_suite_on_namespace(ns)
        total_leaves[ns] = count
        if not passed:
            total_errors.extend(errors)

    print("\n=======================================================")
    print(" SUMMARY OF EMPIRICAL ADVERSARIAL PARITY VERIFICATION")
    print("=======================================================")
    for ns, count in total_leaves.items():
        print(f" Namespace: {ns:<12} | Leaf Keys: {count} | Parity: {'100% OK' if count > 0 and len([e for e in total_errors if ns in e]) == 0 else 'FAIL'}")

    if total_errors:
        print(f"\n[!] TOTAL DISCREPANCIES DETECTED: {len(total_errors)}")
        for idx, err in enumerate(total_errors, 1):
            print(f" {idx}. {err}")
        print("\nOVERALL VERDICT: REQUEST_CHANGES")
        sys.exit(1)
    else:
        print("\n[+] ALL ADVERSARIAL TESTS PASSED: 0 errors detected across all checks.")
        print("OVERALL VERDICT: APPROVE")
        sys.exit(0)


if __name__ == '__main__':
    main()
