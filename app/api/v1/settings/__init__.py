"""User and administrative settings REST resources."""

from flask import Blueprint

from .mcp_tokens import mcp_tokens_bp


settings_bp = Blueprint("api_v1_settings", __name__)
settings_bp.register_blueprint(mcp_tokens_bp, url_prefix="/mcp-tokens")
