"""Send saved personal changes without exposing draft/sync steps to the user."""

from typing import Any

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
    _validate_install_release_for_contribution,
    _validate_request_install_binding,
    change_signature,
    compute_overlay_fingerprint,
    select_local_changes,
)
from app.services.change_request.preview import _build_local_change_payloads
from app.services.clone_field_identity_service import lock_clone_overlay_write
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem


def send_saved_changes(
    *, deck_item_id: str, requester_user_id: int, title: str, description: str,
    expected_overlay_fingerprint: str, selection: Any = None,
) -> dict:
    """Own the transaction; persist conflicts for review instead of losing them.

    Serialize sends with normal overlay edits. A retry returns the already-sent
    request, and a matching draft retains its field-level conflict decisions.
    ``selection`` picks the notes to send; ``None`` keeps a matching draft's
    own choice (or sends everything when there is no draft).
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
        local_changes = None
        if selection is not None:
            _validate_install_release_for_contribution(install, deck_item)
            payloads, built_fingerprint = _build_local_change_payloads(install)
            if not payloads:
                raise ChangeRequestError(
                    "No local overlay changes were found for this install.",
                    status=400, error="NO_LOCAL_CHANGES",
                )
            chosen = select_local_changes(payloads, selection)
            if not chosen:
                raise ChangeRequestError(
                    "Choose at least one change to send.",
                    status=400, error="NO_SELECTED_CHANGES", field="selection",
                )
            local_changes = (chosen, built_fingerprint)
        matches_active = active is not None and active.overlay_fingerprint == fingerprint and (
            local_changes is None
            or {change_signature(change) for change in local_changes[0]}
            == {change_signature(item) for item in active.items}
        )
        if active is not None and active.status == REQUEST_STATUS_PENDING_REVIEW:
            if not matches_active:
                raise ChangeRequestError(
                    "A contribution is already pending review.", status=409, error="CHANGE_REQUEST_PENDING",
                )
            request_obj = active
        else:
            if matches_active:
                request_obj = active
                request_obj.title = _make_request_title(
                    deck_item=deck_item, requester_id=requester_user_id, requested_title=title,
                )
                request_obj.description = description or None
            else:
                request_obj = lifecycle._build_or_refresh_draft_for_install(
                    install, deck_item, active, requester_user_id=requester_user_id,
                    title=title, description=description, local_changes=local_changes,
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
