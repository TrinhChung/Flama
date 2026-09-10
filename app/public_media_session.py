"""Session handling exceptions for public, CDN-cacheable media responses."""

from __future__ import annotations

from flask import has_request_context, request
from flask.sessions import SecureCookieSessionInterface, SessionMixin
from werkzeug.wrappers import Response


class PublicMediaSessionInterface(SecureCookieSessionInterface):
    """Keep the default signed-cookie session behavior outside public media."""

    def save_session(self, app, session: SessionMixin, response: Response) -> None:
        super().save_session(app, session, response)
        if not has_request_context() or not request.path.startswith("/media/proxy/"):
            return

        # Media is authorization-independent. Cookie-specific variants and
        # Set-Cookie both prevent safe browser/CDN cache reuse.
        response.vary.discard("Cookie")
        while "Set-Cookie" in response.headers:
            response.headers.remove("Set-Cookie")
