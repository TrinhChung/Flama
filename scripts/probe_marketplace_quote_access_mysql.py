"""Regress stale template quotes/access against an isolated local MySQL schema.

Only configured schema collation metadata is read. Fixtures and cleanup use one
generated loopback schema; real PayOS clients and external HTTP are forbidden.
"""

from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sys
import threading
from unittest.mock import patch

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

PROBE = re.compile(r"^flama_quote_access_probe_[0-9]+_[a-f0-9]{12}$")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def qualify(uri, schema, report):
    from app import create_app
    from app.api.v1.marketplace.note_types import marketplace_note_types_bp
    from app.routes.payments import payments_bp
    from app.services import note_type_release_service, payment, template_marketplace_service as market
    from app.services import template_release_service
    from app.services.payment.checkout import reconcile_stale_template_quotes
    from app.repositories import note_type_bundle_repository, template_marketplace_repository
    from models import db
    from models.note_type import NoteType
    from models.field_def import FieldDef
    from models.study_application import StudyApplication
    from models.template import Template
    from models.template_subscription import TemplateSubscription
    from models.payment_order import PaymentOrder
    from models.payment_entitlement import PaymentEntitlement
    from models.payment_webhook_event import PaymentWebhookEvent
    from models.user import User
    from models.user_balance_transaction import UserBalanceTransaction

    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri,
        "SECRET_KEY": "isolated-quote-access-probe", "WTF_CSRF_ENABLED": False,
        "PAYMENTS_ENABLED": True, "PAYMENTS_PROVIDER": "payos",
        "PAYMENTS_PAID_INSTALL_REQUIRED": True, "PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED": True,
    }, audit_mode=True)
    app.register_blueprint(marketplace_note_types_bp, url_prefix="/api")
    app.register_blueprint(payments_bp)
    with app.app_context(), ExitStack() as stack:
        stack.callback(db.engine.dispose)
        stack.callback(db.session.remove)
        require(db.engine.url.database == schema, "ORM is not using the generated schema.")
        require(not sa.inspect(db.engine).get_table_names(), "Generated schema is not empty.")
        # Only these domains execute in this probe. Include every FK ancestor;
        # no application database schema or data is reused.
        names = {"users", "user_roles", "templates", "template_versions", "template_publications",
            "template_releases", "template_subscriptions", "note_types", "field_defs",
            "study_applications", "note_type_releases", "note_type_installs", "payment_orders", "payment_order_items",
            "payment_attempts", "payment_entitlements", "payment_webhook_events", "user_balance_transactions", "audit_logs",
            "field_value_identity_definitions", "deck_marketplace_items", "deck_installs"}
        # The optional asynchronous delivery worker is owned by a separate
        # change; exercise this probe with or without its registered model.
        if "template_sync_jobs" in db.metadata.tables:
            names.add("template_sync_jobs")
        while True:
            ancestors = {foreign.column.table.name for name in names for foreign in db.metadata.tables[name].foreign_keys}
            if ancestors <= names:
                break
            names.update(ancestors)
        db.metadata.create_all(db.engine, tables=[db.metadata.tables[name] for name in sorted(names)])
        report["fixture_table_count"] = len(names)
        stack.enter_context(patch("urllib.request.urlopen", side_effect=RuntimeError("External HTTP forbidden.")))
        stack.enter_context(patch("app.services.payos_client.get_payos_client", side_effect=RuntimeError("Live PayOS forbidden.")))
        cancellations = []
        def fake_create(**values):
            code = str(values["provider_order_code"])
            return {"provider_order_code": code, "provider_payment_id": f"probe-{code}",
                "checkout_url": f"https://payments.example.test/{code}", "currency_code": "VND",
                "expires_at": values["expires_at"], "provider_metadata": {}, "raw_response": {}}
        def fake_cancel(**values):
            cancellations.append(values["provider_order_code"])
            return {"status": "CANCELLED"}
        stack.enter_context(patch("app.services.payment.provider.payos_provider.create_checkout_session", side_effect=fake_create))
        stack.enter_context(patch("app.services.payment.provider.payos_provider.get_payment_link_state", return_value={"status": "PENDING"}))
        stack.enter_context(patch("app.services.payment.provider.payos_provider.cancel_checkout_session", side_effect=fake_cancel))
        users = {}
        for label in ("seller", "author", "zero", "independent", "cancel_race", "concurrent", "free_own", "free_download", "restore", "expired", "future", "revoked", "active"):
            user = User(username=f"quote-{label}", email=f"quote-{label}@example.test", custom_platform_fee_percent=0)
            db.session.add(user)
            users[label] = user
        db.session.commit()
        source = Template(owner_user_id=users["seller"].id, name="Paid original", description="Original paid layout",
            primary_category="General", front_html="{{word}}", back_html="{{word}}", shared_css="",
            input_schema=[{"key": "word", "type": "text"}])
        db.session.add(source)
        db.session.commit()
        market.update_listing(user_id=users["seller"].id, template_id=source.id,
            payload={"marketplace_status": "published", "pricing_mode": "paid", "price_amount_minor": 21000})
        author_sub = template_release_service.ensure_subscription(db.session,
            user_id=users["author"].id, source_template_id=source.id, access_granted=True)
        db.session.commit()
        def bundle(name, amount=0):
            nt = NoteType(user_id=users["author"].id, name=name, description=name,
                primary_category="General", publish_status="published", version="1.0.0",
                pricing_mode="paid" if amount else "free", price_amount_minor=amount)
            db.session.add(nt)
            db.session.flush()
            field = FieldDef(note_type_id=nt.id, name="Word", field_type="text", position=0)
            db.session.add(field)
            db.session.flush()
            db.session.add(StudyApplication(note_type_id=nt.id, template_id=author_sub["local_template_id"],
                occurrence_key="one", input_bindings={"word": field.id}))
            db.session.flush()
            note_type_release_service.stage_publication(db.session, note_type=nt, actor_user_id=users["author"].id)
            db.session.commit()
            return nt
        free_bundle = bundle("Zero author component")
        other_bundle = bundle("Independent bundle", amount=10000)
        own_bundle = NoteType(user_id=users["seller"].id, name="Free author package with paid own layout",
            description="Discounted to zero", primary_category="General", publish_status="published", version="1.0.0",
            pricing_mode="free", price_amount_minor=0)
        db.session.add(own_bundle)
        db.session.flush()
        own_field = FieldDef(note_type_id=own_bundle.id, name="Word", field_type="text", position=0)
        db.session.add(own_field)
        db.session.flush()
        db.session.add(StudyApplication(note_type_id=own_bundle.id, template_id=source.id,
            occurrence_key="own", input_bindings={"word": own_field.id}))
        db.session.flush()
        note_type_release_service.stage_publication(db.session, note_type=own_bundle, actor_user_id=users["seller"].id)
        db.session.commit()
        def checkout(label, product_type="template", ref=None):
            return payment.prepare_checkout_for_product(user_id=users[label].id, product_type=product_type,
                product_ref_id=ref or source.id, return_url="https://app.example.test/result", cancel_url="https://app.example.test/cancel")
        def webhook(order_id, suffix="", expected="processed"):
            order = db.session.get(PaymentOrder, order_id)
            attempt = max(order.attempts, key=lambda row: row.created_at)
            event_key = f"probe-{order_id}{suffix}"
            normalized = {"event_key": event_key, "event_type": "payment.succeeded", "provider_code": "payos",
                "provider_order_code": attempt.provider_order_code, "provider_payment_id": attempt.provider_payment_id,
                "payment_reference": attempt.expected_payment_reference, "provider_transaction_ref": event_key,
                "amount_minor": attempt.amount_minor, "currency_code": "VND", "success": True, "status": "00", "raw_payload": {}}
            data, status = payment.process_payment_webhook(normalized, signature_valid=True)
            if data.get("status") == "failed":
                event = PaymentWebhookEvent.query.filter_by(event_key=event_key).one()
                raise RuntimeError(f"Webhook failed: {event.error_message}")
            allowed = {expected} if isinstance(expected, str) else set(expected)
            require(data.get("status") in allowed, f"Webhook expected {expected}, got {status} {data.get('status')}")
            return order
        def credits(label):
            return UserBalanceTransaction.query.filter_by(buyer_user_id=users[label].id, user_id=users["seller"].id).count()

        stale = checkout("zero", "note_type", free_bundle.id)["order"]["id"]
        purchase = checkout("zero")["order"]["id"]
        webhook(purchase)
        require(db.session.get(PaymentOrder, stale).status == "canceled" and cancellations,
            "Standalone purchase did not cancel its independently issued free-bundle quote.")
        from app.services.marketplace_note_type_service import install_shared_note_type
        receipt, status = install_shared_note_type(user_id=users["zero"].id, note_type_id=free_bundle.id)
        require(status == 201 and receipt.get("installed_note_type_id"), "Zero-total bundle could not be received after rights acquisition.")
        webhook(stale, expected="manual_review")
        require(credits("zero") == 1 and db.session.get(PaymentOrder, stale).grant_status != "completed",
            "Late invalidated quote duplicated the seller credit or grant.")
        report["zero_total_path_cancels_stale_link_and_late_payment_has_no_duplicate_revenue"] = True

        # Suppress proactive cleanup once to deterministically reproduce two
        # independently issued payments reaching fulfillment before cleanup.
        first = checkout("independent")["order"]["id"]
        second = checkout("independent", "note_type", other_bundle.id)["order"]["id"]
        with patch("app.services.payment.checkout.reconcile_stale_template_quotes", return_value={"invalidated_order_ids": []}):
            webhook(first)
        webhook(second, expected="manual_review")
        require(credits("independent") == 1 and PaymentEntitlement.query.filter_by(payment_order_id=second, status="active").count() == 0,
            "Independent paid quote race duplicated a license or seller revenue.")
        reviewed = db.session.get(PaymentOrder, second)
        require(any((row.provider_metadata_json or {}).get("duplicate_license_review") for row in reviewed.attempts),
            "Paid duplicate review omitted reconciliation evidence.")
        report["independent_paid_quote_race_is_reviewed_without_grants_or_credits"] = True

        stale = checkout("cancel_race", "note_type", free_bundle.id)["order"]["id"]
        purchase = checkout("cancel_race")["order"]["id"]
        with patch("app.services.payment.provider.payos_provider.cancel_checkout_session", return_value={"status": "PAID"}), patch(
            "app.services.payment.provider.payos_provider.get_payment_link_state", return_value={"status": "PAID", "amount_minor": 21000, "amount_paid_minor": 21000}):
            webhook(purchase)
        require(db.session.get(PaymentOrder, stale).status == "under_review" and credits("cancel_race") == 1,
            "Payment/cancellation race duplicated revenue or lost the paid evidence.")
        try:
            reconcile_stale_template_quotes(user_id=users["cancel_race"].id)
        except payment.PaymentServiceError as exc:
            require(exc.code == "PAYMENT_REQUIRES_REVIEW", "Wrong unresolved paid-race guard.")
        else:
            raise RuntimeError("Unresolved paid stale quote was silently ignored.")
        report["provider_cancel_paid_race_is_preserved_for_review"] = True

        # Both transactions establish their own snapshot before either buyer
        # lock is acquired. Only the winner may credit this template seller.
        first = checkout("concurrent")["order"]["id"]
        second = checkout("concurrent", "note_type", other_bundle.id)["order"]["id"]
        concurrent_user_id = users["concurrent"].id
        db.session.commit()
        from app.repositories import payment_repository
        real_lock = payment_repository.lock_buyer_for_payment
        barrier, local = threading.Barrier(2), threading.local()
        def synchronized_lock(user_id):
            if user_id == concurrent_user_id and not getattr(local, "crossed", False):
                local.crossed = True
                barrier.wait(timeout=15)
            return real_lock(user_id)
        def concurrent_payment(order_id):
            with app.app_context():
                paid_order = webhook(order_id, expected=("processed", "manual_review"))
                return paid_order.status
        with patch("app.services.payment.checkout.reconcile_stale_template_quotes", return_value={"invalidated_order_ids": []}), patch.object(
            payment_repository, "lock_buyer_for_payment", side_effect=synchronized_lock), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(concurrent_payment, order_id) for order_id in (first, second)]
            statuses = sorted(future.result(timeout=30) for future in futures)
        db.session.expire_all()
        require(statuses == ["paid", "under_review"] and credits("concurrent") == 1,
            f"Concurrent snapshot race created duplicate revenue or lost review: {statuses}.")
        report["concurrent_repeatable_read_webhooks_credit_one_template_purchase"] = True

        stale = checkout("free_own")["order"]["id"]
        receipt, status = install_shared_note_type(user_id=users["free_own"].id, note_type_id=own_bundle.id)
        require(status == 201 and receipt.get("installed_note_type_id") and db.session.get(PaymentOrder, stale).status == "canceled",
            "Free author package granted paid own template rights without canceling the standalone quote.")
        existing, status = market.install(user_id=users["free_own"].id, template_id=source.id)
        require(status == 200 and existing.get("already_installed") and credits("free_own") == 0,
            "Free author package charged its own included template later.")
        report["free_author_package_cancels_preexisting_paid_own_template_quote"] = True

        download = Template(owner_user_id=users["seller"].id, name="Repriced free", description="A now-free listing",
            primary_category="General", front_html="{{word}}", back_html="{{word}}", shared_css="",
            input_schema=[{"key": "word", "type": "text"}])
        db.session.add(download)
        db.session.commit()
        market.update_listing(user_id=users["seller"].id, template_id=download.id,
            payload={"marketplace_status": "published", "pricing_mode": "paid", "price_amount_minor": 9000})
        stale = checkout("free_download", ref=download.id)["order"]["id"]
        market.update_listing(user_id=users["seller"].id, template_id=download.id,
            payload={"marketplace_status": "published", "pricing_mode": "free", "price_amount_minor": 0})
        receipt, status = market.install(user_id=users["free_download"].id, template_id=download.id)
        require(status == 201 and receipt.get("local_template_id") and db.session.get(PaymentOrder, stale).status == "canceled",
            "Free standalone receipt did not close the old paid link after acquiring rights.")
        report["free_standalone_receipt_cancels_preexisting_paid_quote"] = True

        purchase = checkout("restore")["order"]["id"]
        webhook(purchase)
        subscription = TemplateSubscription.query.filter_by(user_id=users["restore"].id, source_template_id=source.id).one()
        deleted_id = subscription.local_template_id
        db.session.delete(db.session.get(Template, deleted_id))
        db.session.commit()
        restored = checkout("restore")
        require(not restored.get("payment_required") and restored.get("local_template_id") not in (None, deleted_id) and
            PaymentOrder.query.filter_by(user_id=users["restore"].id).count() == 1,
            "Valid standalone entitlement did not restore a deleted canonical copy without payment.")
        report["valid_standalone_entitlement_restores_deleted_canonical_copy_without_payment"] = True

        # Create actual purchase/receipt first, then exercise changed validity.
        for label in ("expired", "future", "revoked", "active"):
            purchase = checkout(label)["order"]["id"]
            webhook(purchase)
            right = PaymentEntitlement.query.filter_by(user_id=users[label].id, resource_type="template", resource_ref_id=source.id).one()
            if label == "expired":
                right.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
            elif label == "future":
                right.effective_from = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
            elif label == "revoked":
                right.status = "revoked"
            db.session.commit()
            licensed = source.id in note_type_bundle_repository.licensed_template_ids(db.session,
                user_id=users[label].id, template_ids=[source.id])
            require(licensed == (label == "active"), "Bundle license policy disagrees with fixture validity.")
            require(template_marketplace_repository.active_entitlement(db.session, user_id=users[label].id, template_id=source.id) == licensed,
                "Standalone entitlement query disagrees with bundle validity.")
            require((source.id in template_marketplace_repository.purchased(db.session, user_id=users[label].id, template_ids=[source.id])) == licensed,
                "Standalone purchased badge ignores effective/expiry validity.")
            installed, install_status = market.install(user_id=users[label].id, template_id=source.id,
                return_url="https://app.example.test/result", cancel_url="https://app.example.test/cancel")
            require((install_status == 200 and not installed.get("payment_required")) if licensed else
                (install_status == 202 and installed.get("payment_required")),
                f"Standalone {label} access bypassed/duplicated payment: {install_status}.")
        report["standalone_bundle_install_and_catalog_share_validity_policy"] = True


