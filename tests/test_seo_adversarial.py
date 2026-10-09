"""Adversarial stress-test suite for Technical SEO & GEO implementation.

Written by Challenger 1 (SEO & GEO Adversarial Stress Tester)
Target deliverables:
- app/services/seo_service.py
- app/routes/seo.py
- app/spa.py
- frontend/index.html

Empirical challenges:
1. User-Agent edge cases on /robots.txt (GPTBot/1.0, PerplexityBot, ClaudeBot, Google-Extended, empty, etc.)
2. Parser rule precedence stress test (urllib.robotparser first-match ordering vs RFC 9309 longest-match)
3. HTTP methods and protocol bounds on /robots.txt, /sitemap.xml, /llms.txt
4. /sitemap.xml XML schema, 38 URLs, ISO lastmod dates, priority/changefreq, no private route leaks, no duplicate URLs
5. /llms.txt llmstxt.org specification syntax, markdown structure, feature cluster coverage, link resolution
6. frontend/index.html Schema.org JSON-LD extraction, syntax parsing, entity types (Organization, WebSite, SoftwareApplication, Course, FAQPage), graph integrity
7. Meta tags consistency (canonical, OpenGraph, Twitter Cards)
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
import re
import unittest
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ET

from app import create_app
from app.services.seo_service import (
    DEFAULT_BASE_URL,
    PUBLIC_SITEMAP_CATALOG,
    generate_llms_txt,
    generate_robots_txt,
    generate_sitemap_xml,
)


class SeoAdversarialTestCase(unittest.TestCase):
    """Adversarial test harness probing edge cases and failure modes in SEO/GEO."""

    @classmethod
    def setUpClass(cls):
        """Create test Flask app and test client."""
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "STARTUP_RUN_DEFAULT_USER_ROLE_SEED": False,
                "STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED": False,
                "STARTUP_RUN_CLONE_CUTOVER": False,
            }
        )
        cls.client = cls.app.test_client()
        cls.frontend_index_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

    # =========================================================================
    # 1. User-Agent Edge Cases & /robots.txt HTTP Probes
    # =========================================================================

    def test_robots_txt_under_diverse_crawler_user_agents(self):
        """Probe /robots.txt with diverse, realistic, and edge-case crawler User-Agent headers."""
        user_agents = [
            "GPTBot/1.0",
            "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
            "ClaudeBot/1.0",
            "Google-Extended",
            "ChatGPT-User",
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
            "",  # Empty UA
            "A" * 2048,  # Very long UA
        ]

        for ua in user_agents:
            with self.subTest(user_agent=ua[:40]):
                headers = {"User-Agent": ua} if ua else {}
                resp = self.client.get("/robots.txt", headers=headers)
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.content_type.startswith("text/plain"))
                self.assertIn("charset=utf-8", resp.content_type.lower())
                self.assertIn("max-age=86400", resp.headers.get("Cache-Control", ""))

                body = resp.data.decode("utf-8")
                # Must not be intercepted by SPA shell
                self.assertNotIn("<!doctype html>", body.lower())
                self.assertNotIn('<div id="root">', body)

                # Directives must be intact regardless of request UA
                self.assertIn("User-agent: GPTBot", body)
                self.assertIn("User-agent: PerplexityBot", body)
                self.assertIn("User-agent: ClaudeBot", body)
                self.assertIn("User-agent: Google-Extended", body)
                self.assertIn("User-agent: ChatGPT-User", body)
                self.assertIn("User-agent: *", body)
                self.assertIn("Sitemap: https://flama.vn/sitemap.xml", body)

    def test_robots_txt_http_methods_and_head(self):
        """Ensure HTTP HEAD works and unsupported HTTP methods (POST, PUT, DELETE) are rejected."""
        # HEAD should return 200 with matching headers and empty/no body
        head_resp = self.client.head("/robots.txt")
        self.assertEqual(head_resp.status_code, 200)
        self.assertTrue(head_resp.content_type.startswith("text/plain"))
        self.assertIn("max-age=86400", head_resp.headers.get("Cache-Control", ""))

        # POST /robots.txt should return 405 Method Not Allowed
        post_resp = self.client.post("/robots.txt", data={"evil": "payload"})
        self.assertEqual(post_resp.status_code, 405)

        # PUT and DELETE should return 405
        put_resp = self.client.put("/robots.txt")
        self.assertEqual(put_resp.status_code, 405)
        del_resp = self.client.delete("/robots.txt")
        self.assertEqual(del_resp.status_code, 405)

    def test_robots_txt_rule_ordering_parser_stress(self):
        """Stress-test robots.txt with Python standard library urllib.robotparser.

        NOTE ON PARSER VARIATIONS:
        RFC 9309 (modern AI engines: Google, Bing, OpenAI, Perplexity) evaluates rules by longest matching path.
        However, first-match parsers (such as Python's urllib.robotparser) evaluate rules top-to-bottom.
        Having 'Allow: /' at the top of a block before 'Disallow: /api/' causes urllib.robotparser to treat
        everything starting with '/' as allowed.
        """
        resp = self.client.get("/robots.txt")
        self.assertEqual(resp.status_code, 200)
        content = resp.data.decode("utf-8")

        # Parse with standard library RobotFileParser
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(content.splitlines())

        # Public paths should be allowed
        self.assertTrue(rp.can_fetch("GPTBot", "https://flama.vn/"))
        self.assertTrue(rp.can_fetch("GPTBot", "https://flama.vn/guide"))
        self.assertTrue(rp.can_fetch("GPTBot", "https://flama.vn/support"))
        self.assertTrue(rp.can_fetch("GPTBot", "https://flama.vn/llms.txt"))

        # Check explicit Disallow directives in the text
        disallowed_routes = [
            "/api/",
            "/dashboard",
            "/statistics",
            "/browse",
            "/study",
            "/admin/",
            "/settings/",
        ]
        for route in disallowed_routes:
            self.assertIn(f"Disallow: {route}", content)

    # =========================================================================
    # 2. XML Schema & Sitemap Validation
    # =========================================================================

    def test_sitemap_xml_schema_and_integrity(self):
        """Validate XML syntax, schema namespace, urlset root, and catalog alignment."""
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            resp.content_type.startswith("application/xml")
            or resp.content_type.startswith("text/xml")
        )
        self.assertIn("charset=utf-8", resp.content_type.lower())
        self.assertIn("max-age=3600", resp.headers.get("Cache-Control", ""))

        xml_raw = resp.data.decode("utf-8")
        self.assertNotIn("<!doctype html>", xml_raw.lower())
        self.assertTrue(xml_raw.startswith("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"))

        # Parse with ElementTree
        root = ET.fromstring(xml_raw)
        self.assertEqual(root.tag, "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")

        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sm:url", ns)

        # Must have exactly 38 URLs
        self.assertEqual(len(urls), 38)
        self.assertEqual(len(PUBLIC_SITEMAP_CATALOG), 38)

        # Check duplicates
        locs = [u.find("sm:loc", ns).text for u in urls if u.find("sm:loc", ns) is not None]
        self.assertEqual(len(locs), 38)
        self.assertEqual(len(set(locs)), 38, "Duplicate URLs found in sitemap.xml!")

        # Check each entry
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        valid_changefreqs = {"always", "hourly", "daily", "weekly", "monthly", "yearly", "never"}

        for url_elem in urls:
            loc = url_elem.find("sm:loc", ns).text
            lastmod = url_elem.find("sm:lastmod", ns).text
            changefreq = url_elem.find("sm:changefreq", ns).text
            priority = url_elem.find("sm:priority", ns).text

            # Loc validity
            parsed_loc = urllib.parse.urlparse(loc)
            self.assertEqual(parsed_loc.scheme, "https")
            self.assertEqual(parsed_loc.netloc, "flama.vn")
            self.assertFalse("//" in parsed_loc.path, f"Double slashes in path: {loc}")

            # Lastmod ISO format validity
            try:
                dt = datetime.date.fromisoformat(lastmod)
            except ValueError:
                self.fail(f"Invalid ISO lastmod format: {lastmod}")
            self.assertEqual(lastmod, today)

            # Changefreq validity
            self.assertIn(changefreq, valid_changefreqs)

            # Priority validity
            p_float = float(priority)
            self.assertTrue(0.0 <= p_float <= 1.0)

    def test_sitemap_xml_zero_private_route_leaks(self):
        """Adversarial scan verifying NO private, auth, admin, or API paths exist in sitemap.xml."""
        resp = self.client.get("/sitemap.xml")
        root = ET.fromstring(resp.data.decode("utf-8"))
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [u.find("sm:loc", ns).text for u in root.findall("sm:url", ns)]

        forbidden_prefixes = [
            "/api",
            "/dashboard",
            "/statistics",
            "/browse",
            "/study",
            "/installed-decks",
            "/sync",
            "/import",
            "/worksheets",
            "/audio/generate",
            "/settings",
            "/admin",
            "/wallet",
            "/orders",
            "/tickets",
            "/feedback",
            "/creator",
            "/auth",
            "/oauth",
            "/login",
            "/register",
        ]

        for loc in locs:
            parsed = urllib.parse.urlparse(loc)
            path = parsed.path
            for forbidden in forbidden_prefixes:
                # Direct match or exact subpath match
                self.assertFalse(
                    path == forbidden or path.startswith(f"{forbidden}/"),
                    f"PRIVATE ROUTE LEAK DETECTED: {loc} matches forbidden prefix {forbidden}",
                )

    def test_sitemap_xml_http_methods(self):
        """Validate HEAD and rejected methods on /sitemap.xml."""
        head_resp = self.client.head("/sitemap.xml")
        self.assertEqual(head_resp.status_code, 200)
        self.assertTrue(
            head_resp.content_type.startswith("application/xml")
            or head_resp.content_type.startswith("text/xml")
        )

        post_resp = self.client.post("/sitemap.xml")
        self.assertEqual(post_resp.status_code, 405)

    # =========================================================================
    # 3. llms.txt Specification & Link Resolution
    # =========================================================================

    def test_llms_txt_structure_and_syntax(self):
        """Validate llms.txt format against llmstxt.org specification."""
        resp = self.client.get("/llms.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content_type.startswith("text/plain"))
        self.assertIn("charset=utf-8", resp.content_type.lower())
        self.assertIn("max-age=86400", resp.headers.get("Cache-Control", ""))

        content = resp.data.decode("utf-8")
        self.assertNotIn("<!doctype html>", content.lower())

        # llmstxt.org structure: H1 title, summary blockquote, H2 sections
        self.assertTrue(content.startswith("# Flama"), "Must start with H1 '# Flama'")

        # Blockquote summary
        bq_match = re.search(r"^>\s+(.+)$", content, re.MULTILINE)
        self.assertIsNotNone(bq_match, "llms.txt must have a blockquote summary right below H1")
        self.assertIn("https://flama.vn", bq_match.group(1))

        # Required H2 sections
        expected_sections = [
            "Core Features & Concepts",
            "Guides & Documentation",
            "AI Agent & Model Context Protocol (MCP)",
            "Legal & Community",
        ]
        for sec in expected_sections:
            self.assertIn(f"## {sec}", content)

        # Core feature clusters coverage
        self.assertIn("Spaced Repetition", content)
        self.assertIn("Yomitan", content)
        self.assertIn("VoiceVox & Kokoro", content)
        self.assertIn("Marketplace", content)
        self.assertIn("Clone Overlay", content)

    def test_llms_txt_links_resolution_and_integrity(self):
        """Verify that all markdown links in llms.txt are valid and resolvable."""
        resp = self.client.get("/llms.txt")
        content = resp.data.decode("utf-8")

        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
        self.assertGreaterEqual(len(links), 12, "Must contain at least 12 links")

        # Map public catalog paths for cross-checking
        catalog_paths = {entry["path"] for entry in PUBLIC_SITEMAP_CATALOG}

        for text, url in links:
            with self.subTest(link_text=text, url=url):
                parsed = urllib.parse.urlparse(url)
                self.assertEqual(parsed.scheme, "https")
                self.assertEqual(parsed.netloc, "flama.vn")

                path = parsed.path
                # Check if it's an API/discovery path or a cataloged page
                if path in ("/api/mcp", "/.well-known/oauth-protected-resource"):
                    # Known service endpoints
                    pass
                else:
                    # Public content links should exist in PUBLIC_SITEMAP_CATALOG
                    self.assertIn(
                        path,
                        catalog_paths,
                        f"llms.txt link target '{path}' is not cataloged in PUBLIC_SITEMAP_CATALOG",
                    )

    def test_llms_txt_http_methods(self):
        """Validate HEAD and rejected methods on /llms.txt."""
        head_resp = self.client.head("/llms.txt")
        self.assertEqual(head_resp.status_code, 200)
        self.assertTrue(head_resp.content_type.startswith("text/plain"))

        post_resp = self.client.post("/llms.txt")
        self.assertEqual(post_resp.status_code, 405)

    # =========================================================================
    # 4. Schema.org JSON-LD Extraction & Graph Validation
    # =========================================================================

    def test_frontend_index_html_json_ld_schema_graph(self):
        """Extract and thoroughly validate Schema.org JSON-LD graph in frontend/index.html."""
        self.assertTrue(self.frontend_index_path.is_file(), f"File missing: {self.frontend_index_path}")
        html_content = self.frontend_index_path.read_text(encoding="utf-8")

        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
        self.assertIsNotNone(match, "Missing <script type=\"application/ld+json\"> in index.html")

        # Strict JSON parse
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            self.fail(f"Invalid JSON in Schema.org JSON-LD: {e}")

        # @context and @graph
        self.assertEqual(data.get("@context"), "https://schema.org")
        graph = data.get("@graph")
        self.assertIsInstance(graph, list, "@graph must be a list of entity dictionaries")

        # Index entities by type and by @id
        by_type: dict[str, dict] = {}
        by_id: dict[str, dict] = {}
        for entity in graph:
            etype = entity.get("@type")
            eid = entity.get("@id")
            by_type[etype] = entity
            if eid:
                by_id[eid] = entity

        # 1. Organization
        self.assertIn("Organization", by_type)
        org = by_type["Organization"]
        self.assertEqual(org.get("@id"), "https://flama.vn/#organization")
        self.assertEqual(org.get("name"), "Flama")
        self.assertEqual(org.get("legalName"), "Flama Vietnam")
        self.assertEqual(org.get("url"), "https://flama.vn")
        self.assertIsInstance(org.get("logo"), dict)
        self.assertEqual(org["logo"].get("@type"), "ImageObject")
        self.assertEqual(org["logo"].get("url"), "https://flama.vn/logo.png")
        self.assertIsInstance(org.get("sameAs"), list)
        self.assertIn("https://github.com/TrinhChung/Flama", org.get("sameAs", []))
        self.assertIsInstance(org.get("contactPoint"), dict)
        self.assertEqual(org["contactPoint"].get("url"), "https://flama.vn/support")

        # 2. WebSite
        self.assertIn("WebSite", by_type)
        site = by_type["WebSite"]
        self.assertEqual(site.get("@id"), "https://flama.vn/#website")
        self.assertEqual(site.get("url"), "https://flama.vn")
        self.assertEqual(site.get("name"), "Flama")
        self.assertEqual(site.get("inLanguage"), "vi")
        self.assertEqual(site.get("publisher", {}).get("@id"), org["@id"])

        # 3. SoftwareApplication (or EducationalApplication)
        self.assertIn("SoftwareApplication", by_type)
        app = by_type["SoftwareApplication"]
        self.assertEqual(app.get("@id"), "https://flama.vn/#app")
        self.assertEqual(app.get("name"), "Flama")
        self.assertEqual(app.get("applicationCategory"), "EducationalApplication")
        self.assertIn("Web, Windows", app.get("operatingSystem", ""))
        self.assertIsInstance(app.get("offers"), dict)
        self.assertEqual(app["offers"].get("price"), "0")
        self.assertEqual(app["offers"].get("priceCurrency"), "VND")
        self.assertEqual(app.get("publisher", {}).get("@id"), org["@id"])

        # 4. Course
        self.assertIn("Course", by_type)
        course = by_type["Course"]
        self.assertEqual(course.get("@id"), "https://flama.vn/#course-jlpt")
        self.assertIn("JLPT", course.get("name", ""))
        self.assertEqual(course.get("provider", {}).get("@id"), org["@id"])
        self.assertEqual(course.get("inLanguage"), "vi")

        # 5. FAQPage
        self.assertIn("FAQPage", by_type)
        faq = by_type["FAQPage"]
        self.assertEqual(faq.get("@id"), "https://flama.vn/#faq")
        main_entities = faq.get("mainEntity")
        self.assertIsInstance(main_entities, list)
        self.assertGreaterEqual(len(main_entities), 3)

        for q in main_entities:
            self.assertEqual(q.get("@type"), "Question")
            self.assertTrue(bool(q.get("name")), "Question must have name")
            ans = q.get("acceptedAnswer")
            self.assertIsInstance(ans, dict)
            self.assertEqual(ans.get("@type"), "Answer")
            self.assertTrue(bool(ans.get("text")), "Answer must have text")

        # Graph Reference Integrity: Verify all '@id' references point to defined entities
        for entity in graph:
            for k, v in entity.items():
                if isinstance(v, dict) and "@id" in v and len(v) == 1:
                    target_id = v["@id"]
                    self.assertIn(
                        target_id,
                        by_id,
                        f"Dangling @id reference '{target_id}' found in entity {entity.get('@type')}",
                    )

    def test_frontend_index_html_meta_tags_consistency(self):
        """Validate canonical, OpenGraph, and Twitter tags in frontend/index.html."""
        html_content = self.frontend_index_path.read_text(encoding="utf-8")

        # Canonical URL
        self.assertIn('<link rel="canonical" href="https://flama.vn" />', html_content)

        # OpenGraph
        self.assertIn('<meta property="og:type" content="website" />', html_content)
        self.assertIn('<meta property="og:url" content="https://flama.vn" />', html_content)
        self.assertIn('<meta property="og:site_name" content="Flama" />', html_content)
        self.assertIn('<meta property="og:locale" content="vi_VN" />', html_content)
        self.assertIn('<meta property="og:image" content="https://flama.vn/logo.png" />', html_content)

        # Twitter
        self.assertIn('<meta name="twitter:card" content="summary_large_image" />', html_content)
        self.assertIn('<meta name="twitter:url" content="https://flama.vn" />', html_content)
        self.assertIn('<meta name="twitter:image" content="https://flama.vn/logo.png" />', html_content)


if __name__ == "__main__":
    unittest.main()
