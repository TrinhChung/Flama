"""Creator endpoints for managing Deck Access Keys."""

from __future__ import annotations

from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services import deck_access_key_service
from app.utils.permissions import is_admin_user

creator_deck_keys_bp = Blueprint("creator_deck_keys", __name__)


def _parse_iso_datetime(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        # Handle ISO strings (e.g. 2026-12-31T23:59:59.000Z)
        clean = val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:
        return None


@creator_deck_keys_bp.route("/creator/decks/<deck_item_id>/keys", methods=["GET"])
@login_required
def list_deck_keys(deck_item_id: str):
    """List all access keys generated for this deck."""
    try:
        keys = deck_access_key_service.list_deck_access_keys(
            deck_item_id=deck_item_id,
            creator_user_id=current_user.id,
            is_admin=is_admin_user(current_user),
        )
        return jsonify({"keys": keys}), 200
    except PermissionError as exc:
        return jsonify({"error": "FORBIDDEN", "message": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": "NOT_FOUND", "message": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": "SERVER_ERROR", "message": str(exc)}), 500


@creator_deck_keys_bp.route("/creator/decks/<deck_item_id>/keys", methods=["POST"])
@login_required
def create_deck_keys(deck_item_id: str):
    """Create one or more access keys for a deck."""
    payload = request.get_json(silent=True) or {}
    count = int(payload.get("count") or 1)
    label = payload.get("label")
    max_uses_raw = payload.get("max_uses")
    max_uses = int(max_uses_raw) if max_uses_raw not in (None, "", 0) else None
    
    expires_at_raw = payload.get("expires_at")
    expires_at = _parse_iso_datetime(expires_at_raw) if expires_at_raw else None
    
    access_duration_raw = payload.get("access_duration_days")
    access_duration_days = int(access_duration_raw) if access_duration_raw not in (None, "", 0) else None

    try:
        created = deck_access_key_service.create_deck_access_keys(
            deck_item_id=deck_item_id,
            creator_user_id=current_user.id,
            count=count,
            label=label,
            max_uses=max_uses,
            expires_at=expires_at,
            access_duration_days=access_duration_days,
            is_admin=is_admin_user(current_user),
        )
        return (
            jsonify(
                {
                    "success": True,
                    "created_count": len(created),
                    "keys": [
                        {
                            "id": k.id,
                            "key_code": k.key_code,
                            "label": k.label or "",
                            "status": k.status,
                            "max_uses": k.max_uses,
                            "used_count": k.used_count,
                            "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                            "access_duration_days": k.access_duration_days,
                            "created_at": k.created_at.isoformat(),
                        }
                        for k in created
                    ],
                }
            ),
            201,
        )
    except PermissionError as exc:
        return jsonify({"error": "FORBIDDEN", "message": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": "BAD_REQUEST", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "SERVER_ERROR", "message": str(exc)}), 500


@creator_deck_keys_bp.route("/creator/keys/<key_id>", methods=["PATCH"])
@login_required
def update_deck_key(key_id: str):
    """Update or toggle status of an access key (e.g. active / revoked)."""
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    label = payload.get("label")
    expires_at_raw = payload.get("expires_at")
    expires_at = _parse_iso_datetime(expires_at_raw) if expires_at_raw else None

    try:
        updated = deck_access_key_service.update_deck_access_key(
            key_id=key_id,
            creator_user_id=current_user.id,
            status=status,
            label=label,
            expires_at=expires_at,
            is_admin=is_admin_user(current_user),
        )
        return (
            jsonify(
                {
                    "success": True,
                    "key": {
                        "id": updated.id,
                        "key_code": updated.key_code,
                        "label": updated.label or "",
                        "status": updated.status,
                        "max_uses": updated.max_uses,
                        "used_count": updated.used_count,
                        "expires_at": updated.expires_at.isoformat() if updated.expires_at else None,
                        "access_duration_days": updated.access_duration_days,
                        "updated_at": updated.updated_at.isoformat(),
                    },
                }
            ),
            200,
        )
    except PermissionError as exc:
        return jsonify({"error": "FORBIDDEN", "message": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": "BAD_REQUEST", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "SERVER_ERROR", "message": str(exc)}), 500


@creator_deck_keys_bp.route("/creator/keys/<key_id>/redemptions", methods=["GET"])
@login_required
def list_key_redemptions(key_id: str):
    """List student redemptions for a specific key."""
    limit = min(100, max(1, int(request.args.get("limit", 50))))
    offset = max(0, int(request.args.get("offset", 0)))

    try:
        data = deck_access_key_service.list_key_redemptions(
            key_id=key_id,
            creator_user_id=current_user.id,
            limit=limit,
            offset=offset,
            is_admin=is_admin_user(current_user),
        )
        return jsonify(data), 200
    except PermissionError as exc:
        return jsonify({"error": "FORBIDDEN", "message": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": "NOT_FOUND", "message": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": "SERVER_ERROR", "message": str(exc)}), 500
