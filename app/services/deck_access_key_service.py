"""Service for managing Deck Access Keys, generation, validation, and student redemption."""

from __future__ import annotations

from datetime import datetime, timedelta
import secrets
import string
from typing import Any, Sequence

from models import db
from models.audit_log import AuditLog
from models.deck_access_key import DeckAccessKey
from models.deck_access_key_redemption import DeckAccessKeyRedemption
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_install import DeckInstall
from models.user import User
from app.repositories import deck_access_key_repository
from app.services import creator_key_entitlement_service
from app.services import flashcards_share

KEY_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # omit ambiguous characters: 0, O, 1, I


def generate_secure_key_code(prefix: str = "FLM") -> str:
    """Generate an ergonomic, high-entropy key code e.g. FLM-9X7K-M2P4-W8RT."""
    parts = [prefix.upper()]
    for _ in range(3):
        chunk = "".join(secrets.choice(KEY_CHARS) for _ in range(4))
        parts.append(chunk)
    return "-".join(parts)


def _audit(user_id: int, action: str, payload: dict[str, Any]) -> None:
    db.session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            payload=payload,
            created_at=datetime.utcnow(),
        )
    )


def list_deck_access_keys(
    deck_item_id: str,
    creator_user_id: int,
    is_admin: bool = False,
) -> list[dict[str, Any]]:
    """List all access keys for a deck item with serialized statistics."""
    deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
    if not deck_item:
        raise ValueError("Deck marketplace item not found.")

    if not is_admin and deck_item.owner_user_id != creator_user_id:
        raise PermissionError("You do not have permission to view keys for this deck.")

    keys = deck_access_key_repository.list_keys_for_deck(
        deck_item_id,
        creator_user_id=None if is_admin else creator_user_id,
    )

    now = datetime.utcnow()
    results = []
    for k in keys:
        # Check automatic expiration display
        is_expired = bool(k.expires_at and k.expires_at < now)
        effective_status = "expired" if is_expired and k.status == "active" else k.status

        results.append(
            {
                "id": k.id,
                "deck_item_id": k.deck_item_id,
                "key_code": k.key_code,
                "label": k.label or "",
                "status": effective_status,
                "max_uses": k.max_uses,
                "used_count": k.used_count,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "access_duration_days": k.access_duration_days,
                "created_at": k.created_at.isoformat(),
                "updated_at": k.updated_at.isoformat(),
            }
        )
    return results


