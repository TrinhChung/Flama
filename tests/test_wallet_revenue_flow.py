"""Integration tests for wallet revenue sharing and platform fee deductions."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch

from app import create_app
from app.services import user_roles, wallet_service
from models import db
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.user import User
from models.user_balance_transaction import UserBalanceTransaction
from models.user_role import UserRole

UTC = timezone.utc


class WalletRevenueFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": True,
                "STARTUP_RUN_DEFAULT_USER_ROLE_SEED": True,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user_roles.ensure_default_user_roles(db.session)

            creator_role = UserRole.query.filter_by(code="creator").first()
            regular_role = UserRole.query.filter_by(code="regular").first()

            # Regular author
            regular_author = User(
                username="regular_author",
                email="regular@example.com",
                role_id=regular_role.id if regular_role else None,
                balance_amount_minor=0,
            )
            regular_author.set_password("password123")

            # Creator author (5% fee)
            creator_author = User(
                username="creator_author",
                email="creator@example.com",
                role_id=creator_role.id if creator_role else None,
                balance_amount_minor=10000,
            )
            creator_author.set_password("password123")

            # Custom fee author (Admin set 0% fee)
            vip_author = User(
                username="vip_author",
                email="vip@example.com",
                role_id=regular_role.id if regular_role else None,
                custom_platform_fee_percent=0.0,
                balance_amount_minor=0,
            )
            vip_author.set_password("password123")

            # Buyer
            buyer = User(
                username="buyer_user",
                email="buyer@example.com",
                role_id=regular_role.id if regular_role else None,
                balance_amount_minor=0,
            )
            buyer.set_password("password123")

            db.session.add_all([regular_author, creator_author, vip_author, buyer])
            db.session.commit()

            self.regular_author_id = regular_author.id
            self.creator_author_id = creator_author.id
            self.vip_author_id = vip_author.id
            self.buyer_id = buyer.id

            # Create marketplace decks
            deck1 = Deck(owner_user_id=regular_author.id, name="Deck Regular")
            deck2 = Deck(owner_user_id=creator_author.id, name="Deck Creator")
            deck3 = Deck(owner_user_id=vip_author.id, name="Deck VIP")
            db.session.add_all([deck1, deck2, deck3])
            db.session.flush()

            item1 = DeckMarketplaceItem(
                owner_user_id=regular_author.id,
                source_deck_id=deck1.id,
                title="Deck Regular Item",
                pricing_mode="paid",
                price_amount_minor=100000,  # 100k VND
            )
            item2 = DeckMarketplaceItem(
                owner_user_id=creator_author.id,
                source_deck_id=deck2.id,
                title="Deck Creator Item",
                pricing_mode="paid",
                price_amount_minor=200000,  # 200k VND
            )
            item3 = DeckMarketplaceItem(
                owner_user_id=vip_author.id,
                source_deck_id=deck3.id,
                title="Deck VIP Item",
                pricing_mode="paid",
                price_amount_minor=50000,  # 50k VND
            )
            db.session.add_all([item1, item2, item3])
            db.session.commit()

            self.item1_id = item1.id
            self.item2_id = item2.id
            self.item3_id = item3.id

    def test_fee_percent_resolution(self):
        with self.app.app_context():
            regular = db.session.get(User, self.regular_author_id)
            creator = db.session.get(User, self.creator_author_id)
            vip = db.session.get(User, self.vip_author_id)

            self.assertEqual(wallet_service.get_user_platform_fee_percent(regular), 10.0)
            self.assertEqual(wallet_service.get_user_platform_fee_percent(creator), 5.0)
            self.assertEqual(wallet_service.get_user_platform_fee_percent(vip), 0.0)

    def test_credit_creator_for_deck_sale_regular(self):
        with self.app.app_context():
            order = PaymentOrder(
                user_id=self.buyer_id,
                merchant_order_code="ORD-001",
                status="paid",
                grant_status="completed",
                total_amount_minor=100000,
            )
            db.session.add(order)
            db.session.flush()

            order_item = PaymentOrderItem(
                order_id=order.id,
                product_type="deck_marketplace_item",
                product_ref_id=self.item1_id,
                title_snapshot="Deck Regular Item",
                unit_amount_minor=100000,
                line_total_amount_minor=100000,
            )
            db.session.add(order_item)
            db.session.commit()

            now = datetime.now(UTC).replace(tzinfo=None)
            tx = wallet_service.credit_creator_for_deck_sale(
                order=order,
                order_item=order_item,
                now=now,
            )
            db.session.commit()

            self.assertIsNotNone(tx)
            self.assertEqual(tx.gross_amount_minor, 100000)
            self.assertEqual(tx.platform_fee_percent, 10.0)
            self.assertEqual(tx.platform_fee_amount_minor, 10000)  # 10% of 100k = 10k
            self.assertEqual(tx.net_amount_minor, 90000)  # 100k - 10k = 90k
            self.assertEqual(tx.balance_after_minor, 90000)

            # Check author balance updated
            author = db.session.get(User, self.regular_author_id)
            self.assertEqual(author.balance_amount_minor, 90000)

    def test_credit_creator_for_deck_sale_creator_role(self):
        with self.app.app_context():
            order = PaymentOrder(
                user_id=self.buyer_id,
                merchant_order_code="ORD-002",
                status="paid",
                grant_status="completed",
                total_amount_minor=200000,
            )
            db.session.add(order)
            db.session.flush()

            order_item = PaymentOrderItem(
                order_id=order.id,
                product_type="deck_marketplace_item",
                product_ref_id=self.item2_id,
                title_snapshot="Deck Creator Item",
                unit_amount_minor=200000,
                line_total_amount_minor=200000,
            )
            db.session.add(order_item)
            db.session.commit()

            now = datetime.now(UTC).replace(tzinfo=None)
            tx = wallet_service.credit_creator_for_deck_sale(
                order=order,
                order_item=order_item,
                now=now,
            )
            db.session.commit()

            self.assertIsNotNone(tx)
            self.assertEqual(tx.gross_amount_minor, 200000)
            self.assertEqual(tx.platform_fee_percent, 5.0)  # Creator discount: 5%
            self.assertEqual(tx.platform_fee_amount_minor, 10000)  # 5% of 200k = 10k
            self.assertEqual(tx.net_amount_minor, 190000)
            self.assertEqual(tx.balance_after_minor, 200000)  # Initial 10k + 190k = 200k

            author = db.session.get(User, self.creator_author_id)
            self.assertEqual(author.balance_amount_minor, 200000)

    def test_credit_creator_for_deck_sale_vip_zero_fee(self):
        with self.app.app_context():
            order = PaymentOrder(
                user_id=self.buyer_id,
                merchant_order_code="ORD-003",
                status="paid",
                grant_status="completed",
                total_amount_minor=50000,
            )
            db.session.add(order)
            db.session.flush()

            order_item = PaymentOrderItem(
                order_id=order.id,
                product_type="deck_marketplace_item",
                product_ref_id=self.item3_id,
                title_snapshot="Deck VIP Item",
                unit_amount_minor=50000,
                line_total_amount_minor=50000,
            )
            db.session.add(order_item)
            db.session.commit()

            now = datetime.now(UTC).replace(tzinfo=None)
            tx = wallet_service.credit_creator_for_deck_sale(
                order=order,
                order_item=order_item,
                now=now,
            )
            db.session.commit()

            self.assertIsNotNone(tx)
            self.assertEqual(tx.gross_amount_minor, 50000)
            self.assertEqual(tx.platform_fee_percent, 0.0)
            self.assertEqual(tx.platform_fee_amount_minor, 0)
            self.assertEqual(tx.net_amount_minor, 50000)  # Full 50k
            self.assertEqual(tx.balance_after_minor, 50000)

    def test_idempotency_prevents_duplicate_credit(self):
        with self.app.app_context():
            order = PaymentOrder(
                user_id=self.buyer_id,
                merchant_order_code="ORD-004",
                status="paid",
                grant_status="completed",
                total_amount_minor=100000,
            )
            db.session.add(order)
            db.session.flush()

            order_item = PaymentOrderItem(
                order_id=order.id,
                product_type="deck_marketplace_item",
                product_ref_id=self.item1_id,
                title_snapshot="Deck Regular Item",
                unit_amount_minor=100000,
                line_total_amount_minor=100000,
            )
            db.session.add(order_item)
            db.session.commit()

            now = datetime.now(UTC).replace(tzinfo=None)
            tx1 = wallet_service.credit_creator_for_deck_sale(
                order=order,
                order_item=order_item,
                now=now,
            )
            db.session.commit()

            # Second call (e.g. webhook replay or sync)
            tx2 = wallet_service.credit_creator_for_deck_sale(
                order=order,
                order_item=order_item,
                now=now,
            )
            db.session.commit()

            self.assertEqual(tx1.id, tx2.id)

            # Check that only 1 transaction was created
            all_txs = UserBalanceTransaction.query.filter_by(user_id=self.regular_author_id).all()
            self.assertEqual(len(all_txs), 1)

            author = db.session.get(User, self.regular_author_id)
            self.assertEqual(author.balance_amount_minor, 90000)

    def test_self_purchase_does_not_credit(self):
        with self.app.app_context():
            order = PaymentOrder(
                user_id=self.regular_author_id,  # Author buys own deck
                merchant_order_code="ORD-005",
                status="paid",
                grant_status="completed",
                total_amount_minor=100000,
            )
            db.session.add(order)
            db.session.flush()

            order_item = PaymentOrderItem(
                order_id=order.id,
                product_type="deck_marketplace_item",
                product_ref_id=self.item1_id,
                title_snapshot="Deck Regular Item",
                unit_amount_minor=100000,
                line_total_amount_minor=100000,
            )
            db.session.add(order_item)
            db.session.commit()

            now = datetime.now(UTC).replace(tzinfo=None)
            tx = wallet_service.credit_creator_for_deck_sale(
                order=order,
                order_item=order_item,
                now=now,
            )
            self.assertIsNone(tx)


if __name__ == "__main__":
    unittest.main()
