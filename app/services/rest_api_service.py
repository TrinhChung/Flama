"""Read models shared by the versioned REST API.

The existing Jinja pages remain available during the frontend migration.  This
module converts the same service output used by those pages into stable,
JSON-serializable payloads without moving business logic into API routes.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from flask import url_for

from app.csrf import generate_csrf_token
from app.services import support_donation_service
from app.services.dashboard_service import build_dashboard_data
from app.services.stats_today_future import list_stats_decks
from app.utils.permissions import is_admin_user
from app.validators.support_donation import (
    MAX_DONATION_AMOUNT_MINOR,
    MIN_DONATION_AMOUNT_MINOR,
)

UTC = timezone.utc


def serialize_user(user) -> dict[str, Any] | None:
    if user is None or not bool(getattr(user, "is_authenticated", False)):
        return None

    role = getattr(user, "role", None)
    balance = int(getattr(user, "balance_amount_minor", 0) or 0)
    balance_display = f"{balance:,.0f} ₫".replace(",", ".")
    from app.services.student_verification_service import serialize_student_profile

    student_data = serialize_student_profile(user)
    return {
        "id": int(user.id),
        "email": str(user.email or ""),
        "username": str(user.username or ""),
        "display_name": getattr(user, "display_name", None) or str(user.username or ""),
        "avatar_url": getattr(user, "avatar_url", None),
        "bio": getattr(user, "bio", None) or "",
        "social_links": getattr(user, "social_links", None) or [],
        "timezone": str(getattr(user, "timezone", "UTC") or "UTC"),
        "is_admin": bool(is_admin_user(user)),
        "is_disabled": bool(getattr(user, "is_disabled", False)),
        "balance_amount_minor": balance,
        "balance_amount_display": balance_display,
        "email_verified": bool(student_data["email_verified"]),
        "email_verified_at": student_data["email_verified_at"],
        "email_verification_source": student_data["email_verification_source"],
        "student_status": student_data["student_status"],
        "is_verified_student": bool(student_data["is_verified_student"]),
        "is_edu_email": bool(student_data["is_edu_email"]),
        "role": (
            {
                "id": int(role.id),
                "code": str(role.code or ""),
                "name": str(role.name or ""),
                "is_admin": bool(role.is_admin),
            }
            if role is not None
            else None
        ),
    }


def build_session_payload(user) -> dict[str, Any]:
    authenticated = bool(getattr(user, "is_authenticated", False))
    return {
        "authenticated": authenticated,
        "user": serialize_user(user) if authenticated else None,
        "csrf_token": generate_csrf_token(),
    }


def build_dashboard_payload(user) -> dict[str, Any]:
    rows, total_new, total_learn, total_due, admin_mode = build_dashboard_data(user)
    return {
        "items": [asdict(row) for row in rows],
        "summary": {
            "new": int(total_new),
            "learning": int(total_learn),
            "due": int(total_due),
            "total_due": int(total_new) + int(total_learn) + int(total_due),
        },
        "admin_mode": bool(admin_mode),
        "stats_initial_year": datetime.now(UTC).year,
    }


def build_statistics_bootstrap_payload(
    *,
    user_id: int,
    requested_deck_id: int | None,
) -> dict[str, Any]:
    decks = list_stats_decks(user_id)
    deck_ids = {int(deck["id"]) for deck in decks}
    selected_deck_id = requested_deck_id
    if selected_deck_id not in deck_ids:
        selected_deck_id = int(decks[0]["id"]) if decks else None

    return {
        "decks": decks,
        "selected_deck_id": selected_deck_id,
    }


def build_support_donation_payload() -> dict[str, Any]:
    row = support_donation_service.get_latest_config()
    has_qr_image = bool(row is not None and row.qr_image_storage_path)
    return {
        "configured": row is not None,
        "title": (
            str(row.title or support_donation_service.DEFAULT_TITLE)
            if row is not None
            else support_donation_service.DEFAULT_TITLE
        ),
        "description": (
            str(row.description or support_donation_service.DEFAULT_DESCRIPTION)
            if row is not None
            else support_donation_service.DEFAULT_DESCRIPTION
        ),
        "account_name": str(row.account_name or "") if row is not None else "",
        "account_number": str(row.account_number or "") if row is not None else "",
        "thank_you_message": (
            str(row.thank_you_message or support_donation_service.DEFAULT_THANK_YOU)
            if row is not None
            else support_donation_service.DEFAULT_THANK_YOU
        ),
        "qr_image_url": url_for("main.support_donation_qr_image") if has_qr_image else None,
        "limits": {
            "min_amount_minor": int(MIN_DONATION_AMOUNT_MINOR),
            "max_amount_minor": int(MAX_DONATION_AMOUNT_MINOR),
            "suggested_amounts": list(support_donation_service.get_suggested_amounts()),
        },
        "updated_at": row.updated_at.isoformat() if row is not None and row.updated_at else None,
    }
