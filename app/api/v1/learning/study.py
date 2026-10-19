"""Study REST API V1 resources under /api/study."""

from __future__ import annotations

from flask import Blueprint

from app.routes.flashcards import study as _study_routes

study_bp = Blueprint("api_v1_learning_study", __name__)

# Register canonical /api/study endpoints on study_bp
study_bp.add_url_rule(
    "/artifacts/public/deck-items/<deck_item_id>/cards/<card_id>/<kind>/versions/<version>",
    view_func=_study_routes.study_public_artifact,
    methods=["GET"],
)
study_bp.add_url_rule(
    "/artifacts/private/cards/<card_id>/<kind>/versions/<version>",
    view_func=_study_routes.study_private_artifact,
    methods=["GET"],
)
study_bp.add_url_rule(
    "/cards/<card_id>/intervals-preview",
    view_func=_study_routes.study_intervals_preview,
    methods=["GET"],
)
study_bp.add_url_rule(
    "/scopes/<scope_type>/<scope_id>/compositions",
    view_func=_study_routes.study_scope_compositions,
    methods=["GET"],
)
study_bp.add_url_rule(
    "/sessions",
    view_func=_study_routes.study_session_open,
    methods=["POST"],
)
study_bp.add_url_rule(
    "/sessions/<session_id>",
    view_func=_study_routes.study_session_status,
    methods=["GET"],
)
study_bp.add_url_rule(
    "/sessions/<session_id>/batch/<batch_id>",
    view_func=_study_routes.study_session_batch_status,
    methods=["GET"],
)
study_bp.add_url_rule(
    "/sessions/<session_id>/batch",
    view_func=_study_routes.study_session_batch,
    methods=["POST"],
)
study_bp.add_url_rule(
    "/sessions/<session_id>/commit",
    view_func=_study_routes.study_session_commit,
    methods=["POST"],
)
study_bp.add_url_rule(
    "/session/next",
    view_func=_study_routes.study_next,
    methods=["GET"],
)
study_bp.add_url_rule(
    "/next",
    view_func=_study_routes.study_next,
    methods=["GET"],
)
study_bp.add_url_rule(
    "/cards/<card_id>/answer",
    view_func=_study_routes.study_answer,
    methods=["POST"],
)
study_bp.add_url_rule(
    "/<card_id>/answer",
    view_func=_study_routes.study_answer,
    methods=["POST"],
)
study_bp.add_url_rule(
    "/cards/<card_id>/edit",
    view_func=_study_routes.study_edit_card,
    methods=["PATCH"],
)
