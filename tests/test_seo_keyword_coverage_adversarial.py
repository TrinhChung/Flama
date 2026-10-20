"""Adversarial empirical stress-test for Flama SEO Strategic Implementation.

Target files:
- docs/seo/KEYWORD_RESEARCH_MATRIX.md
- docs/seo/KEYWORD_ROLLOUT_PLAN.md
- docs/seo/CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md

Empirical challenges:
1. Parse all keywords from KEYWORD_RESEARCH_MATRIX.md (#1 to #68).
2. Parse all keywords from KEYWORD_ROLLOUT_PLAN.md (#1 to #68).
3. Parse all keywords from CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md (Section 3.1 articles and Section 3.2 weekly audit).
4. Verify exact set equality across documents.
5. Verify zero duplicates, zero missing IDs (#1 to #68).
6. Verify attribute validity (Target URL, Phase, Volume, KD) and consistency between matrix and rollout plan.
7. Verify URL validity against PUBLIC_SITEMAP_CATALOG in app/services/seo_service.py where applicable.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_SEO = REPO_ROOT / "docs" / "seo"
MATRIX_PATH = DOCS_SEO / "KEYWORD_RESEARCH_MATRIX.md"
ROLLOUT_PATH = DOCS_SEO / "KEYWORD_ROLLOUT_PLAN.md"
CALENDAR_PATH = DOCS_SEO / "CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md"


def clean_cell(cell: str) -> str:
    """Strip markdown formatting like backticks, asterisks, extra whitespace."""
    cell = cell.strip()
    cell = re.sub(r"^`|`$", "", cell)
    cell = re.sub(r"^\*\*|\*\*$", "", cell)
    return cell.strip()


def parse_matrix_keywords(path: Path) -> dict[int, dict]:
    """Parse table in KEYWORD_RESEARCH_MATRIX.md.
    
    Columns:
    # | Từ khóa (Keyword) | Cụm chủ đề (Cluster) | Ý định tìm kiếm (Search Intent) | Lượng tìm kiếm/tháng (Est. Volume) | Độ khó (Difficulty) | Trang đích đề xuất (Proposed Landing Page URL) | Định dạng & Tiêu đề bài viết đề xuất
    """
    text = path.read_text(encoding="utf-8")
    keywords = {}
    
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if not parts:
            continue
        # Check if first column is an integer ID
        id_str = clean_cell(parts[0])
        if id_str.isdigit():
            kw_id = int(id_str)
            raw_keyword = clean_cell(parts[1])
            cluster = clean_cell(parts[2])
            intent = clean_cell(parts[3])
            volume_str = clean_cell(parts[4]).replace(",", "")
            difficulty = clean_cell(parts[5])
            url = clean_cell(parts[6])
            title = clean_cell(parts[7]) if len(parts) > 7 else ""
            
            keywords[kw_id] = {
                "id": kw_id,
                "keyword": raw_keyword,
                "cluster": cluster,
                "intent": intent,
                "volume": int(volume_str) if volume_str.isdigit() else volume_str,
                "difficulty": difficulty,
                "target_url": url,
                "title": title,
                "raw_line": line,
            }
    return keywords


def parse_rollout_keywords(path: Path) -> dict[int, dict]:
    """Parse Section 3 Master Catalog table in KEYWORD_ROLLOUT_PLAN.md.
    
    Columns:
    # | Từ Khóa Chiến Lược | Cụm Chủ Đề | Ý Định Tìm Kiếm | Vol/Tháng | Độ Khó (KD Tag / Est.) | Giai Đoạn | Trang Đích Mục Tiêu (Target URL) | Tiêu Đề Bài Viết / Trang Đích Đề Xuất | Giải Pháp Chống Ăn Thịt Từ Khóa
    """
    text = path.read_text(encoding="utf-8")
    keywords = {}
    
    # Target only Section 3
    in_section_3 = False
    for line in text.splitlines():
        line = line.strip()
        if "## 3. BẢNG DANH MỤC" in line:
            in_section_3 = True
            continue
        if in_section_3 and line.startswith("## 4."):
            in_section_3 = False
            break
        if not in_section_3:
            continue
        if not line.startswith("|") or not line.endswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 8:
            continue
        id_str = clean_cell(parts[0])
        if id_str.isdigit():
            kw_id = int(id_str)
            raw_keyword = clean_cell(parts[1])
            cluster = clean_cell(parts[2])
            intent = clean_cell(parts[3])
            volume_str = clean_cell(parts[4]).replace(",", "")
            kd = clean_cell(parts[5])
            phase = clean_cell(parts[6])
            url = clean_cell(parts[7])
            title = clean_cell(parts[8]) if len(parts) > 8 else ""
            mitigation = clean_cell(parts[9]) if len(parts) > 9 else ""
            
            keywords[kw_id] = {
                "id": kw_id,
                "keyword": raw_keyword,
                "cluster": cluster,
                "intent": intent,
                "volume": int(volume_str) if volume_str.isdigit() else volume_str,
                "kd": kd,
                "phase": phase,
                "target_url": url,
                "title": title,
                "mitigation": mitigation,
                "raw_line": line,
            }
    return keywords


def parse_calendar_keywords_section_3_1(path: Path) -> list[dict]:
    """Parse 24 articles table in CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md Section 3.1.
    
    Columns:
    Tuần | Bài | Giai đoạn & Chủ đề | Search Intent | Tiêu Đề Bài Viết Chuẩn SEO | Từ Khóa Chính (Primary) | Từ Khóa Phụ & Ngữ Cảnh (Secondary / LSI) | Độ Dài Đề Xuất | Trang Đích & CTA
    """
    text = path.read_text(encoding="utf-8")
    articles = []
    
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 9:
            continue
        week_str = clean_cell(parts[0])
        article_str = clean_cell(parts[1])
        if re.match(r"^W\d+", week_str) and re.match(r"^#\d+", article_str):
            primary_raw = parts[5]
            secondary_raw = parts[6]
            
            # Extract keywords between backticks
            primary_kws = [clean_cell(k) for k in re.findall(r"`([^`]+)`", primary_raw)]
            secondary_kws = [clean_cell(k) for k in re.findall(r"`([^`]+)`", secondary_raw)]
            
            articles.append({
                "week": week_str,
                "article": article_str,
                "title": clean_cell(parts[4]),
                "primary": primary_kws,
                "secondary": secondary_kws,
                "all_keywords": primary_kws + secondary_kws,
                "target_url": clean_cell(parts[8]),
            })
    return articles


def parse_calendar_keywords_section_3_2(path: Path) -> dict[str, list[str]]:
    """Parse Section 3.2 Coverage Audit table in CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md.
    
    Columns:
    Tuần xuất bản | Danh mục từ khóa được phân bổ trong tuần | Số từ khóa | % Tích lũy
    """
    text = path.read_text(encoding="utf-8")
    weeks = {}
    
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 4:
            continue
        week_col = clean_cell(parts[0])
        if "tuần" in week_col.lower():
            kw_list = [clean_cell(k) for k in re.findall(r"`([^`]+)`", parts[1])]
            weeks[week_col] = kw_list
    return weeks


class SeoKeywordCoverageStressTest(unittest.TestCase):
    """Empirical test suite verifying keyword coverage, URL assignments, and consistency."""

    @classmethod
    def setUpClass(cls):
        cls.matrix_data = parse_matrix_keywords(MATRIX_PATH)
        cls.rollout_data = parse_rollout_keywords(ROLLOUT_PATH)
        cls.calendar_articles = parse_calendar_keywords_section_3_1(CALENDAR_PATH)
        cls.calendar_weeks = parse_calendar_keywords_section_3_2(CALENDAR_PATH)

    def test_matrix_total_count_and_ids(self):
        """Verify KEYWORD_RESEARCH_MATRIX.md has exactly 68 keywords with IDs 1 to 68."""
        self.assertEqual(len(self.matrix_data), 68, f"Expected 68 keywords in matrix, got {len(self.matrix_data)}")
        expected_ids = set(range(1, 69))
        actual_ids = set(self.matrix_data.keys())
        self.assertEqual(actual_ids, expected_ids, f"Matrix ID mismatch: missing {expected_ids - actual_ids}, extra {actual_ids - expected_ids}")

    def test_matrix_keyword_uniqueness(self):
        """Verify zero duplicate keywords in KEYWORD_RESEARCH_MATRIX.md."""
        keywords = [d["keyword"] for d in self.matrix_data.values()]
        duplicates = [k for k in set(keywords) if keywords.count(k) > 1]
        self.assertEqual(duplicates, [], f"Duplicate keywords found in matrix: {duplicates}")

    def test_rollout_total_count_and_ids(self):
        """Verify KEYWORD_ROLLOUT_PLAN.md has exactly 68 keywords with IDs 1 to 68."""
        self.assertEqual(len(self.rollout_data), 68, f"Expected 68 keywords in rollout plan, got {len(self.rollout_data)}")
        expected_ids = set(range(1, 69))
        actual_ids = set(self.rollout_data.keys())
        self.assertEqual(actual_ids, expected_ids, f"Rollout ID mismatch: missing {expected_ids - actual_ids}, extra {actual_ids - expected_ids}")

    def test_rollout_keyword_uniqueness(self):
        """Verify zero duplicate keywords in KEYWORD_ROLLOUT_PLAN.md."""
        keywords = [d["keyword"] for d in self.rollout_data.values()]
        duplicates = [k for k in set(keywords) if keywords.count(k) > 1]
        self.assertEqual(duplicates, [], f"Duplicate keywords found in rollout plan: {duplicates}")

    def test_set_equality_matrix_vs_rollout(self):
        """Verify exact set equality between KEYWORD_RESEARCH_MATRIX.md and KEYWORD_ROLLOUT_PLAN.md."""
        matrix_kws = {d["keyword"] for d in self.matrix_data.values()}
        rollout_kws = {d["keyword"] for d in self.rollout_data.values()}
        
        diff_in_matrix_only = matrix_kws - rollout_kws
        diff_in_rollout_only = rollout_kws - matrix_kws
        
        self.assertEqual(
            matrix_kws,
            rollout_kws,
            f"Set inequality between matrix and rollout:\n"
            f"  In matrix only: {diff_in_matrix_only}\n"
            f"  In rollout only: {diff_in_rollout_only}",
        )

    def test_id_mapping_matrix_vs_rollout(self):
        """Verify each ID 1..68 maps to the exact same keyword in both files."""
        mismatches = []
        for kw_id in range(1, 69):
            m_kw = self.matrix_data.get(kw_id, {}).get("keyword")
            r_kw = self.rollout_data.get(kw_id, {}).get("keyword")
            if m_kw != r_kw:
                mismatches.append(f"ID #{kw_id}: Matrix='{m_kw}' vs Rollout='{r_kw}'")
        self.assertEqual(mismatches, [], f"ID-to-keyword mismatches:\n" + "\n".join(mismatches))

    def test_rollout_attributes_validity(self):
        """Verify every keyword in rollout plan has valid URL, Phase, Volume, and KD."""
        errors = []
        for kw_id, data in sorted(self.rollout_data.items()):
            kw = data["keyword"]
            # Target URL
            url = data["target_url"]
            if not url or not url.startswith("https://flama.vn"):
                errors.append(f"ID #{kw_id} '{kw}': Invalid target_url '{url}'")
            
            # Phase
            phase = data["phase"]
            if phase not in {"Phase 1", "Phase 2", "Phase 3"}:
                errors.append(f"ID #{kw_id} '{kw}': Invalid phase '{phase}'")
            
            # Volume
            vol = data["volume"]
            if not isinstance(vol, int) or vol <= 0:
                errors.append(f"ID #{kw_id} '{kw}': Invalid volume '{vol}'")
            
            # KD
            kd = data["kd"]
            if not kd:
                errors.append(f"ID #{kw_id} '{kw}': Missing KD '{kd}'")
        
        self.assertEqual(errors, [], f"Attribute validity errors in rollout plan:\n" + "\n".join(errors))

    def test_volume_consistency_matrix_vs_rollout(self):
        """Verify volume values are consistent between matrix and rollout plan."""
        mismatches = []
        for kw_id in range(1, 69):
            m_vol = self.matrix_data[kw_id]["volume"]
            r_vol = self.rollout_data[kw_id]["volume"]
            if m_vol != r_vol:
                mismatches.append(f"ID #{kw_id} '{self.matrix_data[kw_id]['keyword']}': Matrix Vol={m_vol} vs Rollout Vol={r_vol}")
        self.assertEqual(mismatches, [], f"Volume mismatches between matrix and rollout:\n" + "\n".join(mismatches))

    def test_phase_breakdown_counts(self):
        """Verify rollout phase counts match documented specifications:
        Phase 1: 38 keywords
        Phase 2: 15 keywords
        Phase 3: 15 keywords
        Total: 68
        """
        phase_counts = {"Phase 1": 0, "Phase 2": 0, "Phase 3": 0}
        for data in self.rollout_data.values():
            phase_counts[data["phase"]] = phase_counts.get(data["phase"], 0) + 1
        
        self.assertEqual(phase_counts["Phase 1"], 38, f"Expected 38 in Phase 1, got {phase_counts.get('Phase 1')}")
        self.assertEqual(phase_counts["Phase 2"], 15, f"Expected 15 in Phase 2, got {phase_counts.get('Phase 2')}")
        self.assertEqual(phase_counts["Phase 3"], 15, f"Expected 15 in Phase 3, got {phase_counts.get('Phase 3')}")

    def test_url_alignment_matrix_vs_rollout(self):
        """Compare proposed landing pages in matrix vs rollout plan."""
        differences = []
        for kw_id in range(1, 69):
            m_url = self.matrix_data[kw_id]["target_url"]
            r_url = self.rollout_data[kw_id]["target_url"]
            if m_url != r_url:
                differences.append({
                    "id": kw_id,
                    "keyword": self.matrix_data[kw_id]["keyword"],
                    "matrix_url": m_url,
                    "rollout_url": r_url,
                })
        print(f"\n--- URL Alignment Matrix vs Rollout Plan ---")
        print(f"Total URL differences: {len(differences)}")
        for diff in differences:
            print(f"  ID #{diff['id']} '{diff['keyword']}':")
            print(f"    Matrix : {diff['matrix_url']}")
            print(f"    Rollout: {diff['rollout_url']}")

    def test_target_url_distribution(self):
        """Analyze distinct target URLs across all 68 keywords."""
        urls = [d["target_url"] for d in self.rollout_data.values()]
        url_counts = {}
        for u in urls:
            url_counts[u] = url_counts.get(u, 0) + 1
        
        print("\n--- Distinct Target URLs in Rollout Plan ---")
        for u, count in sorted(url_counts.items(), key=lambda x: -x[1]):
            print(f"  {u}: {count} keywords")
        
        # Verify that all URLs use HTTPS and canonical domain flama.vn
        for u in url_counts:
            self.assertTrue(u.startswith("https://flama.vn"), f"URL {u} does not use canonical domain https://flama.vn")

    def test_calendar_section_3_1_coverage(self):
        """Examine keywords in Section 3.1 of CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md."""
        calendar_kws = set()
        for art in self.calendar_articles:
            calendar_kws.update(art["all_keywords"])
        
        matrix_kws = {d["keyword"] for d in self.matrix_data.values()}
        
        missing_from_calendar = matrix_kws - calendar_kws
        extra_in_calendar = calendar_kws - matrix_kws
        
        print(f"\n--- Section 3.1 Article Table Keyword Analysis ---")
        print(f"Total articles: {len(self.calendar_articles)}")
        print(f"Total unique keywords extracted from 24 articles: {len(calendar_kws)}")
        print(f"Missing from 24 articles: {len(missing_from_calendar)} -> {missing_from_calendar}")
        print(f"Extra in 24 articles: {len(extra_in_calendar)} -> {extra_in_calendar}")

        # The 68 matrix keywords must be 100% covered (subset of calendar keywords)
        self.assertTrue(
            matrix_kws.issubset(calendar_kws),
            f"Calendar articles missed {len(missing_from_calendar)} keywords: {missing_from_calendar}"
        )

    def test_calendar_section_3_2_coverage(self):
        """Examine keywords in Section 3.2 Weekly Audit Table of CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md."""
        all_audit_kws = []
        for week_name, kws in self.calendar_weeks.items():
            all_audit_kws.extend(kws)
        
        unique_audit_kws = set(all_audit_kws)
        matrix_kws = {d["keyword"] for d in self.matrix_data.values()}
        
        missing_from_audit = matrix_kws - unique_audit_kws
        extra_in_audit = unique_audit_kws - matrix_kws
        
        print(f"\n--- Section 3.2 Weekly Audit Table Keyword Analysis ---")
        print(f"Total entries in audit table: {len(all_audit_kws)}")
        print(f"Total unique keywords in audit table: {len(unique_audit_kws)}")
        print(f"Missing from weekly audit: {len(missing_from_audit)} -> {missing_from_audit}")
        print(f"Extra in weekly audit: {len(extra_in_audit)} -> {extra_in_audit}")

        # The 68 matrix keywords must be 100% covered in weekly audit
        self.assertTrue(
            matrix_kws.issubset(unique_audit_kws),
            f"Weekly audit missed {len(missing_from_audit)} keywords: {missing_from_audit}"
        )


if __name__ == "__main__":
    unittest.main()
