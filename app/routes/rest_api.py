"""Compatibility import for the relocated REST API V1 blueprint.

The application registers V1 through :mod:`app.api`. This alias preserves the
historical import path for extensions and tests outside the application.
"""

from app.api.v1 import api_v1_bp as rest_api_bp

__all__ = ["rest_api_bp"]
