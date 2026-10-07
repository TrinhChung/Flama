"""Orchestration service for Creator Shared Deck Auto-Publish."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services import deck_release_service
from app.services import release_core
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def next_auto_version(current_label: str | None) -> str:
    """Generate the next patch semver version label."""
    return release_core.next_auto_version(current_label)


def get_auto_publish_status(
    *,
    deck_item_id: str,
    user_id: int,
) -> dict[str, Any]:
    """Get the auto-publish configuration and status for a shared deck."""
    item = (
        DeckMarketplaceItem.query.filter_by(
            id=deck_item_id,
            owner_user_id=user_id,
        ).first()
    )
    if item is None:
        raise deck_release_service.DeckReleaseError(
            "ITEM_NOT_FOUND",
            "Shared deck not found or permission denied.",
            status=404,
        )

    current_release = item.current_release
    working_revision = int(item.working_revision or 0)
    current_release_rev = (
        int(current_release.source_working_revision or 0)
        if current_release is not None
        else 0
    )
    has_unreleased_working_edits = working_revision > current_release_rev

    pending_changes_count = 0
    if has_unreleased_working_edits or current_release is None:
        try:
            preview = deck_release_service.preview_release(
                deck_item_id=item.id,
                user_id=user_id,
                limit=1,
            )
            pending_changes_count = int(preview.get("summary", {}).get("change_count", 0))
        except Exception:
            pending_changes_count = 0

    return {
        "deck_item_id": item.id,
        "auto_publish_enabled": bool(item.auto_publish_enabled),
        "last_auto_published_at": (
            item.last_auto_published_at.isoformat()
            if item.last_auto_published_at
            else None
        ),
        "last_auto_publish_error": item.last_auto_publish_error,
        "current_release": deck_release_service.serialize_release(current_release),
        "pending_changes_count": pending_changes_count,
        "working_revision": working_revision,
    }


def update_auto_publish_setting(
    *,
    deck_item_id: str,
    user_id: int,
    auto_publish_enabled: bool,
) -> dict[str, Any]:
    """Enable or disable auto-publish for a shared deck."""
    item = (
        DeckMarketplaceItem.query.filter_by(
            id=deck_item_id,
            owner_user_id=user_id,
        ).first()
    )
    if item is None:
        raise deck_release_service.DeckReleaseError(
            "ITEM_NOT_FOUND",
            "Shared deck not found or permission denied.",
            status=404,
        )

    item.auto_publish_enabled = bool(auto_publish_enabled)
    db.session.flush()

    if item.auto_publish_enabled:
        # If enabled and has unreleased changes, trigger auto-publish immediately
        trigger_auto_publish_for_deck_item(
            deck_item_id=item.id,
            actor_user_id=user_id,
        )

    return get_auto_publish_status(deck_item_id=item.id, user_id=user_id)


def trigger_auto_publish_for_deck_item(
    *,
    deck_item_id: str,
    actor_user_id: int | None = None,
) -> DeckRelease | None:
    """Build and publish an automated release for a deck item if enabled and eligible."""
    item = DeckMarketplaceItem.query.filter_by(id=deck_item_id).first()
    if item is None or not item.auto_publish_enabled:
        return None
    if item.publish_status in {"archived", "private"}:
        return None

    owner_id = int(item.owner_user_id)
    current_release = item.current_release
    working_revision = int(item.working_revision or 0)
    current_release_rev = (
        int(current_release.source_working_revision or 0)
        if current_release is not None
        else -1
    )

    if not release_core.should_auto_publish(
        enabled=item.auto_publish_enabled,
        eligible=item.publish_status not in {"archived", "private"},
        revision=working_revision,
        published_revision=current_release_rev if current_release is not None else None,
    ):
        # No working-tree changes since last release
        return None

    # Compute next version label
    current_label = current_release.version_label if current_release else item.version
    new_version_label = next_auto_version(current_label)
    idempotency_key = f"auto-pub-{item.id}-rev{working_revision}"

    try:
        publish_result = deck_release_service.publish_release(
            deck_item_id=item.id,
            user_id=owner_id,
            version_label=new_version_label,
            changelog="Tự động phát hành bản cập nhật.",
            expected_current_release_id=current_release.id if current_release else None,
            expected_working_revision=working_revision,
            idempotency_key=idempotency_key,
            publish_mode="automatic",
        )
        new_release = publish_result.release
        item.last_auto_published_at = _utcnow()
        item.last_auto_publish_error = None
        db.session.flush()

        # Trigger downstream subscriber auto-updates
        from app.services import deck_install_rebase_service
        deck_install_rebase_service.process_subscriber_auto_updates(
            deck_item_id=item.id,
            release_id=new_release.id,
        )

        return new_release
    except Exception as exc:
        err_msg = str(exc)
        logger.warning(
            "Auto-publish failed for deck item %s (rev %s): %s",
            item.id,
            working_revision,
            err_msg,
        )
        item.last_auto_publish_error = err_msg
        db.session.flush()
        return None
