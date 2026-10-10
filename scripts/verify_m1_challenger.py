import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TARGET_FILES = [
    'shell.json',
    'marketplace.json',
    'dashboard.json',
    'card_templates.json',
    'note_types.json',
    'library.json',
]

VI_DIR = os.path.join('frontend', 'src', 'shared', 'config', 'i18n', 'locales', 'vi')
EN_DIR = os.path.join('frontend', 'src', 'shared', 'config', 'i18n', 'locales', 'en')

def flatten_dict(d, prefix=''):
    items = {}
    for k, v in d.items():
        new_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key))
        else:
            items[new_key] = v
    return items

def check_target_files():
    print("=" * 60)
    print("1. ADVERSARIAL SCAN ON 6 TARGET DICTIONARIES")
    print("=" * 60)
    
    issues = []
    
    for filename in TARGET_FILES:
        vi_path = os.path.join(VI_DIR, filename)
        if not os.path.exists(vi_path):
            issues.append(f"Missing file: {vi_path}")
            continue
            
        with open(vi_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        flat = flatten_dict(data)
        
        for k, v in flat.items():
            # Check 1: publish_note_type
            if 'publish_note_type' in k:
                print(f"[{filename}] {k} -> {v!r}")
                if isinstance(v, str) and 'đăng mẫu thẻ' in v.lower():
                    issues.append(f"VIOLATION: {filename} {k} maps to forbidden 'Đăng mẫu thẻ': {v!r}")
            
            # Check 2: tab_notetypes
            if 'tab_notetypes' in k:
                print(f"[{filename}] {k} -> {v!r}")
                if isinstance(v, str) and v.strip() == 'Mẫu Thẻ':
                    issues.append(f"VIOLATION: {filename} {k} is 'Mẫu Thẻ': {v!r}")
                    
            # Check 3: Check for forbidden phrase "Đăng mẫu thẻ"
            if isinstance(v, str) and 'đăng mẫu thẻ' in v.lower():
                issues.append(f"VIOLATION: {filename} {k} contains forbidden 'đăng mẫu thẻ': {v!r}")
                
            # Check 4: Check if any Note Type is referred to as "Mẫu thẻ"
            lower_k = k.lower()
            if isinstance(v, str) and 'mẫu thẻ' in v.lower():
                print(f"  [CHECK mẫu thẻ] {filename} {k}: {v!r}")
                if any(term in lower_k for term in ['notetype', 'note_type', 'notetypes', 'note_types']):
                    issues.append(f"VIOLATION: {filename} {k} has note_type in key and 'mẫu thẻ' in value: {v!r}")

        # Cross-check with EN: if EN refers to Note Type, does VI refer to it as "Mẫu thẻ"?
        en_path = os.path.join(EN_DIR, filename)
        if os.path.exists(en_path):
            with open(en_path, 'r', encoding='utf-8') as ef:
                en_data = json.load(ef)
            en_flat = flatten_dict(en_data)
            for k, vi_val in flat.items():
                if k in en_flat and isinstance(vi_val, str) and isinstance(en_flat[k], str):
                    en_val = en_flat[k]
                    if 'note type' in en_val.lower():
                        if 'mẫu thẻ' in vi_val.lower():
                            issues.append(f"VIOLATION: EN refers to Note Type but VI uses 'mẫu thẻ' in {filename} [{k}]: EN={en_val!r} | VI={vi_val!r}")
                        elif 'mẫu' in vi_val.lower() and not ('giao diện' in vi_val.lower() or 'cấu trúc' in vi_val.lower() or 'loại thẻ' in vi_val.lower()):
                            print(f"  [NOTE_TYPE SUSPECT] {filename} [{k}]: EN={en_val!r} | VI={vi_val!r}")

    print("\nTarget Files Scan Issues:", len(issues))
    for iss in issues:
        print("  -", iss)
    return issues

def check_symmetry_and_non_empty():
    print("\n" + "=" * 60)
    print("2. LEAF-KEY SYMMETRY & NON-EMPTY VALUES (ALL FILES)")
    print("=" * 60)
    
    vi_files = set(os.listdir(VI_DIR))
    en_files = set(os.listdir(EN_DIR))
    
    file_diff = (vi_files ^ en_files)
    if file_diff:
        print(f"WARNING: File set mismatch: {file_diff}")
    
    common_files = sorted(list(vi_files & en_files))
    
    total_keys = 0
    empty_vi = []
    empty_en = []
    missing_in_en = []
    missing_in_vi = []
    type_mismatches = []
    
    for fn in common_files:
        if not fn.endswith('.json'):
            continue
            
        with open(os.path.join(VI_DIR, fn), 'r', encoding='utf-8') as f:
            try:
                vi_data = json.load(f)
            except Exception as e:
                print(f"JSON Error in {fn} (VI): {e}")
                continue
                
        with open(os.path.join(EN_DIR, fn), 'r', encoding='utf-8') as f:
            try:
                en_data = json.load(f)
            except Exception as e:
                print(f"JSON Error in {fn} (EN): {e}")
                continue
                
        vi_flat = flatten_dict(vi_data)
        en_flat = flatten_dict(en_data)
        
        total_keys += len(vi_flat)
        
        vi_keys = set(vi_flat.keys())
        en_keys = set(en_flat.keys())
        
        for k in (vi_keys - en_keys):
            missing_in_en.append(f"{fn}: {k}")
        for k in (en_keys - vi_keys):
            missing_in_vi.append(f"{fn}: {k}")
            
        for k in (vi_keys & en_keys):
            val_vi = vi_flat[k]
            val_en = en_flat[k]
            
            if type(val_vi) != type(val_en):
                type_mismatches.append(f"{fn} {k}: vi={type(val_vi)} vs en={type(val_en)}")
                
            if isinstance(val_vi, str) and not val_vi.strip():
                empty_vi.append(f"{fn}: {k}")
            if isinstance(val_en, str) and not val_en.strip():
                empty_en.append(f"{fn}: {k}")

    print(f"Total files checked: {len(common_files)}")
    print(f"Total flattened keys in VI: {total_keys}")
    print(f"Keys missing in EN: {len(missing_in_en)}")
    print(f"Keys missing in VI: {len(missing_in_vi)}")
    print(f"Empty strings in VI: {len(empty_vi)}")
    print(f"Empty strings in EN: {len(empty_en)}")
    print(f"Type mismatches: {len(type_mismatches)}")
    
    if missing_in_en:
        print("\nMissing in EN (first 10):")
        for m in missing_in_en[:10]:
            print("  -", m)
    if missing_in_vi:
        print("\nMissing in VI (first 10):")
        for m in missing_in_vi[:10]:
            print("  -", m)
    if empty_vi:
        print("\nEmpty in VI (first 10):")
        for m in empty_vi[:10]:
            print("  -", m)
    if empty_en:
        print("\nEmpty in EN (first 10):")
        for m in empty_en[:10]:
            print("  -", m)
    if type_mismatches:
        print("\nType mismatches:")
        for m in type_mismatches:
            print("  -", m)
            
    return {
        'missing_in_en': missing_in_en,
        'missing_in_vi': missing_in_vi,
        'empty_vi': empty_vi,
        'empty_en': empty_en,
        'type_mismatches': type_mismatches
    }

if __name__ == '__main__':
    t_issues = check_target_files()
    s_results = check_symmetry_and_non_empty()
    
    has_critical = (
        len([x for x in t_issues if 'VIOLATION' in x]) > 0 or
        len(s_results['missing_in_en']) > 0 or
        len(s_results['missing_in_vi']) > 0 or
        len(s_results['empty_vi']) > 0 or
        len(s_results['empty_en']) > 0 or
        len(s_results['type_mismatches']) > 0
    )
    
    if has_critical:
        print("\nOVERALL VERDICT CANDIDATE: FAIL / REQUEST_CHANGES")
        sys.exit(1)
    else:
        print("\nOVERALL VERDICT CANDIDATE: PASS")
        sys.exit(0)
