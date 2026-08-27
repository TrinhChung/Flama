"""Serve the React SPA for routes that have been migrated to the frontend."""

from __future__ import annotations

from pathlib import Path

from flask import Response, current_app, jsonify, redirect, request, send_from_directory

from app.settings import BASE_DIR

_FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

_BINARY_PATH_PREFIXES = (
    "/assets/",
    "/static/",
    "/media/",
)


def init_spa_delivery(app) -> None:
    """Make React the only HTML surface while API adapters remain transitional."""

    @app.before_request
    def route_frontend_navigation():
        path = request.path
        if (
            path == "/api"
            or path.startswith("/api/")
            or path.startswith("/.well-known/")
            or (path.startswith("/oauth/") and path != "/oauth/consent")
        ):
            return None

        legacy_adapters_enabled = bool(
            current_app.config.get("LEGACY_HTTP_ADAPTERS_ENABLED", False)
        )
        if "/api/" in path:
            if legacy_adapters_enabled:
                return None
            return _legacy_adapter_removed()

        if request.method in ("GET", "HEAD"):
            if path.startswith(_BINARY_PATH_PREFIXES):
                return None
            if path == "/support-donation/qr":
                return None
            if path.startswith("/admin/image-library/") and path.endswith("/preview"):
                return None
            if path.startswith(
                (
                    "/vocabulary/topic/",
                    "/vocabulary/study/topic/",
                    "/vocabulary/study/lesson/",
                    "/vocabulary/lesson/",
                )
            ):
                return None
            return serve_react_spa()

        if legacy_adapters_enabled:
            return None
        return _legacy_adapter_removed()


def _legacy_adapter_removed():
    return (
        jsonify(
            {
                "error": "LEGACY_ENDPOINT_REMOVED",
                "message": "Use the canonical REST API under /api.",
            }
        ),
        410,
    )


def serve_react_spa(*_args, **_kwargs) -> Response:
    """Return the React SPA ``index.html``.

    During development the Vite dev-server proxies API calls back to Flask,
    so this helper is primarily used in production where Flask serves the
    built frontend assets itself.  If the build artefact is missing and an
    external frontend origin is configured, redirect there. Otherwise, a
    plain 404 text response is returned so the developer knows to run
    ``npm run build`` first.
    """
    index = _FRONTEND_DIST / "index.html"
    if not index.is_file():
        from app.services import oauth_service

        frontend_base = oauth_service.get_frontend_base_url(request)
        current_base = oauth_service.get_base_url(request)
        if frontend_base and frontend_base.rstrip("/") != current_base.rstrip("/"):
            query_string = request.query_string.decode("utf-8") if request.query_string else ""
            target_path = f"{request.path}?{query_string}" if query_string else request.path
            return redirect(f"{frontend_base}{target_path}")

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

