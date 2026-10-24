"""Dashboard and statistics REST API V1 routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common import error_response, optional_int_query
from app.repositories.study_authority_repository import StudyAuthorityFenceError
from app.services.rest_api_service import (
    build_dashboard_payload,
    build_statistics_bootstrap_payload,
)
from app.services.stats_overview import (
    build_stats_overview,
    get_effective_timezone_name,
    update_user_timezone_and_commit,
)
from app.services.stats_today_future import (
    build_today_future_stats,
    build_user_study_time_stats,
)
from app.services.study_authority_read_service import StudyAuthorityReadError
from app.services.study_analytics_read_service import analytics_read_transaction
from app.services.analytics_summary_readiness import AnalyticsSummaryNotReady


analytics_bp = Blueprint("api_v1_analytics", __name__)


def _summary_pending_response(exc):
    response, status = error_response(exc.code, str(exc), status=409,
        details=[{"metric": exc.metric, "retry_after_seconds": exc.retry_after_seconds}])
    response.headers["Retry-After"] = str(exc.retry_after_seconds)
    return response, status


def _resolve_request_timezone() -> str:
    client_tz = request.args.get("timezone") or request.headers.get("X-Timezone")
    if client_tz:
        effective = get_effective_timezone_name(client_tz)
        if current_user.is_authenticated and client_tz != getattr(current_user, "timezone", None):
            update_user_timezone_and_commit(current_user, client_tz)
        return effective
    return get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))


@analytics_bp.get("/dashboard")
@login_required
def dashboard():
    try:
        with analytics_read_transaction():
            payload = build_dashboard_payload(current_user)
        return jsonify(payload)
    except AnalyticsSummaryNotReady as exc:
        return _summary_pending_response(exc)
    except (StudyAuthorityFenceError, StudyAuthorityReadError) as exc:
        return error_response(
            str(exc.code),
            str(exc),
            status=409,
        )


@analytics_bp.get("/statistics")
@login_required
def statistics_bootstrap():
    deck_id, query_error = optional_int_query("deck_id")
    if query_error is not None:
        return query_error
    return jsonify(
        build_statistics_bootstrap_payload(
            user_id=current_user.id,
            requested_deck_id=deck_id,
        )
    )


# The heatmap reads only these; MCP keeps the builder's full shape.
_OVERVIEW_DAY_KEYS = ("date", "cards", "minutes", "is_future")
_OVERVIEW_METRIC_KEYS = (
    "daily_average_cards", "days_learned_percent", "longest_streak_days", "current_streak_days",
)


def _overview_response(payload: dict) -> dict:
    today = payload["today"]
    return {
        "year": payload["year"],
        "timezone": payload["timezone"],
        "today": {"date": today["date"], "cards": today["cards"], "minutes": today["minutes"]},
        "heatmap": [{key: day[key] for key in _OVERVIEW_DAY_KEYS} for day in payload["heatmap"]],
        "metrics": {key: payload["metrics"][key] for key in _OVERVIEW_METRIC_KEYS},
    }


@analytics_bp.get("/statistics/overview")
@login_required
def statistics_overview():
    year, query_error = optional_int_query("year")
    if query_error is not None:
        return query_error
    if year is not None and (year < 1970 or year > 2100):
        return error_response(
            "VALIDATION_ERROR",
            "year must be between 1970 and 2100.",
            status=400,
            field="year",
        )

    resolved_tz = _resolve_request_timezone()
    try:
        with analytics_read_transaction():
            payload = build_stats_overview(
                user_id=current_user.id,
                year=year,
                timezone_name=resolved_tz,
            )
    except AnalyticsSummaryNotReady as exc:
        return _summary_pending_response(exc)
    except (StudyAuthorityFenceError, StudyAuthorityReadError) as exc:
        return error_response(
            str(exc.code),
            str(exc),
            status=409,
        )
    return jsonify(_overview_response(payload))


@analytics_bp.get("/statistics/today-future")
@login_required
def statistics_today_future():
    scope = str(request.args.get("scope") or "deck").strip().lower()
    history_range = str(
        request.args.get("history_range") or "12m"
    ).strip().lower()
    future_range = str(
        request.args.get("future_range") or "30"
    ).strip().lower()
    backlog = str(
        request.args.get("backlog") or "false"
    ).strip().lower()
    deck_id, query_error = optional_int_query("deck_id")
    if query_error is not None:
        return query_error

    allowed_values = (
        ("scope", scope, {"deck", "collection"}),
        ("history_range", history_range, {"12m", "all"}),
        ("future_range", future_range, {"30", "90", "365", "all"}),
        (
            "backlog",
            backlog,
            {"0", "1", "true", "false", "yes", "no", "on", "off"},
        ),
    )
    for field_name, value, allowed in allowed_values:
        if value not in allowed:
            return error_response(
                "VALIDATION_ERROR",
                f"Invalid {field_name}.",
                status=400,
                field=field_name,
            )

    resolved_tz = _resolve_request_timezone()
    try:
        with analytics_read_transaction():
            payload = build_today_future_stats(
                user_id=current_user.id,
                timezone_name=resolved_tz,
                scope=scope,
                deck_id=deck_id,
                history_range=history_range,
                future_range=future_range,
                backlog=backlog,
            )
    except AnalyticsSummaryNotReady as exc:
        return _summary_pending_response(exc)
    except (StudyAuthorityFenceError, StudyAuthorityReadError) as exc:
        return error_response(
            str(exc.code),
            str(exc),
            status=409,
        )
    return jsonify(payload)


@analytics_bp.get("/statistics/study-time")
@login_required
def statistics_study_time():
    scope = str(request.args.get("scope") or "deck").strip().lower()
    range_preset = str(request.args.get("range") or "30d").strip().lower()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    deck_id, query_error = optional_int_query("deck_id")
    if query_error is not None:
        return query_error

    if scope not in {"deck", "collection"}:
        return error_response(
            "VALIDATION_ERROR",
            "Invalid scope.",
            status=400,
            field="scope",
        )

    resolved_tz = _resolve_request_timezone()
    try:
        with analytics_read_transaction():
            payload = build_user_study_time_stats(
                user_id=current_user.id, timezone_name=resolved_tz, scope=scope,
                deck_id=deck_id, range_preset=range_preset,
                start_date_str=start_date, end_date_str=end_date,
            )
    except AnalyticsSummaryNotReady as exc:
        return _summary_pending_response(exc)
    return jsonify(payload)
