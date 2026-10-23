"""Publish authored templates together and reference third-party releases.

The NoteType owns its fields and application mapping, never the foreign HTML
or listing. Every mutation is staged in the caller's transaction.
"""

from app.repositories import note_type_bundle_publication_repository as repository
from app.repositories import template_release_repository as releases
from app.repositories import template_marketplace_repository as market
from app.services.template_release_service import TemplateReleaseError
from models import db
from models.template import Template

TEMPLATE_LISTING_KEYS = {
    "template_id", "description", "primary_category", "pricing_mode", "price_amount_minor",
}


def _fail(code, message, *, status=409, field="template_listings"):
    raise TemplateReleaseError(code, message, status=status, field=field)


def _resolve(session, attached, *, actor_user_id, lock=False):
    source_id = attached.get("source_template_id") or attached["id"]
    source = releases.template(session, source_id, lock=lock)
    if source is None or source.get("origin") == "market_copy" or source.get("source_template_id"):
        _fail("TEMPLATE_REFERENCE_INVALID", "The original authored template is unavailable.")
    own = source["owner_user_id"] == int(actor_user_id)
    if attached["owner_user_id"] != int(actor_user_id) and attached["id"] != source_id:
        _fail("TEMPLATE_ACCESS_DENIED", "This attached template does not belong to the author.", status=403)
    publication = releases.publication(session, source_id, lock=lock) or {}
    listed = bool(publication.get("marketplace_status") == market.LISTED
        and publication.get("current_release_id") and source.get("archived_at") is None)
    release_id = publication.get("current_release_id")
    if not own:
        subscription = repository.subscription(session, user_id=actor_user_id, source_template_id=source_id)
        if subscription is None:
            _fail("TEMPLATE_ACCESS_DENIED", "Receive the original template before referencing it.", status=403)
        if not listed:
            _fail("TEMPLATE_NOT_LISTED", "A referenced third-party template must have a published original listing.")
        from app.services.note_type_bundle_pricing_service import has_template_access
        if not has_template_access(session, user_id=actor_user_id, template_id=source_id):
            _fail("TEMPLATE_ACCESS_DENIED", "The author no longer has access to the referenced template.", status=403)
        release_id = subscription["applied_release_id"]
    release = releases.release(session, release_id, source_id) if release_id else None
    if (not own or listed) and release is None:
        _fail("TEMPLATE_RELEASE_NOT_READY", "A referenced template release is unavailable.")
    return {"attached": attached, "source": source, "publication": publication,
        "release": release, "is_owned": own, "requires_publication": own and not listed}


def references(session, *, note_type_id, actor_user_id, lock=False):
    return [_resolve(session, row, actor_user_id=actor_user_id, lock=lock)
        for row in sorted(repository.attached_templates(session, note_type_id),
            key=lambda row: (row.get("source_template_id") or row["id"], row["id"]))]


def reference_validation_error(session, *, note_type_id, actor_user_id):
    try:
        references(session, note_type_id=note_type_id, actor_user_id=actor_user_id)
    except TemplateReleaseError as exc:
        return str(exc)
    return None


def get_publish_options(*, user_id, note_type_id):
    note_type = repository.note_type(db.session, note_type_id)
    if note_type is None or note_type.user_id != int(user_id):
        _fail("NOTE_TYPE_NOT_FOUND", "Note type not found.", status=404, field=None)
    if repository.is_received_note_type(db.session, note_type.id):
        _fail("NOTE_TYPE_REPUBLISH_FORBIDDEN", "Installed Note Types cannot be published again.", status=403, field=None)
    result = []
    for item in references(db.session, note_type_id=note_type.id, actor_user_id=user_id):
        source, publication = item["source"], item["publication"]
        result.append({
            "template_id": item["attached"]["id"], "source_template_id": source["id"],
            "name": source["name"], "author": {"id": source["owner_user_id"],
                "username": repository.author_username(db.session, source["owner_user_id"])},
            "is_owned": item["is_owned"], "requires_publication": item["requires_publication"],
            "release_id": item["release"]["id"] if item["release"] else None,
            "marketplace_status": publication.get("marketplace_status") or "private",
            "pricing_mode": publication.get("pricing_mode") or "free",
            "price_amount_minor": int(publication.get("price_amount_minor") or 0),
            "description": source.get("description") or "",
            "primary_category": source.get("primary_category") or "",
        })
    return {"note_type_id": note_type.id, "templates": result}


def stage_template_listings(session, *, note_type, actor_user_id, payload):
    """List only unpublished authored attachments using standalone validation."""
    from app.services.template_marketplace_service import stage_listing
    if note_type.user_id != int(actor_user_id):
        _fail("NOTE_TYPE_ACCESS_DENIED", "Only the author can publish this Note Type.", status=403)
    session.flush()
    items = references(session, note_type_id=note_type.id, actor_user_id=actor_user_id, lock=True)
    entries = payload.get("template_listings", [])
    if not isinstance(entries, list):
        _fail("VALIDATION_ERROR", "template_listings must be a list.", status=400)
    allowed = {item["attached"]["id"]: item for item in items if item["requires_publication"]}
    supplied = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - TEMPLATE_LISTING_KEYS:
            _fail("VALIDATION_ERROR", "A template listing contains unsupported properties.", status=400)
        template_id = entry.get("template_id")
        if not isinstance(template_id, str) or template_id not in allowed or template_id in supplied:
            _fail("VALIDATION_ERROR", "Only unpublished templates belonging to the author may be configured once.", status=400)
        if "pricing_mode" not in entry or "price_amount_minor" not in entry:
            _fail("VALIDATION_ERROR", "Set a price for every unpublished template.", status=400)
        if entry["pricing_mode"] not in ("free", "paid"):
            _fail("VALIDATION_ERROR", "Template pricing_mode must be 'free' or 'paid'.", status=400)
        supplied[template_id] = entry
    if set(supplied) != set(allowed):
        _fail("VALIDATION_ERROR", "Set publication details and a price for every unpublished template.", status=400)
    for template_id, item in allowed.items():
        entry, source = supplied[template_id], item["source"]
        metadata = {}
        for key in ("description", "primary_category"):
            if key in entry:
                value = entry[key]
                if not isinstance(value, str) or (key == "primary_category" and len(value.strip()) > 120):
                    _fail("VALIDATION_ERROR", f"Invalid template {key}.", status=400)
                metadata[key] = value.strip() or None
        if metadata:
            releases.update_row(session, Template, [Template.id == source["id"]], metadata)
        stage_listing(session, user_id=actor_user_id, template_id=source["id"], payload={
            "marketplace_status": market.LISTED, "pricing_mode": entry["pricing_mode"],
            "price_amount_minor": entry["price_amount_minor"],
        })
    return references(session, note_type_id=note_type.id, actor_user_id=actor_user_id)
