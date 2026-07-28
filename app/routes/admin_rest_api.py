"""Compatibility import for the relocated administrative REST blueprint.

New registrations go through :mod:`app.api.v1`; this alias is kept for code
that still imports the historical module path.
"""

from app.api.v1.admin import admin_bp as admin_rest_api_bp

__all__ = ["admin_rest_api_bp"]
