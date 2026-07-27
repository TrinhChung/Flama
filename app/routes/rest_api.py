"""Versioned REST endpoints used while Jinja screens migrate to a SPA."""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.services import (
    admin_service,
    deck_management_service,
    login_rate_limit_service,
    mcp_access_token_service,
)
from app.services.auth_service import register_user_and_commit
from app.services.payment import (
    dashboard_service as payment_dashboard_service,
    order_query_service,
    transaction_query_service,
)
from app.services.rest_api_service import (
    build_dashboard_payload,
    build_session_payload,
    build_statistics_bootstrap_payload,
    build_support_donation_payload,
)
from app.services import marketplace_hub_service
from app.services.stats_overview import build_stats_overview
from app.services.stats_today_future import build_today_future_stats
from app.utils.permissions import is_admin_user
from app.utils.redirects import resolve_safe_next_url
from app.repositories import vocabulary_repository
from app.validators.payment_query import (
    parse_dashboard_filters,
    parse_order_filters,
    parse_transaction_filters,
)
from models import db
from models.deck import Deck
from models.user import User
from models.user_role import UserRole

rest_api_bp = Blueprint("rest_api", __name__, url_prefix="/api/v1")

DEFAULT_USER_ORDER_PAGE_SIZE = 10
DEFAULT_ADMIN_PAGE_SIZE = 20
MAX_USER_ORDER_PAGE_SIZE = 50
MAX_ADMIN_PAGE_SIZE = 100


def _error(
    code: str,
    message: str,
    *,
    status: int,
    field: str | None = None,
):
    payload = {"error": code, "message": message}
    if field:
        payload["field"] = field
    return jsonify(payload), status


def _json_object():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None
    return payload


def _remote_addr() -> str | None:
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def _require_admin():
    if is_admin_user(current_user):
        return None
    return _error("FORBIDDEN", "Administrator access is required.", status=403)


def _parse_optional_int_query(name: str):
    raw_value = str(request.args.get(name) or "").strip()
    if not raw_value:
        return None, None
    try:
        return int(raw_value), None
    except ValueError:
        return None, _error(
            "VALIDATION_ERROR",
            f"{name} must be an integer.",
            status=400,
            field=name,
        )


def _serialize_deck(deck: Deck) -> dict:
    return {
        "id": int(deck.id),
        "name": str(deck.name or ""),
        "parent_id": int(deck.parent_id) if deck.parent_id is not None else None,
        "owner_user_id": (
            int(deck.owner_user_id) if deck.owner_user_id is not None else None
        ),
        "position": int(deck.position or 0),
        "deleted_at": deck.deleted_at.isoformat() if deck.deleted_at else None,
        "created_at": deck.created_at.isoformat() if deck.created_at else None,
        "updated_at": deck.updated_at.isoformat() if deck.updated_at else None,
    }


def _can_delete_or_reset_deck(deck: Deck) -> bool:
    return bool(
        is_admin_user(current_user)
        or deck.owner_user_id == current_user.id
        or vocabulary_repository.can_user_delete_cloned_deck(
            deck_obj=deck,
            user_id=current_user.id,
        )
    )


@rest_api_bp.get("/session")
def get_session():
    return jsonify(build_session_payload(current_user))


@rest_api_bp.delete("/session")
@login_required
def delete_session():
    logout_user()
    return jsonify(build_session_payload(current_user))


