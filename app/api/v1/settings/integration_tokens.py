"""User-managed Flama Connect token lifecycle."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common import error_response
from app.services import user_api_token_service
from models import db


integration_tokens_bp = Blueprint("api_v1_integration_tokens", __name__)


def _expiry_from_payload(payload: dict, *, default: int | None = 180) -> int | None:
    return payload.get("expires_in_days", default)


@integration_tokens_bp.get("")
@login_required
def list_integration_tokens():
    return jsonify(
        {
            "items": [
                user_api_token_service.serialize_token(record)
                for record in user_api_token_service.list_tokens(user_id=current_user.id)
            ],
            "policy": {
                "default_expiry_days": 180,
                "allowed_expiry_days": [30, 90, 180, 365],
                "allow_no_expiry": True,
            },
        }
    )


@integration_tokens_bp.post("")
@login_required
def create_integration_token():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "A JSON object is required.", status=400)
    try:
        issued = user_api_token_service.issue_token(
            user_id=current_user.id,
            name=payload.get("name"),
            expires_in_days=_expiry_from_payload(payload),
        )
        db.session.commit()
    except user_api_token_service.TokenInputError as exc:
        db.session.rollback()
        return error_response("VALIDATION_ERROR", str(exc), status=400)
    except Exception:
        db.session.rollback()
        raise
    item = user_api_token_service.serialize_token(issued.record)
    item["token"] = issued.plaintext
    return jsonify({"item": item}), 201


@integration_tokens_bp.delete("/<int:token_id>")
@login_required
def revoke_integration_token(token_id: int):
    if not user_api_token_service.revoke_token(user_id=current_user.id, token_id=token_id):
        return error_response("NOT_FOUND", "Integration token not found.", status=404)
    db.session.commit()
    return "", 204


@integration_tokens_bp.post("/<int:token_id>/rotate")
@login_required
def rotate_integration_token(token_id: int):
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "A JSON object is required.", status=400)
    try:
        issued = user_api_token_service.rotate_token(
            user_id=current_user.id,
            token_id=token_id,
            expires_in_days=_expiry_from_payload(payload),
        )
        if issued is None:
            return error_response("NOT_FOUND", "Integration token not found.", status=404)
        db.session.commit()
    except user_api_token_service.TokenInputError as exc:
        db.session.rollback()
        return error_response("VALIDATION_ERROR", str(exc), status=400)
    except Exception:
        db.session.rollback()
        raise
    item = user_api_token_service.serialize_token(issued.record)
    item["token"] = issued.plaintext
    return jsonify({"item": item}), 201
