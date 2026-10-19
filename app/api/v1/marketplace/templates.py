"""Standalone template marketplace REST resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, url_for
from flask_login import current_user, login_required

from app.api.common.responses import error_response
from app.services import template_marketplace_service
from app.services.template_release_service import TemplateReleaseError

marketplace_templates_bp = Blueprint("api_v1_marketplace_templates", __name__)


def _respond(operation, **kwargs):
    try:
        result = operation(user_id=current_user.id, **kwargs)
    except TemplateReleaseError as exc:
        return error_response(exc.code, str(exc), status=exc.status, field=exc.field)
    payload, status = result if isinstance(result, tuple) else (result, 200)
    response = jsonify(payload)
    response.headers["Cache-Control"] = "private, no-store"
    return response, status


@marketplace_templates_bp.get("/marketplace/templates")
@login_required
def list_marketplace_templates():
    return _respond(template_marketplace_service.list_catalog, args=request.args)


@marketplace_templates_bp.get("/marketplace/templates/<template_id>")
@login_required
def get_marketplace_template(template_id: str):
    return _respond(template_marketplace_service.get_catalog_item, template_id=template_id)


@marketplace_templates_bp.post("/marketplace/templates/<template_id>/preview")
@login_required
def preview_marketplace_template(template_id: str):
    return _respond(template_marketplace_service.preview_catalog_item, template_id=template_id)


@marketplace_templates_bp.post("/marketplace/templates/<template_id>/install")
@login_required
def install_marketplace_template(template_id: str):
    result_url = url_for("payments.marketplace_payment_result_page", _external=True)
    return _respond(template_marketplace_service.install, template_id=template_id, return_url=result_url, cancel_url=result_url)
