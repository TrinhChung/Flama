"""Administrative Analytics & Growth REST API V1 routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.api.common import admin_required, error_response
from app.services import admin_analytics_service

admin_analytics_bp = Blueprint("api_v1_admin_analytics", __name__)


def _extract_range_args():
    preset = request.args.get("range", "7d")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    return preset, start_date, end_date


@admin_analytics_bp.get("/overview")
@admin_required
def get_analytics_overview():
    """Return top-level growth KPIs and % deltas."""
    preset, start_date, end_date = _extract_range_args()
    try:
        data = admin_analytics_service.get_analytics_overview(
            range_preset=preset,
            start_date_str=start_date,
            end_date_str=end_date,
        )
        return jsonify(data)
    except Exception as exc:
        return error_response(
            "ANALYTICS_QUERY_ERROR",
            str(exc),
            status=500,
        )


@admin_analytics_bp.get("/growth")
@admin_required
def get_user_growth():
    """Return user registration, cumulative users, and daily active user time series."""
    preset, start_date, end_date = _extract_range_args()
    try:
        data = admin_analytics_service.get_user_growth_analytics(
            range_preset=preset,
            start_date_str=start_date,
            end_date_str=end_date,
        )
        return jsonify(data)
    except Exception as exc:
        return error_response(
            "ANALYTICS_QUERY_ERROR",
            str(exc),
            status=500,
        )


@admin_analytics_bp.get("/study-time")
@admin_required
def get_study_time():
    """Return daily average study time per user, 24-hour peak heatmap, and study mode breakdowns."""
    preset, start_date, end_date = _extract_range_args()
    try:
        data = admin_analytics_service.get_study_time_analytics(
            range_preset=preset,
            start_date_str=start_date,
            end_date_str=end_date,
        )
        return jsonify(data)
    except Exception as exc:
        return error_response(
            "ANALYTICS_QUERY_ERROR",
            str(exc),
            status=500,
        )


@admin_analytics_bp.get("/content-growth")
@admin_required
def get_content_growth():
    """Return daily content creation (decks, notes, cards) and Yomitan/Anki imports."""
    preset, start_date, end_date = _extract_range_args()
    try:
        data = admin_analytics_service.get_content_growth_analytics(
            range_preset=preset,
            start_date_str=start_date,
            end_date_str=end_date,
        )
        return jsonify(data)
    except Exception as exc:
        return error_response(
            "ANALYTICS_QUERY_ERROR",
            str(exc),
            status=500,
        )


@admin_analytics_bp.get("/retention-cohorts")
@admin_required
def get_retention_cohorts():
    """Return user retention cohorts matrix across registration weeks."""
    num_weeks_raw = request.args.get("weeks", 8)
    try:
        num_weeks = max(2, min(24, int(num_weeks_raw)))
    except (TypeError, ValueError):
        num_weeks = 8

    try:
        data = admin_analytics_service.get_retention_cohorts_analytics(num_weeks=num_weeks)
        return jsonify(data)
    except Exception as exc:
        return error_response(
            "ANALYTICS_QUERY_ERROR",
            str(exc),
            status=500,
        )
