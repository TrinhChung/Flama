"""Legacy MCP JSON-RPC route forwarding to Flama Connect MCP handler."""

from __future__ import annotations

import logging

from flask import Blueprint
from flask_login import current_user

from app.connect.mcp import handle_mcp_request

mcp_bp = Blueprint("mcp", __name__)

logger = logging.getLogger(__name__)


@mcp_bp.route("/api/mcp", methods=["POST", "OPTIONS"])
def mcp_api():
    """Backward compatible endpoint on main Flask app."""
    return handle_mcp_request(session_user=current_user)