@rest_api_bp.post("/auth/register")
def register():
    if current_user.is_authenticated:
        return _error("ALREADY_AUTHENTICATED", "You are already signed in.", status=409)

    payload = _json_object()
    if payload is None:
        return _error("VALIDATION_ERROR", "Payload must be a JSON object.", status=400)

    email = str(payload.get("email") or "").strip().lower()
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    confirm_password = str(payload.get("confirm_password") or "")

    if not email:
        return _error("VALIDATION_ERROR", "Email is required.", status=400, field="email")
    if not username:
        return _error("VALIDATION_ERROR", "Username is required.", status=400, field="username")
    if not password:
        return _error("VALIDATION_ERROR", "Password is required.", status=400, field="password")
    if password != confirm_password:
        return _error(
            "VALIDATION_ERROR",
            "Password confirmation does not match.",
            status=400,
            field="confirm_password",
        )
    if username.lower() == email:
        return _error(
            "VALIDATION_ERROR",
            "Username must not be the same as email.",
            status=400,
            field="username",
        )

    existing_user = User.query.filter(
        (User.email == email) | (User.username == username)
    ).first()
    if existing_user is not None:
        return _error(
            "CONFLICT",
            "Email or username already exists.",
            status=409,
        )

    try:
        user = register_user_and_commit(email, username, password)
    except IntegrityError:
        db.session.rollback()
        return _error(
            "CONFLICT",
            "Email or username already exists.",
            status=409,
        )
    except SQLAlchemyError:
        db.session.rollback()
        return _error("DB_ERROR", "Could not create the user.", status=500)

    return (
        jsonify(
            {
                "created": True,
                "user": {
                    "id": int(user.id),
                    "email": str(user.email),
                    "username": str(user.username),
                },
            }
        ),
        201,
    )


@rest_api_bp.post("/auth/login")
def login():
    if current_user.is_authenticated:
        return jsonify(
            {
                **build_session_payload(current_user),
                "next_url": resolve_safe_next_url(None, default_endpoint="main.dashboard"),
            }
        )

    payload = _json_object()
    if payload is None:
        return _error("VALIDATION_ERROR", "Payload must be a JSON object.", status=400)

    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    if not email:
        return _error("VALIDATION_ERROR", "Email is required.", status=400, field="email")
    if not password:
        return _error("VALIDATION_ERROR", "Password is required.", status=400, field="password")

    remote_addr = _remote_addr()
    lockout_remaining = login_rate_limit_service.get_lockout_remaining(
        email=email,
        remote_addr=remote_addr,
    )
    if lockout_remaining > 0:
        return (
            jsonify(
                {
                    "error": "LOGIN_RATE_LIMITED",
                    "message": "Too many login attempts. Please try again later.",
                    "retry_after_seconds": int(lockout_remaining),
                }
            ),
            429,
        )

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        login_rate_limit_service.register_failure(email=email, remote_addr=remote_addr)
        return _error("INVALID_CREDENTIALS", "Invalid email or password.", status=401)

    if not login_user(user):
        login_rate_limit_service.register_failure(email=email, remote_addr=remote_addr)
        return _error("USER_DISABLED", "This account is disabled.", status=403)

    login_rate_limit_service.register_success(email=email, remote_addr=remote_addr)
    next_url = resolve_safe_next_url(
        payload.get("next"),
        default_endpoint="main.dashboard",
    )
    return jsonify({**build_session_payload(current_user), "next_url": next_url})


@rest_api_bp.get("/dashboard")
@login_required
def dashboard():
    return jsonify(build_dashboard_payload(current_user))


