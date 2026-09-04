"""REST API endpoints for Worksheet generation and printable exports."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from app.services.worksheets.template_catalog import list_templates
from app.services.worksheets.worksheet_service import (
    WorksheetServiceError,
    generate_worksheet_preview,
    get_deck_worksheet_meta,
    render_printable_html,
)
from app.utils.permissions import is_admin_user

worksheets_bp = Blueprint("api_v1_worksheets", __name__)


def _error_response(exc: WorksheetServiceError):
    payload = {"error": str(exc), "code": exc.code}
    return jsonify(payload), exc.status


@worksheets_bp.get("/worksheets/templates")
@login_required
def list_worksheet_templates_route():
    """List all available worksheet templates with metadata and field slots."""
    return jsonify({
        "templates": list_templates(),
    })


@worksheets_bp.get("/worksheets/meta")
@login_required
def get_standalone_worksheet_meta_route():
    """Retrieve standalone metadata with all templates (no deck required)."""
    return jsonify({
        "deck_id": 0,
        "deck_name": "Mẫu giấy in & Luyện viết",
        "total_notes": 0,
        "note_types": [],
        "suggested_mappings": {},
        "templates": [t.to_dict() for t in list_templates()],
    })


@worksheets_bp.get("/decks/<int:deck_id>/worksheets/meta")
@login_required
def get_deck_worksheet_meta_route(deck_id: int):
    """Retrieve metadata, note types, and fields for a deck to configure worksheet."""
    if deck_id == 0:
        return get_standalone_worksheet_meta_route()
    try:
        meta = get_deck_worksheet_meta(
            user_id=current_user.id,
            deck_id=deck_id,
            admin_mode=is_admin_user(current_user),
        )
    except WorksheetServiceError as exc:
        return _error_response(exc)

    return jsonify(meta)


@worksheets_bp.post("/worksheets/preview")
@login_required
def generate_worksheet_preview_route():
    """Generate structured worksheet preview data with pagination."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Payload phải là JSON object.", "code": "INVALID_PAYLOAD"}), 400

    try:
        result = generate_worksheet_preview(
            user_id=current_user.id,
            payload=payload,
            admin_mode=is_admin_user(current_user),
        )
    except WorksheetServiceError as exc:
        return _error_response(exc)

    return jsonify(result)


@worksheets_bp.post("/worksheets/render-html")
@login_required
def render_worksheet_html_route():
    """Generate a self-contained printable A4 HTML document."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Payload phải là JSON object.", "code": "INVALID_PAYLOAD"}), 400

    try:
        # If payload already contains preview data (e.g. pages), render directly
        if "pages" in payload and "template" in payload:
            html_content = render_printable_html(payload)
        else:
            # Otherwise generate preview first
            preview_data = generate_worksheet_preview(
                user_id=current_user.id,
                payload=payload,
                admin_mode=is_admin_user(current_user),
            )
            html_content = render_printable_html(preview_data)
    except WorksheetServiceError as exc:
        return _error_response(exc)

    # If client requested JSON response containing the HTML string
    if request.args.get("format") == "json" or request.accept_mimetypes.best == "application/json":
        return jsonify({
            "html": html_content,
            "filename": f"worksheet_{payload.get('template_id', 'export')}.html",
        })

    # Default: Return HTML with printable mime type
    return Response(
        html_content,
        mimetype="text/html",
        headers={
            "Content-Disposition": f'inline; filename="flama_worksheet_{payload.get("template_id", "export")}.html"',
        },
    )
