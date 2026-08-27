"""Administrative platform fee and commission configuration service."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.services import admin_service, creator_key_entitlement_service, wallet_service
from app.validators import escape_like_pattern
from models import db
from models.creator_feature_policy import CreatorFeaturePolicy
from models.user import User
from models.user_balance_transaction import UserBalanceTransaction
from models.user_role import UserRole


class AdminFeeServiceError(RuntimeError):
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
        self.status = status
        self.field = field


def _serialize_role_fee_row(role: UserRole, user_count: int = 0) -> dict[str, Any]:
    fee = (
        float(role.default_platform_fee_percent)
        if getattr(role, "default_platform_fee_percent", None) is not None
        else wallet_service.DEFAULT_PLATFORM_FEE_PERCENT
    )
    return {
        "id": int(role.id),
        "code": str(role.code),
        "name": str(role.name),
        "description": str(role.description or ""),
        "is_admin": bool(role.is_admin),
        "position": int(role.position or 0),
        "default_platform_fee_percent": round(fee, 2),
        "user_count": int(user_count),
    }


def _serialize_creator_policy(policy: CreatorFeaturePolicy) -> dict[str, Any]:
    price_minor = int(getattr(policy, "price_per_key_minor", 0) or 0)
    return {
        "id": int(policy.id),
        "feature_code": str(policy.feature_code),
        "is_monetized": bool(policy.is_monetized),
        "free_quota_per_creator": int(policy.free_quota_per_creator),
        "price_per_key_minor": price_minor,
        "price_per_key_display": wallet_service.format_currency_vnd(price_minor),
        "requires_pro_role": bool(policy.requires_pro_role),
        "updated_at": policy.updated_at.isoformat() if getattr(policy, "updated_at", None) else None,
    }


def _serialize_custom_fee_user(user: User) -> dict[str, Any]:
    balance_minor = int(getattr(user, "balance_amount_minor", 0) or 0)
    custom_fee = (
        float(user.custom_platform_fee_percent)
        if getattr(user, "custom_platform_fee_percent", None) is not None
        else None
    )
    return {
        "id": int(user.id),
        "username": str(user.username or ""),
        "account_name": admin_service.resolve_account_name(user),
        "email": str(user.email or ""),
        "is_admin": bool(user.is_admin),
        "is_disabled": bool(user.is_disabled),
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else None,
        "role_code": user.role.code if user.role else None,
        "role_default_fee_percent": (
            float(user.role.default_platform_fee_percent)
            if user.role and getattr(user.role, "default_platform_fee_percent", None) is not None
            else wallet_service.DEFAULT_PLATFORM_FEE_PERCENT
        ),
        "custom_platform_fee_percent": round(custom_fee, 2) if custom_fee is not None else None,
        "effective_platform_fee_percent": round(wallet_service.get_user_platform_fee_percent(user), 2),
        "balance_amount_minor": balance_minor,
        "balance_amount_display": wallet_service.format_currency_vnd(balance_minor),
    }


def get_fee_overview() -> dict[str, Any]:
    """Retrieve full system fee metrics, role tiers, creator policy, and user custom exceptions."""
    # Aggregated platform transaction stats
    tx_summary = (
        db.session.query(
            func.coalesce(func.sum(UserBalanceTransaction.gross_amount_minor), 0).label("total_gross"),
            func.coalesce(func.sum(UserBalanceTransaction.platform_fee_amount_minor), 0).label("total_platform_fees"),
            func.coalesce(func.sum(UserBalanceTransaction.net_amount_minor), 0).label("total_creator_net"),
            func.count(UserBalanceTransaction.id).label("total_sales_count"),
        )
        .filter(UserBalanceTransaction.transaction_type == "deck_sale")
        .one()
    )

    total_gross = int(tx_summary.total_gross)
    total_fees = int(tx_summary.total_platform_fees)
    total_net = int(tx_summary.total_creator_net)
    total_sales = int(tx_summary.total_sales_count)

    # Roles and counts
    role_counts_map = dict(
        db.session.query(User.role_id, func.count(User.id))
        .filter(User.role_id.isnot(None))
        .group_by(User.role_id)
        .all()
    )

    roles = (
        UserRole.query.order_by(UserRole.position.asc(), UserRole.id.asc()).all()
    )

    roles_data = [
        _serialize_role_fee_row(role, role_counts_map.get(role.id, 0))
        for role in roles
    ]

    # Creator policy for deck access keys
    creator_policy = creator_key_entitlement_service.get_or_create_default_policy("deck_access_keys")

    # Users with custom platform fee override
    custom_fee_users = (
        User.query.options(selectinload(User.role))
        .filter(User.custom_platform_fee_percent.isnot(None))
        .order_by(User.id.asc())
        .all()
    )
    custom_users_data = [_serialize_custom_fee_user(u) for u in custom_fee_users]

    # Resolve key role fee averages/values
    creator_role = next((r for r in roles if r.code == "creator"), None)
    creator_fee_default = (
        float(creator_role.default_platform_fee_percent)
        if creator_role and getattr(creator_role, "default_platform_fee_percent", None) is not None
        else 5.0
    )

    regular_role = next((r for r in roles if r.code == "regular"), None)
    regular_fee_default = (
        float(regular_role.default_platform_fee_percent)
        if regular_role and getattr(regular_role, "default_platform_fee_percent", None) is not None
        else wallet_service.DEFAULT_PLATFORM_FEE_PERCENT
    )

    return {
        "summary": {
            "global_default_fee_percent": wallet_service.DEFAULT_PLATFORM_FEE_PERCENT,
            "regular_fee_percent": round(regular_fee_default, 2),
            "creator_fee_percent": round(creator_fee_default, 2),
            "custom_fee_users_count": len(custom_users_data),
            "total_roles_count": len(roles_data),
            "total_sales_count": total_sales,
            "total_gross_amount_minor": total_gross,
            "total_gross_display": wallet_service.format_currency_vnd(total_gross),
            "total_platform_fee_amount_minor": total_fees,
            "total_platform_fee_display": wallet_service.format_currency_vnd(total_fees),
            "total_creator_net_amount_minor": total_net,
            "total_creator_net_display": wallet_service.format_currency_vnd(total_net),
        },
        "roles": roles_data,
        "creator_policy": _serialize_creator_policy(creator_policy),
        "custom_fee_users": custom_users_data,
    }


def update_role_default_fee(*, role_id: int, fee_percent: float) -> dict[str, Any]:
    """Update default platform fee percentage for a specific user role."""
    if fee_percent < 0.0 or fee_percent > 100.0:
        raise AdminFeeServiceError(
            "VALIDATION_ERROR",
            "Tỷ lệ phí phải là một số từ 0 đến 100%.",
            field="default_platform_fee_percent",
        )

    role = db.session.get(UserRole, int(role_id))
    if role is None:
        raise AdminFeeServiceError(
            "NOT_FOUND",
            "Không tìm thấy vai trò người dùng tương ứng.",
            status=404,
        )

    role.default_platform_fee_percent = float(fee_percent)
    db.session.commit()

    user_count = User.query.filter(User.role_id == role.id).count()
    return _serialize_role_fee_row(role, user_count)


def update_creator_feature_policy(
    *,
    feature_code: str = "deck_access_keys",
    is_monetized: bool | None = None,
    free_quota_per_creator: int | None = None,
    price_per_key_minor: int | None = None,
    requires_pro_role: bool | None = None,
) -> dict[str, Any]:
    """Update creator monetization policies for features like deck access keys."""
    if free_quota_per_creator is not None and free_quota_per_creator < -1:
        raise AdminFeeServiceError(
            "VALIDATION_ERROR",
            "Hạn mức miễn phí phải từ -1 trở lên (-1 là không giới hạn).",
            field="free_quota_per_creator",
        )

    if price_per_key_minor is not None and price_per_key_minor < 0:
        raise AdminFeeServiceError(
            "VALIDATION_ERROR",
            "Đơn giá mỗi mã phải là số nguyên không âm.",
            field="price_per_key_minor",
        )

    policy = creator_key_entitlement_service.update_creator_feature_policy(
        feature_code=feature_code,
        is_monetized=is_monetized,
        free_quota_per_creator=free_quota_per_creator,
        price_per_key_minor=price_per_key_minor,
        requires_pro_role=requires_pro_role,
    )
    db.session.commit()
    return _serialize_creator_policy(policy)


def update_user_custom_fee(*, user_id: int, custom_fee_percent: float | None) -> dict[str, Any]:
    """Set or reset custom platform fee override for an individual user."""
    user = db.session.get(User, int(user_id))
    if user is None:
        raise AdminFeeServiceError(
            "NOT_FOUND",
            "Người dùng không tồn tại.",
            status=404,
        )

    if custom_fee_percent is None:
        user.custom_platform_fee_percent = None
    else:
        try:
            val = float(custom_fee_percent)
            if val < 0.0 or val > 100.0:
                raise ValueError()
            user.custom_platform_fee_percent = val
        except (TypeError, ValueError) as exc:
            raise AdminFeeServiceError(
                "VALIDATION_ERROR",
                "Mức phí tùy chỉnh phải là số từ 0 đến 100, hoặc null để dùng mặc định.",
                field="custom_platform_fee_percent",
            ) from exc

    db.session.commit()
    return _serialize_custom_fee_user(user)


def search_users_for_fee_override(*, query_text: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search users by username/email to quickly configure a custom platform fee."""
    term = query_text.strip()
    if not term:
        return []

    like_pattern = f"%{escape_like_pattern(term)}%"
    users = (
        User.query.options(selectinload(User.role))
        .filter(
            or_(
                User.username.ilike(like_pattern, escape="\\"),
                User.email.ilike(like_pattern, escape="\\"),
            )
        )
        .order_by(User.id.asc())
        .limit(min(max(1, limit), 20))
        .all()
    )
    return [_serialize_custom_fee_user(u) for u in users]
