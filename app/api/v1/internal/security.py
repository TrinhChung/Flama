"""Internal security routes for microservice event callbacks."""

from __future__ import annotations

import hmac
import ipaddress
import logging
from flask import Blueprint, current_app, jsonify, request

from app.services.security_incident_service import (
    SecurityIncidentError,
    handle_security_incident,
)

logger = logging.getLogger(__name__)

internal_security_bp = Blueprint("api_v1_internal_security", __name__)


def _is_trusted_remote_ip(remote_ip: str) -> bool:
    """Verify that the caller is on the private WireGuard mesh or loopback."""
    if not remote_ip:
        return False

    if remote_ip in {"127.0.0.1", "::1", "localhost"}:
        return True

    # Allow custom trusted IPs or networks from config
    custom_trusted = current_app.config.get("INTERNAL_TRUSTED_IPS") or ()
    if isinstance(custom_trusted, str):
        custom_trusted = [ip.strip() for ip in custom_trusted.split(",") if ip.strip()]
    if remote_ip in custom_trusted:
        return True

    try:
        ip = ipaddress.ip_address(remote_ip)
        if ip.is_loopback:
            return True
        # WireGuard VPN mesh subnet for Flama nodes (10.10.0.0/24)
        wg_subnet = ipaddress.ip_network("10.10.0.0/24")
        if ip in wg_subnet:
            return True
    except ValueError:
        return False

    return False


def _verify_internal_secret() -> bool:
    provided = request.headers.get("X-Internal-Secret", "").strip()
    if not provided:
        return False

    expected_secret = str(
        current_app.config.get("INTERNAL_SECURITY_SECRET")
        or current_app.config.get("GATEWAY_SECRET")
        or ""
    ).strip()

    if not expected_secret:
        return False

    return hmac.compare_digest(provided, expected_secret)


@internal_security_bp.post("/internal/security/incident")
def report_security_incident():
    """Receive security threat notifications from internal services (e.g., worker 212).

    Enforces 2 layers of authorization:
    1. Remote IP verification: Caller must originate from WireGuard mesh (10.10.0.0/24) or loopback.
    2. Secret token verification: X-Internal-Secret header matching internal secret.
    """
    client_ip = request.remote_addr or ""

    # Layer 1: Network / IP check
    if not current_app.config.get("TESTING") and not _is_trusted_remote_ip(client_ip):
        logger.warning(
            "[SECURITY] Rejected unauthorized caller outside WireGuard mesh: remote_addr=%s",
            client_ip,
        )
        return (
            jsonify({
                "error": "FORBIDDEN",
                "message": "Access denied: Endpoint only accessible via private internal network",
            }),
            403,
        )

    # Layer 2: Secret header verification
    if not _verify_internal_secret():
        logger.warning(
            "[SECURITY] Rejected incident report with invalid or missing secret from: %s",
            client_ip,
        )
        return (
            jsonify({
                "error": "FORBIDDEN",
                "message": "Invalid or missing internal security secret",
            }),
            403,
        )

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return (
            jsonify({
                "error": "INVALID_PAYLOAD",
                "message": "Request body must be a valid JSON object",
            }),
            400,
        )

    try:
        result = handle_security_incident(payload)
        return jsonify(result), 200
    except SecurityIncidentError as exc:
        return (
            jsonify({
                "error": "INCIDENT_PROCESSING_ERROR",
                "message": exc.message,
            }),
            exc.status_code,
        )
    except Exception as exc:
        current_app.logger.exception("Unexpected error processing security incident: %s", exc)
        return (
            jsonify({
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to process security incident",
            }),
            500,
        )
