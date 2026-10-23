"""Explicitly publish selected legacy local Note Types and their own templates.

This creates NEW publications from today's reviewed definitions. It never
invents historical releases, changes private Note Types, or charges buyers.
Plan first; apply is one transaction and supports a rollback rehearsal.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import sqlalchemy as sa

SCHEMA = "flama-marketplace-bundle-rollout.v1"
VISIBLE = ("published", "unlisted")
TAXONOMY_KEYS = {"domain", "subject", "difficulty_band", "learning_goals", "primary_topics",
    "format_features", "audience", "best_used_for", "framework", "framework_level", "framework_track"}
OVERRIDE_KEYS = TAXONOMY_KEYS | {"description", "primary_category", "preview_text", "preview_image_url"}


def canonical(value):
    return json.loads(json.dumps(value, default=lambda obj: obj.isoformat(), ensure_ascii=False))


def digest(value):
    return hashlib.sha256(json.dumps(canonical(value), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never silently replace a previously reviewed plan or execution receipt.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(canonical(value), stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def identity(session):
    url = session.get_bind().url
    if url.get_backend_name() != "mysql" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Only the configured loopback MySQL database is supported.")
    return {"database": url.database, "server_uuid": session.execute(sa.text("SELECT @@server_uuid")).scalar_one()}


def row(session, model, value, key="id"):
    result = session.execute(sa.select(model.__table__).where(getattr(model, key) == value)).mappings().first()
    return canonical(dict(result)) if result else None


def footprint(session, note_type_id):
    from app.repositories.note_type_bundle_publication_repository import attached_templates
    from models.note_type import NoteType
    from models.field_def import FieldDef
    from models.study_application import StudyApplication
    from models.template_publication import TemplatePublication
    templates = sorted(attached_templates(session, note_type_id), key=lambda item: item["id"])
    return canonical({"note_type": row(session, NoteType, note_type_id), "templates": templates,
        "publications": {item["id"]: row(session, TemplatePublication, item["id"], "template_id") for item in templates},
        "fields": [dict(item) for item in session.execute(sa.select(FieldDef.__table__).where(
            FieldDef.note_type_id == note_type_id).order_by(FieldDef.id)).mappings()],
        "applications": [dict(item) for item in session.execute(sa.select(StudyApplication.__table__).where(
            StudyApplication.note_type_id == note_type_id).order_by(StudyApplication.id)).mappings()]})


def protected_state(session, selected_ids):
    from models.note import Note
    from models.card import Card
    from models.note_type import NoteType
    # Publication must not edit content, occurrences, prices or private listings.
    return {"notes": session.query(Note).count(), "derived_cards": session.query(Card).count(),
        "other_note_types": [dict(item) for item in session.execute(sa.select(NoteType.__table__).where(
            NoteType.id.not_in(selected_ids)).order_by(NoteType.id)).mappings()]}


def plan(session, *, free_unpriced, overrides):
    from app.services.note_type_bundle_publication_service import get_publish_options
    from app.services.share.note_types import validate_note_type_publish_requirements
    from app.services.marketplace_taxonomy_service import normalize_taxonomy_payload
    from models.note_type import NoteType
    notes = session.execute(sa.select(NoteType).where(NoteType.publish_status.in_(VISIBLE),
        NoteType.current_release_id.is_(None)).order_by(NoteType.id)).scalars().all()
    result = {"schema": SCHEMA, "identity": identity(session), "created_at": datetime.now(timezone.utc).isoformat(),
        "meaning": "New explicit publication of current definitions; no historical backfill", "entries": []}
    if set(overrides) - {note.id for note in notes}:
        raise ValueError("Overrides contain a Note Type outside the selected legacy public catalog.")
    planned_template_ids = set()
    for note in notes:
        configured = overrides.get(note.id, {})
        if not isinstance(configured, dict) or set(configured) - OVERRIDE_KEYS:
            raise ValueError("Only publication metadata and taxonomy may be overridden.")
        metadata = dict(note.taxonomy_metadata or {})
        if set(configured) & TAXONOMY_KEYS:
            metadata, taxonomy_error = normalize_taxonomy_payload(
                {**metadata, **{key: value for key, value in configured.items() if key in TAXONOMY_KEYS}}, content_type="note_type")
            if taxonomy_error:
                raise ValueError(taxonomy_error)
        candidate = SimpleNamespace(**{column.name: getattr(note, column.name) for column in NoteType.__table__.columns})
        candidate.field_defs = note.field_defs
        candidate.taxonomy_metadata = metadata
        for key, value in configured.items():
            if key not in TAXONOMY_KEYS:
                setattr(candidate, key, value)
        error = validate_note_type_publish_requirements(candidate)
        if error:
            raise ValueError(f"{note.id}: {error}")
        before = footprint(session, note.id)
        options = get_publish_options(user_id=note.user_id, note_type_id=note.id)
        listings = []
        for template in options["templates"]:
            if not template["requires_publication"]:
                continue
            if template["template_id"] in planned_template_ids:
                continue
            previous = before["publications"][template["template_id"]]
            if previous is None and not free_unpriced:
                raise ValueError("A template has no standalone price. Review it, then explicitly use --free-unpriced-templates.")
            listings.append({"template_id": template["template_id"], "description": template["description"],
                "primary_category": template["primary_category"], "pricing_mode": template["pricing_mode"],
                "price_amount_minor": template["price_amount_minor"]})
            planned_template_ids.add(template["template_id"])
        result["entries"].append({"note_type_id": note.id, "author_user_id": note.user_id, "name": note.name,
            "before": before, "before_digest": digest(before), "template_listings": listings,
            "publish_overrides": {**metadata, **{key: value for key, value in configured.items() if key not in TAXONOMY_KEYS}} if configured else {}})
    result["checksum"] = digest(result)
    return result


def verify(session, reviewed):
    from app.services.note_type_release_service import released_definition
    from app.services.note_type_bundle_pricing_service import pricing_breakdown, require_available
    from models.note_type import NoteType
    from models.note_type_release import NoteTypeRelease
    from models.template_publication import TemplatePublication
    from models.template_release import TemplateRelease
    verified = []
    for entry in reviewed["entries"]:
        note = session.get(NoteType, entry["note_type_id"])
        before = entry["before"]
        if note is None or note.user_id != entry["author_user_id"] or note.publish_status != before["note_type"]["publish_status"]:
            raise ValueError("Note Type ownership/visibility changed.")
        if (note.pricing_mode, note.price_amount_minor) != (before["note_type"]["pricing_mode"], before["note_type"]["price_amount_minor"]):
            raise ValueError("Note Type price changed.")
        definition = released_definition(session, note)
        release = session.get(NoteTypeRelease, note.current_release_id) if note.current_release_id else None
        if not definition["release_available"] or not release or release.manifest_json.get("commerce_version") != "note-type-bundle.v1":
            raise ValueError("Complete bundle publication is missing.")
        fields = release.manifest_json["fields"]
        if {item["id"] for item in fields} != {item["id"] for item in before["fields"]}:
            raise ValueError("Published field identities changed.")
        if {item["application_id"] for item in definition["templates"]} != {item["id"] for item in before["applications"] if item["status_code"] == "ACTIVE"}:
            raise ValueError("Published application identities changed.")
        for item in entry["template_listings"]:
            publication = session.get(TemplatePublication, item["template_id"])
            if not publication or publication.marketplace_status != "published" or not publication.current_release_id:
                raise ValueError("Standalone template listing is missing.")
            if (publication.pricing_mode, publication.price_amount_minor) != (item["pricing_mode"], item["price_amount_minor"]):
                raise ValueError("Standalone template price differs from the reviewed plan.")
            template_release = session.get(TemplateRelease, publication.current_release_id)
            if not template_release or template_release.template_id != item["template_id"]:
                raise ValueError("Standalone template release has incorrect provenance.")
        quote = pricing_breakdown(session, note_type=note, user_id=note.user_id)
        require_available(quote)
        verified.append({"note_type_id": note.id, "name": note.name, "release_id": note.current_release_id,
            "fields": len(fields), "applications": len(definition["templates"])})
    return verified


def apply(session, reviewed, *, dry_run):
    from app.services.share.note_types import apply_note_type_marketplace_payload
    from models.audit_log import AuditLog
    from models.note_type import NoteType
    existing = session.execute(sa.select(AuditLog).where(AuditLog.action == "marketplace.bundle_rollout")).scalars().all()
    if any((item.payload or {}).get("checksum") == reviewed["checksum"] for item in existing):
        return {"already_applied": True, "verified": verify(session, reviewed)}
    protected_before = digest(protected_state(session, [entry["note_type_id"] for entry in reviewed["entries"]]))
    locked = {}
    # Validate every preimage before changing a shared template publication.
    for entry in reviewed["entries"]:
        note = session.execute(sa.select(NoteType).where(NoteType.id == entry["note_type_id"]).with_for_update()).scalar_one()
        if digest(footprint(session, note.id)) != entry["before_digest"]:
            raise ValueError(f"Reviewed definition changed: {note.id}; generate a new plan.")
        locked[note.id] = note
    for entry in reviewed["entries"]:
        note = locked[entry["note_type_id"]]
        error = apply_note_type_marketplace_payload(note, {
            **entry["publish_overrides"], "publish_status": note.publish_status, "template_listings": entry["template_listings"],
        }, allow_set_official=False)
        if error:
            raise ValueError(f"{note.id}: {error}")
        session.add(AuditLog(user_id=entry["author_user_id"], action="marketplace.bundle_rollout",
            payload={"checksum": reviewed["checksum"], "note_type_id": note.id, "new_release_id": note.current_release_id}))
    session.flush()
    if digest(protected_state(session, [entry["note_type_id"] for entry in reviewed["entries"]])) != protected_before:
        raise ValueError("Protected content counts or unrelated Note Types changed.")
    return {"dry_run": dry_run, "verified": verify(session, reviewed)}


def rollback(session, reviewed):
    """Restore mutable publication settings; retain immutable release history."""
    from models.audit_log import AuditLog
    from models.note_type import NoteType
    from models.note_type_release import NoteTypeRelease
    from models.template_publication import TemplatePublication
    from app.services.note_type_release_service import METADATA_KEYS
    verified = verify(session, reviewed)
    audit_rows = session.execute(sa.select(AuditLog).where(AuditLog.action == "marketplace.bundle_rollout")).scalars().all()
    published_ids = {(item.payload or {}).get("note_type_id"): (item.payload or {}).get("new_release_id")
        for item in audit_rows if (item.payload or {}).get("checksum") == reviewed["checksum"]}
    protected_before = digest(protected_state(session, [entry["note_type_id"] for entry in reviewed["entries"]]))
    for entry in reviewed["entries"]:
        session.execute(sa.select(NoteType.id).where(NoteType.id == entry["note_type_id"]).with_for_update()).scalar_one()
        current = footprint(session, entry["note_type_id"])
        before = entry["before"]
        release_id = published_ids.get(entry["note_type_id"])
        release = session.get(NoteTypeRelease, release_id) if release_id else None
        if not release or current["note_type"]["current_release_id"] != release_id:
            raise ValueError("Current publication differs from this rollout; refuse rollback.")
        if {key: current["note_type"][key] for key in METADATA_KEYS} != release.manifest_json["metadata"]:
            raise ValueError("Publication metadata changed after rollout; refuse rollback.")
        pinned = {item["attached_template_id"]: item["template_release_id"] for item in release.manifest_json["applications"]}
        for listing in entry["template_listings"]:
            publication = current["publications"][listing["template_id"]]
            if publication["current_release_id"] != pinned.get(listing["template_id"]):
                raise ValueError("A template has a newer publication; refuse rollback.")
        if current["fields"] != before["fields"] or current["applications"] != before["applications"]:
            raise ValueError("Structure changed after publication; refuse rollback.")
        template_content = ("id", "owner_user_id", "front_html", "back_html", "shared_css", "input_schema", "origin", "source_template_id")
        expected_templates = [{key: item[key] for key in template_content} for item in before["templates"]]
        actual_templates = [{key: item[key] for key in template_content} for item in current["templates"]]
        if actual_templates != expected_templates:
            raise ValueError("Template content or provenance changed after publication; refuse rollback.")
    restored_publications = set()
    for entry in reviewed["entries"]:
        before = entry["before"]
        values = {key: before["note_type"][key] for key in (
            "current_release_id", "taxonomy_metadata", "primary_category", "description", "preview_text", "preview_image_url")}
        session.execute(sa.update(NoteType).where(NoteType.id == entry["note_type_id"]).values(**values)
            .execution_options(synchronize_session=False))
        for listing in entry["template_listings"]:
            template_id = listing["template_id"]
            if template_id in restored_publications:
                continue
            restored_publications.add(template_id)
            previous = before["publications"][template_id]
            keys = ("current_release_id", "auto_publish_enabled", "last_auto_published_at", "last_auto_publish_error",
                "marketplace_status", "pricing_mode", "price_amount_minor", "marketplace_published_at")
            values = {key: previous[key] for key in keys} if previous else {
                "current_release_id": None, "auto_publish_enabled": False, "marketplace_status": "private",
                "pricing_mode": "free", "price_amount_minor": 0, "marketplace_published_at": None,
                "last_auto_published_at": None, "last_auto_publish_error": None}
            for key in ("last_auto_published_at", "marketplace_published_at"):
                if isinstance(values.get(key), str):
                    values[key] = datetime.fromisoformat(values[key])
            session.execute(sa.update(TemplatePublication).where(TemplatePublication.template_id == template_id)
                .values(**values).execution_options(synchronize_session=False))
        session.add(AuditLog(user_id=entry["author_user_id"], action="marketplace.bundle_rollout.rollback",
            payload={"checksum": reviewed["checksum"], "note_type_id": entry["note_type_id"]}))
    session.flush()
    if digest(protected_state(session, [entry["note_type_id"] for entry in reviewed["entries"]])) != protected_before:
        raise ValueError("Protected content counts or unrelated Note Types changed during rollback.")
    session.expire_all()
    for entry in reviewed["entries"]:
        if session.get(NoteType, entry["note_type_id"]).current_release_id != entry["before"]["note_type"]["current_release_id"]:
            raise ValueError("Rollback did not restore the original Note Type pointer.")
    return {"restored_note_types": len(verified), "restored_template_listings": len(restored_publications),
        "immutable_history_retained": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "apply", "verify", "rollback"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--receipt")
    parser.add_argument("--expect-database", required=True)
    parser.add_argument("--free-unpriced-templates", action="store_true")
    parser.add_argument("--metadata-overrides", help="Reviewed JSON object keyed by selected Note Type ID")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    from app import create_app
    from models import db
    app = create_app(audit_mode=True)
    with app.app_context():
        try:
            actual = identity(db.session)
            if actual["database"] != args.expect_database:
                raise ValueError("Configured database does not match --expect-database.")
            if args.mode == "plan":
                overrides = json.loads(Path(args.metadata_overrides).read_text(encoding="utf-8")) if args.metadata_overrides else {}
                reviewed = plan(db.session, free_unpriced=args.free_unpriced_templates, overrides=overrides)
                save(args.plan, reviewed)
                db.session.rollback()
                print(json.dumps({"mode": "plan", "database": actual["database"], "checksum": reviewed["checksum"],
                    "note_types": len(reviewed["entries"]), "inline_templates": sum(len(item["template_listings"]) for item in reviewed["entries"])}))
                return
            reviewed = json.loads(Path(args.plan).read_text(encoding="utf-8"))
            checksum = reviewed.pop("checksum")
            if reviewed.get("schema") != SCHEMA or digest(reviewed) != checksum or reviewed["identity"] != actual:
                raise ValueError("Plan checksum or exact database identity does not match.")
            reviewed["checksum"] = checksum
            if args.mode == "verify":
                result = {"verified": verify(db.session, reviewed)}
                db.session.rollback()
            else:
                if not args.receipt:
                    raise ValueError("Apply/rollback requires a new --receipt path.")
                result = rollback(db.session, reviewed) if args.mode == "rollback" else apply(db.session, reviewed, dry_run=args.dry_run)
                # Persist release IDs before commit; a failed save rolls back.
                save(args.receipt, {"checksum": checksum, "identity": actual, **result})
                if args.dry_run:
                    db.session.rollback()
                else:
                    db.session.commit()
                    db.session.expire_all()
                    if args.mode == "apply":
                        result["verified"] = verify(db.session, reviewed)
            print(json.dumps({"mode": args.mode, "database": actual["database"], **result}, ensure_ascii=True))
        finally:
            db.session.rollback()
            db.session.remove()
            db.engine.dispose()


if __name__ == "__main__":
    main()
