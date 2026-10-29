"""Marketplace installation and published-update resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common.responses import error_response
from app.services import marketplace_hub_service
from app.services import deck_install_rebase_service
from app.services.deck_install_rebase_service import DeckInstallUpdateError


marketplace_installations_bp = Blueprint(
    "api_v1_marketplace_installations",
    __name__,
)


@marketplace_installations_bp.before_request
def retire_version_updates():
    from app.services.note_base_context import published_base_enabled
    retired = {
        "installed_deck_update_diff", "prepare_installed_deck_update",
        "apply_installed_deck_update", "mark_installed_deck_update_seen",
        "resolve_installed_deck_update_conflict", "installed_deck_update_conflicts",
        "apply_prepared_installed_deck_update", "resolve_all_installed_deck_conflicts",
        "update_installed_deck_settings",
    }
    if published_base_enabled() and current_user.is_authenticated and request.endpoint.rsplit(".", 1)[-1] in retired:
        return error_response("DECK_VERSION_UPDATES_RETIRED",
            "Installed decks read the latest published content. Personal overrides remain yours.", status=410)


@marketplace_installations_bp.get("/installed-decks")
@login_required
def installed_decks():
    return jsonify(
        marketplace_hub_service.build_installed_deck_workspace(
            user_id=current_user.id
        )
    )


def _handle_update_error(exc: DeckInstallUpdateError):
    return error_response(
        exc.error,
        exc.message,
        status=exc.status,
        field=exc.field,
        details=exc.details,
    )


@marketplace_installations_bp.get("/installations/<install_id>/base-overrides")
@marketplace_installations_bp.get("/installations/<install_id>/updates")
@login_required
def installed_deck_updates(install_id: str):
    from app.services.note_base_context import published_base_enabled
    if published_base_enabled():
        from app.services.note_base_comparison_service import compare_overrides
        try:
            return jsonify(compare_overrides(install_id=install_id, user_id=current_user.id,
                after=request.args.get("cursor"), limit=request.args.get("limit", 50)))
        except DeckInstallUpdateError as exc:
            return _handle_update_error(exc)
    try:
        payload = deck_install_rebase_service.get_update_status(
            install_id=install_id,
            user_id=current_user.id,
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)
    return jsonify(payload)


@marketplace_installations_bp.delete("/installations/<install_id>/overrides/<override_id>")
@login_required
def clear_installed_override(install_id: str, override_id: str):
    from app.services.note_base_context import published_base_enabled
    if not published_base_enabled():
        return error_response("FEATURE_UNAVAILABLE", "Published Base is not active.", status=404)
    from app.services.note_base_comparison_service import clear_override
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("VALIDATION_ERROR", "Payload must be a JSON object.", status=400)
    try:
        return jsonify(clear_override(install_id=install_id, override_id=override_id,
            user_id=current_user.id, expected_overlay_revision=payload.get("expected_overlay_revision")))
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)


@marketplace_installations_bp.post("/installations/<install_id>/overrides/<override_id>/keep")
@login_required
def keep_installed_override(install_id: str, override_id: str):
    from app.services.note_base_context import published_base_enabled
    if not published_base_enabled():
        return error_response("FEATURE_UNAVAILABLE", "Published Base is not active.", status=404)
    from app.services.note_base_comparison_service import keep_override
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("VALIDATION_ERROR", "Payload must be a JSON object.", status=400)
    try:
        return jsonify(keep_override(install_id=install_id, override_id=override_id,
            user_id=current_user.id, expected_overlay_revision=payload.get("expected_overlay_revision"),
            expected_base_hash=payload.get("expected_base_hash")))
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)


@marketplace_installations_bp.get(
    "/installations/<install_id>/updates/<release_id>/diff"
)
@login_required
def installed_deck_update_diff(install_id: str, release_id: str):
    try:
        payload = deck_install_rebase_service.get_update_diff(
            install_id=install_id,
            release_id=release_id,
            user_id=current_user.id,
            cursor=request.args.get("cursor"),
            limit=request.args.get("limit", 100),
            entity_kind=(request.args.get("entity_kind") or request.args.get("entity_type")),
            operation=(request.args.get("operation") or request.args.get("type")),
            query_text=request.args.get("q"),
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)
    return jsonify(payload)


@marketplace_installations_bp.post(
    "/installations/<install_id>/updates/<release_id>/prepare"
)
@login_required
def prepare_installed_deck_update(install_id: str, release_id: str):
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        rebase = deck_install_rebase_service.prepare_update_and_commit(
            install_id=install_id,
            release_id=release_id,
            user_id=current_user.id,
            expected_applied_release_id=body.get("expected_applied_release_id"),
            expected_overlay_revision=body.get("expected_overlay_revision"),
            idempotency_key=(
                request.headers.get("Idempotency-Key")
                or body.get("idempotency_key")
            ),
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)
    return jsonify({"rebase": deck_install_rebase_service.serialize_rebase(rebase)})


@marketplace_installations_bp.post(
    "/installations/<install_id>/updates/<release_id>/apply"
)
@login_required
def apply_installed_deck_update(install_id: str, release_id: str):
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        rebase = deck_install_rebase_service.prepare_and_apply_update_and_commit(
            install_id=install_id,
            release_id=release_id,
            user_id=current_user.id,
            expected_applied_release_id=body.get("expected_applied_release_id"),
            expected_overlay_revision=body.get("expected_overlay_revision"),
            idempotency_key=(
                request.headers.get("Idempotency-Key")
                or body.get("idempotency_key")
            ),
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)
    return jsonify(
        {
            "rebase": deck_install_rebase_service.serialize_rebase(
                rebase,
                include_conflicts=False,
            )
        }
    )


@marketplace_installations_bp.post(
    "/installations/<install_id>/updates/<release_id>/mark-seen"
)
@login_required
def mark_installed_deck_update_seen(install_id: str, release_id: str):
    try:
        payload = deck_install_rebase_service.mark_update_seen_and_commit(
            install_id=install_id,
            release_id=release_id,
            user_id=current_user.id,
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)
    return jsonify(payload)


@marketplace_installations_bp.post(
    "/rebases/<rebase_id>/conflicts/<int:conflict_id>/resolve"
)
@login_required
def resolve_installed_deck_update_conflict(rebase_id: str, conflict_id: int):
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        rebase = deck_install_rebase_service.resolve_conflict_and_commit(
            rebase_id=rebase_id,
            conflict_id=conflict_id,
            user_id=current_user.id,
            resolution_mode=body.get("resolution_mode"),
            resolved_value=body.get("resolved_value"),
            has_resolved_value="resolved_value" in body,
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)
    return jsonify(
        {
            "rebase": deck_install_rebase_service.serialize_rebase(
                rebase,
                include_conflicts=False,
            )
        }
    )


@marketplace_installations_bp.get("/rebases/<rebase_id>/conflicts")
@login_required
def installed_deck_update_conflicts(rebase_id: str):
    try:
        payload = deck_install_rebase_service.get_rebase_conflicts_page(
            rebase_id=rebase_id,
            user_id=current_user.id,
            after_id=request.args.get("after_id"),
            limit=request.args.get("limit", 100),
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)
    return jsonify(payload)


@marketplace_installations_bp.post("/rebases/<rebase_id>/apply")
@login_required
def apply_prepared_installed_deck_update(rebase_id: str):
    try:
        rebase = deck_install_rebase_service.apply_prepared_update_and_commit(
            rebase_id=rebase_id,
            user_id=current_user.id,
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)
    return jsonify(
        {
            "rebase": deck_install_rebase_service.serialize_rebase(
                rebase,
                include_conflicts=False,
            )
        }
    )


@marketplace_installations_bp.get("/installations/<install_id>/settings")
@login_required
def get_installed_deck_settings(install_id: str):
    try:
        payload = deck_install_rebase_service.get_install_settings(
            install_id=install_id,
            user_id=current_user.id,
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)
    return jsonify(payload)


@marketplace_installations_bp.post("/installations/<install_id>/settings")
@login_required
def update_installed_deck_settings(install_id: str):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    if "auto_update_enabled" not in body:
        return error_response(
            "VALIDATION_ERROR",
            "auto_update_enabled is required.",
            status=400,
            field="auto_update_enabled",
        )

    try:
        payload = deck_install_rebase_service.update_install_settings_and_commit(
            install_id=install_id,
            user_id=current_user.id,
            auto_update_enabled=bool(body.get("auto_update_enabled")),
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)

    return jsonify(payload)


@marketplace_installations_bp.post("/installations/<install_id>/detach")
@login_required
def detach_installed_deck(install_id: str):
    try:
        payload = deck_install_rebase_service.detach_installed_deck_and_commit(
            install_id=install_id,
            user_id=current_user.id,
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)

    return jsonify(payload)


@marketplace_installations_bp.post(
    "/rebases/<rebase_id>/conflicts/resolve-all"
)
@login_required
def resolve_all_installed_deck_conflicts(rebase_id: str):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    resolution_mode = body.get("resolution_mode")
    if not resolution_mode or resolution_mode not in {"keep_mine", "keep_upstream"}:
        return error_response(
            "VALIDATION_ERROR",
            "resolution_mode must be 'keep_mine' or 'keep_upstream'.",
            status=400,
            field="resolution_mode",
        )

    try:
        rebase = deck_install_rebase_service.resolve_all_conflicts_and_commit(
            rebase_id=rebase_id,
            user_id=current_user.id,
            resolution_mode=resolution_mode,
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)

    return jsonify(
        {
            "rebase": deck_install_rebase_service.serialize_rebase(
                rebase,
                include_conflicts=False,
            )
        }
    )

