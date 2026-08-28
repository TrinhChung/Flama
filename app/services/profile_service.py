"""Application service for User Profile and Account Management."""

from __future__ import annotations

from io import BytesIO
import logging
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from flask import current_app
from PIL import Image, ImageOps
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.email.address import mask_email
from app.email.constants import EmailCategory, TemplateKey
from app.email.contracts import TransactionalEmailRequest
from app.services import (
    email_verification_service,
    password_change_rate_limit_service,
    wallet_service,
)
from app.email import get_email_service
from app.services.student_verification_service import (
    normalize_email,
    serialize_student_profile,
)
from app.settings import BASE_DIR
from app.validators.password import validate_password_policy
from models import db
from models.deck_change_request import DeckChangeRequest
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note_type import NoteType
from models.user import User

logger = logging.getLogger(__name__)

ALLOWED_SOCIAL_PLATFORMS = {
    "website",
    "github",
    "youtube",
    "facebook",
    "x",
    "twitter",
    "linkedin",
    "instagram",
    "discord",
    "other",
}


class ProfileServiceError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.field = field


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def format_vnd_price(amount_minor: int) -> str:
    if amount_minor <= 0:
        return "Miễn phí"
    return f"{amount_minor:,.0f} ₫".replace(",", ".")


def get_creator_stats(user_id: int) -> dict[str, Any]:
    """Calculate aggregated creator metrics for published decks, installs, and contributions."""
    deck_stats = (
        db.session.query(
            func.count(DeckMarketplaceItem.id).label("created_decks_count"),
            func.coalesce(func.sum(DeckMarketplaceItem.install_count), 0).label("total_installs_count"),
            func.coalesce(func.sum(DeckMarketplaceItem.rating_count), 0).label("total_rating_count"),
            func.coalesce(func.avg(DeckMarketplaceItem.rating_avg), 0.0).label("avg_rating"),
        )
        .filter(
            DeckMarketplaceItem.owner_user_id == user_id,
            DeckMarketplaceItem.publish_status == "published",
        )
        .one()
    )

    note_types_count = (
        db.session.query(func.count(NoteType.id))
        .filter(
            NoteType.user_id == user_id,
            NoteType.publish_status == "published",
        )
        .scalar()
        or 0
    )

    merged_contributions_count = (
        db.session.query(func.count(DeckChangeRequest.id))
        .filter(
            DeckChangeRequest.requester_user_id == user_id,
            DeckChangeRequest.status == "merged",
        )
        .scalar()
        or 0
    )

    total_contributions_count = (
        db.session.query(func.count(DeckChangeRequest.id))
        .filter(
            DeckChangeRequest.requester_user_id == user_id,
        )
        .scalar()
        or 0
    )

    return {
        "created_decks_count": int(deck_stats.created_decks_count or 0),
        "created_note_types_count": int(note_types_count),
        "total_installs_count": int(deck_stats.total_installs_count or 0),
        "rating_count": int(deck_stats.total_rating_count or 0),
        "rating_avg": round(float(deck_stats.avg_rating or 0.0), 1),
        "contributions_merged_count": int(merged_contributions_count),
        "total_contributions_count": int(total_contributions_count),
    }


