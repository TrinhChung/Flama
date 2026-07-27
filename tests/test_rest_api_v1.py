"""Integration coverage for the REST API used by the SPA migration."""

import unittest

from app import create_app
from app.services import login_rate_limit_service
from models import db
from models.deck import Deck
from models.user import User


class RestApiV1Tests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            admin = User(
                username="admin",
                email="admin@example.com",
                is_admin=True,
            )
            admin.set_password("password")
            db.session.add(admin)
            db.session.flush()
            self.admin_id = admin.id

            root = Deck(name="Root deck", owner_user_id=admin.id, position=0)
            db.session.add(root)
            db.session.flush()
            child = Deck(
                name="Child deck",
                owner_user_id=admin.id,
                parent_id=root.id,
                position=0,
            )
            db.session.add(child)
            db.session.commit()
            self.root_deck_id = root.id
            self.child_deck_id = child.id

        login_rate_limit_service.reset_state()

    def tearDown(self):
        login_rate_limit_service.reset_state()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login_admin(self):
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "password"},
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_session_bootstrap_and_api_auth_failure_are_json(self):
        session_response = self.client.get("/api/v1/session")
        self.assertEqual(session_response.status_code, 200)
        session_payload = session_response.get_json()
        self.assertFalse(session_payload["authenticated"])
        self.assertIsNone(session_payload["user"])
        self.assertIn("csrf_token", session_payload)

        api_response = self.client.get("/api/v1/dashboard")
        self.assertEqual(api_response.status_code, 401)
        self.assertEqual(
            api_response.get_json()["error"],
            "AUTHENTICATION_REQUIRED",
        )

        page_response = self.client.get("/dashboard")
        self.assertEqual(page_response.status_code, 302)
        self.assertIn("/login", page_response.headers["Location"])

    def test_register_login_and_logout_flow(self):
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "learner@example.com",
                "username": "learner",
                "password": "secret-password",
                "confirm_password": "secret-password",
            },
        )
        self.assertEqual(register_response.status_code, 201)
        self.assertTrue(register_response.get_json()["created"])

        duplicate_response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "learner@example.com",
                "username": "learner-2",
                "password": "secret-password",
                "confirm_password": "secret-password",
            },
        )
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertEqual(duplicate_response.get_json()["error"], "CONFLICT")

        login_response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "learner@example.com",
                "password": "secret-password",
                "next": "/statistics",
            },
        )
        self.assertEqual(login_response.status_code, 200)
        login_payload = login_response.get_json()
        self.assertTrue(login_payload["authenticated"])
        self.assertEqual(login_payload["user"]["username"], "learner")
        self.assertEqual(login_payload["next_url"], "/statistics")

        logout_response = self.client.delete("/api/v1/session")
        self.assertEqual(logout_response.status_code, 200)
        self.assertFalse(logout_response.get_json()["authenticated"])

    def test_dashboard_and_statistics_read_models(self):
        self._login_admin()

        dashboard_response = self.client.get("/api/v1/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        dashboard_payload = dashboard_response.get_json()
        self.assertTrue(dashboard_payload["admin_mode"])
        self.assertEqual(dashboard_payload["summary"]["total_due"], 0)
        self.assertEqual(len(dashboard_payload["items"]), 1)
        self.assertEqual(
            dashboard_payload["items"][0]["deck_id"],
            self.root_deck_id,
        )
        self.assertEqual(
            dashboard_payload["items"][0]["children"][0]["deck_id"],
            self.child_deck_id,
        )

        statistics_response = self.client.get(
            f"/api/v1/statistics?deck_id={self.child_deck_id}"
        )
        self.assertEqual(statistics_response.status_code, 200)
        statistics_payload = statistics_response.get_json()
        self.assertEqual(
            statistics_payload["selected_deck_id"],
            self.child_deck_id,
        )
        self.assertEqual(len(statistics_payload["decks"]), 2)

        invalid_year_response = self.client.get(
            "/api/v1/statistics/overview?year=2200"
        )
        self.assertEqual(invalid_year_response.status_code, 400)
        self.assertEqual(
            invalid_year_response.get_json()["field"],
            "year",
        )

    def test_deck_resource_create_update_reset_and_delete(self):
        self._login_admin()

        create_response = self.client.post(
            "/api/v1/decks",
            json={"path": "API parent::API child"},
        )
        self.assertEqual(create_response.status_code, 201)
        create_payload = create_response.get_json()
        self.assertEqual(create_payload["created_count"], 2)
        created_deck_id = create_payload["item"]["id"]

        rename_response = self.client.patch(
            f"/api/v1/decks/{created_deck_id}",
            json={"name": "Renamed API child"},
        )
        self.assertEqual(rename_response.status_code, 200)
        self.assertTrue(rename_response.get_json()["changed"])
        self.assertEqual(
            rename_response.get_json()["item"]["name"],
            "Renamed API child",
        )

        reset_response = self.client.post(
            f"/api/v1/decks/{created_deck_id}/progress-reset",
            json={},
        )
        self.assertEqual(reset_response.status_code, 200)
        self.assertEqual(
            reset_response.get_json()["deleted_progress_count"],
            0,
        )

        delete_response = self.client.delete(
            f"/api/v1/decks/{created_deck_id}"
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.get_json()["mode"], "deleted")

        missing_response = self.client.get("/api/v1/not-a-resource")
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(missing_response.get_json()["error"], "NOT_FOUND")

        method_response = self.client.put("/api/v1/dashboard", json={})
        self.assertEqual(method_response.status_code, 405)
        self.assertEqual(
            method_response.get_json()["error"],
            "METHOD_NOT_ALLOWED",
        )

    def test_support_donation_and_empty_order_resources(self):
        support_response = self.client.get("/api/v1/support-donation")
        self.assertEqual(support_response.status_code, 200)
        support_payload = support_response.get_json()
        self.assertFalse(support_payload["configured"])
        self.assertGreater(len(support_payload["limits"]["suggested_amounts"]), 0)

        self._login_admin()
        orders_response = self.client.get("/api/v1/orders")
        self.assertEqual(orders_response.status_code, 200)
        self.assertEqual(orders_response.get_json()["items"], [])

        installed_response = self.client.get(
            "/api/v1/marketplace/installed-decks"
        )
        self.assertEqual(installed_response.status_code, 200)
        self.assertIsInstance(installed_response.get_json(), dict)

        missing_order_response = self.client.get("/api/v1/orders/missing")
        self.assertEqual(missing_order_response.status_code, 404)
        self.assertEqual(missing_order_response.get_json()["error"], "NOT_FOUND")

    def test_admin_payment_resources_and_mcp_token_lifecycle(self):
        self._login_admin()

        payment_dashboard_response = self.client.get("/api/v1/admin/payments")
        self.assertEqual(payment_dashboard_response.status_code, 200)
        self.assertEqual(
            payment_dashboard_response.get_json()["filters"]["period"],
            "30d",
        )

        admin_orders_response = self.client.get(
            "/api/v1/admin/payments/orders?per_page=5"
        )
        self.assertEqual(admin_orders_response.status_code, 200)
        self.assertEqual(admin_orders_response.get_json()["per_page"], 5)

        transactions_response = self.client.get(
            "/api/v1/admin/payments/transactions"
        )
        self.assertEqual(transactions_response.status_code, 200)
        self.assertEqual(transactions_response.get_json()["items"], [])

        create_token_response = self.client.post("/api/v1/mcp-tokens", json={})
        self.assertEqual(create_token_response.status_code, 201)
        issued = create_token_response.get_json()["item"]
        self.assertTrue(issued["token"].startswith("flama_mcp_"))

        list_token_response = self.client.get("/api/v1/mcp-tokens")
        self.assertEqual(list_token_response.status_code, 200)
        token_rows = list_token_response.get_json()["items"]
        self.assertEqual(len(token_rows), 1)
        self.assertEqual(token_rows[0]["status"], "active")

        revoke_response = self.client.delete(
            f"/api/v1/mcp-tokens/{token_rows[0]['id']}"
        )
        self.assertEqual(revoke_response.status_code, 204)

        revoked_list_response = self.client.get("/api/v1/mcp-tokens")
        self.assertEqual(
            revoked_list_response.get_json()["items"][0]["status"],
            "revoked",
        )

    def test_non_admin_cannot_access_admin_rest_resources(self):
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "regular@example.com",
                "username": "regular",
                "password": "secret-password",
                "confirm_password": "secret-password",
            },
        )
        self.assertEqual(register_response.status_code, 201)
        self.client.post(
            "/api/v1/auth/login",
            json={"email": "regular@example.com", "password": "secret-password"},
        )

        response = self.client.get("/api/v1/admin/payments")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "FORBIDDEN")

        create_deck_response = self.client.post(
            "/api/v1/decks",
            json={"name": "Regular owned deck"},
        )
        self.assertEqual(create_deck_response.status_code, 201)
        regular_deck_id = create_deck_response.get_json()["item"]["id"]

        rename_response = self.client.patch(
            f"/api/v1/decks/{regular_deck_id}",
            json={"name": "Not allowed through current admin-only flow"},
        )
        self.assertEqual(rename_response.status_code, 403)

    def test_admin_user_resource_lists_roles_and_updates_status(self):
        self._login_admin()
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "managed@example.com",
                "username": "managed",
                "password": "secret-password",
                "confirm_password": "secret-password",
            },
        )
        # An authenticated admin cannot register through the public endpoint.
        self.assertEqual(register_response.status_code, 409)

        with self.app.app_context():
            managed = User(
                email="managed@example.com",
                username="managed",
                is_admin=False,
            )
            managed.set_password("secret-password")
            db.session.add(managed)
            db.session.commit()
            managed_id = managed.id

        list_response = self.client.get("/api/v1/admin/users?q=managed")
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.get_json()
        self.assertEqual(len(list_payload["items"]), 1)
        self.assertGreaterEqual(len(list_payload["roles"]), 2)

        update_response = self.client.patch(
            f"/api/v1/admin/users/{managed_id}",
            json={"is_disabled": True},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertTrue(update_response.get_json()["item"]["is_disabled"])

    def test_browse_rest_api_v1_endpoints(self):
        self._login_admin()

        decks_response = self.client.get("/api/v1/browse/decks")
        self.assertEqual(decks_response.status_code, 200)
        decks_data = decks_response.get_json()
        self.assertIn("decks", decks_data)
        self.assertIn("tree", decks_data)

        tree_response = self.client.get("/api/v1/browse/decks/tree")
        self.assertEqual(tree_response.status_code, 200)
        self.assertIn("tree", tree_response.get_json())

        cards_response = self.client.get("/api/v1/browse/cards?status=all&sort_by=due&sort_dir=asc&page=1&per_page=50")
        self.assertEqual(cards_response.status_code, 200)
        cards_data = cards_response.get_json()
        self.assertIn("items", cards_data)
        self.assertIn("total", cards_data)


if __name__ == "__main__":
    unittest.main()

