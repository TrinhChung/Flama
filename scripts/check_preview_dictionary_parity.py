import json
import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

NAMESPACES = ['profile', 'wallet', 'card_templates', 'audio', 'guide', 'onboarding']
ALL_NAMESPACES = [
    'common', 'shell', 'auth', 'settings', 'note_types', 'collaboration',
    'orders', 'support', 'worksheets', 'browse', 'dashboard', 'import',
    'landing', 'legal', 'library', 'marketplace', 'mcp', 'statistics',
    'study', 'profile', 'wallet', 'card_templates', 'audio', 'guide', 'onboarding'
]
BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'shared', 'config', 'i18n', 'locales')

VI_REGEX = re.compile(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', re.IGNORECASE)
INTERPOLATION_REGEX = re.compile(r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}')

# Allowed proper nouns/names with diacritics in English translations
ALLOWED_VI_IN_EN = {'Chung Trịnh', 'Đồng', 'VNĐ', 'VND'}

def flatten_keys(d, prefix=''):
    items = {}
    if isinstance(d, dict):
        for k, v in d.items():
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

def check_namespaces(target_namespaces, label="Target"):
    errors = []
    warnings = []
    total_keys = 0

    print(f"\n=======================================================")
    print(f"Checking {label} Namespaces ({len(target_namespaces)} total)")
    print(f"=======================================================")

    for ns in target_namespaces:
        vi_path = os.path.join(BASE_DIR, 'vi', f'{ns}.json')
        en_path = os.path.join(BASE_DIR, 'en', f'{ns}.json')

        if not os.path.exists(vi_path):
            errors.append(f"[{ns}] ERROR: Missing vi file {vi_path}")
            continue
        if not os.path.exists(en_path):
            errors.append(f"[{ns}] ERROR: Missing en file {en_path}")
            continue

        try:
            with open(vi_path, 'r', encoding='utf-8') as f:
                vi_data = json.load(f)
        except Exception as e:
            errors.append(f"[{ns}] ERROR: Failed to parse vi JSON: {e}")
            continue

        try:
            with open(en_path, 'r', encoding='utf-8') as f:
                en_data = json.load(f)
        except Exception as e:
            errors.append(f"[{ns}] ERROR: Failed to parse en JSON: {e}")
            continue

        vi_flat = flatten_keys(vi_data)
        en_flat = flatten_keys(en_data)

        total_keys += len(vi_flat)

        vi_keys = set(vi_flat.keys())
        en_keys = set(en_flat.keys())

        # 1. Parity check
        missing_in_en = vi_keys - en_keys
        missing_in_vi = en_keys - vi_keys

        if missing_in_en:
            errors.append(f"[{ns}] ERROR: {len(missing_in_en)} keys in vi but missing in en: {sorted(missing_in_en)}")
        if missing_in_vi:
            errors.append(f"[{ns}] ERROR: {len(missing_in_vi)} keys in en but missing in vi: {sorted(missing_in_vi)}")

        # 2. Value emptiness & types
        for k, v in vi_flat.items():
            if v is None:
                errors.append(f"[{ns}] ERROR: vi key '{k}' is null")
            elif not isinstance(v, str):
                errors.append(f"[{ns}] ERROR: vi key '{k}' is non-string ({type(v).__name__})")
            elif not v.strip():
                errors.append(f"[{ns}] ERROR: vi key '{k}' is empty string")

        for k, v in en_flat.items():
            if v is None:
                errors.append(f"[{ns}] ERROR: en key '{k}' is null")
            elif not isinstance(v, str):
                errors.append(f"[{ns}] ERROR: en key '{k}' is non-string ({type(v).__name__})")
            elif not v.strip():
                errors.append(f"[{ns}] ERROR: en key '{k}' is empty string")

        # 3. Interpolation placeholder symmetry
        common_keys = vi_keys & en_keys
        for k in common_keys:
            vi_val = vi_flat[k]
            en_val = en_flat[k]
            if isinstance(vi_val, str) and isinstance(en_val, str):
                vi_params = set(INTERPOLATION_REGEX.findall(vi_val))
                en_params = set(INTERPOLATION_REGEX.findall(en_val))
                if vi_params != en_params:
                    errors.append(
                        f"[{ns}] ERROR: Interpolation parameter mismatch at '{k}':\n"
                        f"   vi params: {vi_params} (text: \"{vi_val}\")\n"
                        f"   en params: {en_params} (text: \"{en_val}\")"
                    )

                # 4. Rogue untranslated Vietnamese text in English
                # Check if english string contains vietnamese diacritics
                m = VI_REGEX.search(en_val)
                if m:
                    # check if it matches allowed phrases
                    is_allowed = any(allowed in en_val for allowed in ALLOWED_VI_IN_EN)
                    if not is_allowed:
                        warnings.append(
                            f"[{ns}] POTENTIAL_ROUGE_VI: en key '{k}' contains Vietnamese diacritic: \"{m.group(0)}\"\n"
                            f"   en text: \"{en_val}\"\n"
                            f"   vi text: \"{vi_val}\""
                        )

        print(f"[{ns}] Checked: {len(vi_flat)} leaf keys. Parity: {'PASS' if vi_keys == en_keys else 'FAIL'}")

    return errors, warnings, total_keys

def check_source_code_for_rogue_vietnamese():
    feature_dirs = [
        os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'features', d)
        for d in ['profile', 'wallet', 'audio', 'template-library', 'template-versions', 'template-distribution', 'guide', 'onboarding']
    ]
    suspicious = []

    for fdir in feature_dirs:
        if not os.path.exists(fdir):
            continue
        for root, dirs, files in os.walk(fdir):
            for fname in files:
                if not (fname.endswith('.tsx') or fname.endswith('.ts')):
                    continue
                if '.test.' in fname or '.spec.' in fname:
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                for idx, line in enumerate(lines, 1):
                    clean_line = line.strip()
                    if clean_line.startswith('//') or clean_line.startswith('/*') or clean_line.startswith('*'):
                        continue
                    # Check for Vietnamese diacritics
                    matches = VI_REGEX.findall(line)
                    if matches:
                        # Allow comments at the end of lines
                        # If the match is within a comment:
                        comment_idx = clean_line.find('//')
                        if comment_idx != -1:
                            non_comment_part = clean_line[:comment_idx]
                            if not VI_REGEX.search(non_comment_part):
                                continue
                        suspicious.append({
                            'file': os.path.relpath(fpath, os.path.join(os.path.dirname(__file__), '..')),
                            'line': idx,
                            'text': clean_line,
                            'chars': ''.join(set(matches))
                        })
    return suspicious

