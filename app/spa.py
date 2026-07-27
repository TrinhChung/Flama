"""Serve the React SPA for routes that have been migrated to the frontend."""

from __future__ import annotations

from pathlib import Path

from flask import Response, send_from_directory

from app.settings import BASE_DIR

_FRONTEND_DIST = BASE_DIR / "frontend" / "dist"


def serve_react_spa() -> Response:
    """Return the React SPA ``index.html``.

    During development the Vite dev-server proxies API calls back to Flask,
    so this helper is primarily used in production where Flask serves the
    built frontend assets itself.  If the build artefact is missing a plain
    404 text response is returned so the developer knows to run ``npm run
    build`` first.
    """
    index = _FRONTEND_DIST / "index.html"
    if not index.is_file():
        return Response(
            "React build not found – run 'npm run build' in frontend/",
            status=404,
            content_type="text/plain; charset=utf-8",
        )
    from app.csrf import generate_csrf_token
    generate_csrf_token()
    return send_from_directory(str(_FRONTEND_DIST), "index.html")


def serve_react_spa_assets(filename: str) -> Response:
    assets_dir = _FRONTEND_DIST / "assets"
    return send_from_directory(str(assets_dir), filename)

