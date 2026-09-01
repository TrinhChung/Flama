from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, cast, func, or_, Text

from app.validators import escape_like_pattern
from models import db
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


def get_by_id(asset_id: str | None) -> SharedImageAsset | None:
    if not asset_id:
        return None
    cleaned = str(asset_id).strip()
    if not cleaned:
        return None
    return SharedImageAsset.query.filter_by(id=cleaned).first()


def get_by_key(image_key: str | None) -> SharedImageAsset | None:
    if not image_key:
        return None
    cleaned = str(image_key).strip()
    if not cleaned:
        return None
    return SharedImageAsset.query.filter(
        func.lower(SharedImageAsset.image_key) == cleaned.lower(),
    ).first()


def get_by_sha256(sha256: str) -> SharedImageAsset | None:
    if not sha256:
        return None
    return SharedImageAsset.query.filter_by(sha256=sha256).first()


def list_assets(
    *,
    search_term: str = "",
    tag: str | None = None,
    status: str = "",
    page: int = 1,
    per_page: int = 24,
) -> SharedImagePage:
    query = SharedImageAsset.query
    if search_term:
        term_clean = search_term.strip().lower()
        if term_clean == "stroke_zh_":
            query = query.filter(
                SharedImageAsset.image_key.ilike("stroke_zh_%"),
                ~SharedImageAsset.image_key.ilike("stroke_zh_hant_%"),
            )
        else:
            escaped = escape_like_pattern(term_clean)
            pattern = f"%{escaped}%"
            query = query.filter(
                or_(
                    SharedImageAsset.image_key.ilike(pattern, escape="\\"),
                    SharedImageAsset.description.ilike(pattern, escape="\\"),
                    func.lower(cast(SharedImageAsset.tags, Text)).like(pattern, escape="\\"),
                )
            )
    if tag:
        tag_lower = tag.strip().lower()
        if tag_lower in {"zh", "zh-hans", "zh-cn"}:
            query = query.filter(
                SharedImageAsset.image_key.ilike("stroke_zh_%"),
                ~SharedImageAsset.image_key.ilike("stroke_zh_hant_%"),
            )
        elif tag_lower in {"zh-hant", "zh-tw", "zh-hk", "traditional"}:
            query = query.filter(SharedImageAsset.image_key.ilike("stroke_zh_hant_%"))
        elif tag_lower in {"ja", "ja-jp", "japanese", "kanji"}:
            query = query.filter(SharedImageAsset.image_key.ilike("stroke_ja_%"))
        elif tag_lower in {"stroke", "strokes"}:
            query = query.filter(SharedImageAsset.image_key.ilike("stroke_%"))
        else:
            escaped_tag = escape_like_pattern(tag_lower)
            query = query.filter(
                func.lower(cast(SharedImageAsset.tags, Text)).like(f"%{escaped_tag}%", escape="\\")
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
