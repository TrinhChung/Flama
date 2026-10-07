"""Routes serving technical SEO and GEO machine-readable files.

Exposes:
- GET /robots.txt: Crawler and AI bot access policies.
- GET /sitemap.xml: Dynamic sitemaps.org XML cataloging 38 public URLs.
- GET /llms.txt: llmstxt.org machine-readable knowledge index for AI agents.
"""

from __future__ import annotations

from flask import Blueprint, Response, current_app

from app.services.seo_service import (
    DEFAULT_BASE_URL,
    generate_llms_txt,
    generate_robots_txt,
    generate_sitemap_xml,
)

seo_bp = Blueprint("seo", __name__)


def _resolve_base_url() -> str:
    """Resolve the canonical base URL from configuration or fallback to production."""
    base = current_app.config.get("CANONICAL_BASE_URL") or current_app.config.get("PUBLIC_APP_URL")
    if base and str(base).strip() and not ("127.0.0.1" in str(base) or "localhost" in str(base)):
        return str(base).rstrip("/")
    return DEFAULT_BASE_URL


@seo_bp.route("/robots.txt", methods=["GET"])
def robots_txt() -> Response:
    """Serve robots.txt with AI bot rules and sitemap pointer."""
    base_url = _resolve_base_url()
    content = generate_robots_txt(base_url=base_url)
    response = Response(content, mimetype="text/plain; charset=utf-8")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@seo_bp.route("/sitemap.xml", methods=["GET"])
def sitemap_xml() -> Response:
    """Serve dynamic sitemap.xml cataloging all public indexable URLs."""
    base_url = _resolve_base_url()
    content = generate_sitemap_xml(base_url=base_url)
    response = Response(content, mimetype="application/xml; charset=utf-8")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@seo_bp.route("/llms.txt", methods=["GET"])
def llms_txt() -> Response:
    """Serve llms.txt adhering to llmstxt.org for AI search and agents."""
    base_url = _resolve_base_url()
    content = generate_llms_txt(base_url=base_url)
    response = Response(content, mimetype="text/plain; charset=utf-8")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response
