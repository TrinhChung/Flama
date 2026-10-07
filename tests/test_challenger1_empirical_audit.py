"""Empirical Challenger 1 Test Suite — Technical SEO & GEO Validation.

Verifies:
1. Edge-case crawler User-Agent headers on /robots.txt
2. XML schema validation of /sitemap.xml (all 38 URLs, namespaces, lastmod, zero private leaks)
3. llmstxt.org specification compliance of /llms.txt
4. Schema.org JSON-LD graph extraction and validation from frontend/index.html
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


class Challenger1EmpiricalAuditTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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

    # -------------------------------------------------------------------------
    # 1. Edge-case crawler User-Agent headers on /robots.txt
    # -------------------------------------------------------------------------

    def test_robots_txt_edge_case_crawlers_and_anomalous_headers(self):
        """Test edge-case crawler User-Agent headers on /robots.txt."""
        edge_crawlers = [
            ("GPTBot/1.0", "GPTBot token"),
            ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.0; +https://openai.com/gptbot)", "GPTBot full UA"),
            ("PerplexityBot", "PerplexityBot simple"),
            ("Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)", "PerplexityBot full UA"),
            ("ClaudeBot", "ClaudeBot simple"),
            ("ClaudeBot/1.0", "ClaudeBot versioned"),
            ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +https://claudebot.com)", "ClaudeBot full UA"),
            ("Google-Extended", "Google-Extended token"),
            ("ChatGPT-User", "ChatGPT-User token"),
            ("ChatGPT-User/1.0", "ChatGPT-User versioned"),
            ("Googlebot/2.1 (+http://www.google.com/bot.html)", "Googlebot standard"),
            ("Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", "bingbot"),
            ("", "Empty User-Agent"),
            ("A" * 4096, "Oversized User-Agent (4KB)"),
            ("SELECT * FROM users WHERE '1'='1'", "SQL injection attempt"),
            ("<script>alert('xss')</script>", "XSS payload attempt"),
        ]

        for ua, label in edge_crawlers:
            with self.subTest(crawler=label):
                headers = {"User-Agent": ua} if ua else {}
                response = self.client.get("/robots.txt", headers=headers)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "text/plain")
                self.assertIn("charset=utf-8", response.content_type.lower())
                self.assertIn("max-age=86400", response.headers.get("Cache-Control", ""))

                body = response.data.decode("utf-8")
                self.assertNotIn("<!doctype html>", body.lower())
                self.assertNotIn('<div id="root">', body)

                # Essential directives must be present
                self.assertIn("User-agent: GPTBot", body)
                self.assertIn("User-agent: PerplexityBot", body)
                self.assertIn("User-agent: ClaudeBot", body)
                self.assertIn("User-agent: Google-Extended", body)
                self.assertIn("User-agent: ChatGPT-User", body)
                self.assertIn("User-agent: *", body)
                self.assertIn("Sitemap: https://flama.vn/sitemap.xml", body)

    def test_robots_txt_http_verbs_and_head(self):
        """Verify HTTP method boundaries for /robots.txt."""
        head_resp = self.client.head("/robots.txt")
        self.assertEqual(head_resp.status_code, 200)
        self.assertEqual(head_resp.mimetype, "text/plain")
        self.assertEqual(len(head_resp.data), 0)

        for verb in ["post", "put", "delete", "patch"]:
            resp = getattr(self.client, verb)("/robots.txt")
            self.assertEqual(resp.status_code, 405)

    def test_robots_txt_parser_behavior_and_rule_audit(self):
        """Analyze crawler parsing behavior and identify rule differences."""
        body = self.client.get("/robots.txt").data.decode("utf-8")

        # Verify presence of AI search crawler blocks
        self.assertIn("User-agent: GPTBot", body)
        self.assertIn("User-agent: PerplexityBot", body)
        self.assertIn("User-agent: ClaudeBot", body)
        self.assertIn("User-agent: Google-Extended", body)
        self.assertIn("User-agent: ChatGPT-User", body)

        # Verify public allowances in all blocks
        for bot in ["GPTBot", "PerplexityBot", "ClaudeBot", "Google-Extended"]:
            pattern = rf"User-agent: {bot}\s+(?:Allow: [^\n]+\s+)+Disallow: /api/"
            self.assertTrue(re.search(pattern, body), f"Bot {bot} must allow public and disallow /api/")

    # -------------------------------------------------------------------------
    # 2. XML Schema of /sitemap.xml
    # -------------------------------------------------------------------------

    def test_sitemap_xml_schema_and_catalog_validation(self):
        """Validate XML schema, xmlns namespace, 38 URLs, lastmod, priority, changefreq."""
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/xml")
        self.assertIn("charset=utf-8", resp.content_type.lower())
        self.assertIn("max-age=3600", resp.headers.get("Cache-Control", ""))

        xml_raw = resp.data.decode("utf-8")
        self.assertTrue(xml_raw.startswith('<?xml version="1.0" encoding="UTF-8"?>'))

        root = ET.fromstring(xml_raw)
        # Namespace and root tag
        self.assertEqual(root.tag, "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")

        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        url_nodes = root.findall("sm:url", ns)

        # Count must be exactly 38
        self.assertEqual(len(url_nodes), 38)
        self.assertEqual(len(PUBLIC_SITEMAP_CATALOG), 38)

        today_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        valid_changefreqs = {"always", "hourly", "daily", "weekly", "monthly", "yearly", "never"}

        collected_locs = []
        for url_node in url_nodes:
            loc = url_node.find("sm:loc", ns)
            lastmod = url_node.find("sm:lastmod", ns)
            changefreq = url_node.find("sm:changefreq", ns)
            priority = url_node.find("sm:priority", ns)

            self.assertIsNotNone(loc, "Missing <loc>")
            self.assertIsNotNone(lastmod, "Missing <lastmod>")
            self.assertIsNotNone(changefreq, "Missing <changefreq>")
            self.assertIsNotNone(priority, "Missing <priority>")

            # Tag sequence validation (must be loc, lastmod, changefreq, priority)
            child_tags = [c.tag.split("}")[-1] for c in url_node]
            self.assertEqual(child_tags, ["loc", "lastmod", "changefreq", "priority"])

            # Loc validation
            loc_text = loc.text
            collected_locs.append(loc_text)
            parsed_loc = urllib.parse.urlparse(loc_text)
            self.assertEqual(parsed_loc.scheme, "https")
            self.assertEqual(parsed_loc.netloc, "flama.vn")
            self.assertNotIn("//", parsed_loc.path)

            # Lastmod validation (ISO 8601 date YYYY-MM-DD)
            self.assertEqual(lastmod.text, today_iso)
            self.assertRegex(lastmod.text, r"^\d{4}-\d{2}-\d{2}$")

            # Changefreq validation
            self.assertIn(changefreq.text, valid_changefreqs)

            # Priority validation (between 0.0 and 1.0)
            p_val = float(priority.text)
            self.assertTrue(0.0 <= p_val <= 1.0)
            self.assertRegex(priority.text, r"^(0(\.\d+)?|1(\.0+)?)$")

        # Verify uniqueness (no duplicate URLs)
        self.assertEqual(len(set(collected_locs)), 38, "Duplicate URLs found in sitemap!")

    def test_sitemap_xml_zero_private_route_leaks(self):
        """Validate absence of private, user, auth, or internal API routes in sitemap."""
        resp = self.client.get("/sitemap.xml")
        root = ET.fromstring(resp.data.decode("utf-8"))
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [u.find("sm:loc", ns).text for u in root.findall("sm:url", ns)]

        forbidden_prefixes = (
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
        )

        for loc in locs:
            parsed = urllib.parse.urlparse(loc)
            path = parsed.path
            for forbidden in forbidden_prefixes:
                self.assertFalse(
                    path == forbidden or path.startswith(f"{forbidden}/"),
                    f"Private route leak in sitemap: {loc} matches forbidden prefix {forbidden}",
                )

    def test_sitemap_all_38_urls_return_200_ok_on_client(self):
        """Verify that every single URL in PUBLIC_SITEMAP_CATALOG is reachable."""
        for entry in PUBLIC_SITEMAP_CATALOG:
            path = entry["path"]
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertEqual(
                    resp.status_code,
                    200,
                    f"Catalog URL {path} returned status {resp.status_code}",
                )

    # -------------------------------------------------------------------------
    # 3. /llms.txt Specification Validation
    # -------------------------------------------------------------------------

    def test_llms_txt_llmstxt_org_specification(self):
        """Validate /llms.txt syntax, markdown headers, and link validity."""
        resp = self.client.get("/llms.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/plain")
        self.assertIn("charset=utf-8", resp.content_type.lower())
        self.assertIn("max-age=86400", resp.headers.get("Cache-Control", ""))

        text = resp.data.decode("utf-8")
        lines = text.splitlines()

        # 1. H1 title
        first_line = next(l for l in lines if l.strip())
        self.assertEqual(first_line, "# Flama")

        # 2. Blockquote summary
        bq_lines = [l for l in lines if l.startswith("> ")]
        self.assertGreaterEqual(len(bq_lines), 1)
        self.assertIn("https://flama.vn", bq_lines[0])

        # 3. Expected H2 sections
        required_h2 = [
            "## Core Features & Concepts",
            "## Guides & Documentation",
            "## AI Agent & Model Context Protocol (MCP)",
            "## Legal & Community",
        ]
        for h2 in required_h2:
            self.assertIn(h2, text)

        # 4. Links validation
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
        self.assertGreaterEqual(len(links), 15)

        sitemap_paths = {e["path"] for e in PUBLIC_SITEMAP_CATALOG}
        for link_text, link_url in links:
            with self.subTest(link=link_text):
                parsed = urllib.parse.urlparse(link_url)
                self.assertEqual(parsed.scheme, "https")
                self.assertEqual(parsed.netloc, "flama.vn")
                path = parsed.path
                if path not in ("/api/mcp", "/.well-known/oauth-protected-resource"):
                    self.assertIn(
                        path,
                        sitemap_paths,
                        f"llms.txt link target {path} not cataloged in sitemap",
                    )

    # -------------------------------------------------------------------------
    # 4. Schema.org JSON-LD from frontend/index.html
    # -------------------------------------------------------------------------

    def test_schema_jsonld_extraction_and_entity_validation(self):
        """Extract and validate Schema.org JSON-LD from frontend/index.html."""
        self.assertTrue(self.frontend_index_path.is_file())
        html = self.frontend_index_path.read_text(encoding="utf-8")

        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        self.assertIsNotNone(match, "JSON-LD script tag missing in frontend/index.html")

        # JSON syntax check
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as err:
            self.fail(f"Invalid JSON in JSON-LD script: {err}")

        # @context and @graph
        self.assertEqual(data.get("@context"), "https://schema.org")
        graph = data.get("@graph")
        self.assertIsInstance(graph, list)
        self.assertEqual(len(graph), 5)

        entities = {e.get("@type"): e for e in graph}
        id_map = {e.get("@id"): e for e in graph if e.get("@id")}

        # Check required entity types
        for required_type in ["Organization", "WebSite", "SoftwareApplication", "FAQPage", "Course"]:
            self.assertIn(required_type, entities, f"Missing Schema.org entity: {required_type}")

        # Organization
        org = entities["Organization"]
        self.assertEqual(org.get("@id"), "https://flama.vn/#organization")
        self.assertEqual(org.get("name"), "Flama")
        self.assertEqual(org.get("url"), "https://flama.vn")
        self.assertIn("logo", org)
        self.assertEqual(org["logo"].get("@type"), "ImageObject")
        self.assertEqual(org["logo"].get("url"), "https://flama.vn/logo.png")
        self.assertIn("sameAs", org)
        self.assertIn("contactPoint", org)

        # WebSite
        site = entities["WebSite"]
        self.assertEqual(site.get("@id"), "https://flama.vn/#website")
        self.assertEqual(site.get("url"), "https://flama.vn")
        self.assertEqual(site.get("name"), "Flama")
        self.assertEqual(site.get("publisher", {}).get("@id"), org["@id"])
        self.assertEqual(site.get("inLanguage"), "vi")

        # SoftwareApplication
        app = entities["SoftwareApplication"]
        self.assertEqual(app.get("@id"), "https://flama.vn/#app")
        self.assertEqual(app.get("name"), "Flama")
        self.assertEqual(app.get("applicationCategory"), "EducationalApplication")
        self.assertIn("Web, Windows", app.get("operatingSystem", ""))
        self.assertEqual(app.get("offers", {}).get("price"), "0")
        self.assertEqual(app.get("offers", {}).get("priceCurrency"), "VND")
        self.assertEqual(app.get("publisher", {}).get("@id"), org["@id"])

        # Course
        course = entities["Course"]
        self.assertEqual(course.get("@id"), "https://flama.vn/#course-jlpt")
        self.assertIn("JLPT", course.get("name", ""))
        self.assertTrue(bool(course.get("description")))
        self.assertEqual(course.get("provider", {}).get("@id"), org["@id"])
        self.assertEqual(course.get("inLanguage"), "vi")

        # FAQPage
        faq = entities["FAQPage"]
        self.assertEqual(faq.get("@id"), "https://flama.vn/#faq")
        main_entity = faq.get("mainEntity", [])
        self.assertGreaterEqual(len(main_entity), 3)
        for item in main_entity:
            self.assertEqual(item.get("@type"), "Question")
            self.assertTrue(bool(item.get("name")))
            ans = item.get("acceptedAnswer")
            self.assertEqual(ans.get("@type"), "Answer")
            self.assertTrue(bool(ans.get("text")))

        # Check all cross-reference @ids resolve
        for entity in graph:
            for key, val in entity.items():
                if isinstance(val, dict) and "@id" in val and len(val) == 1:
                    ref_id = val["@id"]
                    self.assertIn(
                        ref_id,
                        id_map,
                        f"Unresolvable @id '{ref_id}' in {entity.get('@type')}.{key}",
                    )


if __name__ == "__main__":
    unittest.main()
