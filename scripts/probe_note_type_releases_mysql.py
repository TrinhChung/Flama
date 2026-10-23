"""Exercise NoteType release DDL and receipt isolation in disposable local MySQL.

Only configured schema collation metadata is read; no application rows are read
or modified. All fixtures, DDL and cleanup use one generated loopback schema.
"""

from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
from types import SimpleNamespace
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

PROBE = re.compile(r"^flama_notetype_release_probe_[0-9]+_[a-f0-9]{12}$")


def _require(condition, description):
    if not condition:
        raise RuntimeError(description)


def _qualify(uri, schema):
    from app import create_app
    from models import db
    from models.field_def import FieldDef
    from models.note_type import NoteType
    from models.note_type_install import NoteTypeInstall
    from models.note_type_release import NoteTypeRelease
    from models.study_application import StudyApplication
    from models.template import Template
    from models.template_subscription import TemplateSubscription
    from app.services import note_type_release_service as service
    from app.services import marketplace_note_type_service as market
    from app.services.marketplace_query_service import serialize_note_type_marketplace_card
    from app.services.payment.fulfillment import _fulfill_order_item
    from app.services.payment.checkout import _validate_note_type_for_checkout
    from app.services.payment.base import PaymentServiceError
    from tests.study_note_fixtures import attach_template, create_note_user
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri,
        "WTF_CSRF_ENABLED": False}, audit_mode=True)
    from app.api.v1.marketplace.note_types import marketplace_note_types_bp
    from app.routes.payments import payments_bp
    app.register_blueprint(marketplace_note_types_bp, url_prefix="/api")
    app.register_blueprint(payments_bp)
    result = {}
    with app.app_context():
        _require(db.engine.url.database == schema, "ORM database is not the generated fixture schema.")
        _require(not sa.inspect(db.engine).get_table_names(), "Fixture schema was not empty.")
        db.create_all()
        with db.engine.connect() as connection:
            parent_collation = sa.inspect(connection).get_table_options("note_types").get("mysql_collate")
            different_default = "utf8mb4_bin" if parent_collation != "utf8mb4_bin" else "utf8mb4_unicode_ci"
            connection.execute(sa.text(f"ALTER DATABASE `{schema}` COLLATE {different_default}"))
            connection.commit()
        migration = importlib.import_module("migrations.versions.20261020_000070_note_type_releases")
        with db.engine.connect() as connection:
            def migrate(step):
                with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
                    getattr(migration, step)()
                connection.commit()
            # Rehearse empty expansion rollback then applying twice on MySQL.
            migrate("downgrade")
            migrate("upgrade")
            migrate("upgrade")
            _require(sa.inspect(connection).has_table("note_type_releases"), "Release expansion failed.")
            _require(sa.inspect(connection).get_table_options("note_type_releases").get("mysql_collate") == parent_collation,
                "Release table collation did not follow the existing parent table.")
            result["mysql_migration_upgrade_repeatable_and_empty_rollback"] = True
            result["migration_matches_parent_when_database_default_collation_differs"] = True
        author = create_note_user(db.session, username="release-author", email="release-author@example.test")
        free_user = create_note_user(db.session, username="release-free", email="release-free@example.test")
        paid_user = create_note_user(db.session, username="release-paid", email="release-paid@example.test")
        legacy_user = create_note_user(db.session, username="release-legacy", email="release-legacy@example.test")
        concurrent_user = create_note_user(db.session, username="release-concurrent", email="release-concurrent@example.test")
        source = NoteType(user_id=author.id, name="Published schema", description="Published description",
            publish_status="published", version="1.0.0", pricing_mode="free")
        legacy = NoteType(user_id=author.id, name="Legacy schema", publish_status="published")
        db.session.add_all([source, legacy])
        db.session.flush()
        word = FieldDef(note_type_id=source.id, name="Word", field_type="text", required=True,
            identity_role="primary", position=0)
        db.session.add(word)
        db.session.flush()
        template = attach_template(db.session, note_type_id=source.id, owner_user_id=author.id,
            name="Shared card", front_html="PUBLISHED {{Word}}", back_html="BACK", shared_css=".card{}",
            input_schema=[{"key": "word", "type": "text"}])
        app1 = db.session.execute(sa.select(StudyApplication).where(StudyApplication.template_id == template.id)).scalar_one()
        app1.input_bindings = {"word": word.id}
        db.session.add(StudyApplication(note_type_id=source.id, template_id=template.id, occurrence_key="second",
            source_ord=4, position=1, input_bindings={"word": word.id}, display_name="Second card"))
        db.session.commit()
        try:
            service.stage_publication(db.session, note_type=source, actor_user_id=free_user.id)
        except service.NoteTypeReleaseError as error:
            _require(error.code == "NOTE_TYPE_ACCESS_DENIED" and error.status == 403, "Unexpected publication ownership guard.")
            db.session.rollback()
        else:
            raise RuntimeError("A reader could publish the author's Note Type release.")
        result["reader_cannot_publish_author_release"] = True
        release = service.stage_publication(db.session, note_type=source, actor_user_id=author.id)
        first_id = release.id
        db.session.commit()
        _require(service.stage_publication(db.session, note_type=source, actor_user_id=author.id).id == first_id,
            "Unchanged publication did not reuse the release.")
        db.session.commit()
        template.front_html = "UNPUBLISHED DRAFT"
        source.name = "Draft schema name"
        db.session.add(FieldDef(note_type_id=source.id, name="DraftOnly", field_type="array", position=1))
        app1.input_bindings = {"word": None}
        db.session.commit()
        card = serialize_note_type_marketplace_card(source)
        _require(card["name"] == "Published schema" and card["version"] == "1.0.0", "Draft metadata leaked.")
        _require([row["name"] for row in card["field_defs"]] == ["Word"], "Draft schema leaked.")
        _require(len(card["templates"]) == 2 and all(row["front_html"] == "PUBLISHED {{Word}}" for row in card["templates"]),
            "Draft template content or application topology leaked.")
        _require(all(row["input_bindings"] == {"word": word.id} for row in card["templates"]), "Draft mapping leaked.")
        result["immutable_complete_schema_mapping_and_preview_payload"] = True
        try:
            service.stage_publication(db.session, note_type=source, actor_user_id=author.id)
        except service.NoteTypeReleaseError as error:
            _require(error.code == "NOTE_TYPE_VERSION_CONFLICT", "Unexpected version conflict.")
            db.session.rollback()
        else:
            raise RuntimeError("Changed schema reused an existing version label.")
        result["version_label_cannot_change_manifest"] = True
        free_response, status = market.install_shared_note_type(user_id=free_user.id, note_type_id=source.id)
        _require(status == 201, "Free receipt did not complete.")
        free_install = NoteTypeInstall.query.filter_by(source_note_type_id=source.id, user_id=free_user.id).one()
        source.pricing_mode = "paid"
        source.price_amount_minor = 45000
        db.session.commit()
        checkout = _validate_note_type_for_checkout(source, user_id=paid_user.id)
        _require(checkout["product_snapshot"]["note_type_release_id"] == first_id,
            "Checkout did not pin the offered complete release.")
        source.version = "2.0.0"
        service.stage_publication(db.session, note_type=source, actor_user_id=author.id)
        db.session.commit()
        grant = _fulfill_order_item(order=SimpleNamespace(user_id=paid_user.id),
            order_item=SimpleNamespace(product_type="note_type", product_ref_id=source.id,
                product_snapshot_json=checkout["product_snapshot"],
                line_total_amount_minor=45000, unit_amount_minor=45000), attempt=None, now=datetime.now(timezone.utc).replace(tzinfo=None))
        db.session.commit()
        paid_install = db.session.get(NoteTypeInstall, grant["note_type_install_id"])
        for install in (free_install, paid_install):
            local = db.session.get(NoteType, install.installed_note_type_id)
            _require(install.applied_release_id == first_id and local.name == "Published schema", "Receipt used draft metadata/release.")
            _require([field.name for field in local.field_defs] == ["Word"], "Receipt used draft fields.")
            apps = StudyApplication.query.filter_by(note_type_id=local.id, status_code="ACTIVE").all()
            _require(len(apps) == 2 and {row.occurrence_key for row in apps} == {"compat", "second"}, "Receipt lost an occurrence.")
            _require(all(row.template.front_html == "PUBLISHED {{Word}}" for row in apps), "Receipt copied a template draft.")
            _require(all(row.input_bindings == {"word": local.field_defs[0].id} for row in apps), "Receipt used mutable source bindings.")
            _require(TemplateSubscription.query.filter_by(user_id=install.user_id, source_template_id=template.id).count() == 1,
                "Receipt did not create one canonical subscription.")
        result["free_paid_receipt_parity_and_occurrence_preservation"] = True
        result["checkout_pins_release_across_later_author_publication"] = True
        prior_install_count = NoteTypeInstall.query.filter_by(source_note_type_id=source.id).count()
        prior_source_count = source.install_count
        try:
            _fulfill_order_item(order=SimpleNamespace(user_id=legacy_user.id),
                order_item=SimpleNamespace(product_type="note_type", product_ref_id=source.id,
                    product_snapshot_json={"version": "1.0.0"},
                    line_total_amount_minor=45000, unit_amount_minor=45000), attempt=None, now=datetime.now(timezone.utc).replace(tzinfo=None))
        except PaymentServiceError as error:
            _require(error.code == "PURCHASED_NOTE_TYPE_RELEASE_UNAVAILABLE" and error.status == 409,
                "Unexpected legacy paid-order recovery diagnostic.")
        else:
            raise RuntimeError("Legacy paid order silently substituted the current release.")
        _require(NoteTypeInstall.query.filter_by(source_note_type_id=source.id).count() == prior_install_count and
            source.install_count == prior_source_count, "Legacy paid order changed a receipt or counter.")
        result["legacy_paid_order_requires_recovery_without_substituting_release_or_grant"] = True
        canonical = TemplateSubscription.query.filter_by(user_id=paid_user.id, source_template_id=template.id).one()
        db.session.get(Template, canonical.local_template_id).front_html = "PERSONAL CANONICAL CONTENT"
        db.session.commit()
        paid_apps = StudyApplication.query.filter_by(note_type_id=paid_install.installed_note_type_id).all()
        _require(all(row.template.front_html == "PUBLISHED {{Word}}" for row in paid_apps),
            "A canonical edit changed an already received NoteType release.")
        result["canonical_template_edits_do_not_change_complete_notetype_receipt"] = True
        original = (paid_install.id, paid_install.purchase_amount_minor, paid_install.purchased_at, paid_install.installed_at)
        old_local_id = paid_install.installed_note_type_id
        db.session.delete(db.session.get(NoteType, old_local_id))
        db.session.commit()
        db.session.expire_all()
        _require(paid_install.installed_note_type_id is None, "MySQL SET NULL did not clear deleted local target.")
        before_count = db.session.get(NoteType, source.id).install_count
        restored, status = market.install_shared_note_type(user_id=paid_user.id, note_type_id=source.id)
        _require(status == 201 and restored["installed_note_type_id"] != old_local_id, "Paid reinstall did not restore without checkout.")
        _require((paid_install.id, paid_install.purchase_amount_minor, paid_install.purchased_at, paid_install.installed_at) == original,
            "Reinstall changed original purchase/provenance.")
        _require(db.session.get(NoteType, source.id).install_count == before_count, "Reinstall double-counted receipt.")
        _require(paid_install.applied_release_id == first_id, "Reinstall did not retain original release.")
        result["deleted_target_restores_original_release_without_payment_or_counter_duplication"] = True
        deck_local = NoteType(user_id=legacy_user.id, name="Existing deck schema")
        db.session.add(deck_local)
        db.session.flush()
        deck_install = NoteTypeInstall(source_note_type_id=source.id, user_id=legacy_user.id,
            installed_note_type_id=deck_local.id)
        db.session.add(deck_install)
        db.session.commit()
        retained, created = service.stage_receipt(db.session, source_note_type=source, user_id=legacy_user.id)
        _require(not created and retained.id == deck_install.id and retained.applied_release_id is None and
            retained.installed_note_type_id == deck_local.id and deck_local.name == "Existing deck schema",
            "Receipt rewrote an existing unversioned deck installation.")
        result["existing_deck_schema_retained_without_inventing_release"] = True
        snapshot = serialize_note_type_marketplace_card(legacy)
        _require(not snapshot["release_available"] and snapshot["requires_author_republish"] and
            snapshot["field_defs"] == snapshot["templates"] == [], "Legacy publication falsely claims a release.")
        try:
            market.install_shared_note_type(user_id=legacy_user.id, note_type_id=legacy.id)
        except market.MarketplaceNoteTypeError as error:
            _require(error.error == "NOTE_TYPE_RELEASE_NOT_READY" and error.status == 409, "Unexpected legacy install response.")
        else:
            raise RuntimeError("Reader silently published or received a legacy draft.")
        result["legacy_requires_explicit_author_publication"] = True
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(legacy_user.id)
            session["_fresh"] = True
        legacy_response = client.post(f"/api/marketplace/note-types/{legacy.id}/install")
        _require(legacy_response.status_code == 409 and
            legacy_response.get_json()["error"] == "NOTE_TYPE_RELEASE_NOT_READY" and
            "author" in legacy_response.get_json()["message"].lower(), "Legacy REST error was not actionable.")
        detail_response = client.get(f"/api/marketplace/note-types/{source.id}")
        _require(detail_response.status_code == 200 and detail_response.get_json()["release_available"],
            "Release detail endpoint did not expose the immutable definition.")
        preview_response = client.post(f"/api/marketplace/note-types/{source.id}/templates/{template.id}/preview",
            json={"application_id": app1.id})
        _require(preview_response.status_code == 200, "Released preview endpoint failed.")
        result["rest_detail_preview_and_actionable_legacy_conflict"] = True
        legacy.pricing_mode, legacy.price_amount_minor = "paid", 1000
        legacy_local = NoteType(user_id=free_user.id, name="Prior legacy receipt")
        db.session.add(legacy_local)
        db.session.flush()
        db.session.add(NoteTypeInstall(source_note_type_id=legacy.id, user_id=free_user.id,
            installed_note_type_id=legacy_local.id))
        db.session.commit()
        legacy_checkout = _validate_note_type_for_checkout(legacy, user_id=free_user.id)
        _require(legacy_checkout["existing_access"]["installed_note_type_id"] == legacy_local.id and
            legacy_checkout["existing_access"]["legacy_installation"], "Checkout broke an existing legacy receipt.")
        result["existing_legacy_access_does_not_require_republication"] = True
        # Begin a repeatable-read snapshot before another receipt commits. A
        # user-row lock alone does not refresh subsequent consistent reads.
        with Session(db.engine) as stale_reader:
            stale_source = stale_reader.get(NoteType, source.id)
            _require(stale_reader.execute(sa.select(NoteTypeInstall).where(
                NoteTypeInstall.source_note_type_id == source.id,
                NoteTypeInstall.user_id == concurrent_user.id)).scalar_one_or_none() is None,
                "Concurrent receipt fixture already existed.")
            first_receipt, created = service.stage_receipt(db.session, source_note_type=source,
                user_id=concurrent_user.id, access_granted=True)
            db.session.commit()
            second_receipt, second_created = service.stage_receipt(stale_reader, source_note_type=stale_source,
                user_id=concurrent_user.id, access_granted=True)
            _require(created and not second_created and first_receipt.id == second_receipt.id,
                "Serialized receipt read a stale snapshot and attempted a duplicate installation.")
            stale_reader.commit()
        result["serialized_receipt_uses_current_read_after_prior_repeatable_read_snapshot"] = True
        db.session.rollback()
        with db.engine.connect() as connection:
            try:
                with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
                    migration.downgrade()
            except RuntimeError:
                result["populated_release_downgrade_refused"] = True
            else:
                raise RuntimeError("Populated release downgrade was not refused.")
        db.session.remove()
        db.engine.dispose()
    return result


def run():
    load_dotenv(ROOT / ".env", override=False)
    settings = _connection_settings()
    schema = f"flama_notetype_release_probe_{os.getpid()}_{secrets.token_hex(6)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE.fullmatch(schema) or schema == os.getenv("DB_NAME"):
        raise RuntimeError("Probe requires a generated loopback schema distinct from the configured application database.")
    admin = pymysql.connect(**settings)
    created = False
    report = {"status": "FAIL", "configured_database_modified": False}
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (schema,))
            if cursor.fetchone():
                raise RuntimeError("Generated fixture schema already exists.")
            cursor.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        report.update(_qualify(_database_uri(settings, schema), schema))
        report["status"] = "PASS"
    except Exception as error:
        report["error_type"] = type(error).__name__
        if isinstance(error, sa.exc.DBAPIError):
            report["driver_error"] = str(error.orig.args[:2])
        if isinstance(error, RuntimeError):
            report["contract_error"] = str(error)
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
