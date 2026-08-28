"""Marketplace installation and published-update resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common.responses import error_response
from app.services import marketplace_hub_service
from app.services import deck_install_rebase_service
from app.services.deck_install_rebase_service import DeckInstallUpdateError
from models import db


marketplace_installations_bp = Blueprint(
    "api_v1_marketplace_installations",
    __name__,
)

_PERSISTED_REBASE_ERRORS = {
    "REBASE_CONFLICTS_UNRESOLVED",
    "APPLIED_RELEASE_STALE",
    "OVERLAY_REVISION_STALE",
}


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


@marketplace_installations_bp.get("/installations/<install_id>/updates")
@login_required
def installed_deck_updates(install_id: str):
    try:
        payload = deck_install_rebase_service.get_update_status(
            install_id=install_id,
            user_id=current_user.id,
        )
    except DeckInstallUpdateError as exc:
        return _handle_update_error(exc)
    return jsonify(payload)


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
        rebase = deck_install_rebase_service.prepare_update(
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
        db.session.commit()
    except DeckInstallUpdateError as exc:
        db.session.rollback()
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
        rebase = deck_install_rebase_service.prepare_and_apply_update(
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
        db.session.commit()
    except DeckInstallUpdateError as exc:
        # A conflicting preparation is durable so the user can resolve it by
        # field without rebuilding the entire diff.
        if exc.error in _PERSISTED_REBASE_ERRORS:
            db.session.commit()
        else:
            db.session.rollback()
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
        payload = deck_install_rebase_service.mark_update_seen(
            install_id=install_id,
            release_id=release_id,
            user_id=current_user.id,
        )
        db.session.commit()
    except DeckInstallUpdateError as exc:
        db.session.rollback()
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
        rebase = deck_install_rebase_service.resolve_conflict(
            rebase_id=rebase_id,
            conflict_id=conflict_id,
            user_id=current_user.id,
            resolution_mode=body.get("resolution_mode"),
            resolved_value=body.get("resolved_value"),
            has_resolved_value="resolved_value" in body,
        )
        db.session.commit()
    except DeckInstallUpdateError as exc:
        db.session.rollback()
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
        rebase = deck_install_rebase_service.apply_prepared_update(
            rebase_id=rebase_id,
            user_id=current_user.id,
        )
        db.session.commit()
    except DeckInstallUpdateError as exc:
        if exc.error in _PERSISTED_REBASE_ERRORS:
            db.session.commit()
        else:
            db.session.rollback()
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
        payload = deck_install_rebase_service.update_install_settings(
            install_id=install_id,
            user_id=current_user.id,
            auto_update_enabled=bool(body.get("auto_update_enabled")),
        )
        db.session.commit()
    except DeckInstallUpdateError as exc:
        db.session.rollback()
        return _handle_update_error(exc)
    except Exception:
        db.session.rollback()
        raise

    return jsonify(payload)


@marketplace_installations_bp.post("/installations/<install_id>/detach")
@login_required
def detach_installed_deck(install_id: str):
    try:
        payload = deck_install_rebase_service.detach_installed_deck(
            install_id=install_id,
            user_id=current_user.id,
        )
        db.session.commit()
    except DeckInstallUpdateError as exc:
        db.session.rollback()
        return _handle_update_error(exc)
    except Exception:
        db.session.rollback()
        raise

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
        rebase = deck_install_rebase_service.resolve_all_conflicts(
            rebase_id=rebase_id,
            user_id=current_user.id,
            resolution_mode=resolution_mode,
        )
        db.session.commit()
    except DeckInstallUpdateError as exc:
        db.session.rollback()
        return _handle_update_error(exc)
    except Exception:
        db.session.rollback()
        raise

    return jsonify(
        {
            "rebase": deck_install_rebase_service.serialize_rebase(
                rebase,
                include_conflicts=False,
            )
        }
    )

