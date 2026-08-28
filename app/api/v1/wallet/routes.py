"""User Wallet and Creator Balance REST API routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services import wallet_service
from app.services.admin_service import coerce_int

wallet_bp = Blueprint("api_v1_wallet", __name__)


@wallet_bp.get("")
@login_required
def get_wallet():
    return jsonify(wallet_service.get_user_wallet_summary(current_user))


@wallet_bp.get("/transactions")
@login_required
def list_transactions():
    page = coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = coerce_int(request.args.get("per_page"), default=10, minimum=1, maximum=100)
    tx_type = str(request.args.get("type") or "").strip() or None

    result = wallet_service.list_user_transactions(
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        transaction_type=tx_type,
    )
    return jsonify(result)
