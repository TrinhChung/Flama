"""Administrative Security Alerts API."""

from __future__ import annotations

from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.api.common import admin_required, error_response
from models import db
from models.admin_security_alert import AdminSecurityAlert

admin_security_alerts_bp = Blueprint("api_v1_admin_security_alerts", __name__)


@admin_security_alerts_bp.get("")
@admin_required
def list_security_alerts():
    query = AdminSecurityAlert.query

    threat_type = (request.args.get("threat_type") or "").strip()
    if threat_type:
        query = query.filter_by(threat_type=threat_type)

    severity = (request.args.get("severity") or "").strip().lower()
    if severity:
        query = query.filter_by(severity=severity)

    resolved_param = request.args.get("is_resolved")
    if resolved_param is not None and resolved_param != "":
        is_resolved = resolved_param.strip().lower() in {"1", "true", "yes"}
        query = query.filter_by(is_resolved=is_resolved)

    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except (TypeError, ValueError):
        page = 1
        per_page = 20

    pagination = query.order_by(AdminSecurityAlert.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return jsonify({
        "items": [item.to_dict() for item in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    })


from app.utils.db import transaction


@admin_security_alerts_bp.patch("/<alert_id>")
@admin_required
def resolve_security_alert(alert_id: str):
    alert = AdminSecurityAlert.query.get(alert_id)
    if alert is None:
        return error_response(
            "NOT_FOUND",
            "Security alert not found.",
            status=404,
        )

    payload = request.get_json(silent=True) or {}
    is_resolved = payload.get("is_resolved", True)

    with transaction():
        alert.is_resolved = bool(is_resolved)
        if alert.is_resolved:
            alert.resolved_by_user_id = current_user.id
            alert.resolved_at = datetime.utcnow()
        else:
            alert.resolved_by_user_id = None
            alert.resolved_at = None

    return jsonify({"item": alert.to_dict()})
