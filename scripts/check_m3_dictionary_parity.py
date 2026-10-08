import json
import os
import sys
import re

NAMESPACES = ['settings', 'note_types', 'collaboration', 'orders', 'support', 'worksheets']
BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'shared', 'config', 'i18n', 'locales')

VI_REGEX = re.compile(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', re.IGNORECASE)

def flatten_keys(d, prefix=''):
    items = {}
    for k, v in d.items():
        full_k = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten_keys(v, full_k))
        else:
            items[full_k] = v
    return items

def main():
    has_error = False
    total_keys = 0

    for ns in NAMESPACES:
        vi_path = os.path.join(BASE_DIR, 'vi', f'{ns}.json')
        en_path = os.path.join(BASE_DIR, 'en', f'{ns}.json')

        if not os.path.exists(vi_path):
            print(f"ERROR: Missing vi file {vi_path}")
            has_error = True
            continue
        if not os.path.exists(en_path):
            print(f"ERROR: Missing en file {en_path}")
            has_error = True
            continue

        with open(vi_path, 'r', encoding='utf-8') as f:
            vi_data = json.load(f)
        with open(en_path, 'r', encoding='utf-8') as f:
            en_data = json.load(f)

        vi_flat = flatten_keys(vi_data)
        en_flat = flatten_keys(en_data)

        total_keys += len(vi_flat)

        vi_keys = set(vi_flat.keys())
        en_keys = set(en_flat.keys())

        missing_in_en = vi_keys - en_keys
        missing_in_vi = en_keys - vi_keys

        if missing_in_en:
            print(f"[{ns}] ERROR: Keys in vi but missing in en ({len(missing_in_en)}): {missing_in_en}")
            has_error = True
        if missing_in_vi:
            print(f"[{ns}] ERROR: Keys in en but missing in vi ({len(missing_in_vi)}): {missing_in_vi}")
            has_error = True

        for k, v in vi_flat.items():
            if v is None or (isinstance(v, str) and not v.strip()):
                print(f"[{ns}] ERROR: vi key '{k}' has empty or null value")
                has_error = True

        for k, v in en_flat.items():
            if v is None or (isinstance(v, str) and not v.strip()):
                print(f"[{ns}] ERROR: en key '{k}' has empty or null value")
                has_error = True
            elif isinstance(v, str):
                # Check for untranslated Vietnamese characters in EN, ignoring brand words like Yomitan/PayOS/VoiceVox
                # if needed, but Vietnamese diacritics shouldn't appear in English translations
                # Wait: Check if there are Vietnamese diacritics
                m = VI_REGEX.search(v)
                if m:
                    # Let's inspect the match
                    print(f"[{ns}] WARNING: en key '{k}' contains Vietnamese diacritic: '{m.group(0)}' in '{v}'")

    print(f"\nAnalyzed {len(NAMESPACES)} namespaces with total {total_keys} keys.")
    if has_error:
        print("RESULT: FAILED parity check!")
        sys.exit(1)
    else:
        print("RESULT: 100% PARITY! Zero missing keys, zero empty values.")
        sys.exit(0)

if __name__ == '__main__':
    main()
