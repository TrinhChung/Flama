"""Security incident processing service.

Handles attack notifications forwarded by media edge services or internal microservices,
creates administrative security alerts, logs audit trails, and automatically blocks/bans offending users.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from models import db
from models.admin_security_alert import AdminSecurityAlert
from models.audit_log import AuditLog
from models.mcp_access_token import McpAccessToken
from models.model_uuid import uuid_str
from models.user import User
from models.user_api_token import UserApiToken

logger = logging.getLogger(__name__)


class SecurityIncidentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def handle_security_incident(payload: dict[str, Any]) -> dict[str, Any]:
    """Process a verified security incident reported by internal worker services.

    1. Records an AdminSecurityAlert threat record.
    2. If a user_id is associated:
       - Protects admin accounts from DoS auto-bans (alert and audit log only).
       - Automatically disables malicious normal users (is_disabled = True).
       - Immediately revokes all active UserApiTokens and McpAccessTokens.
       - Records a security.user_auto_banned AuditLog entry.
    3. Commits the transaction and returns a status summary.
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

    user_banned = False
    admin_protected = False

    if user_id:
        user = db.session.get(User, user_id)
        if user:
            if user.is_admin:
                admin_protected = True
                logger.warning(
                    "[SECURITY] Threat detected from admin user_id=%s (%s), skipping auto-disable to prevent DoS lockout.",
                    user_id,
                    user.username,
                )
                audit = AuditLog(
                    user_id=user.id,
                    action="security.incident_admin_bypassed",
                    payload={
                        "incident_type": incident_type,
                        "detail": detail,
                        "client_ip": client_ip,
                        "alert_id": alert_id,
                    },
                )
                db.session.add(audit)
            else:
                user.is_disabled = True
                user_banned = True

                # Revoke active User API tokens
                now = datetime.utcnow()
                UserApiToken.query.filter_by(user_id=user.id).filter(
                    UserApiToken.revoked_at.is_(None)
                ).update({"revoked_at": now})

                # Revoke active MCP access tokens
                McpAccessToken.query.filter_by(user_id=user.id, revoked=False).update(
                    {"revoked": True}
                )

                audit = AuditLog(
                    user_id=user.id,
                    action="security.user_auto_banned",
                    payload={
                        "reason": incident_type,
                        "detail": detail,
                        "client_ip": client_ip,
                        "alert_id": alert_id,
                    },
                )
                db.session.add(audit)

                logger.critical(
                    "[SECURITY] User user_id=%s (%s) automatically BANNED due to incident %s: %s",
                    user.id,
                    user.username,
                    incident_type,
                    detail,
                )

    db.session.commit()

    return {
        "status": "ok",
        "alert_id": alert_id,
        "user_id": user_id,
        "user_banned": user_banned,
        "admin_protected": admin_protected,
    }