def get_user_badges(user: User, stats: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute badges earned based on verified system attributes and activities."""
    badges: list[dict[str, Any]] = []

    if user.is_admin:
        badges.append({
            "id": "admin",
            "code": "admin",
            "name": "Quản trị viên",
            "description": "Quản trị viên hệ thống Flama.",
            "icon": "Shield",
            "tier": "system",
        })

    is_creator = stats["created_decks_count"] > 0 or stats["created_note_types_count"] > 0 or (user.role and user.role.code == "creator")
    if is_creator:
        badges.append({
            "id": "creator",
            "code": "creator",
            "name": "Nhà sáng tạo",
            "description": "Đã xuất bản học liệu chất lượng lên Flama Marketplace.",
            "icon": "Sparkles",
            "tier": "creator",
        })

    if stats["total_installs_count"] >= 50 or (stats["rating_avg"] >= 4.5 and stats["rating_count"] >= 5):
        badges.append({
            "id": "top_creator",
            "code": "top_creator",
            "name": "Tác giả nổi bật",
            "description": "Học liệu đạt số lượng người học và đánh giá xuất sắc.",
            "icon": "Award",
            "tier": "highlight",
        })

    if stats["contributions_merged_count"] > 0:
        badges.append({
            "id": "contributor",
            "code": "contributor",
            "name": "Cộng tác viên",
            "description": f"Đã đóng góp {stats['contributions_merged_count']} cải tiến được duyệt cho các bộ thẻ cộng đồng.",
            "icon": "GitPullRequest",
            "tier": "community",
        })

    student_data = serialize_student_profile(user)
    if student_data.get("is_verified_student"):
        badges.append({
            "id": "verified_student",
            "code": "verified_student",
            "name": "Sinh viên xác thực",
            "description": f"Sinh viên trường đại học ({student_data.get('institution_domain') or 'Đối tác Flama'}).",
            "icon": "GraduationCap",
            "tier": "verified",
        })

    return badges


def serialize_public_deck_item(item: DeckMarketplaceItem) -> dict[str, Any]:
    price_minor = int(item.price_amount_minor or 0)
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description or "",
        "primary_category": item.primary_category or "General",
        "tags": item.tags or [],
        "sample_cards_count": int(item.sample_cards_count or 0),
        "pricing_mode": item.pricing_mode,
        "price_amount_minor": price_minor,
        "price_display": format_vnd_price(price_minor),
        "install_count": int(item.install_count or 0),
        "rating_avg": round(float(item.rating_avg or 0.0), 1),
        "rating_count": int(item.rating_count or 0),
        "version": item.version or "1.0.0",
        "published_at": _iso(item.published_at),
        "updated_at": _iso(item.updated_at),
    }


def serialize_public_note_type_item(item: NoteType) -> dict[str, Any]:
    price_minor = int(item.price_amount_minor or 0)
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description or "",
        "primary_category": item.primary_category or "General",
        "tags": item.tags or [],
        "preview_text": item.preview_text,
        "pricing_mode": item.pricing_mode,
        "price_amount_minor": price_minor,
        "price_display": format_vnd_price(price_minor),
        "install_count": int(item.install_count or 0),
        "rating_avg": round(float(item.rating_avg or 0.0), 1),
        "rating_count": int(item.rating_count or 0),
        "version": item.version or "1.0.0",
        "published_at": _iso(item.published_at),
        "updated_at": _iso(item.updated_at),
    }


def serialize_public_contribution_item(cr: DeckChangeRequest) -> dict[str, Any]:
    deck_title = "Bộ thẻ cộng đồng"
    if cr.deck_item:
        deck_title = cr.deck_item.title
    elif cr.source_deck:
        deck_title = cr.source_deck.name

    return {
        "id": cr.id,
        "title": cr.title or "Đóng góp cải tiến",
        "description": cr.description or "",
        "status": cr.status,
        "deck_item_id": cr.deck_item_id,
        "deck_title": deck_title,
        "merged_at": _iso(cr.merged_at),
        "created_at": _iso(cr.created_at),
    }


def get_profile_payload(user: User) -> dict[str, Any]:
    role = getattr(user, "role", None)
    student_data = serialize_student_profile(user)
    stats = get_creator_stats(user.id)
    badges = get_user_badges(user, stats)
    wallet_summary = wallet_service.get_user_wallet_summary(user)

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": getattr(user, "display_name", None) or user.username,
            "email": user.email,
            "avatar_url": getattr(user, "avatar_url", None),
            "bio": getattr(user, "bio", None) or "",
            "social_links": getattr(user, "social_links", None) or [],
            "timezone": getattr(user, "timezone", "UTC") or "UTC",
            "is_admin": bool(user.is_admin),
            "is_disabled": bool(getattr(user, "is_disabled", False)),
            "created_at": _iso(getattr(user, "created_at", None)),
            "email_verified": bool(student_data["email_verified"]),
            "email_verified_at": student_data["email_verified_at"],
            "email_verification_source": student_data["email_verification_source"],
            "student_status": student_data["student_status"],
            "is_verified_student": bool(student_data["is_verified_student"]),
            "is_edu_email": bool(student_data["is_edu_email"]),
            "institution_domain": student_data["institution_domain"],
            "has_password": getattr(
                user,
                "has_password",
                bool(getattr(user, "password_hash", None) and str(user.password_hash).strip()),
            ),
            "role": (
                {
                    "id": role.id,
                    "code": role.code,
                    "name": role.name,
                    "description": role.description,
                    "is_admin": bool(role.is_admin),
                }
                if role is not None
                else None
            ),
        },
        "creator_stats": stats,
        "badges": badges,
        "wallet": wallet_summary,
    }


def get_public_profile(username: str, current_user_id: int | None = None) -> dict[str, Any]:
    """Retrieve public creator/contributor profile with published decks and achievements."""
    clean_username = username.strip()
    user = User.query.filter(func.lower(User.username) == clean_username.lower()).first()
    if user is None:
        raise ProfileServiceError("USER_NOT_FOUND", "Không tìm thấy người dùng này.", status=404)

    is_own_profile = (current_user_id is not None and user.id == current_user_id)
    stats = get_creator_stats(user.id)
    badges = get_user_badges(user, stats)

    # Published Decks
    published_decks = (
        DeckMarketplaceItem.query.filter(
            DeckMarketplaceItem.owner_user_id == user.id,
            DeckMarketplaceItem.publish_status == "published",
        )
        .order_by(DeckMarketplaceItem.install_count.desc(), DeckMarketplaceItem.updated_at.desc())
        .all()
    )

    # Published Note Types
    published_note_types = (
        NoteType.query.filter(
            NoteType.user_id == user.id,
            NoteType.publish_status == "published",
        )
        .order_by(NoteType.install_count.desc(), NoteType.updated_at.desc())
        .all()
    )

    # Public Merged Contributions
    contributions = (
        DeckChangeRequest.query.filter(
            DeckChangeRequest.requester_user_id == user.id,
            DeckChangeRequest.status == "merged",
        )
        .order_by(DeckChangeRequest.merged_at.desc(), DeckChangeRequest.updated_at.desc())
        .limit(20)
        .all()
    )

    role = getattr(user, "role", None)
    student_data = serialize_student_profile(user)

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": getattr(user, "display_name", None) or user.username,
            "avatar_url": getattr(user, "avatar_url", None),
            "bio": getattr(user, "bio", None) or "",
            "social_links": getattr(user, "social_links", None) or [],
            "created_at": _iso(getattr(user, "created_at", None)),
            "is_admin": bool(user.is_admin),
            "is_verified_student": bool(student_data.get("is_verified_student")),
            "role": (
                {
                    "id": role.id,
                    "code": role.code,
                    "name": role.name,
                    "description": role.description,
                    "is_admin": bool(role.is_admin),
                }
                if role is not None
                else None
            ),
        },
        "stats": stats,
        "badges": badges,
        "published_decks": [serialize_public_deck_item(d) for d in published_decks],
        "published_note_types": [serialize_public_note_type_item(nt) for nt in published_note_types],
        "contributions": [serialize_public_contribution_item(cr) for cr in contributions],
        "is_own_profile": is_own_profile,
    }


def validate_social_links(raw_links: Any) -> list[dict[str, str]]:
    if raw_links is None:
        return []
    if not isinstance(raw_links, list):
        raise ProfileServiceError("VALIDATION_ERROR", "social_links phải là một danh sách liên kết.", status=400, field="social_links")
    if len(raw_links) > 10:
        raise ProfileServiceError("VALIDATION_ERROR", "Tối đa 10 liên kết mạng xã hội.", status=400, field="social_links")

    clean_links: list[dict[str, str]] = []
    for idx, item in enumerate(raw_links):
        if not isinstance(item, dict):
            raise ProfileServiceError("VALIDATION_ERROR", f"Liên kết #{idx+1} không đúng định dạng.", status=400, field="social_links")
        platform = str(item.get("type") or "other").strip().lower()
        if platform not in ALLOWED_SOCIAL_PLATFORMS:
            platform = "other"

        url = str(item.get("url") or "").strip()
        if not url:
            continue

        if len(url) > 500:
            raise ProfileServiceError("VALIDATION_ERROR", f"URL liên kết #{idx+1} quá dài (tối đa 500 ký tự).", status=400, field="social_links")

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ProfileServiceError("VALIDATION_ERROR", f"URL liên kết #{idx+1} không hợp lệ (phải bắt đầu bằng http:// hoặc https://).", status=400, field="social_links")

        label = str(item.get("label") or "").strip()[:50]
        clean_links.append({
            "type": platform,
            "url": url,
            "label": label,
        })
    return clean_links


def update_profile(
    user: User, payload: dict[str, Any], *, remote_addr: str | None = None
) -> dict[str, Any]:
    """Update profile attributes like display_name, bio, social_links, timezone and password."""
    next_timezone: str | None = None
    next_password: str | None = None
    next_email: str | None = None
    next_display_name: str | None = None
    next_bio: str | None = None
    next_social_links: list[dict[str, str]] | None = None

    if "display_name" in payload:
        raw_name = str(payload.get("display_name") or "").strip()
        if len(raw_name) > 100:
            raise ProfileServiceError("VALIDATION_ERROR", "Tên hiển thị không được vượt quá 100 ký tự.", status=400, field="display_name")
        next_display_name = raw_name or None

    if "bio" in payload:
        raw_bio = str(payload.get("bio") or "").strip()
        if len(raw_bio) > 500:
            raise ProfileServiceError("VALIDATION_ERROR", "Giới thiệu bản thân không được vượt quá 500 ký tự.", status=400, field="bio")
        next_bio = raw_bio

    if "social_links" in payload:
        next_social_links = validate_social_links(payload.get("social_links"))

    if "email" in payload:
        raw_email = normalize_email(payload.get("email"))
        if raw_email and raw_email != normalize_email(user.email):
            existing = User.query.filter(User.email == raw_email, User.id != user.id).first()
            if existing is not None:
                raise ProfileServiceError(
                    "CONFLICT",
                    "Địa chỉ email này đã được sử dụng bởi một tài khoản khác.",
                    status=409,
                    field="email",
                )
            next_email = raw_email

    if "timezone" in payload:
        tz = str(payload.get("timezone") or "").strip()
        if tz:
            if len(tz) > 64:
                raise ProfileServiceError(
                    "VALIDATION_ERROR",
                    "Timezone must not exceed 64 characters.",
                    status=400,
                    field="timezone",
                )
            next_timezone = tz

    if (
        "current_password" in payload
        or "new_password" in payload
        or "confirm_password" in payload
    ):
        lockout_remaining = password_change_rate_limit_service.get_lockout_remaining(
            user_id=user.id, remote_addr=remote_addr
        )
        if lockout_remaining > 0:
            raise ProfileServiceError(
                "RATE_LIMITED",
                f"Quá nhiều lần thử mật khẩu không chính xác. Vui lòng thử lại sau {lockout_remaining} giây.",
                status=429,
            )

        current_pw = str(payload.get("current_password") or "")
        new_pw = str(payload.get("new_password") or "")
        confirm_pw = str(payload.get("confirm_password") or "")

        if not current_pw:
            raise ProfileServiceError(
                "VALIDATION_ERROR",
                "Current password is required.",
                status=400,
                field="current_password",
            )
        if not new_pw:
            raise ProfileServiceError(
                "VALIDATION_ERROR",
                "New password is required.",
                status=400,
                field="new_password",
            )
        if not confirm_pw:
            raise ProfileServiceError(
                "VALIDATION_ERROR",
                "Password confirmation is required.",
                status=400,
                field="confirm_password",
            )

        if not getattr(user, "has_password", bool(getattr(user, "password_hash", None))):
            raise ProfileServiceError(
                "PASSWORD_NOT_SET",
                "This account does not have a password configured.",
                status=400,
            )

        if not user.check_password(current_pw):
            password_change_rate_limit_service.register_failure(
                user_id=user.id, remote_addr=remote_addr
            )
            raise ProfileServiceError(
                "INVALID_CURRENT_PASSWORD",
                "Current password is incorrect.",
                status=400,
                field="current_password",
            )

        policy_error = validate_password_policy(new_pw)
        if policy_error:
            raise ProfileServiceError(
                "VALIDATION_ERROR",
                policy_error,
                status=400,
                field="new_password",
            )

        if new_pw != confirm_pw:
            raise ProfileServiceError(
                "VALIDATION_ERROR",
                "Password confirmation does not match.",
                status=400,
                field="confirm_password",
            )

        if current_pw == new_pw:
            raise ProfileServiceError(
                "PASSWORD_REUSED",
                "New password must be different from current password.",
                status=400,
                field="new_password",
            )

        next_password = new_pw

    try:
        if "display_name" in payload:
            user.display_name = next_display_name
        if "bio" in payload:
            user.bio = next_bio
        if "social_links" in payload:
            user.social_links = next_social_links
        if next_email is not None:
            user.email = next_email
            email_verification_service.invalidate_user_email_verification(user)
        if next_timezone is not None:
            user.timezone = next_timezone
        if next_password is not None:
            user.set_password(next_password)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ProfileServiceError(
            "DB_ERROR",
            "Could not update profile.",
            status=500,
        ) from exc

    if next_password is not None:
        password_change_rate_limit_service.register_success(
            user_id=user.id, remote_addr=remote_addr
        )
        logger.info(
            "Security event: PASSWORD_CHANGED user_id=%s ip=%s",
            user.id,
            remote_addr or "unknown",
        )
        try:
            get_email_service().send(
                TransactionalEmailRequest(
                    recipient=str(user.email),
                    template_key=TemplateKey.SECURITY_PASSWORD_CHANGED,
                    category=EmailCategory.SECURITY_PASSWORD_CHANGED,
                    variables={
                        "recipient_name": str(user.username),
                    },
                )
            )
        except Exception as exc:
            current_app.logger.warning(
                "Failed to send password_changed email to recipient=%s: %s",
                mask_email(user.email),
                exc,
            )

    return get_profile_payload(user)


def upload_avatar(user: User, file_storage) -> dict[str, Any]:
    """Process, crop, resize and persist a user avatar image as WebP."""
    if not file_storage or not getattr(file_storage, "filename", None):
        raise ProfileServiceError("VALIDATION_ERROR", "Vui lòng chọn tệp hình ảnh để tải lên.", status=400, field="file")

    raw_bytes = file_storage.read()
    if not raw_bytes:
        raise ProfileServiceError("VALIDATION_ERROR", "Tệp tải lên rỗng.", status=400, field="file")

    if len(raw_bytes) > 5 * 1024 * 1024:
        raise ProfileServiceError("MEDIA_TOO_LARGE", "Ảnh đại diện không được vượt quá 5MB.", status=413, field="file")

    try:
        with Image.open(BytesIO(raw_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            if w < 16 or h < 16:
                raise ProfileServiceError("IMAGE_TOO_SMALL", "Kích thước hình ảnh quá nhỏ.", status=400, field="file")

            # Center crop to 1:1 square
            min_dim = min(w, h)
            left = (w - min_dim) // 2
            top = (h - min_dim) // 2
            cropped = img.crop((left, top, left + min_dim, top + min_dim))

            if min_dim > 512:
                cropped = cropped.resize((512, 512), Image.Resampling.LANCZOS)

            has_alpha = cropped.mode in {"RGBA", "LA"} or (
                cropped.mode == "P" and "transparency" in cropped.info
            )
            clean_img = cropped.convert("RGBA" if has_alpha else "RGB")

            avatar_dir = BASE_DIR / "static" / "uploads" / "avatars"
            avatar_dir.mkdir(parents=True, exist_ok=True)

            # Remove previous local avatar if exists
            old_url = getattr(user, "avatar_url", None)
            if old_url and str(old_url).startswith("/static/uploads/avatars/"):
                old_filename = Path(str(old_url)).name
                old_file = avatar_dir / old_filename
                if old_file.is_file():
                    try:
                        old_file.unlink()
                    except OSError:
                        pass

            filename = f"avatar_{user.id}_{int(time.time())}_{uuid4().hex[:8]}.webp"
            target_path = avatar_dir / filename
            clean_img.save(target_path, format="WEBP", quality=90, method=6)

            user.avatar_url = f"/static/uploads/avatars/{filename}"
            db.session.commit()

            return {
                "avatar_url": user.avatar_url,
                "user": get_profile_payload(user)["user"],
            }
    except ProfileServiceError:
        raise
    except Exception as exc:
        raise ProfileServiceError("INVALID_IMAGE", "Tệp hình ảnh không hợp lệ hoặc bị lỗi.", status=400, field="file") from exc


def delete_avatar(user: User) -> dict[str, Any]:
    """Remove user avatar and return to default initials."""
    old_url = getattr(user, "avatar_url", None)
    if old_url and str(old_url).startswith("/static/uploads/avatars/"):
        avatar_dir = BASE_DIR / "static" / "uploads" / "avatars"
        old_filename = Path(str(old_url)).name
        old_file = avatar_dir / old_filename
        if old_file.is_file():
            try:
                old_file.unlink()
            except OSError:
                pass

    user.avatar_url = None
    db.session.commit()

    return {
        "avatar_url": None,
        "user": get_profile_payload(user)["user"],
    }


def list_profile_transactions(
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 10,
    transaction_type: str | None = None,
) -> dict[str, Any]:
    return wallet_service.list_user_transactions(
        user_id=user_id,
        page=page,
        per_page=per_page,
        transaction_type=transaction_type,
    )
