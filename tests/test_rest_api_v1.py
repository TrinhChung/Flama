"""Integration coverage for the REST API used by the SPA migration."""

import unittest
from unittest.mock import patch
from datetime import datetime

from sqlalchemy import event

from app import create_app
from app.services import login_rate_limit_service
from models import db
from models.deck import Deck
from models.flashcard import Card, Note, NoteType, Template
from models.user import User
from app.utils.deck_move_token import parse_deck_move_token
from app.repositories.deck_tree_query import collect_accessible_decks


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
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "password"},
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_health_reports_application_and_database_readiness(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_health_fails_when_authoritative_redis_is_unavailable(self):
        self.app.config["RATE_LIMIT_BACKEND"] = "redis"
        with patch(
            "app.api.v1.health.redis_state_service.redis_client",
            side_effect=RuntimeError("redis offline"),
        ):
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {"status": "unavailable", "dependency": "redis"},
        )

    def test_session_bootstrap_and_api_auth_failure_are_json(self):
        session_response = self.client.get("/api/session")
        self.assertEqual(session_response.status_code, 200)
        session_payload = session_response.get_json()
        self.assertFalse(session_payload["authenticated"])
        self.assertIsNone(session_payload["user"])
        self.assertIn("csrf_token", session_payload)

        api_response = self.client.get("/api/dashboard")
        self.assertEqual(api_response.status_code, 401)
        self.assertEqual(
            api_response.get_json()["error"],
            "AUTHENTICATION_REQUIRED",
        )

        page_response = self.client.get("/dashboard")
        self.assertEqual(page_response.status_code, 200)
        self.assertIn("text/html", page_response.content_type)

    def test_register_login_and_logout_flow(self):
        register_response = self.client.post(
            "/api/auth/register",
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
            "/api/auth/register",
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
            "/api/auth/login",
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

        logout_response = self.client.delete("/api/session")
        self.assertEqual(logout_response.status_code, 200)
        self.assertFalse(logout_response.get_json()["authenticated"])

    def test_register_password_policy_bounds(self):
        short_response = self.client.post(
            "/api/auth/register",
            json={
                "email": "short@example.com",
                "username": "shortpass",
                "password": "short",
                "confirm_password": "short",
            },
        )
        self.assertEqual(short_response.status_code, 400)
        self.assertEqual(short_response.get_json()["error"], "VALIDATION_ERROR")
        self.assertEqual(short_response.get_json()["field"], "password")

        long_response = self.client.post(
            "/api/auth/register",
            json={
                "email": "long@example.com",
                "username": "longpass",
                "password": "a" * 256,
                "confirm_password": "a" * 256,
            },
        )
        self.assertEqual(long_response.status_code, 400)
        self.assertEqual(long_response.get_json()["error"], "VALIDATION_ERROR")
        self.assertEqual(long_response.get_json()["field"], "password")

    def test_dashboard_and_statistics_read_models(self):
        self._login_admin()

        dashboard_response = self.client.get("/api/dashboard")
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

        with self.app.app_context():
            root = dashboard_payload["items"][0]
            child = root["children"][0]
            self.assertEqual(parse_deck_move_token(root["move_token"], user_id=self.admin_id), self.root_deck_id)
            self.assertEqual(parse_deck_move_token(child["parent_move_token"], user_id=self.admin_id), self.root_deck_id)
            self.assertEqual(root["href"], f"/vocabulary/study/deck/{self.root_deck_id}")

        statistics_response = self.client.get(
            f"/api/statistics?deck_id={self.child_deck_id}"
        )
        self.assertEqual(statistics_response.status_code, 200)
        statistics_payload = statistics_response.get_json()
        self.assertEqual(
            statistics_payload["selected_deck_id"],
            self.child_deck_id,
        )
        self.assertEqual(len(statistics_payload["decks"]), 2)

        invalid_year_response = self.client.get(
            "/api/statistics/overview?year=2200"
        )
        self.assertEqual(invalid_year_response.status_code, 400)
        self.assertEqual(
            invalid_year_response.get_json()["field"],
            "year",
        )

    def test_compact_dashboard_preserves_tree_counts_and_note_types_without_tokens(self):
        with self.app.app_context():
            note_type = NoteType(user_id=self.admin_id, name="Dashboard type")
            db.session.add(note_type)
            db.session.flush()
            templates = [Template(note_type_id=note_type.id, name=name) for name in ("Front", "Reverse")]
            db.session.add_all(templates)
            note = Note(user_id=self.admin_id, note_type_id=note_type.id, deck_id=self.child_deck_id)
            db.session.add(note)
            db.session.flush()
            db.session.add_all([Card(note_id=note.id, template_id=template.id) for template in templates])
            db.session.commit()
            note_type_id = note_type.id

        self._login_admin()
        legacy = self.client.get("/api/dashboard").get_json()
        # Compact reads must not sign tokens that the numeric deck REST API never uses.
        with patch("app.services.dashboard_service.create_deck_move_token", side_effect=AssertionError("unexpected signing")):
            response = self.client.get("/api/dashboard?compact=1")
            repeated = self.client.get("/api/dashboard?compact=true")
        self.assertEqual(response.status_code, 200)
        compact = response.get_json()
        self.assertEqual(compact, repeated.get_json())
        self.assertEqual(compact["summary"], legacy["summary"])
        self.assertEqual(compact["summary"]["new"], 2)
        self.assertEqual(compact["items"][0]["children"][0]["note_type_id"], note_type_id)

        omitted = {"move_token", "parent_move_token", "parent_move_alias", "href"}
        aliases = []

        def compare_rows(old_rows, new_rows):
            self.assertEqual(len(old_rows), len(new_rows))
            for old, new in zip(old_rows, new_rows):
                self.assertTrue(omitted.isdisjoint(new))
                for key in ("deck_id", "parent_id", "label", "depth", "new_count", "learn_count", "due_count", "note_type_id"):
                    self.assertEqual(new[key], old[key], key)
                self.assertRegex(new["move_alias"], r"^MID-[A-F0-9]{10,64}$")
                aliases.append(new["move_alias"])
                compare_rows(old["children"], new["children"])

        compare_rows(legacy["items"], compact["items"])
        self.assertEqual(len(aliases), len(set(aliases)))
        self.assertLess(len(response.data), len(self.client.get("/api/dashboard").data))
        moved = self.client.patch(
            f"/api/decks/{self.child_deck_id}", json={"parent_id": None}
        )
        self.assertEqual(moved.status_code, 200)
        self.assertIsNone(moved.get_json()["item"]["parent_id"])

    def test_dashboard_rejects_invalid_compact_parameter(self):
        self._login_admin()
        response = self.client.get("/api/dashboard?compact=maybe")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["field"], "compact")
        self.assertEqual(response.get_json()["error"], "VALIDATION_ERROR")

    def test_admin_deck_collection_reads_once_when_all_ancestors_are_owned(self):
        with self.app.app_context():
            deck_queries = []
            engine = db.engine

            def capture(conn, cursor, statement, parameters, context, executemany):
                if "from decks" in statement.lower():
                    deck_queries.append(statement)

            event.listen(engine, "before_cursor_execute", capture)
            try:
                rows = collect_accessible_decks(user_id=self.admin_id, admin_mode=True)
            finally:
                event.remove(engine, "before_cursor_execute", capture)
            self.assertEqual([row.id for row in rows], [self.root_deck_id, self.child_deck_id])
            self.assertEqual(len(deck_queries), 1, deck_queries)

    def test_admin_deck_collection_keeps_foreign_ancestors_and_excludes_deleted_decks(self):
        with self.app.app_context():
            outsider = User(username="outsider", email="outsider@example.com")
            db.session.add(outsider)
            db.session.flush()
            ancestor = Deck(name="Foreign ancestor", owner_user_id=outsider.id, position=-1)
            unrelated = Deck(name="Other foreign root", owner_user_id=outsider.id)
            deleted = Deck(name="Deleted own root", owner_user_id=self.admin_id, deleted_at=datetime(2026, 1, 1))
            db.session.add_all([ancestor, unrelated, deleted])
            db.session.flush()
            parent = Deck(name="Foreign parent", parent_id=ancestor.id, owner_user_id=outsider.id)
            db.session.add(parent)
            db.session.flush()
            db.session.get(Deck, self.child_deck_id).parent_id = parent.id
            db.session.commit()

            rows = collect_accessible_decks(user_id=self.admin_id, admin_mode=True)
            self.assertEqual([row.id for row in rows], [ancestor.id, self.root_deck_id, self.child_deck_id, parent.id])
            self.assertNotIn(unrelated.id, [row.id for row in rows])
            self.assertNotIn(deleted.id, [row.id for row in rows])

    def test_deck_resource_create_update_reset_and_delete(self):
        self._login_admin()

        create_response = self.client.post(
            "/api/decks",
            json={"path": "API parent::API child"},
        )
        self.assertEqual(create_response.status_code, 201)
        create_payload = create_response.get_json()
        self.assertEqual(create_payload["created_count"], 2)
        created_deck_id = create_payload["item"]["id"]

        rename_response = self.client.patch(
            f"/api/decks/{created_deck_id}",
            json={"name": "Renamed API child"},
        )
        self.assertEqual(rename_response.status_code, 200)
        self.assertTrue(rename_response.get_json()["changed"])
        self.assertEqual(
            rename_response.get_json()["item"]["name"],
            "Renamed API child",
        )

        reset_response = self.client.post(
            f"/api/decks/{created_deck_id}/progress-reset",
            json={},
        )
        self.assertEqual(reset_response.status_code, 200)
        self.assertEqual(
            reset_response.get_json()["deleted_progress_count"],
            0,
        )

        delete_response = self.client.delete(
            f"/api/decks/{created_deck_id}"
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.get_json()["mode"], "deleted")

        missing_response = self.client.get("/api/not-a-resource")
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(missing_response.get_json()["error"], "NOT_FOUND")

        method_response = self.client.put("/api/dashboard", json={})
        self.assertEqual(method_response.status_code, 405)
        self.assertEqual(
            method_response.get_json()["error"],
            "METHOD_NOT_ALLOWED",
        )

    def test_support_donation_and_empty_order_resources(self):
        support_response = self.client.get("/api/support-donation")
        self.assertEqual(support_response.status_code, 200)
        support_payload = support_response.get_json()
        self.assertFalse(support_payload["configured"])
        self.assertGreater(len(support_payload["limits"]["suggested_amounts"]), 0)

        self._login_admin()
        orders_response = self.client.get("/api/orders")
        self.assertEqual(orders_response.status_code, 200)
        self.assertEqual(orders_response.get_json()["items"], [])

        installed_response = self.client.get(
            "/api/marketplace/installed-decks"
        )
        self.assertEqual(installed_response.status_code, 200)
        self.assertIsInstance(installed_response.get_json(), dict)

        missing_order_response = self.client.get("/api/orders/missing")
        self.assertEqual(missing_order_response.status_code, 404)
        self.assertEqual(missing_order_response.get_json()["error"], "NOT_FOUND")

    def test_admin_payment_resources_and_mcp_token_lifecycle(self):
        self._login_admin()

        payment_dashboard_response = self.client.get("/api/admin/payments")
        self.assertEqual(payment_dashboard_response.status_code, 200)
        self.assertEqual(
            payment_dashboard_response.get_json()["filters"]["period"],
            "30d",
        )

        admin_orders_response = self.client.get(
            "/api/admin/payments/orders?per_page=5"
        )
        self.assertEqual(admin_orders_response.status_code, 200)
        self.assertEqual(admin_orders_response.get_json()["per_page"], 5)

        transactions_response = self.client.get(
            "/api/admin/payments/transactions"
        )
        self.assertEqual(transactions_response.status_code, 200)
        self.assertEqual(transactions_response.get_json()["items"], [])

        create_token_response = self.client.post("/api/mcp-tokens", json={})
        self.assertEqual(create_token_response.status_code, 201)
        issued = create_token_response.get_json()["item"]
        self.assertTrue(issued["token"].startswith("flama_mcp_"))

        list_token_response = self.client.get("/api/mcp-tokens")
        self.assertEqual(list_token_response.status_code, 200)
        token_rows = list_token_response.get_json()["items"]
        self.assertEqual(len(token_rows), 1)
        self.assertEqual(token_rows[0]["status"], "active")

        revoke_response = self.client.delete(
            f"/api/mcp-tokens/{token_rows[0]['id']}"
        )
        self.assertEqual(revoke_response.status_code, 204)

        revoked_list_response = self.client.get("/api/mcp-tokens")
        self.assertEqual(
            revoked_list_response.get_json()["items"][0]["status"],
            "revoked",
        )

    def test_non_admin_cannot_access_admin_rest_resources(self):
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "email": "regular@example.com",
                "username": "regular",
                "password": "secret-password",
                "confirm_password": "secret-password",
            },
        )
        self.assertEqual(register_response.status_code, 201)
        self.client.post(
            "/api/auth/login",
            json={"email": "regular@example.com", "password": "secret-password"},
        )

        response = self.client.get("/api/admin/payments")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "FORBIDDEN")

        create_deck_response = self.client.post(
            "/api/decks",
            json={"name": "Regular owned deck"},
        )
        self.assertEqual(create_deck_response.status_code, 201)
        regular_deck_id = create_deck_response.get_json()["item"]["id"]

        rename_response = self.client.patch(
            f"/api/decks/{regular_deck_id}",
            json={"name": "Not allowed through current admin-only flow"},
        )
        self.assertEqual(rename_response.status_code, 403)

        purge_response = self.client.delete(
            f"/api/decks/{regular_deck_id}?purge=true"
        )
        self.assertEqual(purge_response.status_code, 403)
        self.assertEqual(purge_response.get_json()["error"], "FORBIDDEN")

    def test_admin_user_resource_lists_roles_and_updates_status(self):
        self._login_admin()
        register_response = self.client.post(
            "/api/auth/register",
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

        list_response = self.client.get("/api/admin/users?q=managed")
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.get_json()
        self.assertEqual(len(list_payload["items"]), 1)
        self.assertGreaterEqual(len(list_payload["roles"]), 2)

        update_response = self.client.patch(
            f"/api/admin/users/{managed_id}",
            json={"is_disabled": True},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertTrue(update_response.get_json()["item"]["is_disabled"])

    def test_browse_rest_api_v1_endpoints(self):
        self._login_admin()

        decks_response = self.client.get("/api/browse/decks")
        self.assertEqual(decks_response.status_code, 200)
        decks_data = decks_response.get_json()
        self.assertIn("decks", decks_data)
        self.assertIn("tree", decks_data)

        tree_response = self.client.get("/api/browse/decks/tree")
        self.assertEqual(tree_response.status_code, 200)
        self.assertIn("tree", tree_response.get_json())

        cards_response = self.client.get("/api/browse/cards?status=all&sort_by=due&sort_dir=asc&page=1&per_page=50")
        self.assertEqual(cards_response.status_code, 200)
        cards_data = cards_response.get_json()
        self.assertIn("items", cards_data)
        self.assertIn("total", cards_data)

    def test_browse_voicevox_precheck_matches_transition_adapter(self):
        self._login_admin()
        payload = {
            "card_ids": [],
            "destination_field": "Audio",
        }

        legacy_response = self.client.post(
            "/vocabulary/api/browse/voicevox/precheck",
            json=payload,
        )
        v1_response = self.client.post(
            "/api/browse/voicevox/precheck",
            json=payload,
        )

        self.assertEqual(legacy_response.status_code, 200)
        self.assertEqual(v1_response.status_code, 200)
        self.assertEqual(v1_response.get_json(), legacy_response.get_json())

    def test_deck_and_note_type_purge(self):
        self._login_admin()

        from models.note_type import NoteType
        from models.note import Note
        from models.card import Card
        from models.card_progress import CardProgress
        from models.deck_install import DeckInstall
        from models.deck_marketplace_item import DeckMarketplaceItem
        from models.review_event import ReviewEvent

        # 1. Create a NoteType and Deck
        with self.app.app_context():
            nt = NoteType(user_id=self.admin_id, name="Test NT")
            db.session.add(nt)
            db.session.flush()
            nt_id = nt.id

            deck = Deck(name="Test Purge Deck", owner_user_id=self.admin_id)
            db.session.add(deck)
            db.session.flush()
            deck_id = deck.id

            # Create a Note, Card, CardProgress
            note = Note(note_type_id=nt_id, user_id=self.admin_id, deck_id=deck_id)
            db.session.add(note)
            db.session.flush()
            note_id = note.id

            card = Card.query.filter_by(note_id=note_id, template_id="some-template").one()
            db.session.flush()
            card_id = card.id

            prog = CardProgress(user_id=self.admin_id, card_id=card_id, queue="new")
            db.session.add(prog)

            # Create some dependent objects
            mitem = DeckMarketplaceItem(owner_user_id=self.admin_id, source_deck_id=deck_id, title="MItem")
            db.session.add(mitem)
            db.session.flush()
            mitem_id = mitem.id

            dinstall = DeckInstall(deck_item_id=mitem_id, user_id=self.admin_id, local_deck_id=deck_id, source_deck_id=deck_id)
            db.session.add(dinstall)

            from models.deck_change_request import DeckChangeRequest
            dcr = DeckChangeRequest(
                requester_user_id=self.admin_id,
                owner_user_id=self.admin_id,
                local_deck_id=deck_id,
                source_deck_id=deck_id,
                overlay_fingerprint="fingerprint_test"
            )
            db.session.add(dcr)

            from models.note_type_install import NoteTypeInstall
            nti = NoteTypeInstall(
                source_note_type_id=nt_id,
                installed_note_type_id=nt_id,
                user_id=self.admin_id
            )
            db.session.add(nti)

            from datetime import datetime, timezone
            rev = ReviewEvent(
                user_id=self.admin_id,
                card_id=card_id,
                deck_id=deck_id,
                note_type_id=nt_id,
                rating="good",
                mode="review",
                reviewed_at=datetime.now(timezone.utc).replace(tzinfo=None)
            )
            db.session.add(rev)

            db.session.commit()
            review_event_id = rev.id

        # Verify they exist
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Deck, deck_id))
            self.assertIsNotNone(db.session.get(NoteType, nt_id))
            self.assertEqual(ReviewEvent.query.filter_by(deck_id=deck_id).count(), 1)
            self.assertEqual(DeckInstall.query.filter_by(source_deck_id=deck_id).count(), 1)
            self.assertEqual(DeckChangeRequest.query.filter_by(source_deck_id=deck_id).count(), 1)
            self.assertEqual(NoteTypeInstall.query.filter_by(source_note_type_id=nt_id).count(), 1)

        # Try to purge note type as regular user
        self.client.delete("/api/session")
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "email": "purgeuser@example.com",
                "username": "purgeuser",
                "password": "secret-password",
                "confirm_password": "secret-password",
            },
        )
        self.assertEqual(register_response.status_code, 201)
        self.client.post(
            "/api/auth/login",
            json={"email": "purgeuser@example.com", "password": "secret-password"},
        )

        # Non-admin purge note type -> should fail
        response = self.client.delete(f"/api/note-types/{nt_id}?purge=true")
        self.assertEqual(response.status_code, 403)

        # Login admin back
        self.client.delete("/api/session")
        self._login_admin()

        # Admin purge deck
        delete_deck_res = self.client.delete(f"/api/decks/{deck_id}?purge=true")
        if delete_deck_res.status_code != 200:
            print("PURGE_DECK_ERROR:", delete_deck_res.get_data(as_text=True))
        self.assertEqual(delete_deck_res.status_code, 200)
        self.assertEqual(delete_deck_res.get_json()["mode"], "purged")

        # Verify deck and its dependencies are deleted
        with self.app.app_context():
            from models.deck_change_request import DeckChangeRequest
            self.assertIsNone(db.session.get(Deck, deck_id))
            self.assertEqual(ReviewEvent.query.filter_by(deck_id=deck_id).count(), 0)
            preserved_review = db.session.get(ReviewEvent, review_event_id)
            self.assertIsNotNone(preserved_review)
            self.assertIsNone(preserved_review.deck_id)
            self.assertEqual(preserved_review.note_type_id, nt_id)
            self.assertEqual(DeckInstall.query.filter_by(source_deck_id=deck_id).count(), 0)
            self.assertEqual(DeckMarketplaceItem.query.filter_by(source_deck_id=deck_id).count(), 0)
            self.assertEqual(DeckChangeRequest.query.filter_by(source_deck_id=deck_id).count(), 0)
            self.assertIsNone(db.session.get(Note, note_id))
            self.assertIsNone(db.session.get(Card, card_id))

        # Admin purge note type
        delete_nt_res = self.client.delete(f"/api/note-types/{nt_id}?purge=true")
        self.assertEqual(delete_nt_res.status_code, 200)
        self.assertTrue(delete_nt_res.get_json()["purged"])

        # Verify note type and its dependencies are deleted
        with self.app.app_context():
            from models.note_type_install import NoteTypeInstall
            self.assertIsNone(db.session.get(NoteType, nt_id))
            self.assertEqual(NoteTypeInstall.query.filter_by(source_note_type_id=nt_id).count(), 0)
            preserved_review = db.session.get(ReviewEvent, review_event_id)
            self.assertIsNotNone(preserved_review)
            self.assertIsNone(preserved_review.note_type_id)

if __name__ == "__main__":
    unittest.main()
