"""Unit test suite for Technical SEO, GEO standards, and machine-readable endpoints.

Verifies:
1. /robots.txt response code, MIME type, Cache-Control, AI bot rules, and sitemap reference.
2. /sitemap.xml XML syntax, 38 cataloged public URLs, priority/changefreq metadata, and lack of private routes.
3. /llms.txt Markdown format, core feature clusters, MCP endpoint link, and llmstxt.org structure.
4. SPA route exemption verification ensuring /robots.txt, /sitemap.xml, and /llms.txt bypass the SPA shell.
5. frontend/index.html SEO tags, canonical URL, OpenGraph, Twitter Cards, and Schema.org JSON-LD graph.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from app import create_app
from app.services.seo_service import (
    DEFAULT_BASE_URL,
    PUBLIC_SITEMAP_CATALOG,
    generate_llms_txt,
    generate_robots_txt,
    generate_sitemap_xml,
)


class SeoRoutesTestCase(unittest.TestCase):
    """Test case for Technical SEO endpoints and SPA bypass behavior."""

    @classmethod
    def setUpClass(cls):
        """Initialize test Flask app."""
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

    def test_robots_txt_served_with_correct_headers_and_ai_bot_rules(self):
        """GET /robots.txt must return text/plain with 86400s cache, AI bot rules, and sitemap pointer."""
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith("text/plain"))
        self.assertIn("charset=utf-8", response.content_type.lower())
        cache_control = response.headers.get("Cache-Control", "")
        self.assertIn("public", cache_control)
        self.assertIn("max-age=86400", cache_control)

        text = response.data.decode("utf-8")

        # Must not be intercepted by SPA shell
        self.assertNotIn("<!doctype html>", text.lower())
        self.assertNotIn('<div id="root">', text)

        # AI Bot Directives
        self.assertIn("User-agent: GPTBot", text)
        self.assertIn("User-agent: ChatGPT-User", text)
        self.assertIn("User-agent: PerplexityBot", text)
        self.assertIn("User-agent: ClaudeBot", text)
        self.assertIn("User-agent: Google-Extended", text)

        # Public allowances
        self.assertIn("Allow: /", text)
        self.assertIn("Allow: /guide", text)
        self.assertIn("Allow: /support", text)
        self.assertIn("Allow: /terms", text)
        self.assertIn("Allow: /privacy", text)
        self.assertIn("Allow: /cookies", text)
        self.assertIn("Allow: /marketplace-guidelines", text)
        self.assertIn("Allow: /community-guidelines", text)
        self.assertIn("Allow: /llms.txt", text)

        # Private disallowances
        self.assertIn("Disallow: /api/", text)
        self.assertIn("Disallow: /dashboard", text)
        self.assertIn("Disallow: /statistics", text)
        self.assertIn("Disallow: /browse", text)
        self.assertIn("Disallow: /study", text)
        self.assertIn("Disallow: /admin/", text)
        self.assertIn("Disallow: /settings/", text)

        # Dynamic sitemap directive
        self.assertIn("Sitemap: https://flama.vn/sitemap.xml", text)

    def test_sitemap_xml_valid_syntax_and_contains_38_public_urls(self):
        """GET /sitemap.xml must return valid XML cataloging exactly 38 public indexable URLs."""
        response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.content_type.startswith("application/xml")
            or response.content_type.startswith("text/xml")
        )
        cache_control = response.headers.get("Cache-Control", "")
        self.assertIn("public", cache_control)
        self.assertIn("max-age=3600", cache_control)

        raw_xml = response.data.decode("utf-8")

        # Must not be intercepted by SPA shell
        self.assertNotIn("<!doctype html>", raw_xml.lower())

        # Parse XML tree
        root = ET.fromstring(raw_xml)
        self.assertTrue(root.tag.endswith("urlset"))

        # Verify XML namespace
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        url_elements = root.findall("sm:url", ns)

        # Exactly 38 public indexable URLs
        self.assertEqual(len(url_elements), 38)
        self.assertEqual(len(PUBLIC_SITEMAP_CATALOG), 38)

        locs = [url.find("sm:loc", ns).text for url in url_elements if url.find("sm:loc", ns) is not None]
        self.assertEqual(len(locs), 38)

        # Required public pages must be present
        self.assertIn("https://flama.vn", locs)
        self.assertIn("https://flama.vn/guide", locs)
        self.assertIn("https://flama.vn/guide/study/spaced-repetition", locs)
        self.assertIn("https://flama.vn/guide/integrations/yomitan", locs)
        self.assertIn("https://flama.vn/guide/integrations/mcp-ai", locs)
        self.assertIn("https://flama.vn/guide/flama-audio", locs)
        self.assertIn("https://flama.vn/support", locs)
        self.assertIn("https://flama.vn/marketplace-guidelines", locs)
        self.assertIn("https://flama.vn/community-guidelines", locs)
        self.assertIn("https://flama.vn/terms", locs)
        self.assertIn("https://flama.vn/privacy", locs)
        self.assertIn("https://flama.vn/cookies", locs)

        # Private / authenticated routes must NEVER be in sitemap
        private_prefixes = (
            "https://flama.vn/dashboard",
            "https://flama.vn/statistics",
            "https://flama.vn/browse",
            "https://flama.vn/study",
            "https://flama.vn/admin",
            "https://flama.vn/api",
            "https://flama.vn/settings",
            "https://flama.vn/wallet",
            "https://flama.vn/orders",
        )
        for loc in locs:
            for pref in private_prefixes:
                self.assertFalse(
                    loc == pref or loc.startswith(f"{pref}/"),
                    f"Private route leaked in sitemap: {loc}",
                )

        # Validate that each entry has changefreq and priority
        for url_elem in url_elements:
            changefreq = url_elem.find("sm:changefreq", ns)
            priority = url_elem.find("sm:priority", ns)
            lastmod = url_elem.find("sm:lastmod", ns)

            self.assertIsNotNone(changefreq, "Missing <changefreq>")
            self.assertIsNotNone(priority, "Missing <priority>")
            self.assertIsNotNone(lastmod, "Missing <lastmod>")
            self.assertIn(changefreq.text, ["always", "hourly", "daily", "weekly", "monthly", "yearly", "never"])
            self.assertTrue(0.0 <= float(priority.text) <= 1.0)

    def test_llms_txt_served_with_markdown_format_and_mcp_links(self):
        """GET /llms.txt must return text/plain adhering to llmstxt.org specification."""
        response = self.client.get("/llms.txt")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith("text/plain"))
        cache_control = response.headers.get("Cache-Control", "")
        self.assertIn("public", cache_control)
        self.assertIn("max-age=86400", cache_control)

        content = response.data.decode("utf-8")

        # Must not be intercepted by SPA shell
        self.assertNotIn("<!doctype html>", content.lower())

        # Specification compliance
        self.assertTrue(content.startswith("# Flama"))
        self.assertIn("> Flama (https://flama.vn)", content)

        # Required Sections
        self.assertIn("## Core Features & Concepts", content)
        self.assertIn("## Guides & Documentation", content)
        self.assertIn("## AI Agent & Model Context Protocol (MCP)", content)
        self.assertIn("## Legal & Community", content)

        # Core concepts covered
        self.assertIn("Spaced Repetition", content)
        self.assertIn("Yomitan", content)
        self.assertIn("VoiceVox & Kokoro", content)
        self.assertIn("Marketplace", content)
        self.assertIn("Clone Overlay", content)

        # MCP AI Search integration pointer
        self.assertIn("https://flama.vn/api/mcp", content)
        self.assertIn("/.well-known/oauth-protected-resource", content)

    def test_spa_navigation_routes_preserved(self):
        """SPA delivery must not be broken for standard frontend routes."""
        # Non-SEO routes should either return SPA or proceed to their handler
        response = self.client.get("/support")
        self.assertIn(response.status_code, (200, 404))

        response = self.client.get("/dashboard")
        self.assertIn(response.status_code, (200, 404))

    def test_seo_service_generator_custom_base_url(self):
        """Generator functions must properly support custom base URLs."""
        custom_base = "https://custom.flama.local"

        robots = generate_robots_txt(base_url=custom_base)
        self.assertIn(f"Sitemap: {custom_base}/sitemap.xml", robots)

        sitemap = generate_sitemap_xml(base_url=custom_base)
        self.assertIn(f"<loc>{custom_base}/guide</loc>", sitemap)

        llms = generate_llms_txt(base_url=custom_base)
        self.assertIn(f"> Flama ({custom_base})", llms)
        self.assertIn(f"{custom_base}/api/mcp", llms)

    def test_frontend_index_html_has_complete_seo_tags_and_schema_jsonld(self):
        """Validate frontend/index.html head tags and Schema.org JSON-LD graph."""
        index_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
        self.assertTrue(index_path.is_file(), f"index.html not found at {index_path}")

        html_content = index_path.read_text(encoding="utf-8")

        # Favicon and touch icon
        self.assertIn('<link rel="icon" type="image/svg+xml" href="/favicon.svg" />', html_content)
        self.assertIn('<link rel="apple-touch-icon" href="/logo.png" />', html_content)

        # Canonical tag
        self.assertIn('<link rel="canonical" href="https://flama.vn" />', html_content)

        # OpenGraph tags
        self.assertIn('<meta property="og:type" content="website" />', html_content)
        self.assertIn('<meta property="og:url" content="https://flama.vn" />', html_content)
        self.assertIn('<meta property="og:site_name" content="Flama" />', html_content)
        self.assertTrue(re.search(r'property="og:title"', html_content))
        self.assertTrue(re.search(r'property="og:description"', html_content))
        self.assertIn('<meta property="og:image" content="https://flama.vn/logo.png" />', html_content)

        # Twitter Card tags
        self.assertIn('<meta name="twitter:card" content="summary_large_image" />', html_content)
        self.assertIn('<meta name="twitter:url" content="https://flama.vn" />', html_content)
        self.assertTrue(re.search(r'name="twitter:title"', html_content))
        self.assertTrue(re.search(r'name="twitter:description"', html_content))
        self.assertIn('<meta name="twitter:image" content="https://flama.vn/logo.png" />', html_content)

        # Schema.org JSON-LD Graph parsing
        json_ld_match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            html_content,
            re.DOTALL,
        )
        self.assertIsNotNone(json_ld_match, "Schema.org JSON-LD script tag missing")

        data = json.loads(json_ld_match.group(1))
        self.assertEqual(data.get("@context"), "https://schema.org")
        self.assertIn("@graph", data)

        entities = data["@graph"]
        type_to_entity = {entity.get("@type"): entity for entity in entities}

        # Validate Organization
        self.assertIn("Organization", type_to_entity)
        org = type_to_entity["Organization"]
        self.assertEqual(org.get("name"), "Flama")
        self.assertEqual(org.get("url"), "https://flama.vn")
        self.assertIn("logo", org)

        # Validate WebSite
        self.assertIn("WebSite", type_to_entity)
        website = type_to_entity["WebSite"]
        self.assertEqual(website.get("name"), "Flama")
        self.assertEqual(website.get("inLanguage"), "vi")

        # Validate SoftwareApplication / EducationalApplication
        self.assertIn("SoftwareApplication", type_to_entity)
        app = type_to_entity["SoftwareApplication"]
        self.assertEqual(app.get("name"), "Flama")
        self.assertEqual(app.get("applicationCategory"), "EducationalApplication")
        self.assertIn("Web, Windows", app.get("operatingSystem", ""))

        # Validate FAQPage
        self.assertIn("FAQPage", type_to_entity)
        faq = type_to_entity["FAQPage"]
        self.assertTrue(len(faq.get("mainEntity", [])) >= 3)

        # Validate Course
        self.assertIn("Course", type_to_entity)
        course = type_to_entity["Course"]
        self.assertIn("JLPT", course.get("name", ""))

    def test_root_static_assets_served_correctly(self):
        """Root static files like favicon.svg, favicon.ico, and logo.png must be served with proper MIME types."""
        # Favicon SVG
        res_svg = self.client.get("/favicon.svg")
        self.assertEqual(res_svg.status_code, 200)
        self.assertTrue("image/svg+xml" in res_svg.content_type)
        svg_body = res_svg.data.decode("utf-8")
        self.assertIn("url(#flame)", svg_body, "Favicon must contain Flama flame mark")
        self.assertNotIn("#863bff", svg_body, "Favicon must not contain default Vite colors")

        # Favicon ICO
        res_ico = self.client.get("/favicon.ico")
        self.assertEqual(res_ico.status_code, 200)
        self.assertTrue(any(mime in res_ico.content_type for mime in ("image/x-icon", "image/vnd.microsoft.icon")))

        # Logo PNG
        res_logo = self.client.get("/logo.png")
        self.assertEqual(res_logo.status_code, 200)
        self.assertTrue("image/png" in res_logo.content_type)


if __name__ == "__main__":
    unittest.main()
