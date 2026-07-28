"""Shared HTTP mapping for flashcard V1 resources."""

from flask import jsonify

from app.services.flashcard_content_service import ContentApiError


def content_error(exc: ContentApiError):
    payload = {"error": exc.error, "message": str(exc)}
    if exc.field is not None:
        payload["field"] = exc.field
    return jsonify(payload), exc.status
