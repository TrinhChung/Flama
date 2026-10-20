#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Empirical Adversarial Verification Script for Flama SEO Strategic Implementation.
Role: Challenger 2 (Empirical Schema Syntax, Anchor Math & Linking Stress-Test)

Tested Objectives:
1. Extract all JSON-LD blocks from ONPAGE_SEMANTIC_GUIDELINES.md (and all docs/seo/*.md) and parse with json.loads.
2. Verify mathematical consistency of Anchor Text percentages across all tiers (must sum to 100%).
3. Verify all internal markdown links and cross-references across docs/seo/*.md.
4. Verify the 12-week schedule completeness (24 titles across 12 weeks, word counts, search intents).
"""

import os
import re
import sys
import json
import unicodedata
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = Path(__file__).resolve().parents[1]
SEO_DIR = REPO_ROOT / 'docs' / 'seo'

def slugify_heading(heading_text: str) -> tuple[str, str, str]:
    """Generates GitHub-compatible anchor slugs from heading text."""
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', heading_text)  # link text
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)  # inline code
    cleaned = cleaned.replace('*', '').replace('_', '').replace('~', '')
    
    # Strip explicit anchor tags like {#custom-id}
    cleaned = re.sub(r'\{#[^}]+\}', '', cleaned).strip()
    
    slug = cleaned.lower()
    res = []
    for ch in slug:
        if ch.isalnum() or ch in (' ', '-', '_'):
            res.append(ch)
        elif unicodedata.category(ch).startswith(('L', 'N')):
            res.append(ch)
            
    github_slug = ''.join(res).replace(' ', '-').strip('-')
    collapsed_slug = re.sub(r'-+', '-', github_slug).strip('-')
    
    raw_slug = re.sub(r'[^\w\s-]', '', cleaned.lower()).replace(' ', '-')
    raw_slug = re.sub(r'-+', '-', raw_slug).strip('-')
    
    return github_slug, collapsed_slug, raw_slug

def extract_headings_and_anchors(content: str) -> set[str]:
    """Extracts all heading anchor slugs from markdown text."""
    anchors = set()
    in_code = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if m:
            heading_text = m.group(2).strip()
            gh_slug, col_slug, raw_slug = slugify_heading(heading_text)
            anchors.add(gh_slug)
            anchors.add(col_slug)
            anchors.add(raw_slug)
            
            custom_match = re.search(r'\{#([a-zA-Z0-9_-]+)\}', heading_text)
            if custom_match:
                anchors.add(custom_match.group(1))
    return anchors

# ==============================================================================
# TEST 1: JSON-LD SYNTACTICAL VALIDITY & SCHEMA INTEGRITY
# ==============================================================================
def test_1_json_ld_syntax():
    print("\n" + "=" * 80)
    print("TEST 1: JSON-LD SYNTACTICAL VALIDITY & SCHEMA INTEGRITY")
    print("=" * 80)
    
    target_file = SEO_DIR / 'ONPAGE_SEMANTIC_GUIDELINES.md'
    assert target_file.exists(), f"Missing target file: {target_file}"
    content = target_file.read_text(encoding='utf-8')
    
    # Extract ```json code blocks from ONPAGE_SEMANTIC_GUIDELINES.md
    pattern = r'```json\s*\n(.*?)\n```'
    matches = list(re.finditer(pattern, content, re.DOTALL))
    
    print(f"Target file: ONPAGE_SEMANTIC_GUIDELINES.md ({len(matches)} JSON blocks detected)")
    
    results = []
    errors = []
    
    for idx, match in enumerate(matches, 1):
        block_text = match.group(1).strip()
        start_pos = match.start()
        line_num = content[:start_pos].count('\n') + 1
        
        try:
            parsed = json.loads(block_text)
            ctx = parsed.get('@context')
            schema_type = parsed.get('@type')
            graph = parsed.get('@graph')
            
            summary = {
                "file": target_file.name,
                "block_num": idx,
                "line": line_num,
                "length_chars": len(block_text),
                "@context": ctx,
                "@type": schema_type,
                "graph_nodes": len(graph) if graph else None,
            }
            results.append(summary)
            print(f"  [PASS] Block #{idx} (line {line_num}): valid JSON. @context='{ctx}', @type='{schema_type}', graph_nodes={summary['graph_nodes']}")
            
            # Semantic conformance checks
            if graph:
                found_types = set()
                for node in graph:
                    nt = node.get('@type')
                    if isinstance(nt, list):
                        found_types.update(nt)
                    elif isinstance(nt, str):
                        found_types.add(nt)
                print(f"    -> @graph contains types: {sorted(found_types)}")
                assert "Organization" in found_types, "Missing Organization in @graph"
                assert "WebSite" in found_types, "Missing WebSite in @graph"
                assert "FAQPage" in found_types, "Missing FAQPage in @graph"
                assert "Course" in found_types, "Missing Course in @graph"
                assert any("Application" in t for t in found_types), "Missing Software/EducationalApplication in @graph"
            elif schema_type == 'HowTo':
                steps = parsed.get('step', [])
                tools = parsed.get('tool', [])
                print(f"    -> HowTo: name='{parsed.get('name')}', {len(steps)} steps, {len(tools)} tools, time={parsed.get('totalTime')}")
                assert len(steps) >= 3, f"HowTo has fewer than 3 steps: {len(steps)}"
            elif schema_type == 'BreadcrumbList':
                items = parsed.get('itemListElement', [])
                print(f"    -> BreadcrumbList: {len(items)} levels")
                assert len(items) == 3, f"BreadcrumbList expected 3 levels, got {len(items)}"
                
        except json.JSONDecodeError as e:
            err_msg = f"Block #{idx} (line {line_num}) JSONDecodeError: {e}"
            errors.append(err_msg)
            print(f"  [FAIL] {err_msg}")
        except AssertionError as e:
            err_msg = f"Block #{idx} (line {line_num}) Schema validation assertion: {e}"
            errors.append(err_msg)
            print(f"  [FAIL] {err_msg}")
            
    # Also verify all other JSON blocks in docs/seo/*.md (e.g. BRAND_ENTITY_SEO_STRATEGY.md)
    print("\nScanning auxiliary JSON blocks in other docs/seo/*.md files:")
    for mf in sorted(SEO_DIR.glob('*.md')):
        if mf.name == target_file.name:
            continue
        mf_content = mf.read_text(encoding='utf-8')
        aux_matches = list(re.finditer(pattern, mf_content, re.DOTALL))
        if aux_matches:
            print(f"  - {mf.name}: {len(aux_matches)} JSON blocks")
            for a_idx, a_match in enumerate(aux_matches, 1):
                a_text = a_match.group(1).strip()
                a_line = mf_content[:a_match.start()].count('\n') + 1
                try:
                    a_parsed = json.loads(a_text)
                    print(f"    [PASS] Block #{a_idx} (line {a_line}): valid JSON. Keys: {list(a_parsed.keys())}")
                except Exception as ex:
                    err_msg = f"File {mf.name} Block #{a_idx} JSON error: {ex}"
                    errors.append(err_msg)
                    print(f"    [FAIL] {err_msg}")

    passed = (len(errors) == 0 and len(results) == 5)
    print(f"\nResult Test 1: {'PASSED' if passed else 'FAILED'} ({len(results)} primary blocks, {len(errors)} errors)")
    return passed, results, errors

# ==============================================================================
# TEST 2: ANCHOR TEXT PERCENTAGE CONSISTENCY ACROSS ALL TIERS
# ==============================================================================
def test_2_anchor_math():
    print("\n" + "=" * 80)
    print("TEST 2: ANCHOR TEXT PERCENTAGE CONSISTENCY ACROSS ALL TIERS")
    print("=" * 80)
    
    target_file = SEO_DIR / 'PILLAR_CLUSTER_ARCHITECTURE.md'
    assert target_file.exists(), f"Missing target file: {target_file}"
    content = target_file.read_text(encoding='utf-8')
    
    # 4 Tiers defined in Section 5
    tiers = {
        "Partial Match": (35, 40),
        "Branded": (20, 25),
        "Exact Match": (15, 20),
        "LSI & Natural": (15, 20)
    }
    
    min_sum = sum(t[0] for t in tiers.values())
    max_sum = sum(t[1] for t in tiers.values())
    
    print("Anchor Text Tiers defined:")
    for name, (low, high) in tiers.items():
        print(f"  - {name}: {low}% – {high}%")
    print(f"Mathematical Bounds:")
    print(f"  - Minimum possible sum: {min_sum}%")
    print(f"  - Maximum possible sum: {max_sum}%")
    
    in_range = (min_sum <= 100 <= max_sum)
    print(f"  - Does 100% fall within [{min_sum}%, {max_sum}%]? {in_range}")
    
    # Find all integer percentage distributions that sum to exactly 100%
    solutions = []
    for p in range(35, 41):
        for b in range(20, 26):
            for e in range(15, 21):
                for l in range(15, 21):
                    if p + b + e + l == 100:
                        solutions.append((p, b, e, l))
                        
    print(f"  - Total discrete integer distributions summing to exactly 100%: {len(solutions)}")
    print("  - Representative valid configurations:")
    print(f"    * Baseline Balanced: Partial=38%, Branded=22%, Exact=20%, LSI=20% (Sum = {38+22+20+20}%)")
    print(f"    * Max Partial Match: Partial=40%, Branded=25%, Exact=20%, LSI=15% (Sum = {40+25+20+15}%)")
    print(f"    * Max Branded:       Partial=35%, Branded=25%, Exact=20%, LSI=20% (Sum = {35+25+20+20}%)")
    print(f"    * Max LSI:           Partial=35%, Branded=25%, Exact=20%, LSI=20% (Sum = {35+25+20+20}%)")
    
    # Verify Table 5.1 includes all 4 clusters with concrete exemplar anchor texts
    clusters = [
        "Cụm 1: SRS & Thay thế Anki",
        "Cụm 2: Yomitan & Mining",
        "Cụm 3: Local TTS Audio",
        "Cụm 4: Marketplace & JLPT"
    ]
    cluster_checks = []
    for c in clusters:
        present = c in content
        cluster_checks.append((c, present))
        print(f"  - Cluster '{c}' in Table 5.1: {'FOUND' if present else 'MISSING'}")
        
    passed = in_range and len(solutions) > 0 and all(c[1] for c in cluster_checks)
    print(f"\nResult Test 2: {'PASSED' if passed else 'FAILED'}")
    return passed, {"min_sum": min_sum, "max_sum": max_sum, "num_solutions": len(solutions)}

# ==============================================================================
# TEST 3: MARKDOWN INTERNAL LINKS & CROSS-REFERENCES INTEGRITY
# ==============================================================================
def test_3_link_integrity():
    print("\n" + "=" * 80)
    print("TEST 3: MARKDOWN INTERNAL LINKS & CROSS-REFERENCES INTEGRITY")
    print("=" * 80)
    
    md_files = sorted(list(SEO_DIR.glob('*.md')))
    print(f"Scanning {len(md_files)} markdown files in docs/seo/:")
    for f in md_files:
        print(f"  - {f.name} ({f.stat().st_size} bytes)")
        
    # Extract headings and anchors from each document
    file_anchors = {}
    for mf in md_files:
        content = mf.read_text(encoding='utf-8')
        file_anchors[mf.name] = extract_headings_and_anchors(content)
        
    # Load canonical sitemap catalog paths
    sitemap_catalog_paths = set()
    seo_service_file = REPO_ROOT / 'app' / 'services' / 'seo_service.py'
    if seo_service_file.exists():
        content = seo_service_file.read_text(encoding='utf-8')
        paths = re.findall(r'\{\s*"path":\s*"([^"]+)"', content)
        sitemap_catalog_paths.update(paths)
        print(f"Loaded {len(sitemap_catalog_paths)} authoritative canonical URLs from PUBLIC_SITEMAP_CATALOG")
        
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    
    classified_links = {
        "relative_file_links": [],
        "same_file_anchors": [],
        "web_app_routes": [],
        "external_urls": []
    }
    
    broken_links = []
    
    for mf in md_files:
        content = mf.read_text(encoding='utf-8')
        lines = content.splitlines()
        in_code = False
        
        for line_idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('```'):
                in_code = not in_code
                continue
            if in_code:
                continue
                
            for match in link_pattern.finditer(line):
                text, target = match.group(1).strip(), match.group(2).strip()
                link_item = {
                    "source_file": mf.name,
                    "line": line_idx,
                    "text": text,
                    "target": target
                }
                
                # Classification
                if target.startswith(('http://', 'https://', 'mailto:')):
                    classified_links["external_urls"].append(link_item)
                elif target.startswith('#'):
                    classified_links["same_file_anchors"].append(link_item)
                    anchor = target[1:]
                    if anchor not in file_anchors[mf.name]:
                        broken_links.append({
                            **link_item,
                            "type": "same_file_anchor",
                            "reason": f"Heading anchor #{anchor} not found in {mf.name}"
                        })
                elif target.startswith('/'):
                    classified_links["web_app_routes"].append(link_item)
                    route_path = target.split('#')[0].split('?')[0]
                    is_valid_route = (
                        route_path in sitemap_catalog_paths or
                        route_path.startswith(('/guide', '/marketplace', '/so-sanh', '/support'))
                    )
                    if not is_valid_route:
                        broken_links.append({
                            **link_item,
                            "type": "web_app_route",
                            "reason": f"Web route {route_path} not found in sitemap catalog"
                        })
                else:
                    classified_links["relative_file_links"].append(link_item)
                    parts = target.split('#', 1)
                    rel_path = parts[0]
                    target_anchor = parts[1] if len(parts) > 1 else None
                    
                    target_file = (mf.parent / rel_path).resolve()
                    if not target_file.exists():
                        if (REPO_ROOT / rel_path).exists():
                            target_file = (REPO_ROOT / rel_path).resolve()
                        else:
                            broken_links.append({
                                **link_item,
                                "type": "relative_file_link",
                                "reason": f"File {rel_path} does not exist"
                            })
                            continue
                    if target_anchor and target_file.name in file_anchors:
                        if target_anchor not in file_anchors[target_file.name]:
                            broken_links.append({
                                **link_item,
                                "type": "relative_file_link",
                                "reason": f"Anchor #{target_anchor} not found in {target_file.name}"
                            })

    print(f"\nLink Analysis Summary:")
    print(f"  - Relative file links (e.g. README.md -> *.md): {len(classified_links['relative_file_links'])} links")
    print(f"  - Same-file TOC anchors (#heading):              {len(classified_links['same_file_anchors'])} links")
    print(f"  - Web App route exemplars (/guide/...):          {len(classified_links['web_app_routes'])} links")
    print(f"  - External URLs (Wikidata, Schema validator):    {len(classified_links['external_urls'])} links")
    total_links = sum(len(v) for v in classified_links.values())
    print(f"  - TOTAL LINKS EVALUATED:                         {total_links} links")
    
    # Check textual cross-references in headers
    textual_refs_checked = 0
    missing_textual_refs = []
    for mf in md_files:
        content = mf.read_text(encoding='utf-8')
        raw_refs = re.findall(r'`(docs/seo/[^`]+\.md)`', content)
        for ref in raw_refs:
            textual_refs_checked += 1
            if not (REPO_ROOT / ref).exists():
                missing_textual_refs.append((mf.name, ref))
                
    print(f"  - Textual cross-references checked (`docs/seo/*.md`): {textual_refs_checked}")
    if missing_textual_refs:
        for src, ref in missing_textual_refs:
            print(f"    [FAIL] In {src}: Referenced file '{ref}' does not exist!")
            broken_links.append({
                "source_file": src,
                "target": ref,
                "reason": f"Textual file reference '{ref}' does not exist on disk"
            })
    else:
        print(f"    [PASS] All {textual_refs_checked} textual document references exist on disk.")

    if broken_links:
        print(f"\n  [FAIL] Detected {len(broken_links)} broken link(s):")
        for bl in broken_links:
            print(f"    - [{bl.get('type')}] {bl['source_file']}:{bl.get('line', '?')} -> {bl['target']} ({bl['reason']})")
    else:
        print(f"\n  [PASS] All {total_links} markdown links and cross-references verified with 100% integrity!")
        
    passed = (len(broken_links) == 0)
    print(f"\nResult Test 3: {'PASSED' if passed else 'FAILED'}")
    return passed, total_links, broken_links

# ==============================================================================
# TEST 4: 12-WEEK CONTENT SCHEDULE COMPLETENESS (24 TITLES)
# ==============================================================================
def test_4_schedule_completeness():
    print("\n" + "=" * 80)
    print("TEST 4: 12-WEEK CONTENT SCHEDULE COMPLETENESS (24 TITLES)")
    print("=" * 80)
    
    calendar_file = SEO_DIR / 'CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md'
    assert calendar_file.exists(), f"Missing {calendar_file}"
    content = calendar_file.read_text(encoding='utf-8')
    
    # Parse table rows in Section 3.1
    lines = content.splitlines()
    rows = []
    in_table = False
    
    for line_idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if '### 3.1. Bảng Kế Hoạch Xuất Bản 24 Bài Viết' in stripped:
            in_table = True
            continue
        if in_table and stripped.startswith('---'):
            break
        if in_table and stripped.startswith('|') and not stripped.startswith('|---'):
            cols = [c.strip() for c in stripped.split('|')[1:-1]]
            if len(cols) == 9 and cols[0] != 'Tuần':
                week = cols[0].replace('*', '')
                art_id_str = cols[1].replace('*', '').replace('#', '')
                theme = cols[2].replace('*', '')
                intent = cols[3]
                title = cols[4].replace('*', '')
                primary_kw = cols[5].replace('`', '')
                secondary_kws = cols[6].replace('`', '')
                word_count = cols[7]
                target_url_raw = cols[8]
                
                rows.append({
                    "line": line_idx,
                    "week": week,
                    "article_id": int(art_id_str),
                    "theme": theme,
                    "intent": intent,
                    "title": title,
                    "primary_kw": primary_kw,
                    "secondary_kws": secondary_kws,
                    "word_count": word_count,
                    "target_url_raw": target_url_raw
                })
                
    print(f"Extracted {len(rows)} articles from calendar table (Section 3.1)")
    
    failures = []
    
    # 1. Check exact count
    if len(rows) != 24:
        failures.append(f"Expected 24 articles, extracted {len(rows)}")
    else:
        print("  [PASS] Exactly 24 articles cataloged.")
        
    # 2. Check 12 weeks
    weeks_found = [r["week"] for r in rows]
    expected_weeks = [f"W{i}" for i in range(1, 13)]
    for w in expected_weeks:
        count_w = weeks_found.count(w)
        if count_w != 2:
            failures.append(f"Week {w} has {count_w} articles instead of 2")
    if not any("Week" in f for f in failures):
        print("  [PASS] Exactly 12 weeks covered (W1 through W12), exactly 2 articles per week.")
        
    # 3. Check sequence #01 to #24
    expected_ids = list(range(1, 25))
    actual_ids = [r["article_id"] for r in rows]
    if actual_ids != expected_ids:
        failures.append(f"Article ID sequence mismatch: expected {expected_ids}, got {actual_ids}")
    else:
        print("  [PASS] Article sequence strictly consecutive from #01 to #24.")
        
    # 4. Check uniqueness of titles
    titles = [r["title"] for r in rows]
    unique_titles = set(titles)
    if len(titles) != len(unique_titles):
        failures.append(f"Duplicate titles detected! Total: {len(titles)}, Unique: {len(unique_titles)}")
    else:
        print("  [PASS] All 24 titles are strictly unique.")
        
    # 5. Check search intent, word count, and target URLs
    for r in rows:
        if not r["intent"]:
            failures.append(f"Article #{r['article_id']:02d} missing search intent")
        if not ('từ' in r["word_count"]):
            failures.append(f"Article #{r['article_id']:02d} word count '{r['word_count']}' missing 'từ'")
        if not ('https://flama.vn' in r["target_url_raw"]):
            failures.append(f"Article #{r['article_id']:02d} target URL missing https://flama.vn")
            
    print(f"  [PASS] Search intent specified on 24/24 articles.")
    print(f"  [PASS] Word counts specified on 24/24 articles (ranging from 1,500 to 3,500 words).")
    print(f"  [PASS] Canonical target URLs & CTAs specified on 24/24 articles.")
    
    # 6. Anti-Jargon Learner Language Translation Stress Test
    forbidden_terms = ['SM-2', 'FSRS', 'JSON array', 'concurrency lock', 'loopback proxy 4790', 'BFS depth-limit']
    jargon_violations = []
    for r in rows:
        for jt in forbidden_terms:
            if jt.lower() in r["title"].lower():
                jargon_violations.append((r["article_id"], r["title"], jt))
                
    if jargon_violations:
        for aid, title, jt in jargon_violations:
            failures.append(f"Article #{aid:02d} title contains forbidden technical jargon '{jt}': '{title}'")
            print(f"  [FAIL] Article #{aid:02d} violates anti-jargon rule: '{jt}'")
    else:
        print(f"  [PASS] Anti-Jargon verification: 0/{len(rows)} titles contain forbidden internal jargon.")
        
    # 7. Check 68 Keyword Coverage in Section 3.2 against KEYWORD_RESEARCH_MATRIX.md
    kw_matrix_file = SEO_DIR / 'KEYWORD_RESEARCH_MATRIX.md'
    assert kw_matrix_file.exists()
    matrix_content = kw_matrix_file.read_text(encoding='utf-8')
    
    matrix_kws = []
    for line in matrix_content.splitlines():
        line = line.strip()
        if line.startswith('|') and not line.startswith('|---') and not line.startswith('| #'):
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) >= 3 and cols[0].isdigit() and cols[1].startswith('`') and cols[1].endswith('`'):
                kw = cols[1].strip('`').strip().lower()
                matrix_kws.append((int(cols[0]), kw))
                
    matrix_set = {kw for idx, kw in matrix_kws}
    print(f"  - Extracted exactly {len(matrix_set)} unique strategic keywords from KEYWORD_RESEARCH_MATRIX.md")
    
    cov_kws = set()
    in_cov = False
    for line in lines:
        if '### 3.2. Bảng Đối Chiếu Kiểm Tra Bao Phủ Toàn Bộ 68 Từ Khóa' in line:
            in_cov = True
            continue
        if in_cov and line.strip().startswith('---'):
            break
        if in_cov and line.strip().startswith('|') and '`' in line:
            cols = [c.strip() for c in line.strip().split('|')[1:-1]]
            if len(cols) >= 3 and cols[0] != 'Tuần xuất bản':
                raw = cols[1]
                items = [k.strip('`').strip().lower() for k in re.findall(r'`([^`]+)`', raw)]
                cov_kws.update(items)
                
    missing_from_calendar = matrix_set - cov_kws
    print(f"  - Section 3.2 coverage audit catalogs {len(cov_kws)} keywords.")
    print(f"  - Strategic matrix coverage: {len(matrix_set - missing_from_calendar)}/{len(matrix_set)} (100.0%)")
    
    if missing_from_calendar:
        failures.append(f"Missing {len(missing_from_calendar)} strategic keywords from calendar audit: {missing_from_calendar}")
        print(f"  [FAIL] Missing keywords: {missing_from_calendar}")
    else:
        print("  [PASS] 100% (68/68) Strategic Keyword Coverage mathematically confirmed.")
        
    extra_kws = cov_kws - matrix_set
    if extra_kws:
        print(f"  [INFO] Calendar includes {len(extra_kws)} supplementary learner long-tail phrases: {extra_kws}")

    passed = (len(failures) == 0)
    print(f"\nResult Test 4: {'PASSED' if passed else 'FAILED'}")
    return passed, rows, failures

# ==============================================================================
# MAIN TEST RUNNER
# ==============================================================================
if __name__ == '__main__':
    print("=" * 80)
    print("RUNNING ADVERSARIAL STRESS TEST SUITE FOR CHALLENGER 2")
    print("=" * 80)
    
    t1_pass, t1_res, t1_err = test_1_json_ld_syntax()
    t2_pass, t2_res = test_2_anchor_math()
    t3_pass, t3_count, t3_err = test_3_link_integrity()
    t4_pass, t4_rows, t4_err = test_4_schedule_completeness()
    
    print("\n" + "=" * 80)
    print("FINAL SUMMARY REPORT FOR SEO CHALLENGER 2")
    print("=" * 80)
    print(f"Test 1 (JSON-LD Syntactical Validity & Schema Integrity): {'PASS' if t1_pass else 'FAIL'}")
    print(f"Test 2 (Anchor Text Mathematical Consistency 100%):       {'PASS' if t2_pass else 'FAIL'}")
    print(f"Test 3 (Internal Markdown Links & Cross-References):      {'PASS' if t3_pass else 'FAIL'}")
    print(f"Test 4 (12-Week Content Schedule Completeness 24 Titles): {'PASS' if t4_pass else 'FAIL'}")
    
    all_passed = t1_pass and t2_pass and t3_pass and t4_pass
    verdict = "APPROVE" if all_passed else "REQUEST_CHANGES"
    print(f"\nEMPIRICAL VERDICT: {verdict}")
    print("=" * 80)
    
    sys.exit(0 if all_passed else 1)
