"""Allowlisted static MCP UI resources alongside existing documentation resources."""

from pathlib import Path
from urllib.parse import urlsplit

from flask import current_app, has_app_context, has_request_context, request


TEMPLATE_PREVIEW_URI = "ui://flama/template-preview/v1.html"
TEMPLATE_PREVIEW_MIME = "text/html;profile=mcp-app"
_UI_PATH = Path(__file__).resolve().parents[2] / "frontend" / "dist-mcp" / "index.html"


def template_preview_ui_available():
    return (has_app_context() and bool(current_app.config.get("MCP_TEMPLATE_PREVIEW_UI_ENABLED", False))
            and _UI_PATH.is_file())


def media_base_url():
    """Use explicit deployment origin when present, otherwise the MCP request origin."""
    configured = str(current_app.config.get("MCP_TEMPLATE_PREVIEW_MEDIA_BASE_URL")
        or current_app.config.get("PUBLIC_APP_URL") or "") if has_app_context() else ""
    if not configured and has_request_context():
        from app.services.oauth_service import get_base_url
        configured = get_base_url(request)
    parsed = urlsplit(configured)
    if parsed.scheme in ("http", "https") and parsed.netloc and not parsed.username and not parsed.password:
        return f"{parsed.scheme}://{parsed.netloc}/"
    return ""


def _ui_meta():
    origin = media_base_url().rstrip("/")
    return {"ui": {"prefersBorder": True, "csp": {
        "connectDomains": [origin] if origin else [],
        "resourceDomains": [origin] if origin else [],
        # CardRendererFrame uses srcdoc in an opaque-origin nested iframe.
        "frameDomains": ["'self'", "blob:"],
        "baseUriDomains": [origin] if origin else [],
    }}}


def list_resources():
    from app.services.mcp.public_search_tools import list_documentation_resources
    resources = list_documentation_resources()
    if template_preview_ui_available():
        resources.append(dict(uri=TEMPLATE_PREVIEW_URI, name="Flama Template Preview",
            description="Read-only candidate preview using the Study sandbox.",
            mimeType=TEMPLATE_PREVIEW_MIME, _meta=_ui_meta()))
    return resources


def read_resource(uri):
    if uri == TEMPLATE_PREVIEW_URI:
        if not template_preview_ui_available():
            return None
        return dict(uri=uri, mimeType=TEMPLATE_PREVIEW_MIME, text=_UI_PATH.read_text(encoding="utf-8"),
                    _meta=_ui_meta())
    from app.services.mcp.public_search_tools import read_documentation_resource
    return read_documentation_resource(uri)