def run():
    load_dotenv(ROOT / ".env", override=False)
    settings = _connection_settings()
    schema = f"flama_quote_access_probe_{os.getpid()}_{secrets.token_hex(6)}"
    require(settings["host"] in {"localhost", "127.0.0.1", "::1"} and PROBE.fullmatch(schema) and schema != os.getenv("DB_NAME"),
        "Probe requires a generated loopback schema distinct from configured application DB.")
    admin = pymysql.connect(**settings)
    created = False
    report = {"status": "FAIL", "configured_database_modified": False}
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (schema,))
            require(cursor.fetchone() is None, "Generated schema already exists.")
            cursor.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        qualify(_database_uri(settings, schema), schema, report)
        report["status"] = "PASS"
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        if isinstance(exc, RuntimeError):
            report["contract_error"] = str(exc)
        elif isinstance(exc, sa.exc.DBAPIError):
            report["driver_error"] = str(exc.orig.args[:2])
        else:
            report["error_message"] = str(exc)
    finally:
        if created:
            require(PROBE.fullmatch(schema) and schema != os.getenv("DB_NAME"), "Refusing non-probe cleanup.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{schema}`")
                cursor.execute("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (schema,))
                require(cursor.fetchone()[0] == 0, "Generated schema cleanup failed.")
            report["probe_database_dropped"] = True
        admin.close()
    return report


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
