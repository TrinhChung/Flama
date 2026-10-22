"""Verify multi-author NoteType bundle publication and sales on local MySQL.

Creates and drops one generated loopback-only schema. The configured application
database is used only to read its default collation. All fixtures, routes,
payments and wallet writes use the disposable schema. PayOS is mocked and HTTP
requests are forbidden, so this probe cannot create a real payment link.

Run from the repository root with .venv/Scripts/python.exe and this file path.
"""

from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import secrets
import sys
import traceback
from unittest.mock import patch

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

PROBE = re.compile(r"^flama_notetype_bundle_probe_[0-9]+_[a-f0-9]{12}$")


def _require(condition, description):
    if not condition:
        raise RuntimeError(description)


def _fake_checkout(**values):
    code = str(values["provider_order_code"])
    return {
        "provider_code": "payos", "provider_order_code": code,
        "provider_payment_id": f"probe-link-{code}",
        "checkout_url": f"https://payments.example.test/{code}",
        "amount_minor": values["amount_minor"], "currency_code": "VND",
        "expires_at": values["expires_at"],
        "provider_metadata": {"provider_status": "PENDING"}, "raw_response": {},
    }


def _qualify(uri, schema, result):
    from app import create_app
    from app.api.v1.marketplace.note_types import marketplace_note_types_bp
    from app.routes.payments import payments_bp
    from app.services import marketplace_note_type_service as market
    from app.services import note_type_release_service as note_releases
    from app.services import payment
    from app.services import template_marketplace_service as template_market
    from models import db
    from models.field_def import FieldDef
    from models.note_type import NoteType
    from models.note_type_install import NoteTypeInstall
    from models.note_type_release import NoteTypeRelease
    from models.payment_entitlement import PaymentEntitlement
    from models.payment_order import PaymentOrder
    from models.payment_webhook_event import PaymentWebhookEvent
    from models.study_application import StudyApplication
    from models.template import Template
    from models.template_publication import TemplatePublication
    from models.template_release import TemplateRelease
    from models.template_subscription import TemplateSubscription
    from models.user_balance_transaction import UserBalanceTransaction
    from tests.study_note_fixtures import attach_template, create_note_user

    app = create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": uri, "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "disposable-note-type-bundle-probe",
        "PAYMENTS_ENABLED": True, "PAYMENTS_PROVIDER": "payos",
        "PAYMENTS_PAID_INSTALL_REQUIRED": True, "PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED": True,
        "PAYMENTS_ORDER_EXPIRY_SECONDS": 3600,
    }, audit_mode=True)
    app.register_blueprint(marketplace_note_types_bp, url_prefix="/api")
    app.register_blueprint(payments_bp)

    with app.app_context(), ExitStack() as stack:
        stack.callback(db.engine.dispose)
        stack.callback(db.session.remove)
        _require(db.engine.url.database == schema, "ORM target is not the generated schema.")
        _require(not sa.inspect(db.engine).get_table_names(), "Generated schema is not empty.")
        db.create_all()
        stack.enter_context(patch("urllib.request.urlopen", side_effect=RuntimeError("Probe forbids external HTTP.")))
        stack.enter_context(patch("app.services.payos_client.get_payos_client", side_effect=RuntimeError("Probe forbids live PayOS clients.")))
        stack.enter_context(patch("app.services.payment.provider.payos_provider.create_checkout_session", side_effect=_fake_checkout))
        stack.enter_context(patch("app.services.payment.provider.payos_provider.cancel_checkout_session",
            return_value={"status": "CANCELLED"}))
        stack.enter_context(patch("app.services.payment.provider.payos_provider.get_payment_link_state",
            return_value={"status": "PENDING", "amount_paid_minor": 0, "amount_remaining_minor": 999999}))

        users = {}
        for label in ("author", "designer", "free_designer", "buyer", "owns_foreign", "free_bundle_buyer", "outsider"):
            user = create_note_user(db.session, username=f"bundle-{label}", email=f"bundle-{label}@example.test")
            user.custom_platform_fee_percent = 0
            users[label] = user
        db.session.commit()
        clients = {}

        def client_for(label):
            if label not in clients:
                client = app.test_client()
                with client.session_transaction() as session:
                    session["_user_id"] = str(users[label].id)
                    session["_fresh"] = True
                clients[label] = client
            return clients[label]

        def post(label, path, payload=None, statuses=(200,)):
            response = api_request(label, "post", path, json=payload or {})
            data = response.get_json() or {}
            _require(response.status_code in statuses,
                f"POST {path}: expected {statuses}, got {response.status_code}: {data.get('error')}: {data.get('message')}")
            return data

        def get(label, path):
            response = api_request(label, "get", path)
            data = response.get_json() or {}
            _require(response.status_code == 200,
                f"GET {path} returned {response.status_code}: {data.get('error')}")
            return data

        def api_request(label, method, path, **values):
            # This probe keeps an outer app context for ORM assertions. Reset
            # Flask-Login's g cache when switching clients inside that context.
            from flask import g
            client = client_for(label)
            g.pop("_login_user", None)
            return getattr(client, method)(path, **values)

        def checkout(label, product_type, product_id):
            return payment.prepare_checkout_for_product(user_id=users[label].id,
                product_type=product_type, product_ref_id=product_id,
                return_url="https://app.example.test/result", cancel_url="https://app.example.test/cancel")

        def paid(order_id, *, event_key=None, expected="processed"):
            order = db.session.get(PaymentOrder, order_id)
            attempt = max(order.attempts, key=lambda row: row.created_at)
            event_key = event_key or f"bundle-payment-{order_id}"
            normalized = {
                "provider_code": "payos", "event_key": event_key, "event_type": "payment.succeeded",
                "provider_order_code": attempt.provider_order_code, "provider_payment_id": attempt.provider_payment_id,
                "provider_transaction_ref": f"txn-{event_key}", "payment_reference": attempt.expected_payment_reference,
                "amount_minor": attempt.amount_minor, "currency_code": "VND", "success": True,
                "status": "00", "raw_payload": {"probe_event": event_key},
            }
            with patch("app.services.payment.provider.payos_provider.verify_webhook_payload", return_value=normalized):
                response = api_request("outsider", "post", "/api/payments/providers/payos/webhook", data=b"{}", content_type="application/json")
            data = response.get_json() or {}
            if data.get("status") == "failed":
                event = PaymentWebhookEvent.query.filter_by(event_key=event_key).one()
                raise RuntimeError(f"Payment fulfillment failed: {event.error_message}")
            _require(response.status_code == 200 and data.get("status") == expected,
                f"Webhook did not return {expected}: {response.status_code} {data.get('status')}")
            return data

        def source_template(label, name, price):
            template = Template(owner_user_id=users[label].id, name=name,
                description=f"Published {name}", primary_category="General",
                front_html=f"{name} {{{{word}}}}", back_html="{{word}}", shared_css=".card{}",
                input_schema=[{"key": "word", "type": "text"}])
            db.session.add(template)
            db.session.commit()
            listing = template_market.update_listing(user_id=users[label].id, template_id=template.id,
                payload={"marketplace_status": "published", "pricing_mode": "paid" if price else "free", "price_amount_minor": price})
            return template, listing["current_release"]["id"]

        foreign, foreign_release = source_template("designer", "B paid layout", 15000)
        free_foreign, free_foreign_release = source_template("free_designer", "C free layout", 0)
        author_purchase = checkout("author", "template", foreign.id)
        paid(author_purchase["order"]["id"])
        foreign_local = TemplateSubscription.query.filter_by(user_id=users["author"].id, source_template_id=foreign.id).one()
        foreign_copy = db.session.get(Template, foreign_local.local_template_id)
        free_receipt, status = template_market.install(user_id=users["author"].id, template_id=free_foreign.id)
        _require(status == 201, "Free foreign template fixture receipt failed.")
        free_copy = db.session.get(Template, free_receipt["local_template_id"])
        foreign_copy.front_html = "LOCAL EDIT MUST NOT BE SOLD AS B"
        db.session.commit()

        def note_type(name, *, bundle=10000, foreign_id=None):
            note = NoteType(user_id=users["author"].id, name=name,
                description=f"Description {name}", primary_category="General", tags=[], preview_text="Example word",
                taxonomy_metadata={"domain": "language_learning", "subject": "japanese", "difficulty_band": "beginner",
                    "learning_goals": ["vocabulary"], "primary_topics": ["meaning_recall"]},
                version="1.0.0", publish_status="private", pricing_mode="paid" if bundle else "free", price_amount_minor=bundle)
            db.session.add(note)
            db.session.flush()
            field = FieldDef(note_type_id=note.id, name="Word", field_type="text", required=True,
                identity_role="primary", position=0)
            db.session.add(field)
            db.session.flush()
            if foreign_id:
                db.session.add(StudyApplication(note_type_id=note.id, template_id=foreign_id,
                    occurrence_key="foreign", input_bindings={"word": field.id}, position=0))
            db.session.commit()
            return note, field

        bundle, word = note_type("A own discounted bundle")
        own = []
        for idx, price in enumerate((30000, 20000)):
            template = attach_template(db.session, note_type_id=bundle.id, owner_user_id=users["author"].id,
                name=f"A layout {idx}", front_html="{{word}}", back_html="{{word}}", shared_css="",
                input_schema=[{"key": "word", "type": "text"}], position=idx)
            application = StudyApplication.query.filter_by(note_type_id=bundle.id, template_id=template.id).one()
            application.input_bindings = {"word": word.id}
            own.append((template, price))
        for idx, template in enumerate((foreign_copy, free_copy, foreign_copy), start=2):
            db.session.add(StudyApplication(note_type_id=bundle.id, template_id=template.id,
                occurrence_key=f"external-{idx}", position=idx, input_bindings={"word": word.id}))
        db.session.commit()
        options = get("author", f"/api/marketplace/note-types/{bundle.id}/publish-options")
        option_rows = options.get("templates") or []
        _require(len(option_rows) >= 4, "Publish options omitted attached template definitions.")
        _require(all(any(row.get("template_id", row.get("id")) == template.id and row.get("requires_publication") for row in option_rows)
            for template, _price in own), "Owned unpublished templates are not marked for inline listing.")
        inline = [{"template_id": template.id, "description": f"Standalone {template.name}",
            "primary_category": "General", "pricing_mode": "paid", "price_amount_minor": price} for template, price in own]
        post("author", f"/api/marketplace/note-types/{bundle.id}/publish", {
            "publish_status": "published", "pricing_mode": "paid", "price_amount_minor": 10000,
            "template_listings": inline})
        bundle_release = db.session.get(NoteTypeRelease, db.session.get(NoteType, bundle.id).current_release_id)
        _require(bundle_release is not None, "Bundle publication did not produce a complete release.")
        applications = bundle_release.manifest_json["applications"]
        foreign_apps = [row for row in applications if row["template_id"] == foreign.id]
        _require(len(foreign_apps) == 2 and all(row["template_release_id"] == foreign_release for row in foreign_apps),
            "Foreign occurrences did not preserve the original source template/release.")
        _require(all(row["template_id"] != foreign_copy.id for row in applications), "Received copy was republished under a new identity.")
        _require(TemplateRelease.query.filter_by(template_id=foreign_copy.id).count() == 0,
            "Locally edited foreign copy acquired an authored release.")
        for template, price in own:
            listing = template_market.get_listing(user_id=users["author"].id, template_id=template.id)
            _require(listing["marketplace_status"] == "published" and listing["price_amount_minor"] == price,
                "Inline publication did not preserve the standalone price.")
        result["inline_publication_and_discounted_own_bundle"] = True
        result["foreign_copy_reference_and_duplicate_occurrence_provenance"] = True

        detail = get("buyer", f"/api/marketplace/note-types/{bundle.id}")
        breakdown = detail.get("pricing_breakdown") or {}
        _require((breakdown.get("bundle_amount_minor"), breakdown.get("template_amount_minor"), breakdown.get("total_amount_minor")) == (10000, 15000, 25000),
            f"Bundle detail price must be 10k own + 15k foreign, charged once: {breakdown}.")
        _require(breakdown.get("payment_required") is True, "Bundle detail omitted required payment.")
        _require(any(row.get("id") == foreign.id and row.get("front_html") == "B paid layout {{word}}" for row in detail.get("templates", [])),
            "Buyer preview exposed foreign local draft content.")
        result["detail_price_and_original_foreign_preview"] = True

        # Buying B separately exempts B from this bundle, without reducing A's price.
        initial_pending = post("owns_foreign", f"/api/marketplace/note-types/{bundle.id}/install", statuses=(202,))
        initial_order_id = initial_pending["order"]["id"]
        _require(initial_pending["order"]["total_amount_minor"] == 25000,
            "Initial pending bundle quote must include the unowned foreign license.")
        existing_purchase = checkout("owns_foreign", "template", foreign.id)
        paid(existing_purchase["order"]["id"])
        from app.services.note_type_bundle_pricing_service import has_template_access
        own_rights = PaymentEntitlement.query.filter_by(user_id=users["owns_foreign"].id,
            resource_type="template", resource_ref_id=foreign.id).all()
        _require(has_template_access(db.session, user_id=users["owns_foreign"].id, template_id=foreign.id),
            f"Purchased foreign rights unavailable: {[(row.status, row.effective_from, row.expires_at) for row in own_rights]}.")
        owned_detail = get("owns_foreign", f"/api/marketplace/note-types/{bundle.id}")["pricing_breakdown"]
        _require((owned_detail["bundle_amount_minor"], owned_detail["template_amount_minor"], owned_detail["total_amount_minor"]) == (10000, 0, 10000),
            f"Existing foreign rights were charged again or reduced the fixed own bundle price: {owned_detail}.")
        with patch("app.services.payment.provider.payos_provider.cancel_checkout_session",
                return_value={"status": "CANCELLED"}) as cancel_old_quote:
            own_checkout = post("owns_foreign", f"/api/marketplace/note-types/{bundle.id}/install", statuses=(202,))
            _require(cancel_old_quote.call_count == 1 or db.session.get(PaymentOrder, initial_order_id).status == "canceled",
                "Changed license quote did not cancel its old payable link.")
        own_order = db.session.get(PaymentOrder, own_checkout["order"]["id"])
        _require(own_order.id != initial_order_id and db.session.get(PaymentOrder, initial_order_id).status == "canceled",
            "Newly owned template still reused the old higher-priced bundle order.")
        _require(own_order.total_amount_minor == 10000 and
            all(item.product_type == "note_type" or item.line_total_amount_minor == 0 for item in own_order.items) and
            not any(item.product_type == "template" and item.product_ref_id == foreign.id for item in own_order.items),
            "Owned foreign template still created a charge line.")
        result["already_entitled_foreign_template_is_not_recharged"] = True
        result["pending_quote_is_canceled_and_repriced_after_template_purchase"] = True
        entitlement = PaymentEntitlement.query.filter_by(user_id=users["owns_foreign"].id,
            resource_type="template", resource_ref_id=foreign.id).one()
        entitlement.status = "revoked"
        db.session.commit()
        revoked_price = get("owns_foreign", f"/api/marketplace/note-types/{bundle.id}")["pricing_breakdown"]
        _require(revoked_price["template_amount_minor"] == 15000,
            "A revoked foreign template entitlement still waived its price.")
        entitlement.status = "active"
        entitlement.expires_at = datetime.utcnow() - timedelta(days=1)
        db.session.commit()
        expired_price = get("owns_foreign", f"/api/marketplace/note-types/{bundle.id}")["pricing_breakdown"]
        _require(expired_price["template_amount_minor"] == 15000,
            "An expired foreign template entitlement still waived its price.")
        entitlement.expires_at = None
        db.session.commit()
        result["revoked_and_expired_foreign_rights_do_not_waive_payment"] = True
        entitlement.effective_from = datetime.utcnow() + timedelta(days=1)
        db.session.commit()
        future_price = get("owns_foreign", f"/api/marketplace/note-types/{bundle.id}")["pricing_breakdown"]
        _require(future_price["template_amount_minor"] == 15000,
            "A future foreign template entitlement still waived its price.")
        entitlement.effective_from = None
        db.session.commit()
        result["future_foreign_rights_do_not_waive_payment"] = True

        # Payment guards must run below the marketplace route too.
        try:
            note_releases.stage_receipt(db.session, source_note_type=bundle, user_id=users["outsider"].id)
        except note_releases.NoteTypeReleaseError as exc:
            _require(exc.code == "PAYMENT_REQUIRED" and exc.status == 402, "Unexpected unpaid receipt guard.")
            db.session.rollback()
        else:
            raise RuntimeError("Direct unpaid bundle receipt bypassed payment.")
        try:
            note_releases.stage_receipt(db.session, source_note_type=bundle,
                user_id=users["outsider"].id, access_granted=True)
        except note_releases.NoteTypeReleaseError as exc:
            _require(exc.code == "PAYMENT_REQUIRED", "Unexpected foreign payment receipt guard.")
            db.session.rollback()
        else:
            raise RuntimeError("Paying the author bundle alone granted unpaid foreign template rights.")

        checkout_payload = post("buyer", f"/api/marketplace/note-types/{bundle.id}/install", statuses=(202,))
        order = db.session.get(PaymentOrder, checkout_payload["order"]["id"])
        order_id = order.id
        _require(order.total_amount_minor == 25000, "Checkout did not charge the full multi-author total.")
        amounts = {(item.product_type, item.product_ref_id): item.line_total_amount_minor for item in order.items if item.line_total_amount_minor > 0}
        _require(amounts == {("note_type", bundle.id): 10000, ("template", foreign.id): 15000},
            "Checkout did not create one own bundle line plus one canonical foreign line.")
        _require(len({(item.product_type, item.product_ref_id) for item in order.items}) == len(order.items),
            "Checkout created duplicate canonical template lines.")
        snap = deepcopy(next(item.product_snapshot_json for item in order.items if item.product_type == "note_type"))
        _require(snap.get("note_type_release_id") == bundle_release.id, "Checkout did not pin the NoteType release.")
        foreign_item = next(item for item in order.items if item.product_type == "template" and item.product_ref_id == foreign.id)
        _require(foreign_item.product_snapshot_json.get("release_id") == foreign_release and foreign_item.product_snapshot_json.get("owner_user_id") == users["designer"].id,
            "Checkout failed to pin foreign template version and original seller.")
        _require(NoteTypeInstall.query.filter_by(source_note_type_id=bundle.id, user_id=users["buyer"].id).count() == 0,
            "Unpaid checkout granted a NoteType receipt.")
        result["checkout_deduplicated_lines_and_pinned_sellers"] = True

        # A pending order must fulfill its original prices and release, not new live values.
        foreign.front_html = "B NEXT RELEASE"
        db.session.commit()
        template_market.update_listing(user_id=users["designer"].id, template_id=foreign.id,
            payload={"marketplace_status": "published", "pricing_mode": "paid", "price_amount_minor": 21000})
        bundle.price_amount_minor = 17000
        db.session.commit()
        ledger_before = UserBalanceTransaction.query.filter_by(payment_order_id=order_id).count()
        _require(ledger_before == 0, "Pending order credited a seller wallet.")
        paid(order_id)
        install = NoteTypeInstall.query.filter_by(source_note_type_id=bundle.id, user_id=users["buyer"].id).one()
        _require(install.applied_release_id == bundle_release.id, "Paid receipt used the latest mutable NoteType release.")
        local_apps = StudyApplication.query.filter_by(note_type_id=install.installed_note_type_id, status_code="ACTIVE").all()
        _require(len(local_apps) == 5, "Bundle receipt lost application occurrences.")
        b_apps = [row for row in local_apps if row.template.source_template_id == foreign.id]
        _require(len(b_apps) == 2 and all(row.template.front_html == "B paid layout {{word}}" for row in b_apps),
            "Bundle receipt did not use the purchased foreign release.")
        b_sub = TemplateSubscription.query.filter_by(user_id=users["buyer"].id, source_template_id=foreign.id).one()
        _require(db.session.get(Template, b_sub.local_template_id).front_html == "B paid layout {{word}}",
            "Canonical foreign subscription used the latest release instead of the purchased release.")
        credits = UserBalanceTransaction.query.filter_by(payment_order_id=order_id).all()
        _require({row.user_id: row.gross_amount_minor for row in credits} == {users["author"].id: 10000, users["designer"].id: 15000},
            "Wallet revenue did not follow the recorded multi-author prices.")
        _require(all(row.net_amount_minor == row.gross_amount_minor for row in credits), "Zero-fee fixture revenue changed unexpectedly.")
        for source_id in [foreign.id] + [template.id for template, _price in own]:
            _require(template_market.existing_access(user_id=users["buyer"].id, template_id=source_id) is not None,
                "Bundle purchase omitted standalone template access rights.")
        own_access = template_market.install(user_id=users["buyer"].id, template_id=own[0][0].id)
        _require(own_access[1] == 200 and own_access[0].get("already_installed"), "Own paid bundled template was charged again standalone.")
        result["webhook_snapshot_fulfillment_and_original_author_revenue"] = True
        result["own_bundle_grants_paid_standalone_template_rights"] = True
        active_before = PaymentEntitlement.query.filter_by(payment_order_id=order_id, status="active").count()
        paid(order_id, expected="duplicate")
        paid(order_id, event_key=f"second-success-{order_id}", expected="already_processed")
        _require(UserBalanceTransaction.query.filter_by(payment_order_id=order_id).count() == 2 and
            PaymentEntitlement.query.filter_by(payment_order_id=order_id, status="active").count() == active_before and
            NoteTypeInstall.query.filter_by(source_note_type_id=bundle.id, user_id=users["buyer"].id).count() == 1,
            "Webhook replay duplicated a wallet credit, entitlement or NoteType receipt.")
        result["webhook_replay_and_second_event_are_idempotent"] = True

        # A zero-priced NoteType may still require paid third-party template rights.
        free_bundle, _ = note_type("A free bundle with B paid", bundle=0, foreign_id=foreign_copy.id)
        post("author", f"/api/marketplace/note-types/{free_bundle.id}/publish", {"publish_status": "published"})
        try:
            note_releases.stage_receipt(db.session, source_note_type=free_bundle, user_id=users["outsider"].id)
        except note_releases.NoteTypeReleaseError as exc:
            _require(exc.code == "PAYMENT_REQUIRED", "Unexpected free bundle third-party payment guard.")
            db.session.rollback()
        else:
            raise RuntimeError("Free bundle silently granted unpaid foreign paid template rights.")
        free_checkout = post("free_bundle_buyer", f"/api/marketplace/note-types/{free_bundle.id}/install", statuses=(202,))
        free_order = db.session.get(PaymentOrder, free_checkout["order"]["id"])
        _require(free_order.total_amount_minor == 21000 and sum(item.line_total_amount_minor for item in free_order.items if item.product_type == "note_type") == 0,
            "Free own bundle omitted the foreign price or charged the author component.")
        _require(free_order.items[0].product_type == "note_type", "Zero-value bundle lost its primary item after reload.")
        free_detail = get("free_bundle_buyer", f"/api/marketplace/note-types/{free_bundle.id}")
        _require(free_detail["pricing_mode"] == "paid" and "Mien phi" not in free_detail.get("badges", []),
            "Paid foreign dependencies were displayed with a free bundle badge.")
        paid_catalog = get("free_bundle_buyer", "/api/marketplace/note-types?pricing_mode=paid&page=1&page_size=20")
        free_catalog = get("free_bundle_buyer", "/api/marketplace/note-types?pricing_mode=free&page=1&page_size=20")
        _require(any(item["id"] == free_bundle.id for item in paid_catalog.get("items", [])) and
            not any(item["id"] == free_bundle.id for item in free_catalog.get("items", [])),
            "Catalog marked a free-author bundle with paid foreign rights as free.")
        result["catalog_price_filters_include_foreign_charges"] = True
        paid_hub = get("free_bundle_buyer", "/api/marketplace/note-types/hub?compact=1&pricing_mode=paid")
        free_hub = get("free_bundle_buyer", "/api/marketplace/note-types/hub?compact=1&pricing_mode=free")
        _require(any(item["id"] == free_bundle.id for item in paid_hub["marketplace"]["items"]) and
            not any(item["id"] == free_bundle.id for item in free_hub["marketplace"]["items"]),
            "Marketplace hub filters still used only the own-bundle price.")
        result["hub_filters_and_badges_include_foreign_prices"] = True
        designer_receipt = post("designer", f"/api/marketplace/note-types/{free_bundle.id}/install", statuses=(201,))
        _require(designer_receipt.get("installed_note_type_id"), "Original template author could not receive a referencing bundle.")
        result["original_template_author_can_receive_referencing_bundle"] = True
        individual_response = api_request("outsider", "post", f"/api/marketplace/note-types/{free_bundle.id}/templates/{foreign.id}/install", json={})
        individual_data = individual_response.get_json() or {}
        _require(individual_response.status_code == 402 or
            (individual_response.status_code == 202 and individual_data.get("payment_required")),
            "Individual template install bypassed its paid price through a free NoteType.")
        result["free_bundle_still_charges_foreign_paid_templates"] = True
        result["individual_template_and_direct_receipt_cannot_bypass_payment"] = True

        # Invalid inline entries must not publish a partial valid listing first.
        rejected, _ = note_type("Atomic invalid mixed-author publication", bundle=0, foreign_id=foreign_copy.id)
        unpublished = attach_template(db.session, note_type_id=rejected.id, owner_user_id=users["author"].id,
            name="Atomic own template", front_html="{{word}}", back_html="{{word}}", shared_css="",
            input_schema=[{"key": "word", "type": "text"}])
        db.session.commit()
        bad_payload = {"publish_status": "published", "template_listings": [
            {"template_id": unpublished.id, "description": "Valid own listing", "primary_category": "General", "pricing_mode": "free", "price_amount_minor": 0},
            {"template_id": foreign.id, "description": "Unauthorized foreign change", "primary_category": "General", "pricing_mode": "free", "price_amount_minor": 0},
        ]}
        rejected_response = api_request("author", "post", f"/api/marketplace/note-types/{rejected.id}/publish", json=bad_payload)
        _require(rejected_response.status_code in (400, 403, 409), "Foreign price override was not rejected.")
        db.session.expire_all()
        unpublished_listing = db.session.get(TemplatePublication, unpublished.id)
        _require((unpublished_listing is None or unpublished_listing.marketplace_status != "published") and
            TemplateRelease.query.filter_by(template_id=unpublished.id).count() == 0 and
            db.session.get(NoteType, rejected.id).current_release_id is None,
            "Failed publication left a partial listing or release.")
        result["foreign_pricing_override_rejected_without_partial_publication"] = True

        # An unavailable original cannot be used to publish a new bundle.
        unlisted, _ = source_template("designer", "B withdrawn layout", 0)
        author_free, _ = template_market.install(user_id=users["author"].id, template_id=unlisted.id)
        unlisted_copy_id = author_free["local_template_id"]
        template_market.update_listing(user_id=users["designer"].id, template_id=unlisted.id,
            payload={"marketplace_status": "private"})
        invalid_note, _ = note_type("Unavailable foreign listing", bundle=0, foreign_id=unlisted_copy_id)
        invalid_response = api_request("author", "post", f"/api/marketplace/note-types/{invalid_note.id}/publish",
            json={"publish_status": "published"})
        _require(invalid_response.status_code in (400, 403, 409), "Unlisted original template was accepted for publication.")
        db.session.expire_all()
        _require(db.session.get(NoteType, invalid_note.id).current_release_id is None,
            "Unavailable foreign original left a complete NoteType publication.")
        result["unavailable_original_reference_cannot_be_published"] = True

        # Free inline listing and invalid/unlisted original reference exercise both paths.
        free_note, _ = note_type("Inline free layout", bundle=0)
        free_owned = attach_template(db.session, note_type_id=free_note.id, owner_user_id=users["author"].id,
            name="Free inline", front_html="{{word}}", back_html="{{word}}", shared_css="",
            input_schema=[{"key": "word", "type": "text"}])
        db.session.commit()
        post("author", f"/api/marketplace/note-types/{free_note.id}/publish", {"publish_status": "published", "template_listings": [
            {"template_id": free_owned.id, "description": "Free standalone layout", "primary_category": "General", "pricing_mode": "free", "price_amount_minor": 0}]})
        free_data = post("outsider", f"/api/marketplace/note-types/{free_note.id}/install", statuses=(201,))
        _require(free_data.get("installed_note_type_id"), "Free inline template bundle could not be received.")
        result["free_inline_listing_and_free_bundle_receipt"] = True

        # The latest release must not gate restoration of an earlier receipt.
        additional, _ = source_template("designer", "New dependency only in v2", 5000)
        additional_purchase = checkout("author", "template", additional.id)
        paid(additional_purchase["order"]["id"])
        additional_sub = TemplateSubscription.query.filter_by(user_id=users["author"].id, source_template_id=additional.id).one()
        alternate = FieldDef(note_type_id=bundle.id, name="Alternate", field_type="text", position=1)
        db.session.add(alternate)
        db.session.flush()
        repeated = StudyApplication.query.filter_by(note_type_id=bundle.id, template_id=foreign_copy.id).order_by(StudyApplication.position).all()
        repeated[1].input_bindings = {"word": alternate.id}
        repeated[1].display_name = "Second mapping"
        db.session.add(StudyApplication(note_type_id=bundle.id, template_id=additional_sub.local_template_id,
            occurrence_key="new-dependency", position=10, input_bindings={"word": word.id}))
        bundle.version = "2.0.0"
        db.session.commit()
        post("author", f"/api/marketplace/note-types/{bundle.id}/publish", {"publish_status": "published"})
        preview_url = f"/api/marketplace/note-types/{bundle.id}/templates/{foreign.id}/preview"
        first = post("buyer", preview_url, {"application_id": repeated[0].id})
        second = post("buyer", preview_url, {"application_id": repeated[1].id})
        _require("Word" in first["front_html"] and "Alternate" in second["front_html"] and
            first["front_html"] != second["front_html"], "Duplicate source preview ignored its occurrence mapping.")
        ambiguous = api_request("buyer", "post", preview_url, json={})
        _require(ambiguous.status_code == 409 and (ambiguous.get_json() or {}).get("error") == "APPLICATION_SELECTION_REQUIRED",
            "An ambiguous preview silently chose the first occurrence.")
        missing = api_request("buyer", "post", preview_url, json={"application_id": "unrelated-application"})
        _require(missing.status_code == 404, "Preview accepted an application outside its published source.")
        result["duplicate_source_preview_selects_exact_published_occurrence"] = True

        template_market.update_listing(user_id=users["designer"].id, template_id=additional.id,
            payload={"marketplace_status": "private"})
        receipt = NoteTypeInstall.query.filter_by(source_note_type_id=bundle.id, user_id=users["buyer"].id).one()
        pinned_release_id = receipt.applied_release_id
        removed_local_id = receipt.installed_note_type_id
        receipt.installed_note_type_id = None
        db.session.flush()
        db.session.execute(sa.delete(NoteType).where(NoteType.id == removed_local_id))
        db.session.commit()
        restored = post("buyer", f"/api/marketplace/note-types/{bundle.id}/install", statuses=(201,))
        _require(restored.get("applied_release_id") == pinned_release_id and pinned_release_id != bundle.current_release_id,
            "Restore used or validated the newer dependency set.")
        restored_apps = StudyApplication.query.filter_by(note_type_id=restored["installed_note_type_id"], status_code="ACTIVE").all()
        _require(len(restored_apps) == 5, "Restored purchase gained an unpaid newer application.")
        result["restore_uses_purchased_release_despite_unavailable_new_dependency"] = True

        # A removed legacy copy cannot be reconstructed from an unknown base.
        db.session.add(NoteTypeInstall(source_note_type_id=bundle.id, user_id=users["outsider"].id,
            installed_note_type_id=None, applied_release_id=None, purchase_amount_minor=0))
        db.session.commit()
        legacy_restore = api_request("outsider", "post", f"/api/marketplace/note-types/{bundle.id}/install", json={})
        _require(legacy_restore.status_code == 409 and (legacy_restore.get_json() or {}).get("error") == "NOTE_TYPE_LEGACY_RELEASE_UNKNOWN",
            "Legacy restore invented a historical release from today's current publication.")
        result["unknown_legacy_restore_never_guesses_current_release"] = True


