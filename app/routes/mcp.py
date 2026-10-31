"""Legacy MCP JSON-RPC route forwarding to Flama Connect MCP handler."""

from __future__ import annotations

import logging

from flask import Blueprint
from flask_login import current_user

from app.connect.mcp import handle_mcp_request, openai_apps_challenge

mcp_bp = Blueprint("mcp", __name__)

logger = logging.getLogger(__name__)

# Either MCP origin may be the one submitted to OpenAI, so both answer the challenge.
mcp_bp.add_url_rule("/.well-known/openai-apps-challenge", view_func=openai_apps_challenge, methods=["GET"])


@mcp_bp.route("/api/mcp", methods=["POST", "OPTIONS"])
def mcp_api():
    """Backward compatible endpoint on main Flask app."""
    return handle_mcp_request(session_user=current_user)


