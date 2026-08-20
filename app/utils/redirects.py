"""Helpers for validating in-app redirect targets."""

from __future__ import annotations

from urllib.parse import urlparse

from flask import request, url_for


def resolve_safe_next_url(raw_value: str | None, *, default_endpoint: str = "main.dashboard") -> str:
    candidate = str(raw_value or "").strip()
    if not candidate:
        return url_for(default_endpoint)

    if candidate.startswith("/") and not candidate.startswith("//"):
        return candidate

    parsed_candidate = urlparse(candidate)
    parsed_host = urlparse(request.host_url)
    if (
        parsed_candidate.scheme in {"http", "https"}
        and parsed_candidate.netloc == parsed_host.netloc
    ):
        path = parsed_candidate.path or "/"
        if parsed_candidate.query:
            path = f"{path}?{parsed_candidate.query}"
        return path

    from app.services import oauth_service

    frontend_base = oauth_service.get_frontend_base_url(request)
    if frontend_base:
        parsed_frontend = urlparse(frontend_base)
        if (
            parsed_candidate.scheme in {"http", "https"}
            and parsed_candidate.netloc == parsed_frontend.netloc
        ):
            path = parsed_candidate.path or "/"
            if parsed_candidate.query:
                path = f"{path}?{parsed_candidate.query}"
            return path

    return url_for(default_endpoint)
