"""Integration tests for DB-managed Marketplace Taxonomy."""

import unittest

from app import create_app
from app.repositories import marketplace_taxonomy_repository
from app.services import marketplace_taxonomy_service
from models import db
from models.user import User


class MarketplaceTaxonomyDbTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": True,
                "STARTUP_RUN_DEFAULT_TAXONOMY_SEED": True,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            admin = User(
                username="admin_tax",
                email="admin_tax@example.com",
                is_admin=True,
                is_disabled=False,
            )
            admin.set_password("password")
            db.session.add(admin)
            db.session.commit()
            self.admin_id = admin.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login_admin(self):
        return self.client.post(
            "/login",
            data={"email": "admin_tax@example.com", "password": "password"},
            follow_redirects=True,
        )

    def test_taxonomy_data_is_seeded_on_startup(self):
        with self.app.app_context():
            domains = marketplace_taxonomy_repository.list_domains()
            self.assertGreaterEqual(len(domains), 5)
            domain_ids = {d.id for d in domains}
            self.assertIn("language_learning", domain_ids)
            self.assertIn("certification", domain_ids)
            self.assertIn("academic", domain_ids)

            subjects = marketplace_taxonomy_repository.list_subjects()
            self.assertGreaterEqual(len(subjects), 10)
            subject_ids = {s.id for s in subjects}
            self.assertIn("japanese", subject_ids)
            self.assertIn("english", subject_ids)

    def test_public_taxonomy_schema_api(self):
        response = self.client.get("/api/marketplace/taxonomy/schema?content_type=deck_marketplace_item")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["content_type"], "deck_marketplace_item")
        self.assertGreaterEqual(len(data["domains"]), 5)
        self.assertGreaterEqual(len(data["subjects"]), 10)
        self.assertIn("subject_packs", data)
        self.assertIn("japanese", data["subject_packs"])

    def test_admin_can_create_domain_subject_option(self):
        self._login_admin()

        # 1. Create new domain: astronomy
        resp = self.client.post(
            "/api/admin/taxonomy/domains",
            json={"id": "astronomy", "label": "Thiên văn học", "sort_order": 99},
        )
        self.assertEqual(resp.status_code, 201)

        # 2. Create new subject: space
        resp_sub = self.client.post(
            "/api/admin/taxonomy/subjects",
            json={"id": "space", "domain_id": "astronomy", "label": "Vũ trụ học", "sort_order": 1},
        )
        self.assertEqual(resp_sub.status_code, 201)

        # 3. Create option: astrophysics
        resp_opt = self.client.post(
            "/api/admin/taxonomy/options",
            json={"id": "astrophysics", "option_type": "primary_topic", "label": "Vật lý thiên văn"},
        )
        self.assertEqual(resp_opt.status_code, 201)

        # 4. Map option to subject
        resp_map = self.client.post(
            "/api/admin/taxonomy/subject-mappings",
            json={"subject_id": "space", "option_type": "primary_topic", "option_ids": ["astrophysics"]},
        )
        self.assertEqual(resp_map.status_code, 200)

        # 5. Check public schema reflects new domain and subject
        response = self.client.get("/api/marketplace/taxonomy/schema")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        domain_ids = [d["id"] for d in data["domains"]]
        self.assertIn("astronomy", domain_ids)

        subject_ids = [s["id"] for s in data["subjects"]]
        self.assertIn("space", subject_ids)

    def test_admin_framework_and_level_crud(self):
        self._login_admin()

        # 1. Create Framework
        resp_fw = self.client.post(
            "/api/admin/taxonomy/frameworks",
            json={"id": "space_cert", "subject_id": "japanese", "label": "Space Certification", "sort_order": 5},
        )
        self.assertEqual(resp_fw.status_code, 201)

        # 2. Update Framework
        resp_fw_up = self.client.put(
            "/api/admin/taxonomy/frameworks/space_cert",
            json={"label": "Space Certification Pro", "sort_order": 10},
        )
        self.assertEqual(resp_fw_up.status_code, 200)
        self.assertEqual(resp_fw_up.get_json()["framework"]["label"], "Space Certification Pro")

        # 3. Create Framework Level
        resp_lvl = self.client.post(
            "/api/admin/taxonomy/framework-levels",
            json={
                "id": "space_level_1",
                "framework_id": "space_cert",
                "subject_id": "japanese",
                "label": "Space Cadet Level 1",
                "difficulty_band": "beginner",
                "sort_order": 1,
            },
        )
        self.assertEqual(resp_lvl.status_code, 201)

        # 4. Update Framework Level
        resp_lvl_up = self.client.put(
            "/api/admin/taxonomy/framework-levels/space_level_1",
            json={"label": "Space Cadet Level 1 (Advanced)", "difficulty_band": "intermediate"},
        )
        self.assertEqual(resp_lvl_up.status_code, 200)
        self.assertEqual(resp_lvl_up.get_json()["level"]["difficulty_band"], "intermediate")

        # 5. Delete Framework Level
        resp_lvl_del = self.client.delete("/api/admin/taxonomy/framework-levels/space_level_1")
        self.assertEqual(resp_lvl_del.status_code, 200)

        # 6. Delete Framework
        resp_fw_del = self.client.delete("/api/admin/taxonomy/frameworks/space_cert")
        self.assertEqual(resp_fw_del.status_code, 200)

    def test_admin_option_crud_and_mappings(self):
        self._login_admin()

        # 1. Create Option
        resp_opt = self.client.post(
            "/api/admin/taxonomy/options",
            json={
                "id": "orbital_mechanics",
                "option_type": "primary_topic",
                "label": "Cơ học quỹ đạo",
                "sub_label": "Học lực hút",
            },
        )
        self.assertEqual(resp_opt.status_code, 201)

        # 2. Update Option
        resp_opt_up = self.client.put(
            "/api/admin/taxonomy/options/orbital_mechanics",
            json={"option_type": "primary_topic", "label": "Cơ học quỹ đạo nâng cao"},
        )
        self.assertEqual(resp_opt_up.status_code, 200)
        self.assertEqual(resp_opt_up.get_json()["option"]["label"], "Cơ học quỹ đạo nâng cao")

        # 3. Set Subject Mapping
        resp_map = self.client.post(
            "/api/admin/taxonomy/subject-mappings",
            json={"subject_id": "japanese", "option_type": "primary_topic", "option_ids": ["orbital_mechanics"]},
        )
        self.assertEqual(resp_map.status_code, 200)

        # 4. Get Subject Mappings
        resp_get_maps = self.client.get("/api/admin/taxonomy/subject-mappings?subject_id=japanese&option_type=primary_topic")
        self.assertEqual(resp_get_maps.status_code, 200)
        maps = resp_get_maps.get_json()["mappings"]
        self.assertEqual(len(maps), 1)
        self.assertEqual(maps[0]["option_id"], "orbital_mechanics")

        # 5. Delete Option
        resp_opt_del = self.client.delete("/api/admin/taxonomy/options/orbital_mechanics?option_type=primary_topic")
        self.assertEqual(resp_opt_del.status_code, 200)


if __name__ == "__main__":
    unittest.main()

