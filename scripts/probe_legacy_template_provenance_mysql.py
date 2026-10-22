"""Rehearse provenance-only legacy cutover in a generated local MySQL schema.

Reads configured schema collation only; all fixture writes and cleanup target
one generated loopback schema. Never applies the cutover to application data.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import re
import secrets
import sys

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

PROBE = re.compile(r"^flama_legacy_provenance_probe_[0-9]+_[a-f0-9]{12}$")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def qualify(uri, schema):
    from app import create_app
    from app.services import legacy_template_provenance_service as provenance
    from app.repositories.legacy_template_provenance_repository import legacy_license_source_ids
    from app.services import template_library_service, template_marketplace_service
    from app.repositories import template_release_repository
    from app.services.template_release_service import TemplateReleaseError, get_subscription, prepare_update
    from models import db
    from models.deck_install import DeckInstall
    from models.deck_marketplace_item import DeckMarketplaceItem
    from models.field_def import FieldDef
    from models.note import Note
    from models.note_type import NoteType
    from models.note_type_install import NoteTypeInstall
    from models.payment_attempt import PaymentAttempt
    from models.payment_entitlement import PaymentEntitlement
    from models.payment_order import PaymentOrder
    from models.payment_order_item import PaymentOrderItem
    from models.study_application import StudyApplication
    from models.template import Template
    from models.template_subscription import TemplateSubscription
    from scripts.migrations import marketplace_legacy_provenance as tool
    from tests.study_note_fixtures import attach_template, create_note_user
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri,
        "WTF_CSRF_ENABLED": False}, audit_mode=True)
    result = {}
    with app.app_context():
        require(db.engine.url.database == schema, "ORM target is not the generated schema.")
        require(not sa.inspect(db.engine).get_table_names(), "Generated schema is not empty.")
        db.create_all()
        author = create_note_user(db.session, username="legacy-author", email="legacy-author@example.test")
        learner = create_note_user(db.session, username="legacy-receiver", email="legacy-receiver@example.test")
        deck_learner = create_note_user(db.session, username="deck-receiver", email="deck-receiver@example.test")
        foreign_author = create_note_user(db.session, username="foreign-author", email="foreign-author@example.test")
        instant = datetime(2026, 8, 28, 15, 48, 33)
        source_nt = NoteType(user_id=author.id, name="Original schema")
        local_nt = NoteType(user_id=learner.id, name="Legacy schema", created_at=instant)
        db.session.add_all([source_nt, local_nt])
        db.session.flush()
        original = attach_template(db.session, note_type_id=source_nt.id, owner_user_id=author.id,
            name="Original", front_html="ORIGINAL", back_html="BACK", shared_css=".original{}", input_schema=[])
        local = attach_template(db.session, note_type_id=local_nt.id, owner_user_id=learner.id,
            name="Legacy edited", front_html="PERSONAL EDIT", back_html="PRIVATE BACK", shared_css=".mine{}", input_schema=[])
        local.created_at = instant
        original.description, original.primary_category = "Original published template", "Language"
        field = FieldDef(note_type_id=local_nt.id, name="Word", field_type="text", position=0)
        db.session.add(field)
        db.session.flush()
        local_app = db.session.execute(sa.select(StudyApplication).where(StudyApplication.template_id == local.id)).scalar_one()
        local_app.input_bindings = {"word": field.id}
        note = Note(user_id=learner.id, note_type_id=local_nt.id, tags=[])
        note.field_values_by_id = {field.id: "preserved content"}
        db.session.add(note)
        install = NoteTypeInstall(user_id=learner.id, source_note_type_id=source_nt.id,
            installed_note_type_id=local_nt.id, installed_at=instant, applied_release_id=None)
        db.session.add(install)
        db.session.commit()
        template_marketplace_service.update_listing(user_id=author.id, template_id=original.id,
            payload={"marketplace_status": "published", "pricing_mode": "paid", "price_amount_minor": 4000})
        try:
            reference = provenance.legacy_reference(db.session, local.id)
            require(reference["source_template_id"] == original.id, "Legacy original was not identified.")
            require(provenance.is_received_template(db.session, local.id), "Legacy receipt was not protected before cutover.")
            require(not provenance.is_received_template(db.session, original.id), "Original author was incorrectly blocked.")
            for stage in ("before", "after"):
                if stage == "after":
                    reviewed = tool.plan(db.session)
                    require(len(reviewed["entries"]) == 1 and not reviewed["unresolved"], "Unexpected cutover selection.")
                    tool.execute(db.session, reviewed)
                    db.session.rollback()
                    tool.verify(db.session, reviewed, applied=False)
                    tool.execute(db.session, reviewed)
                    db.session.commit()
                    tool.verify(db.session, reviewed)
                    require(tool.execute(db.session, reviewed)["already_applied"], "Apply is not idempotent.")
                    db.session.rollback()
                try:
                    template_marketplace_service.update_listing(user_id=learner.id, template_id=local.id,
                        payload={"marketplace_status": "published", "pricing_mode": "paid", "price_amount_minor": 4000})
                except TemplateReleaseError as exc:
                    require(exc.code == "MARKET_TEMPLATE_REPUBLISH_FORBIDDEN", "Unexpected received publication guard.")
                else:
                    raise RuntimeError(f"Legacy copy could be sold {stage} cutover.")
                dto = get_subscription(user_id=learner.id, template_id=local.id)
                require(dto["legacy_unpinned"] and dto["applied_release"] is None, "A historical release was invented.")
                try:
                    prepare_update(user_id=learner.id, template_id=local.id, payload={"release_id": "unknown"})
                except TemplateReleaseError as exc:
                    require(exc.code == "TEMPLATE_LEGACY_RELEASE_UNKNOWN", "Legacy update failed without explaining the unknown base.")
                else:
                    raise RuntimeError("An unpinned legacy copy accepted an update.")
                require(original.id in legacy_license_source_ids(db.session, user_id=learner.id), "Legacy license was lost.")
                library_dto = template_library_service.serialize_template(db.session.get(Template, local.id))
                require(library_dto["origin"] == "market_copy" and library_dto["legacy_unpinned"], "Library hides received legacy provenance.")
                try:
                    template_library_service.duplicate_template(user_id=learner.id, template_id=local.id, payload={})
                except template_library_service.TemplateLibraryError as exc:
                    require(exc.code == "MARKET_TEMPLATE_REPUBLISH_FORBIDDEN", "Unexpected duplicate guard.")
                else:
                    raise RuntimeError("An inferred legacy copy could escape provenance through duplication.")
                result[f"protected_and_licensed_{stage}_cutover"] = True
            require(db.session.query(TemplateSubscription).count() == 0, "A false historical subscription was created.")
            require(db.session.get(NoteTypeInstall, install.id).applied_release_id is None, "A false NoteType release was assigned.")
            received, status = template_marketplace_service.install(user_id=learner.id, template_id=original.id)
            require(status == 201 and received["local_template_id"] != local.id, "Explicit new canonical receipt reused the unpinned legacy copy.")
            require(db.session.get(Template, local.id).source_version_id is None, "A new canonical receipt fabricated a legacy base.")
            result["explicit_current_receipt_is_separate_from_legacy_content"] = True
            tool.execute(db.session, reviewed, rollback=True)
            db.session.commit()
            tool.verify(db.session, reviewed, applied=False)
            result["rollback_restores_exact_preimages"] = True
            template_library_service.update_template(user_id=learner.id, template_id=local.id,
                payload={"front_html": "ANOTHER PERSONAL EDIT"})
            try:
                tool.execute(db.session, reviewed)
            except ValueError:
                db.session.rollback()
            else:
                raise RuntimeError("A stale plan overwrote a subsequent personal edit.")
            require(db.session.get(Template, local.id).front_html == "ANOTHER PERSONAL EDIT", "Personal edit was overwritten.")
            result["stale_plan_rejected_and_personal_editor_remains_functional"] = True
            own_later = attach_template(db.session, note_type_id=local_nt.id, owner_user_id=learner.id,
                name="Created later", front_html="MINE", back_html="BACK", shared_css="", input_schema=[])
            db.session.commit()
            require(not provenance.is_received_template(db.session, own_later.id), "A later authored attachment was misclassified.")
            duplicate = template_library_service.duplicate_template(user_id=learner.id, template_id=own_later.id, payload={})
            require(duplicate["origin"] == "authored", "A later authored attachment cannot be duplicated.")
            result["later_authored_attachment_remains_owned_and_duplicable"] = True
            deck_item = DeckMarketplaceItem(owner_user_id=author.id, source_note_type_id=source_nt.id,
                title="Owned deck", publish_status="published")
            db.session.add(deck_item)
            db.session.flush()
            deck_install = DeckInstall(deck_item_id=deck_item.id, user_id=deck_learner.id,
                source_note_type_id=source_nt.id, source_owner_user_id=author.id)
            db.session.add(deck_install)
            foreign = attach_template(db.session, note_type_id=source_nt.id, owner_user_id=foreign_author.id,
                name="Later foreign paid", front_html="FOREIGN", back_html="BACK", shared_css="", input_schema=[])
            foreign.description, foreign.primary_category = "A paid foreign source", "Language"
            db.session.commit()
            template_marketplace_service.update_listing(user_id=foreign_author.id, template_id=foreign.id,
                payload={"marketplace_status": "published", "pricing_mode": "paid", "price_amount_minor": 7000})
            require(template_release_repository.source_access(db.session, user_id=deck_learner.id,
                source_template_id=original.id), "A valid deck no longer grants its author's own template.")
            require(not template_release_repository.source_access(db.session, user_id=deck_learner.id,
                source_template_id=foreign.id), "An old deck granted a newly attached foreign paid template.")
            order = PaymentOrder(user_id=deck_learner.id, merchant_order_code="legacy-negative-right", total_amount_minor=4000)
            db.session.add(order)
            db.session.flush()
            item = PaymentOrderItem(order_id=order.id, product_type="template", product_ref_id=original.id,
                title_snapshot="Original", product_snapshot_json={})
            db.session.add(item)
            db.session.flush()
            db.session.add(PaymentEntitlement(user_id=deck_learner.id, payment_order_id=order.id,
                payment_order_item_id=item.id, entitlement_type="shared_template_install", resource_type="template",
                resource_ref_id=original.id, status="revoked"))
            db.session.commit()
            require(not template_release_repository.source_access(db.session, user_id=deck_learner.id,
                source_template_id=original.id), "An old deck overrode an explicitly revoked template right.")
            result["deck_own_template_retained_foreign_and_revoked_rights_blocked"] = True
            result["dry_run_apply_verify_idempotence_and_no_fake_pins"] = True
            return result
        finally:
            db.session.rollback()
            db.session.remove()
            db.engine.dispose()


def main():
    load_dotenv(ROOT / ".env")
    settings = _connection_settings()
    require(settings["host"] in {"127.0.0.1", "localhost", "::1"}, "Only loopback MySQL is permitted.")
    schema = f"flama_legacy_provenance_probe_{os.getpid()}_{secrets.token_hex(6)}"
    require(PROBE.fullmatch(schema), "Generated schema name is unsafe.")
    admin = pymysql.connect(**settings)
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE {collation}")
        result = qualify(_database_uri(settings, schema), schema)
        print(json.dumps({"status": "PASS", **result}, indent=2))
    finally:
        with admin.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{schema}`")
        admin.close()


if __name__ == "__main__":
    main()
