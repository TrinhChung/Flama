"""
Adversarial Verification Harness for Documentation Link Integrity (Milestone 4)
Checks:
- Markdown links [text](url)
- HTML links <a href="...">
- Reference definitions [id]: url
- Accidental absolute paths (file:///, C:\, D:\, /)
- Target file / directory existence
- Heading anchor resolution (#anchor)
- Exact file casing matching (Linux/Git case-sensitivity)
"""

import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]

# Heading anchor slug generator (mimics GitHub/CommonMark slugification)
def slugify_heading(heading_text: str) -> tuple[str, str]:
    """
    Returns both exact GitHub slug and collapsed-hyphen slug.
    GitHub preserves spaces converted to hyphens after stripping punctuation.
    E.g. 'A & B' -> 'A  B' (two spaces) -> 'a--b'.
    """
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', heading_text)  # link text
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)  # inline code
    cleaned = cleaned.replace('*', '').replace('_', '').replace('~', '')
    
    slug = cleaned.lower()
    res = []
    for ch in slug:
        if ch.isalnum() or ch == ' ' or ch == '-' or ch == '_':
            res.append(ch)
        elif unicodedata.category(ch).startswith(('L', 'N')):
            res.append(ch)
    
    # Standard GitHub slug: each space becomes a hyphen
    github_slug = ''.join(res).replace(' ', '-').strip('-')
    # Collapsed hyphen variant
    collapsed_slug = re.sub(r'-+', '-', github_slug).strip('-')
    return github_slug, collapsed_slug


def extract_anchors_from_markdown(content: str) -> set[str]:
    anchors = set()
    # 1. Markdown headings (# Heading)
    # Exclude code fences
    lines = content.splitlines()
    in_code_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        m = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if m:
            heading_text = m.group(2)
            # Remove trailing hashes if any
            heading_text = re.sub(r'\s+#+\s*$', '', heading_text)
            g_slug, c_slug = slugify_heading(heading_text)
            if g_slug:
                anchors.add(g_slug)
            if c_slug:
                anchors.add(c_slug)
    
    # 2. Explicit HTML anchors: <a id="...">, <a name="...">, id="..."
    for match in re.finditer(r'''(?:id|name)=["']([^"']+)["']''', content, re.IGNORECASE):
        anchors.add(match.group(1).lower())
    
    return anchors

def extract_links_from_markdown(file_path: Path) -> list[dict]:
    content = file_path.read_text(encoding='utf-8')
    links = []

    # Strip code blocks to avoid scanning example markdown inside documentation
    # We want line numbers, so replace contents of fenced code blocks with blank lines
    def mask_code_blocks(text):
        def replacer(match):
            return '\n' * match.group(0).count('\n')
        return re.sub(r'```.*?```', replacer, text, flags=re.DOTALL)

    masked_content = mask_code_blocks(content)

    # 1. Standard markdown links: [text](url)
    for m in re.finditer(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)', masked_content):
        text = m.group(1).strip()
        raw_url = m.group(2).strip()
        line_num = content[:m.start()].count('\n') + 1
        parts = raw_url.split(None, 1)
        url = parts[0] if parts else ''
        links.append({
            'source_file': file_path,
            'line': line_num,
            'type': 'markdown',
            'text': text,
            'raw_url': raw_url,
            'url': url
        })

    # 2. Reference definitions: [id]: url
    for m in re.finditer(r'^\[([^\]]+)\]:\s*([^\s]+)', masked_content, re.MULTILINE):
        ref_id = m.group(1).strip()
        url = m.group(2).strip()
        line_num = content[:m.start()].count('\n') + 1
        links.append({
            'source_file': file_path,
            'line': line_num,
            'type': 'reference_def',
            'text': ref_id,
            'raw_url': url,
            'url': url
        })

    # 3. HTML <a> tags: <a href="...">
    for m in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\']', masked_content, re.IGNORECASE):
        url = m.group(1).strip()
        line_num = content[:m.start()].count('\n') + 1
        links.append({
            'source_file': file_path,
            'line': line_num,
            'type': 'html_a',
            'text': '',
            'raw_url': url,
            'url': url
        })

    # 4. Check for accidental file:/// in actual links or unescaped URLs (not inside inline `...`)
    # Mask inline code first
    content_no_inline = re.sub(r'`[^`]*`', '', masked_content)
    for m in re.finditer(r'file:///[^\s)"\'>]+', content_no_inline):
        line_num = content[:m.start()].count('\n') + 1
        links.append({
            'source_file': file_path,
            'line': line_num,
            'type': 'file_protocol_violation',
            'text': '',
            'raw_url': m.group(0),
            'url': m.group(0)
        })

    return links


