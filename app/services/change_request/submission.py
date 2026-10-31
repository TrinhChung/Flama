"""Send saved personal changes without exposing draft/sync steps to the user."""

from app.repositories import deck_change_request_repository
from app.services import flashcards_share
from app.services.change_request import lifecycle
from app.services.change_request.helpers import (
    OPEN_REQUEST_STATUSES,
    REQUEST_STATUS_HAS_CONFLICT,
    REQUEST_STATUS_PENDING_REVIEW,
    ChangeRequestError,
    _ensure_requester_access,
    _make_request_title,
    _validate_request_install_binding,
    compute_overlay_fingerprint,
)
from app.services.clone_field_identity_service import lock_clone_overlay_write
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem


def send_saved_changes(
    *, deck_item_id: str, requester_user_id: int, title: str, description: str,
    expected_overlay_fingerprint: str,
) -> dict:
    """Own the transaction; persist conflicts for review instead of losing them.

    Serialize sends with normal overlay edits. A retry returns the already-sent
    request, and a matching draft retains its field-level conflict decisions.
    """
    try:
        install = flashcards_share.get_user_deck_install_for_item(
            user_id=requester_user_id, deck_item_id=deck_item_id,
        )
        if install is None:
            raise ChangeRequestError("Installed clone deck not found.", status=404, error="FIELD_NOT_FOUND")
        install = lock_clone_overlay_write(install)
        deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
        if deck_item is None:
            raise ChangeRequestError("Deck item not found.", status=404, error="FIELD_NOT_FOUND")
        active = deck_change_request_repository.get_active_request_for_install(
            install.id, statuses=OPEN_REQUEST_STATUSES, for_update=True,
        )
        fingerprint = compute_overlay_fingerprint(install)
        if fingerprint != expected_overlay_fingerprint:
            raise ChangeRequestError(
                "Your saved changes changed. Review the refreshed preview before sending.",
                status=409, error="CHANGE_REQUEST_STALE",
            )
        if active is not None:
            _ensure_requester_access(active, user_id=requester_user_id)
            _validate_request_install_binding(active, install, requester_user_id=requester_user_id)
        if active is not None and active.status == REQUEST_STATUS_PENDING_REVIEW:
            if active.overlay_fingerprint != fingerprint:
                raise ChangeRequestError(
                    "A contribution is already pending review.", status=409, error="CHANGE_REQUEST_PENDING",
                )
            request_obj = active
        else:
            if active is not None and active.overlay_fingerprint == fingerprint:
                request_obj = active
                request_obj.title = _make_request_title(
                    deck_item=deck_item, requester_id=requester_user_id, requested_title=title,
                )
                request_obj.description = description or None
            else:
                request_obj = lifecycle._build_or_refresh_draft_for_install(
                    install, deck_item, active, requester_user_id=requester_user_id,
                    title=title, description=description,
                )
            lifecycle.sync_request(request_obj, actor_user_id=requester_user_id)
            if request_obj.status != REQUEST_STATUS_HAS_CONFLICT:
                try:
                    lifecycle.submit_request_for_review(request_obj, actor_user_id=requester_user_id)
                except ChangeRequestError as exc:
                    # Submit checks again. Preserve newly discovered conflicts so
                    # the requester can resolve them on the existing detail screen.
                    if exc.error != "CHANGE_REQUEST_CONFLICTS_UNRESOLVED":
                        raise
        db.session.commit()
        return lifecycle.get_serialized_request_page_for_user(
            request_id=request_obj.id, user_id=requester_user_id,
        )
    except Exception:
        db.session.rollback()
        raise
