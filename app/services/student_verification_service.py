"""Centralized Student Eligibility and Education Domain Policy Service.

Evaluates student status based on verified email domains and extensible educational policy.
The server is the authoritative source of truth for student eligibility.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any

from models.user import User


class StudentStatus(str, Enum):
    """Finite set of student eligibility statuses."""

    NOT_ELIGIBLE = "not_eligible"
    ELIGIBLE_UNVERIFIED_EMAIL = "eligible_unverified_email"
    VERIFIED_STUDENT = "verified_student"


# Standard supported education domain suffixes (extensible for future domains)
SUPPORTED_EDU_SUFFIXES: tuple[str, ...] = (
    ".edu.vn",
)

# Explicitly allowed custom institutions without standard suffix (if any in future)
CUSTOM_EDU_ALLOWLIST: set[str] = set()

# Disallowed / blacklisted forwarding domains (if any)
EDU_DENYLIST: set[str] = set()


def normalize_email(email: str | None) -> str:
    """Sanitize and normalize an email address."""
    if not email:
        return ""
    return str(email).strip().lower()


def extract_email_domain(email: str | None) -> str:
    """Extract domain part from an email address."""
    normalized = normalize_email(email)
    if "@" not in normalized:
        return ""
    parts = normalized.split("@")
    if len(parts) != 2:
        return ""
    return parts[1].strip()


def is_education_email_domain(domain: str | None) -> bool:
    """Check whether a domain matches accepted education institution policies."""
    if not domain:
        return False
    domain = domain.strip().lower()
    if domain in EDU_DENYLIST:
        return False
    if domain in CUSTOM_EDU_ALLOWLIST:
        return True
    return any(
        domain == suffix.lstrip(".") or domain.endswith(suffix)
        for suffix in SUPPORTED_EDU_SUFFIXES
    )


def is_education_email(email: str | None) -> bool:
    """Determine if an email address belongs to a recognized education domain."""
    domain = extract_email_domain(email)
    return is_education_email_domain(domain)


def evaluate_student_status(
    email: str | None,
    *,
    is_email_verified: bool,
) -> StudentStatus:
    """Evaluate student status from email and verified status."""
    if not email or not is_education_email(email):
        return StudentStatus.NOT_ELIGIBLE
    if not is_email_verified:
        return StudentStatus.ELIGIBLE_UNVERIFIED_EMAIL
    return StudentStatus.VERIFIED_STUDENT


def get_user_student_status(user: User | None) -> StudentStatus:
    """Evaluate student status for a user entity."""
    if user is None or not getattr(user, "is_authenticated", False):
        return StudentStatus.NOT_ELIGIBLE
    email = getattr(user, "email", "")
    is_verified = getattr(user, "email_verified_at", None) is not None
    return evaluate_student_status(email, is_email_verified=is_verified)


def is_user_verified_student(user: User | None) -> bool:
    """Check if the user is a fully verified student eligible for discounts."""
    return get_user_student_status(user) == StudentStatus.VERIFIED_STUDENT


def serialize_student_profile(user: User | None) -> dict[str, Any]:
    """Serialize student verification details for user profile & session payloads."""
    if user is None or not getattr(user, "is_authenticated", False):
        return {
            "email_verified": False,
            "email_verified_at": None,
            "email_verification_source": None,
            "student_status": StudentStatus.NOT_ELIGIBLE.value,
            "is_verified_student": False,
            "is_edu_email": False,
            "institution_domain": None,
        }

    email = str(getattr(user, "email", "") or "").strip().lower()
    verified_at = getattr(user, "email_verified_at", None)
    source = getattr(user, "email_verification_source", None)
    is_verified = verified_at is not None
    status = evaluate_student_status(email, is_email_verified=is_verified)
    domain = extract_email_domain(email)
    is_edu = is_education_email_domain(domain)

    return {
        "email_verified": is_verified,
        "email_verified_at": verified_at.isoformat() if verified_at else None,
        "email_verification_source": str(source) if source else None,
        "student_status": status.value,
        "is_verified_student": status == StudentStatus.VERIFIED_STUDENT,
        "is_edu_email": is_edu,
        "institution_domain": domain if is_edu else None,
    }
