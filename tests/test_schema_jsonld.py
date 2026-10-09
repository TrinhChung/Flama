"""Automated validator for frontend Schema.org JSON-LD syntax and entities.

Validates:
1. Successful extraction of <script type="application/ld+json"> from frontend/index.html.
2. Valid JSON-LD syntax without errors.
3. @context is https://schema.org and @graph contains required entities.
4. Entity structure and property contracts for:
   - Organization (Brand identity, logo, sameAs, contactPoint)
   - WebSite (Publisher link, inLanguage)
   - SoftwareApplication (EducationalApplication, pricing offer, operatingSystem)
   - Course (JLPT curriculum, provider link)
   - FAQPage (Questions and accepted answers)
5. Graph reference integrity (@id references between entities).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


class SchemaJsonLdTestCase(unittest.TestCase):
    """Test suite validating Schema.org JSON-LD structured data."""

    @classmethod
    def setUpClass(cls):
        """Locate frontend/index.html and extract JSON-LD."""
        cls.index_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
        if not cls.index_path.is_file():
            raise FileNotFoundError(f"frontend/index.html not found at {cls.index_path}")

        html_content = cls.index_path.read_text(encoding="utf-8")
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
        if not match:
            raise ValueError("No <script type=\"application/ld+json\"> tag found in frontend/index.html")

        cls.raw_json = match.group(1).strip()
        cls.data = json.loads(cls.raw_json)
        cls.graph = cls.data.get("@graph", [])
        cls.entities_by_type = {e.get("@type"): e for e in cls.graph}
        cls.entities_by_id = {e.get("@id"): e for e in cls.graph if e.get("@id")}

    def test_context_and_graph_root(self):
        """Validate top-level @context and @graph structure."""
        self.assertEqual(self.data.get("@context"), "https://schema.org")
        self.assertIsInstance(self.graph, list)
        self.assertGreaterEqual(len(self.graph), 5)

    def test_organization_entity(self):
        """Validate Organization entity for Flama brand authority."""
        self.assertIn("Organization", self.entities_by_type)
        org = self.entities_by_type["Organization"]

        self.assertEqual(org.get("@id"), "https://flama.vn/#organization")
        self.assertEqual(org.get("name"), "Flama")
        self.assertEqual(org.get("legalName"), "Flama Vietnam")
        self.assertEqual(org.get("url"), "https://flama.vn")

        # Logo ImageObject
        logo = org.get("logo")
        self.assertIsInstance(logo, dict)
        self.assertEqual(logo.get("@type"), "ImageObject")
        self.assertEqual(logo.get("url"), "https://flama.vn/logo.png")

        # Social linking
        same_as = org.get("sameAs")
        self.assertIsInstance(same_as, list)
        self.assertIn("https://github.com/TrinhChung/Flama", same_as)

        # Contact point
        cp = org.get("contactPoint")
        self.assertIsInstance(cp, dict)
        self.assertEqual(cp.get("@type"), "ContactPoint")
        self.assertEqual(cp.get("contactType"), "customer support")
        self.assertEqual(cp.get("url"), "https://flama.vn/support")

    def test_website_entity(self):
        """Validate WebSite entity."""
        self.assertIn("WebSite", self.entities_by_type)
        site = self.entities_by_type["WebSite"]

        self.assertEqual(site.get("@id"), "https://flama.vn/#website")
        self.assertEqual(site.get("name"), "Flama")
        self.assertEqual(site.get("url"), "https://flama.vn")
        self.assertEqual(site.get("inLanguage"), "vi")
        self.assertEqual(site.get("publisher", {}).get("@id"), "https://flama.vn/#organization")

    def test_software_application_entity(self):
        """Validate SoftwareApplication / EducationalApplication entity."""
        self.assertIn("SoftwareApplication", self.entities_by_type)
        app = self.entities_by_type["SoftwareApplication"]

        self.assertEqual(app.get("@id"), "https://flama.vn/#app")
        self.assertEqual(app.get("name"), "Flama")
        self.assertEqual(app.get("applicationCategory"), "EducationalApplication")
        self.assertIn("Web, Windows", app.get("operatingSystem", ""))

        # Free tier offer
        offers = app.get("offers")
        self.assertIsInstance(offers, dict)
        self.assertEqual(offers.get("@type"), "Offer")
        self.assertEqual(offers.get("price"), "0")
        self.assertEqual(offers.get("priceCurrency"), "VND")

        self.assertEqual(app.get("publisher", {}).get("@id"), "https://flama.vn/#organization")

    def test_course_entity(self):
        """Validate Course entity for JLPT curriculum."""
        self.assertIn("Course", self.entities_by_type)
        course = self.entities_by_type["Course"]

        self.assertEqual(course.get("@id"), "https://flama.vn/#course-jlpt")
        self.assertIn("JLPT", course.get("name", ""))
        self.assertEqual(course.get("provider", {}).get("@id"), "https://flama.vn/#organization")
        self.assertEqual(course.get("inLanguage"), "vi")

    def test_faq_page_entity(self):
        """Validate FAQPage entity with questions and answers."""
        self.assertIn("FAQPage", self.entities_by_type)
        faq = self.entities_by_type["FAQPage"]

        self.assertEqual(faq.get("@id"), "https://flama.vn/#faq")
        main_entities = faq.get("mainEntity")
        self.assertIsInstance(main_entities, list)
        self.assertGreaterEqual(len(main_entities), 3)

        for q in main_entities:
            self.assertEqual(q.get("@type"), "Question")
            self.assertTrue(bool(q.get("name")))
            ans = q.get("acceptedAnswer")
            self.assertIsInstance(ans, dict)
            self.assertEqual(ans.get("@type"), "Answer")
            self.assertTrue(bool(ans.get("text")))

    def test_graph_reference_integrity(self):
        """Verify that all publisher/provider references resolve to defined @id entities in the graph."""
        for entity in self.graph:
            for prop_name, prop_val in entity.items():
                if isinstance(prop_val, dict) and "@id" in prop_val and len(prop_val) == 1:
                    ref_id = prop_val["@id"]
                    self.assertIn(
                        ref_id,
                        self.entities_by_id,
                        f"Dangling @id reference '{ref_id}' in entity {entity.get('@type')}.{prop_name}",
                    )


if __name__ == "__main__":
    unittest.main()
