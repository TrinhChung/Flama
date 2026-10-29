"""Owner-operated publication of every listing sharing a NoteType.

Each listing keeps its existing atomic publish contract. A batch reports partial
completion explicitly; it never rolls back an earlier committed publication.
"""
import hashlib

from sqlalchemy import select

from app.services import deck_release_service as releases
from app.services.note_base_context import published_base_enabled
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.note_type import NoteType


def publish_note_type_listings(*, user_id, note_type_id, version_label, batch_key,
                               changelog=None, apply=False):
    if not published_base_enabled():
        raise releases.DeckReleaseError("FEATURE_UNAVAILABLE", "Published Base is not active.", status=404)
    version_label = releases._normalize_version_label(version_label)
    batch_key = releases._normalize_idempotency_key(batch_key)
    owned = db.session.execute(select(NoteType.id).where(NoteType.id == note_type_id,
        NoteType.user_id == user_id)).scalar_one_or_none()
    if owned is None:
        raise releases.DeckReleaseError("NOTE_TYPE_NOT_FOUND", "Note type not found.", status=404)
    ids = list(db.session.execute(select(DeckMarketplaceItem.id).where(
        DeckMarketplaceItem.owner_user_id == user_id,
        DeckMarketplaceItem.source_note_type_id == note_type_id).order_by(DeckMarketplaceItem.id)).scalars())
    plans = [releases.preview_release(deck_item_id=identity, user_id=user_id) for identity in ids]
    # Release the preview snapshot before each publisher takes current locks.
    db.session.rollback()
    report = {"apply": bool(apply), "note_type_id": note_type_id, "items": [], "complete": True}
    for plan in plans:
        row = {"deck_item_id": plan["deck_item_id"], "title": plan["deck_title"],
            "summary": plan["summary"], "status": "preview"}
        report["items"].append(row)
        if not apply:
            continue
        try:
            key = hashlib.sha256(f"{batch_key}:{plan['deck_item_id']}".encode()).hexdigest()
            existing = db.session.execute(select(DeckRelease).where(
                DeckRelease.deck_item_id == plan["deck_item_id"], DeckRelease.idempotency_key == key)).scalar_one_or_none()
            head = existing.parent_release_id if existing else (plan["base_release"] or {}).get("id")
            revision = existing.source_working_revision if existing else plan["working_revision"]
            result = releases.publish_release_and_commit(deck_item_id=plan["deck_item_id"], user_id=user_id,
                version_label=version_label, changelog=changelog,
                expected_current_release_id=head, expected_working_revision=revision, idempotency_key=key)
            row.update(status="replayed" if result.replayed else "published", release_id=result.release.id)
        except releases.DeckReleaseError as exc:
            if exc.error == "NO_RELEASE_CHANGES":
                row["status"] = "unchanged"
                continue
            row.update(status="failed", error=exc.error, message=exc.message)
            report["complete"] = False
            break
    return report
