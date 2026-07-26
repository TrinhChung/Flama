from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, func

from app.validators import escape_like_pattern
from models.shared_image_asset import SharedImageAsset


@dataclass(frozen=True)
class SharedImagePage:
    items: list[SharedImageAsset]
    page: int
    per_page: int
    total: int
    total_pages: int

    @property
    def pages(self) -> int:
        return self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages


def get_by_id(asset_id: str) -> SharedImageAsset | None:
    return SharedImageAsset.query.filter_by(id=asset_id).first()


def get_by_key(image_key: str) -> SharedImageAsset | None:
    return SharedImageAsset.query.filter(
        func.lower(SharedImageAsset.image_key) == image_key.lower(),
    ).first()


def list_assets(
    *,
    search_term: str,
    status: str,
    page: int,
    per_page: int,
) -> SharedImagePage:
    query = SharedImageAsset.query
    if search_term:
        escaped = escape_like_pattern(search_term)
        query = query.filter(
            SharedImageAsset.image_key.ilike(f"%{escaped}%", escape="\\"),
        )
    if status == "enabled":
        query = query.filter(SharedImageAsset.is_enabled.is_(True))
    elif status == "disabled":
        query = query.filter(SharedImageAsset.is_enabled.is_(False))
    elif status == "missing_file":
        query = query.filter(SharedImageAsset.storage_path.is_(None))

    total = int(query.count())
    total_pages = max(1, (total + per_page - 1) // per_page)
    resolved_page = min(max(1, page), total_pages)
    items = (
        query.order_by(
            SharedImageAsset.updated_at.desc(),
            SharedImageAsset.image_key.asc(),
        )
        .offset((resolved_page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return SharedImagePage(
        items=items,
        page=resolved_page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
    )


def count_summary() -> dict[str, int]:
    total, enabled, with_file = (
        SharedImageAsset.query.with_entities(
            func.count(SharedImageAsset.id),
            func.sum(
                case(
                    (SharedImageAsset.is_enabled.is_(True), 1),
                    else_=0,
                )
            ),
            func.sum(
                case(
                    (SharedImageAsset.storage_path.is_not(None), 1),
                    else_=0,
                )
            ),
        ).one()
    )
    total = int(total or 0)
    enabled = int(enabled or 0)
    with_file = int(with_file or 0)
    return {
        "total": total,
        "enabled": enabled,
        "disabled": max(0, total - enabled),
        "missing_file": max(0, total - with_file),
    }
