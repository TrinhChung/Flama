"""Security incident processing service.

Handles attack notifications forwarded by media edge services or internal microservices,
creates administrative security alerts and audit trails. It never disables accounts or
revokes tokens: the worker's detectors also fire on ordinary uploads (very large photos,
an SVG file), so an automatic ban would lock out legitimate users. Admins decide.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from models import db
from models.admin_security_alert import AdminSecurityAlert
from models.audit_log import AuditLog
from models.model_uuid import uuid_str
from models.user import User

logger = logging.getLogger(__name__)


class SecurityIncidentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def handle_security_incident(payload: dict[str, Any]) -> dict[str, Any]:
    """Record a verified incident reported by an internal worker service.

    Creates an AdminSecurityAlert and, when the incident names an existing user, a
    ``security.incident_reported`` audit entry for that user. Accounts and tokens
    are left unchanged.
    """
    if not isinstance(payload, dict):
        raise SecurityIncidentError("Invalid incident payload: expected JSON object", status_code=400)

    raw_user_id = payload.get("user_id")
    user_id: int | None = None
    if raw_user_id is not None:
        try:
            user_id = int(raw_user_id)
        except (ValueError, TypeError):
            user_id = None

    incident_type = str(payload.get("incident_type") or "UNKNOWN_ATTACK").strip()
    detail = str(payload.get("detail") or "Suspicious activity detected").strip()
    client_ip = str(payload.get("client_ip") or "").strip() or None

    alert_id = uuid_str()
    threat_type = incident_type.lower()
    alert_message = f"Malicious media payload detected: [{incident_type}] {detail}"

    alert = AdminSecurityAlert(
        id=alert_id,
        user_id=user_id,
        severity="critical",
        threat_type=threat_type,
        source_ip=client_ip,
        source_url="media.flama.vn",
        message=alert_message,
        details={
            "raw_incident": payload,
            "detected_at": datetime.utcnow().isoformat(),
        },
        is_resolved=False,
    )
    db.session.add(alert)

    user = db.session.get(User, user_id) if user_id else None
    if user is not None:
        db.session.add(AuditLog(
            user_id=user.id,
            action="security.incident_reported",
            payload={
                "incident_type": incident_type,
                "detail": detail,
                "client_ip": client_ip,
                "alert_id": alert_id,
            },
        ))
        logger.warning(
            "[SECURITY] Incident %s reported for user_id=%s (%s); alert %s created, account unchanged.",
            incident_type,
            user.id,
            user.username,
            alert_id,
        )

    db.session.commit()

    return {
        "status": "ok",
        "alert_id": alert_id,
        "user_id": user_id,
        "user_banned": False,
    }