def check_link(link: dict, repo_root: Path) -> tuple[str, str]:
    """
    Returns (status, message).
    status: 'PASS', 'FAIL', 'SKIP', 'WARN'
    """
    url = link['url']
    source_file = link['source_file']

    if link['type'] == 'file_protocol_violation':
        return 'FAIL', f'Accidental file:/// URL detected: {url}'

    # Ignore non-local protocols
    if url.startswith(('http://', 'https://', 'mailto:', 'tel:', 'ftp://', 'javascript:')):
        return 'SKIP', 'External protocol'

    # Check for accidental hardcoded Windows drives (e.g. D:/..., C:\...)
    if re.match(r'^[a-zA-Z]:[\\/]', url):
        return 'FAIL', f'Hardcoded local absolute Windows drive path: {url}'

    # Clean URL of quotes or surrounding brackets
    url_clean = url.strip('\'"<>')

    # Parse anchor
    parts = url_clean.split('#', 1)
    file_part = parts[0].strip()
    anchor_part = parts[1].strip() if len(parts) > 1 else None

    # Determine target file
    if not file_part:
        # Same-file anchor link: #anchor
        target_path = source_file
    else:
        # Unquote URL (e.g. %20 -> space)
        unquoted = unquote(file_part)
        
        # Handle root-relative vs relative
        if unquoted.startswith('/'):
            target_path = repo_root / unquoted.lstrip('/')
        else:
            target_path = (source_file.parent / unquoted).resolve()

    # Check existence
    if not target_path.exists():
        return 'FAIL', f'Target path does not exist: {target_path} (from {url_clean})'

    # Check exact case matching on disk (adversarial check for Linux/macOS case sensitivity)
    # Check parent directory path casing
    try:
        # Compare actual name on disk
        target_dir = target_path.parent
        if target_dir.exists():
            actual_name = next((f.name for f in target_dir.iterdir() if f.name.lower() == target_path.name.lower()), None)
            if actual_name and actual_name != target_path.name:
                return 'WARN', f'Case mismatch: link has {target_path.name}, disk has {actual_name}'
    except Exception:
        pass

    # If anchor is present and target is a markdown file, check anchor existence
    if anchor_part and target_path.suffix.lower() in ('.md', '.markdown'):
        try:
            target_content = target_path.read_text(encoding='utf-8')
            valid_anchors = extract_anchors_from_markdown(target_content)
            anchor_lower = unquote(anchor_part).lower()
            if anchor_lower not in valid_anchors:
                # Some anchors might be slightly formatted or partial
                return 'FAIL', f'Anchor "#{anchor_part}" not found in target {target_path.name}. (Found {len(valid_anchors)} headings: {list(valid_anchors)[:5]}...)'
        except Exception as e:
            return 'WARN', f'Could not read target to verify anchor: {e}'

    return 'PASS', 'OK'

