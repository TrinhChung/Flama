"""Marketplace endpoints for redeeming Deck Access Keys."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services import deck_access_key_service

marketplace_deck_keys_bp = Blueprint("marketplace_deck_keys", __name__)


@marketplace_deck_keys_bp.route("/marketplace/keys/validate", methods=["POST"])
def validate_deck_key():
    """Check if an access key is valid and return preview details without redeeming."""
    payload = request.get_json(silent=True) or {}
    key_code = payload.get("key_code") or payload.get("code") or ""
    
    user_id = current_user.id if getattr(current_user, "is_authenticated", False) else None
    result = deck_access_key_service.validate_key_for_redemption(key_code, user_id=user_id)
    
    status_code = 200 if result.get("valid") else 400
    return jsonify(result), status_code


@marketplace_deck_keys_bp.route("/marketplace/keys/redeem", methods=["POST"])
@login_required
def redeem_deck_key():
    """Redeem an access key and install the shared deck into the user's library."""
    payload = request.get_json(silent=True) or {}
    key_code = payload.get("key_code") or payload.get("code") or ""

    try:
        res = deck_access_key_service.redeem_deck_access_key(
            key_code=key_code,
            user_id=current_user.id,
        )
        return jsonify(res), 200
    except ValueError as exc:
        return jsonify({"error": "BAD_REQUEST", "message": str(exc)}), 400
    except PermissionError as exc:
        return jsonify({"error": "FORBIDDEN", "message": str(exc)}), 403
    except Exception as exc:
        return jsonify({"error": "SERVER_ERROR", "message": str(exc)}), 500
