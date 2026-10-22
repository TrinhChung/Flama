"""Explicit publications for tests that sell or receive complete Note Types."""

from app.services.note_type_bundle_publication_service import references, stage_template_listings
from app.services.note_type_release_service import stage_publication


def stage_template_listings_for_note_type(session, note_type):
    items = references(session, note_type_id=note_type.id, actor_user_id=note_type.user_id)
    stage_template_listings(session, note_type=note_type, actor_user_id=note_type.user_id,
        payload={"template_listings": [
            {"template_id": item["attached"]["id"], "pricing_mode": "free", "price_amount_minor": 0,
             "description": item["source"].get("description") or "Published test template",
             "primary_category": item["source"].get("primary_category") or "General"}
            for item in items if item["requires_publication"]]})


def stage_note_type_release(session, note_type):
    stage_template_listings_for_note_type(session, note_type)
    return stage_publication(session, note_type=note_type, actor_user_id=note_type.user_id)