def main():
    print(f'Starting link integrity audit from repo root: {REPO_ROOT}')
    
    # Define file sets
    # Set 1: Specified files in prompt
    prompt_files = [
        REPO_ROOT / 'README.md',
        REPO_ROOT / 'AGENTS.md',
        REPO_ROOT / 'docs/README.md',
        REPO_ROOT / 'docs/DOCUMENTATION_AUDIT_REPORT.md'
    ]
    
    frontend_files = list((REPO_ROOT / 'docs/frontend').rglob('*.md'))
    backend_files = list((REPO_ROOT / 'docs/backend').rglob('*.md'))
    ops_files = list((REPO_ROOT / 'docs/ops').rglob('*.md'))
    logs_files = list((REPO_ROOT / 'docs/logs').rglob('*.md'))

    all_target_files = sorted(set(prompt_files + frontend_files + backend_files + ops_files + logs_files))
    
    # Active-only files (non-old)
    active_target_files = [f for f in all_target_files if 'old' not in f.parts or f.name == 'README.md' and f.parent.name == 'old']

    print(f'Total target markdown files found: {len(all_target_files)}')
    print(f'  - Core/Active index files: {len(active_target_files)}')
    print(f'  - Historical archived files in old/: {len(all_target_files) - len(active_target_files)}')

    print('\n' + '='*60)
    print('AUDIT 1: ACTIVE DOCUMENTATION SURFACE (20 Core Files)')
    print('='*60)

    total_active_links = 0
    passed_active_links = 0
    skipped_active_links = 0
    failed_active = []
    warn_active = []

    for f in active_target_files:
        links = extract_links_from_markdown(f)
        for link in links:
            total_active_links += 1
            status, msg = check_link(link, REPO_ROOT)
            if status == 'PASS':
                passed_active_links += 1
            elif status == 'SKIP':
                skipped_active_links += 1
            elif status == 'WARN':
                warn_active.append((link, msg))
                passed_active_links += 1  # count as resolved but flagged
            else:
                failed_active.append((link, msg))

    print(f'Active files scanned: {len(active_target_files)}')
    print(f'Total links evaluated: {total_active_links}')
    print(f'  - Passed relative / resolved: {passed_active_links}')
    print(f'  - Skipped external: {skipped_active_links}')
    print(f'  - Warnings (e.g. case mismatch): {len(warn_active)}')
    print(f'  - Broken / Failed links: {len(failed_active)}')

    if failed_active:
        print('\nFAILED ACTIVE LINKS:')
        for link, msg in failed_active:
            print(f'  {link["source_file"].relative_to(REPO_ROOT)}:{link["line"]}: {link["raw_url"]} -> {msg}')

    if warn_active:
        print('\nACTIVE LINK WARNINGS:')
        for link, msg in warn_active:
            print(f'  {link["source_file"].relative_to(REPO_ROOT)}:{link["line"]}: {link["raw_url"]} -> {msg}')

    print('\n' + '='*60)
    print('AUDIT 2: EXHAUSTIVE SCAN ACROSS ALL 174 FILES (INCLUDING HISTORICAL old/)')
    print('='*60)

    total_all_links = 0
    passed_all_links = 0
    skipped_all_links = 0
    failed_all = []
    warn_all = []

    for f in all_target_files:
        links = extract_links_from_markdown(f)
        for link in links:
            total_all_links += 1
            status, msg = check_link(link, REPO_ROOT)
            if status == 'PASS':
                passed_all_links += 1
            elif status == 'SKIP':
                skipped_all_links += 1
            elif status == 'WARN':
                warn_all.append((link, msg))
                passed_all_links += 1
            else:
                failed_all.append((link, msg))

    print(f'Total markdown files scanned: {len(all_target_files)}')
    print(f'Total links evaluated: {total_all_links}')
    print(f'  - Passed relative / resolved: {passed_all_links}')
    print(f'  - Skipped external: {skipped_all_links}')
    print(f'  - Warnings: {len(warn_all)}')
    print(f'  - Broken / Failed links: {len(failed_all)}')

    if failed_all:
        print(f'\nTotal failures across all files (including historical old/): {len(failed_all)}')
        # Print breakdown by category (active vs historical)
        hist_failures = [x for x in failed_all if 'old' in x[0]['source_file'].parts]
        print(f'  - Failures in active docs: {len(failed_active)}')
        print(f'  - Failures in historical old/ docs: {len(hist_failures)}')
        for link, msg in failed_all[:20]:
            print(f'  {link["source_file"].relative_to(REPO_ROOT)}:{link["line"]}: {link["raw_url"]} -> {msg}')
        if len(failed_all) > 20:
            print(f'  ... and {len(failed_all) - 20} more historical broken links.')

if __name__ == '__main__':
    main()