def create_deck_access_keys(
    deck_item_id: str,
    creator_user_id: int,
    *,
    count: int = 1,
    label: str | None = None,
    max_uses: int | None = None,
    expires_at: datetime | None = None,
    access_duration_days: int | None = None,
    is_admin: bool = False,
) -> list[DeckAccessKey]:
    """
    Generate one or more access keys for a deck item.
    Enforces ownership and stealth monetization entitlement check.
    """
    deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
    if not deck_item:
        raise ValueError("Deck marketplace item not found.")

    if not is_admin and deck_item.owner_user_id != creator_user_id:
        raise PermissionError("You do not have permission to create keys for this deck.")

    if count < 1 or count > 100:
        raise ValueError("Count must be between 1 and 100.")

    if max_uses is not None and max_uses <= 0:
        raise ValueError("max_uses must be greater than 0 if provided.")

    if access_duration_days is not None and access_duration_days <= 0:
        raise ValueError("access_duration_days must be greater than 0 if provided.")

    if expires_at and expires_at <= datetime.utcnow():
        raise ValueError("expires_at must be in the future.")

    # Check stealth monetization entitlement (free by default during platform launch)
    allowed, err_msg, fee_minor = creator_key_entitlement_service.check_creator_can_issue_keys(
        creator_user_id=creator_user_id,
        requested_count=count,
    )
    if not allowed:
        raise PermissionError(err_msg or "Cannot issue keys at this time.")

    # Deduct creator balance if monetized and fee > 0
    creator = db.session.get(User, creator_user_id)
    if fee_minor > 0 and creator:
        creator.balance_amount_minor = max(0, creator.balance_amount_minor - fee_minor)

    created_keys: list[DeckAccessKey] = []
    clean_label = (label or "").strip() or None

    for i in range(count):
        # Ensure unique code
        code = generate_secure_key_code()
        while deck_access_key_repository.get_key_by_code(code) is not None:
            code = generate_secure_key_code()

        key_label = clean_label
        if count > 1 and clean_label:
            key_label = f"{clean_label} #{i + 1}"

        key_obj = DeckAccessKey(
            deck_item_id=deck_item_id,
            creator_user_id=creator_user_id,
            key_code=code,
            label=key_label,
            status="active",
            max_uses=max_uses,
            used_count=0,
            expires_at=expires_at,
            access_duration_days=access_duration_days,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(key_obj)
        created_keys.append(key_obj)

    _audit(
        creator_user_id,
        "market.deck_key.create",
        {
            "deck_item_id": deck_item_id,
            "count": count,
            "max_uses": max_uses,
            "fee_minor": fee_minor,
        },
    )

    db.session.commit()
    return created_keys


def update_deck_access_key(
    key_id: str,
    creator_user_id: int,
    *,
    status: str | None = None,
    label: str | None = None,
    expires_at: datetime | None = None,
    is_admin: bool = False,
) -> DeckAccessKey:
    """Update or revoke/un-active an access key."""
    key_obj = db.session.get(DeckAccessKey, key_id)
    if not key_obj:
        raise ValueError("Access key not found.")

    if not is_admin and key_obj.creator_user_id != creator_user_id:
        raise PermissionError("You do not have permission to modify this key.")

    if status is not None:
        status_clean = status.strip().lower()
        if status_clean not in {"active", "revoked"}:
            raise ValueError("Status must be either 'active' or 'revoked'.")
        key_obj.status = status_clean

    if label is not None:
        key_obj.label = label.strip() or None

    if expires_at is not None:
        key_obj.expires_at = expires_at

    key_obj.updated_at = datetime.utcnow()

    _audit(
        creator_user_id,
        "market.deck_key.update",
        {
            "key_id": key_id,
            "status": key_obj.status,
            "label": key_obj.label,
        },
    )

    db.session.commit()
    return key_obj


def list_key_redemptions(
    key_id: str,
    creator_user_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
    is_admin: bool = False,
) -> dict[str, Any]:
    """List students / users who redeemed this key."""
    key_obj = db.session.get(DeckAccessKey, key_id)
    if not key_obj:
        raise ValueError("Access key not found.")

    if not is_admin and key_obj.creator_user_id != creator_user_id:
        raise PermissionError("You do not have permission to view redemptions for this key.")

    redemptions = deck_access_key_repository.list_redemptions_for_key(key_id, limit=limit, offset=offset)
    total_count = deck_access_key_repository.count_redemptions_for_key(key_id)

    items = []
    for r in redemptions:
        user_obj = db.session.get(User, r.user_id)
        items.append(
            {
                "id": r.id,
                "user_id": r.user_id,
                "username": user_obj.username if user_obj else "Unknown",
                "redeemed_at": r.redeemed_at.isoformat(),
                "access_expires_at": r.access_expires_at.isoformat() if r.access_expires_at else None,
                "status": r.status,
            }
        )

    return {
        "items": items,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
    }


def validate_key_for_redemption(
    key_code: str,
    user_id: int | None = None,
) -> dict[str, Any]:
    """
    Validate a key code and return deck summary information for the preview card.
    Does NOT mutate database or consume the key.
    """
    key_code_clean = (key_code or "").strip().upper()
    if not key_code_clean:
        return {"valid": False, "error": "Vui lòng nhập mã kích hoạt."}

    key_obj = deck_access_key_repository.get_key_by_code(key_code_clean)
    if not key_obj:
        return {"valid": False, "error": "Mã kích hoạt không tồn tại hoặc không chính xác."}

    now = datetime.utcnow()
    if key_obj.status == "revoked":
        return {"valid": False, "error": "Mã kích hoạt này đã bị vô hiệu hóa bởi tác giả."}

    if key_obj.expires_at and key_obj.expires_at < now:
        return {"valid": False, "error": "Mã kích hoạt này đã hết hạn sử dụng."}

    if key_obj.max_uses is not None and key_obj.used_count >= key_obj.max_uses:
        return {"valid": False, "error": "Mã kích hoạt này đã hết lượt sử dụng."}

    deck_item = db.session.get(DeckMarketplaceItem, key_obj.deck_item_id)
    if not deck_item:
        return {"valid": False, "error": "Bộ thẻ liên kết với mã này không tồn tại."}

    if user_id is not None:
        if deck_item.owner_user_id == user_id:
            return {"valid": False, "error": "Bạn là tác giả của bộ thẻ này, không thể tự kích hoạt mã của chính mình."}

        existing_install = DeckInstall.query.filter_by(
            deck_item_id=deck_item.id,
            user_id=user_id,
        ).first()
        if existing_install is not None:
            return {
                "valid": True,
                "already_installed": True,
                "installed_deck_id": existing_install.local_deck_id,
                "deck_item_id": deck_item.id,
                "title": deck_item.title,
                "author": deck_item.owner.username if deck_item.owner else "Flama Creator",
                "sample_cards_count": deck_item.sample_cards_count,
                "access_duration_days": key_obj.access_duration_days,
            }

    return {
        "valid": True,
        "already_installed": False,
        "deck_item_id": deck_item.id,
        "title": deck_item.title,
        "description": deck_item.description or "",
        "primary_category": deck_item.primary_category,
        "author": deck_item.owner.username if deck_item.owner else "Flama Creator",
        "sample_cards_count": deck_item.sample_cards_count,
        "access_duration_days": key_obj.access_duration_days,
        "expires_at": key_obj.expires_at.isoformat() if key_obj.expires_at else None,
    }


def redeem_deck_access_key(
    key_code: str,
    user_id: int,
) -> dict[str, Any]:
    """
    Redeem an access key for a student/learner:
    1. Pessimistically lock key row to prevent race conditions.
    2. Validate status, expiration, max_uses.
    3. Install deck via standard logical overlay pipeline.
    4. Create redemption record, increment used_count.
    5. Return installed deck details.
    """
    key_code_clean = (key_code or "").strip().upper()
    if not key_code_clean:
        raise ValueError("Vui lòng nhập mã kích hoạt.")

    # Row-level lock
    key_obj = deck_access_key_repository.get_key_by_code_locked(key_code_clean)
    if not key_obj:
        raise ValueError("Mã kích hoạt không tồn tại hoặc không chính xác.")

    now = datetime.utcnow()
    if key_obj.status == "revoked":
        raise ValueError("Mã kích hoạt này đã bị vô hiệu hóa bởi tác giả.")

    if key_obj.expires_at and key_obj.expires_at < now:
        key_obj.status = "expired"
        db.session.commit()
        raise ValueError("Mã kích hoạt này đã hết hạn sử dụng.")

    if key_obj.max_uses is not None and key_obj.used_count >= key_obj.max_uses:
        raise ValueError("Mã kích hoạt này đã hết lượt sử dụng.")

    deck_item = db.session.get(DeckMarketplaceItem, key_obj.deck_item_id)
    if not deck_item:
        raise ValueError("Bộ thẻ liên kết với mã này không tồn tại.")

    if deck_item.owner_user_id == user_id:
        raise ValueError("Bạn là tác giả của bộ thẻ này, không thể tự kích hoạt mã của chính mình.")

    existing_redemption = deck_access_key_repository.get_redemption_by_key_and_user(key_obj.id, user_id)
    existing_install = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()

    if existing_install:
        # Already installed
        return {
            "already_installed": True,
            "deck_item_id": deck_item.id,
            "installed_deck_id": existing_install.local_deck_id,
            "title": deck_item.title,
            "message": "Bạn đã cài đặt bộ thẻ này trước đó trong thư viện.",
        }

    # Perform deck installation with permission to install private/unlisted/published items with key
    install_res = flashcards_share.install_shared_deck_item_for_user(
        deck_item,
        user_id=user_id,
        publish_statuses_visible={"published", "unlisted", "private"},
    )

    install_obj = DeckInstall.query.filter_by(
        deck_item_id=deck_item.id,
        user_id=user_id,
    ).first()
    if not install_obj:
        raise RuntimeError("Không thể hoàn tất cài đặt bộ thẻ.")

    # Calculate access expiration for this student
    student_access_expires = None
    if key_obj.access_duration_days and key_obj.access_duration_days > 0:
        student_access_expires = now + timedelta(days=key_obj.access_duration_days)

    redemption = DeckAccessKeyRedemption(
        key_id=key_obj.id,
        user_id=user_id,
        deck_install_id=install_obj.id,
        redeemed_at=now,
        access_expires_at=student_access_expires,
        status="active",
    )
    db.session.add(redemption)

    # Increment usage
    key_obj.used_count += 1
    key_obj.updated_at = now

    _audit(
        user_id,
        "market.deck_key.redeem",
        {
            "key_id": key_obj.id,
            "deck_item_id": deck_item.id,
            "install_id": install_obj.id,
        },
    )

    db.session.commit()

    return {
        "success": True,
        "already_installed": False,
        "deck_item_id": deck_item.id,
        "installed_deck_id": install_obj.local_deck_id,
        "title": deck_item.title,
        "access_expires_at": student_access_expires.isoformat() if student_access_expires else None,
        "message": f"Kích hoạt thành công bộ thẻ '{deck_item.title}'!",
    }
