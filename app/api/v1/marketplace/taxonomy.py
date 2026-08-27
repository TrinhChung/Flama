"""Public Marketplace Taxonomy REST API V1 resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from app.services import marketplace_taxonomy_service

marketplace_taxonomy_bp = Blueprint("api_v1_marketplace_taxonomy", __name__)


@marketplace_taxonomy_bp.get("/marketplace/taxonomy/schema")
def get_taxonomy_schema():
    content_type = request.args.get("content_type") or "deck_marketplace_item"
    if content_type not in ("deck_marketplace_item", "note_type"):
        content_type = "deck_marketplace_item"
    schema = marketplace_taxonomy_service.build_taxonomy_schema(content_type=content_type)
    return jsonify(schema)