def run():
    load_dotenv(ROOT / ".env", override=False)
    settings = _connection_settings()
    schema = f"flama_notetype_bundle_probe_{os.getpid()}_{secrets.token_hex(6)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE.fullmatch(schema) or schema == os.getenv("DB_NAME"):
        raise RuntimeError("Probe requires a generated loopback schema distinct from the configured application database.")
    admin = pymysql.connect(**settings)
    created = False
    report = {"status": "FAIL", "configured_database_modified": False}
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (schema,))
            _require(cursor.fetchone() is None, "Generated fixture schema already exists.")
            cursor.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        _qualify(_database_uri(settings, schema), schema, report)
        report["status"] = "PASS"
    except Exception as error:
        report["error_type"] = type(error).__name__
        if isinstance(error, RuntimeError):
            report["contract_error"] = str(error)
        report["error_locations"] = [f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
            for frame in traceback.extract_tb(error.__traceback__)[-6:]]
    finally:
        if created:
            if not PROBE.fullmatch(schema) or schema == os.getenv("DB_NAME"):
                raise RuntimeError("Refusing non-probe cleanup.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{schema}`")
                cursor.execute("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (schema,))
                _require(cursor.fetchone()[0] == 0, "Probe database cleanup failed.")
            report["probe_database_dropped"] = True
        admin.close()
    return report


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