@rest_api_bp.post("/decks")
@login_required
def create_deck():
    payload = _json_object()
    if payload is None:
        return _error("VALIDATION_ERROR", "Payload must be a JSON object.", status=400)

    parent_id_raw = str(payload.get("parent_id") or "").strip()
    deck_path_raw = str(payload.get("path") or payload.get("deck_path") or "").strip()
    deck_name = str(payload.get("name") or "").strip() or "New Deck"
    admin_mode = is_admin_user(current_user)

    parent_resolution = vocabulary_repository.resolve_create_deck_parent(
        parent_id_raw=parent_id_raw,
        user_id=current_user.id,
        admin_mode=admin_mode,
    )
    if parent_resolution.error:
        return _error(
            "VALIDATION_ERROR",
            parent_resolution.error,
            status=400,
            field="parent_id",
        )

    path_tokens = vocabulary_repository.parse_create_deck_tokens(
        deck_path_raw=deck_path_raw,
        fallback_name=deck_name,
    )
    path_tokens = vocabulary_repository.normalize_create_deck_tokens_for_parent(
        path_tokens=path_tokens,
        parent_path_tokens=vocabulary_repository.deck_name_path_tokens(
            parent_resolution.parent_deck
        ),
        fallback_name=deck_name,
    )

    try:
        result = vocabulary_repository.upsert_deck_path(
            parent_id=parent_resolution.parent_id,
            path_tokens=path_tokens,
            owner_user_id=current_user.id,
            admin_mode=admin_mode,
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return _error("DB_ERROR", "Could not create the deck.", status=500)

    status = 201 if result.created_count else 200
    return (
        jsonify(
            {
                "created_count": int(result.created_count),
                "created_names": list(result.created_names),
                "path": list(result.path_tokens),
                "item": (
                    _serialize_deck(result.final_deck)
                    if result.final_deck is not None
                    else None
                ),
            }
        ),
        status,
    )


@rest_api_bp.patch("/decks/<int:deck_id>")
@login_required
def update_deck(deck_id: int):
    guard = _require_admin()
    if guard is not None:
        return guard

    deck = db.session.get(Deck, deck_id)
    if deck is None or deck.deleted_at is not None:
        return _error("NOT_FOUND", "Deck not found.", status=404)
    payload = _json_object()
    if payload is None:
        return _error("VALIDATION_ERROR", "Payload must be a JSON object.", status=400)

    changed = False
    if "name" in payload:
        new_name = str(payload.get("name") or "").strip()
        if not new_name:
            return _error(
                "VALIDATION_ERROR",
                "Deck name is required.",
                status=400,
                field="name",
            )
        if vocabulary_repository.deck_name_exists_under_parent(
            parent_id=deck.parent_id,
            name=new_name,
            exclude_deck_id=deck.id,
        ):
            return _error(
                "CONFLICT",
                "A deck with this name already exists at the selected level.",
                status=409,
                field="name",
            )
        if new_name != deck.name:
            deck.name = new_name
            changed = True

    if "parent_id" in payload:
        raw_parent_id = payload.get("parent_id")
        new_parent_id = None
        if raw_parent_id not in (None, ""):
            try:
                new_parent_id = int(raw_parent_id)
            except (TypeError, ValueError):
                return _error(
                    "VALIDATION_ERROR",
                    "parent_id must be an integer or null.",
                    status=400,
                    field="parent_id",
                )

        new_parent = db.session.get(Deck, new_parent_id) if new_parent_id else None
        if new_parent_id is not None and (
            new_parent is None or new_parent.deleted_at is not None
        ):
            return _error("NOT_FOUND", "Parent deck not found.", status=404)

        cursor = new_parent
        while cursor is not None:
            if cursor.id == deck.id:
                return _error(
                    "VALIDATION_ERROR",
                    "A deck cannot be moved into itself or its descendants.",
                    status=400,
                    field="parent_id",
                )
            cursor = cursor.parent

        if vocabulary_repository.deck_name_exists_under_parent(
            parent_id=new_parent_id,
            name=deck.name,
            exclude_deck_id=deck.id,
        ):
            return _error(
                "CONFLICT",
                "The destination already contains a deck with this name.",
                status=409,
                field="parent_id",
            )
        if deck.parent_id != new_parent_id:
            deck.parent_id = new_parent_id
            deck.position = vocabulary_repository.next_deck_position(new_parent_id)
            changed = True

    if not changed:
        return jsonify({"changed": False, "item": _serialize_deck(deck)})

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return _error("DB_ERROR", "Could not update the deck.", status=500)
    return jsonify({"changed": True, "item": _serialize_deck(deck)})


@rest_api_bp.delete("/decks/<int:deck_id>")
@login_required
def delete_deck(deck_id: int):
    deck = db.session.get(Deck, deck_id)
    if deck is None or deck.deleted_at is not None:
        return _error("NOT_FOUND", "Deck not found.", status=404)
    if not _can_delete_or_reset_deck(deck):
        return _error("FORBIDDEN", "You cannot delete this deck.", status=403)

    try:
        deletion_mode = deck_management_service.delete_deck_subtree(
            deck_obj=deck,
            user_id=current_user.id,
            is_admin=is_admin_user(current_user),
        )
    except SQLAlchemyError:
        db.session.rollback()
        return _error("DB_ERROR", "Could not delete the deck.", status=500)
    return jsonify({"deleted": True, "mode": deletion_mode, "id": deck_id})


@rest_api_bp.post("/decks/<int:deck_id>/progress-reset")
@login_required
def reset_deck_progress(deck_id: int):
    deck = db.session.get(Deck, deck_id)
    if deck is None or deck.deleted_at is not None:
        return _error("NOT_FOUND", "Deck not found.", status=404)
    if not _can_delete_or_reset_deck(deck):
        return _error("FORBIDDEN", "You cannot reset this deck.", status=403)

    try:
        deleted_count = deck_management_service.reset_deck_progress(
            deck_obj=deck,
            user_id=current_user.id,
        )
    except SQLAlchemyError:
        db.session.rollback()
        return _error("DB_ERROR", "Could not reset deck progress.", status=500)
    return jsonify(
        {
            "reset": True,
            "deck_id": int(deck.id),
            "deleted_progress_count": int(deleted_count),
        }
    )


@rest_api_bp.get("/marketplace/installed-decks")
@login_required
def installed_decks():
    return jsonify(
        marketplace_hub_service.build_installed_deck_workspace(
            user_id=current_user.id
        )
    )


@rest_api_bp.get("/statistics")
@login_required
def statistics_bootstrap():
    deck_id, error_response = _parse_optional_int_query("deck_id")
    if error_response is not None:
        return error_response
    return jsonify(
        build_statistics_bootstrap_payload(
            user_id=current_user.id,
            requested_deck_id=deck_id,
        )
    )


@rest_api_bp.get("/statistics/overview")
@login_required
def statistics_overview():
    year, error_response = _parse_optional_int_query("year")
    if error_response is not None:
        return error_response
    if year is not None and (year < 1970 or year > 2100):
        return _error(
            "VALIDATION_ERROR",
            "year must be between 1970 and 2100.",
            status=400,
            field="year",
        )

    return jsonify(
        build_stats_overview(
            user_id=current_user.id,
            year=year,
            timezone_name=getattr(current_user, "timezone", "UTC"),
        )
    )


@rest_api_bp.get("/statistics/today-future")
@login_required
def statistics_today_future():
    scope = str(request.args.get("scope") or "deck").strip().lower()
    history_range = str(request.args.get("history_range") or "12m").strip().lower()
    future_range = str(request.args.get("future_range") or "30").strip().lower()
    backlog = str(request.args.get("backlog") or "false").strip().lower()
    deck_id, error_response = _parse_optional_int_query("deck_id")
    if error_response is not None:
        return error_response

    allowed_values = (
        ("scope", scope, {"deck", "collection"}),
        ("history_range", history_range, {"12m", "all"}),
        ("future_range", future_range, {"30", "90", "365", "all"}),
        ("backlog", backlog, {"0", "1", "true", "false", "yes", "no", "on", "off"}),
    )
    for field_name, value, allowed in allowed_values:
        if value not in allowed:
            return _error(
                "VALIDATION_ERROR",
                f"Invalid {field_name}.",
                status=400,
                field=field_name,
            )

    return jsonify(
        build_today_future_stats(
            user_id=current_user.id,
            timezone_name=getattr(current_user, "timezone", "UTC"),
            scope=scope,
            deck_id=deck_id,
            history_range=history_range,
            future_range=future_range,
            backlog=backlog,
        )
    )


@rest_api_bp.get("/support-donation")
def support_donation():
    return jsonify(build_support_donation_payload())


@rest_api_bp.get("/orders")
@login_required
def list_user_orders():
    filters = parse_order_filters(request.args)
    page = admin_service.coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = admin_service.coerce_int(
        request.args.get("per_page"),
        default=DEFAULT_USER_ORDER_PAGE_SIZE,
        minimum=1,
        maximum=MAX_USER_ORDER_PAGE_SIZE,
    )
    payload = order_query_service.list_user_orders(
        user_id=current_user.id,
        filters=filters,
        page=page,
        per_page=per_page,
    )
    payload["filters"] = asdict(filters)
    return jsonify(payload)


@rest_api_bp.get("/orders/<order_id>")
@login_required
def get_user_order(order_id: str):
    payload = order_query_service.get_user_order_detail(
        order_id=order_id,
        user_id=current_user.id,
    )
    if payload is None:
        return _error("NOT_FOUND", "Order not found.", status=404)
    return jsonify(payload)


@rest_api_bp.get("/admin/payments")
@login_required
def admin_payment_dashboard():
    guard = _require_admin()
    if guard is not None:
        return guard
    filters = parse_dashboard_filters(request.args)
    payload = payment_dashboard_service.build_admin_dashboard(filters=filters)
    payload["filters"] = asdict(filters)
    return jsonify(payload)


@rest_api_bp.get("/admin/users")
@login_required
def list_admin_users():
    guard = _require_admin()
    if guard is not None:
        return guard

    search_term = str(request.args.get("q") or "").strip()
    if len(search_term) > 120:
        return _error(
            "VALIDATION_ERROR",
            "q must not exceed 120 characters.",
            status=400,
            field="q",
        )
    status_filter = admin_service.normalize_status_filter(request.args.get("status"))
    page = admin_service.coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = admin_service.coerce_int(
        request.args.get("per_page"),
        default=10,
        minimum=1,
        maximum=50,
    )

    pagination = admin_service.build_users_query(
        search_term=search_term,
        status_filter=status_filter,
    ).paginate(page=page, per_page=per_page, error_out=False)
    roles = UserRole.query.order_by(UserRole.position.asc(), UserRole.id.asc()).all()
    return jsonify(
        {
            "items": [
                admin_service.serialize_user_row(user)
                for user in pagination.items
            ],
            "page": pagination.page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": max(pagination.pages, 1),
            "summary": admin_service.load_user_summary(),
            "filters": {
                "q": search_term,
                "status": status_filter,
            },
            "roles": [
                {
                    "id": int(role.id),
                    "code": str(role.code or ""),
                    "name": str(role.name or ""),
                    "description": str(role.description or ""),
                    "is_admin": bool(role.is_admin),
                    "position": int(role.position or 0),
                }
                for role in roles
            ],
        }
    )


@rest_api_bp.patch("/admin/users/<int:user_id>")
@login_required
def update_admin_user(user_id: int):
    guard = _require_admin()
    if guard is not None:
        return guard
    payload = _json_object()
    if payload is None:
        return _error("VALIDATION_ERROR", "Payload must be a JSON object.", status=400)

    user = db.session.get(User, user_id)
    if user is None:
        return _error("NOT_FOUND", "User not found.", status=404)

    fields_present = {
        field_name for field_name in ("role_id", "is_disabled") if field_name in payload
    }
    if len(fields_present) != 1:
        return _error(
            "VALIDATION_ERROR",
            "Provide exactly one of role_id or is_disabled.",
            status=400,
        )

    result_rows: list[dict] = []
    if "role_id" in payload:
        try:
            role_id = int(payload.get("role_id"))
        except (TypeError, ValueError):
            return _error(
                "VALIDATION_ERROR",
                "role_id must be an integer.",
                status=400,
                field="role_id",
            )
        target_role = db.session.get(UserRole, role_id)
        if target_role is None:
            return _error("NOT_FOUND", "Role not found.", status=404)
        _, fail_count, role_results = admin_service.batch_assign_roles(
            actor_user_id=current_user.id,
            user_ids=[user_id],
            target_role=target_role,
        )
        result_rows.extend(role_results)
        if fail_count:
            return (
                jsonify(
                    {
                        "error": "UPDATE_REJECTED",
                        "message": role_results[0]["message"],
                        "results": result_rows,
                    }
                ),
                409,
            )

    if "is_disabled" in payload:
        raw_disabled = payload.get("is_disabled")
        if not isinstance(raw_disabled, bool):
            return _error(
                "VALIDATION_ERROR",
                "is_disabled must be a boolean.",
                status=400,
                field="is_disabled",
            )
        action = "disable" if raw_disabled else "activate"
        _, fail_count, status_results = admin_service.batch_update_status(
            actor_user_id=current_user.id,
            user_ids=[user_id],
            action=action,
        )
        result_rows.extend(status_results)
        if fail_count:
            return (
                jsonify(
                    {
                        "error": "UPDATE_REJECTED",
                        "message": status_results[0]["message"],
                        "results": result_rows,
                    }
                ),
                409,
            )

    refreshed_user = db.session.get(User, user_id)
    return jsonify(
        {
            "item": admin_service.serialize_user_row(refreshed_user),
            "results": result_rows,
        }
    )


@rest_api_bp.get("/admin/payments/orders")
@login_required
def list_admin_orders():
    guard = _require_admin()
    if guard is not None:
        return guard
    filters = parse_order_filters(request.args)
    page = admin_service.coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = admin_service.coerce_int(
        request.args.get("per_page"),
        default=DEFAULT_ADMIN_PAGE_SIZE,
        minimum=1,
        maximum=MAX_ADMIN_PAGE_SIZE,
    )
    payload = order_query_service.list_admin_orders(
        filters=filters,
        page=page,
        per_page=per_page,
    )
    payload["filters"] = asdict(filters)
    return jsonify(payload)


@rest_api_bp.get("/admin/payments/orders/<order_id>")
@login_required
def get_admin_order(order_id: str):
    guard = _require_admin()
    if guard is not None:
        return guard
    payload = order_query_service.get_admin_order_detail(order_id)
    if payload is None:
        return _error("NOT_FOUND", "Order not found.", status=404)
    return jsonify(payload)


@rest_api_bp.get("/admin/payments/transactions")
@login_required
def list_admin_transactions():
    guard = _require_admin()
    if guard is not None:
        return guard
    filters = parse_transaction_filters(request.args)
    page = admin_service.coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = admin_service.coerce_int(
        request.args.get("per_page"),
        default=DEFAULT_ADMIN_PAGE_SIZE,
        minimum=1,
        maximum=MAX_ADMIN_PAGE_SIZE,
    )
    payload = transaction_query_service.list_admin_transactions(
        filters=filters,
        page=page,
        per_page=per_page,
    )
    payload["filters"] = asdict(filters)
    return jsonify(payload)


@rest_api_bp.get("/admin/payments/transactions/<attempt_id>")
@login_required
def get_admin_transaction(attempt_id: str):
    guard = _require_admin()
    if guard is not None:
        return guard
    payload = transaction_query_service.get_admin_transaction_detail(attempt_id)
    if payload is None:
        return _error("NOT_FOUND", "Transaction not found.", status=404)
    return jsonify(payload)


@rest_api_bp.get("/mcp-tokens")
@login_required
def list_mcp_tokens():
    guard = _require_admin()
    if guard is not None:
        return guard
    return jsonify(
        {
            "items": mcp_access_token_service.list_token_summaries(user_id=current_user.id),
            "policy": mcp_access_token_service.get_token_policy(),
        }
    )


@rest_api_bp.post("/mcp-tokens")
@login_required
def create_mcp_token():
    guard = _require_admin()
    if guard is not None:
        return guard
    try:
        issued_token = mcp_access_token_service.issue_short_lived_token(
            user_id=current_user.id
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return _error("DB_ERROR", "Could not create the MCP token.", status=500)
    return jsonify({"item": issued_token.to_display_payload()}), 201


@rest_api_bp.delete("/mcp-tokens/<int:token_id>")
@login_required
def delete_mcp_token(token_id: int):
    guard = _require_admin()
    if guard is not None:
        return guard
    try:
        revoked = mcp_access_token_service.revoke_token(
            user_id=current_user.id,
            token_id=token_id,
        )
        if not revoked:
            db.session.rollback()
            return _error("NOT_FOUND", "MCP token not found.", status=404)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return _error("DB_ERROR", "Could not revoke the MCP token.", status=500)
    return "", 204
