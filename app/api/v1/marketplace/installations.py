"""Marketplace installation read resources."""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.services import marketplace_hub_service


marketplace_installations_bp = Blueprint(
    "api_v1_marketplace_installations",
    __name__,
)


@marketplace_installations_bp.get("/installed-decks")
@login_required
def installed_decks():
    return jsonify(
        marketplace_hub_service.build_installed_deck_workspace(
            user_id=current_user.id
        )
    )
