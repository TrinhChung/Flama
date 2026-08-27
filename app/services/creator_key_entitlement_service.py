"""Service for managing creator feature quotas and hidden monetization policies."""

from __future__ import annotations

from datetime import datetime
from typing import Tuple

from models import db
from models.creator_feature_policy import CreatorFeaturePolicy
from models.user import User
from app.repositories import deck_access_key_repository


def get_or_create_default_policy(feature_code: str = "deck_access_keys") -> CreatorFeaturePolicy:
    """Ensure a policy record exists, defaulting to 100% free / unmonetized."""
    policy = deck_access_key_repository.get_creator_feature_policy(feature_code)
    if policy is None:
        policy = CreatorFeaturePolicy(
            feature_code=feature_code,
            is_monetized=False,
            free_quota_per_creator=-1,
            price_per_key_minor=0,
            requires_pro_role=False,
        )
        db.session.add(policy)
        db.session.flush()
    return policy


def check_creator_can_issue_keys(
    creator_user_id: int,
    requested_count: int = 1,
    feature_code: str = "deck_access_keys",
) -> Tuple[bool, str | None, int]:
    """
    Check if a creator is permitted to issue the requested number of keys.
    Returns: (is_allowed, error_message, fee_amount_minor)
    
    During platform launch, is_monetized is False and fee is always 0.
    """
    if requested_count <= 0:
        return False, "Số lượng mã tạo phải lớn hơn 0.", 0

    policy = deck_access_key_repository.get_creator_feature_policy(feature_code)
    if policy is None or not policy.is_monetized:
        # Default launch phase: 100% Free, Unlimited
        return True, None, 0

    user = db.session.get(User, creator_user_id)
    if not user:
        return False, "Người dùng không tồn tại.", 0

    if user.is_admin:
        return True, None, 0

    if policy.requires_pro_role:
        role_code = getattr(user.role, "code", "") if user.role else ""
        if role_code not in ("creator", "enterprise", "admin"):
            return False, "Tính năng yêu cầu tài khoản Nhà sáng tạo (Creator).", 0

    current_keys_count = deck_access_key_repository.count_creator_keys(creator_user_id)
    free_quota = policy.free_quota_per_creator

    # If within free quota
    if free_quota < 0 or (current_keys_count + requested_count) <= free_quota:
        return True, None, 0

    # Exceeds quota -> calculate required fee
    chargeable_keys = requested_count
    if free_quota >= 0 and current_keys_count < free_quota:
        chargeable_keys = (current_keys_count + requested_count) - free_quota

    unit_price = max(0, policy.price_per_key_minor or 0)
    total_fee = chargeable_keys * unit_price

    if total_fee > 0 and user.balance_amount_minor < total_fee:
        return (
            False,
            f"Hạn mức mã miễn phí đã hết. Cần {total_fee:,} VNĐ để tạo thêm {requested_count} mã.",
            total_fee,
        )

    return True, None, total_fee


def update_creator_feature_policy(
    feature_code: str = "deck_access_keys",
    *,
    is_monetized: bool | None = None,
    free_quota_per_creator: int | None = None,
    price_per_key_minor: int | None = None,
    requires_pro_role: bool | None = None,
) -> CreatorFeaturePolicy:
    """Admin-only helper to adjust creator monetization settings in the background."""
    policy = get_or_create_default_policy(feature_code)
    if is_monetized is not None:
        policy.is_monetized = bool(is_monetized)
    if free_quota_per_creator is not None:
        policy.free_quota_per_creator = int(free_quota_per_creator)
    if price_per_key_minor is not None:
        policy.price_per_key_minor = max(0, int(price_per_key_minor))
    if requires_pro_role is not None:
        policy.requires_pro_role = bool(requires_pro_role)
    policy.updated_at = datetime.utcnow()
    db.session.commit()
    return policy
