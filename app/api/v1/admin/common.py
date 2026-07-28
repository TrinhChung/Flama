"""Shared request and error mapping for administrative V1 resources."""

from __future__ import annotations

from flask import request

from app.api.common import error_response
from app.services.admin_rest_api_service import AdminRestApiError


def request_payload() -> dict:
    if request.is_json:
        payload = request.get_json(silent=True)
        return payload if isinstance(payload, dict) else {}
    return request.form.to_dict(flat=True)


def admin_service_error(error: AdminRestApiError):
    return error_response(
        error.code,
        str(error),
        status=error.status,
        field=error.field,
    )