def main():
    target_errors, target_warnings, target_total = check_namespaces(NAMESPACES, "Target 6 Preview")
    all_errors, all_warnings, all_total = check_namespaces(ALL_NAMESPACES, "All 25 Registered")
    source_suspicious = check_source_code_for_rogue_vietnamese()

    print("\n=======================================================")
    print("SUMMARY RESULTS")
    print("=======================================================")
    print(f"Target 6 Namespaces Keys: {target_total}")
    print(f"Target 6 Errors: {len(target_errors)}")
    print(f"Target 6 Warnings/Suspects: {len(target_warnings)}")

    print(f"\nAll 25 Namespaces Total Keys: {all_total}")
    print(f"All 25 Namespaces Errors: {len(all_errors)}")
    print(f"All 25 Namespaces Warnings: {len(all_warnings)}")

    print(f"\nSource Code Vietnamese Hardcode Check (8 feature directories):")
    print(f"Suspicious lines found in feature code: {len(source_suspicious)}")

    if target_warnings:
        print("\n--- TARGET WARNINGS (Vietnamese diacritics in EN) ---")
        for w in target_warnings:
            print(w)

    if source_suspicious:
        print("\n--- SUSPICIOUS HARDCODED VIETNAMESE IN FEATURE CODE (GROUPED BY FILE) ---")
        by_file = {}
        for s in source_suspicious:
            by_file.setdefault(s['file'], []).append(s)
        for f, items in sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"\nFile: {f} ({len(items)} lines)")
            for item in items[:5]:
                print(f"  Line {item['line']}: {item['text'][:120]}")
            if len(items) > 5:
                print(f"  ... and {len(items) - 5} more lines.")

    if target_errors:
        print("\n--- TARGET CRITICAL ERRORS ---")
        for e in target_errors:
            print(e)
        sys.exit(1)

    if all_errors:
        print("\n--- OTHER NAMESPACES CRITICAL ERRORS ---")
        for e in all_errors:
            print(e)
        sys.exit(1)

    if source_suspicious:
        print("\nWARNING: Hardcoded Vietnamese strings detected in feature components!")
        # We will inspect if any are genuine violations

    print("\nSUCCESS: All checks passed!")
    sys.exit(0)

if __name__ == '__main__':
    main()

