"""Bounded marketplace listing responses without changing legacy clients."""

from app.repositories.marketplace_list_repository import ordered_items_query, visible_items_query
from app.services import marketplace_query_service
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem


def enabled_arg(value):
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def list_page(args):
    if not (
        enabled_arg(args.get("compact"))
        or args.get("page") is not None
        or args.get("page_size") is not None
    ):
        return None

    def integer(value, default):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    return (
        max(1, integer(args.get("page"), 1)),
        min(100, max(1, integer(args.get("page_size"), 24))),
    )


def pagination(page, total, *, has_more=None):
    number, size = page
    return {
        "page": number, "page_size": size, "total": total,
        "has_more": number * size < total if has_more is None else has_more,
    }


def has_inferred_filters(filters):
    # Taxonomy labels can be inferred from legacy title/category/tags. SQL
    # predicates on taxonomy JSON alone would discard legitimate matches.
    scalar_filters = {"pricing_mode", "min_price_amount_minor", "max_price_amount_minor"}
    return any(value for key, value in filters.items() if key not in scalar_filters)


def _curated_page(items, page):
    if len(items) < 5:
        return None
    groups = {}
    for item in items:
        groups.setdefault(item.primary_category or "Tổng hợp", []).append(item)
    major = [(category, rows) for category, rows in groups.items() if len(rows) >= 3]
    if not major:
        return None
    other = [item for rows in groups.values() if len(rows) < 3 for item in rows]
    number, size = page
    # Bound serialization even when the catalog has many categories. The
    # category counts and classification still use the complete visible set.
    section_size = max(1, size // 4)
    selected = major[(number - 1) * section_size:number * section_size]
    other_page = other[(number - 1) * size:number * size]
    metadata = {
        "major_sections": [
            {"category": category, "total": len(rows), "item_ids": [item.id for item in rows[:4]]}
            for category, rows in selected
        ],
        "other_item_ids": [item.id for item in other_page],
        "other_total": len(other),
    }
    page_items = [item for _, rows in selected for item in rows[:4]] + other_page
    has_more = number * section_size < len(major) or number * size < len(other)
    return page_items, metadata, has_more


def list_shared_decks(*, user_id, args):
    normalize = marketplace_query_service.normalize_marketplace_tags
    filters = {
        key: (args.get(key) or "").strip()
        for key in ("category", "domain", "subject", "framework", "framework_level")
    }
    filters["query_text"] = (args.get("q") or "").strip()
    filters["difficulty_band"] = (args.get("difficulty_band") or args.get("level") or "").strip()
    for key, aliases in (
        ("tags", ()), ("learning_goals", ("goal", "goals")),
        ("primary_topics", ("topic", "topics")),
        ("format_features", ("feature", "features")),
    ):
        raw = args.get(key)
        for alias in aliases:
            raw = raw or args.get(alias)
        filters[key] = {item.lower() for item in normalize(raw)}
    filters["pricing_mode"] = (args.get("pricing_mode") or args.get("pricing") or "").strip().lower()
    for bound in ("min", "max"):
        filters[f"{bound}_price_amount_minor"] = (
            marketplace_query_service.parse_query_price_amount_minor(args.get(f"{bound}_price"))
        )
    sort = (args.get("sort") or "popular").strip().lower()
    page = list_page(args)
    query = visible_items_query(
        DeckMarketplaceItem, user_id=user_id, owner_column=DeckMarketplaceItem.owner_user_id,
        pricing_mode=filters["pricing_mode"], min_price=filters["min_price_amount_minor"],
        max_price=filters["max_price_amount_minor"],
    )
    query = ordered_items_query(query, DeckMarketplaceItem, sort)
    curated_requested = (
        page is not None and enabled_arg(args.get("curated"))
        and not has_inferred_filters(filters) and not filters["pricing_mode"]
        and all(filters[f"{bound}_price_amount_minor"] is None for bound in ("min", "max"))
    )
    curated = None
    if curated_requested:
        # Group using just identity/category; hydrate only featured/page rows.
        # No inferred filter is active here, so no taxonomy content is needed
        # for grouping or classification.
        catalog = query.with_entities(
            DeckMarketplaceItem.id, DeckMarketplaceItem.primary_category,
        ).all()
        total = len(catalog)
        curated_result = _curated_page(catalog, page)
        if curated_result is not None:
            selected, curated, has_more = curated_result
        else:
            number, size = page
            selected = catalog[(number - 1) * size:number * size]
        selected_ids = [item.id for item in selected]
        page_rows = query.filter(DeckMarketplaceItem.id.in_(selected_ids)).all() if selected_ids else []
        by_id = {item.id: item for item in page_rows}
        items = [by_id[item_id] for item_id in selected_ids]
    elif has_inferred_filters(filters) or page is None:
        items = marketplace_query_service.filter_deck_items(query.all(), **filters)
        items = marketplace_query_service.sort_deck_items(items, sort)
        total = len(items)
        if page is not None:
            number, size = page
            items = items[(number - 1) * size:number * size]
    else:
        total = query.order_by(None).count()
        number, size = page
        offset = (number - 1) * size
        items = query.offset(offset).limit(size).all() if offset < total else []
    ids = [item.id for item in items]
    installs = DeckInstall.query.filter(
        DeckInstall.user_id == user_id, DeckInstall.deck_item_id.in_(ids),
    ).all() if ids else []
    install_map = {row.deck_item_id: row for row in installs}
    stats = marketplace_query_service.batch_compute_deck_items_stats(items)
    payload_items = []
    for item in items:
        row = marketplace_query_service.serialize_deck_marketplace_item(item, stats=stats.get(item.id))
        install = install_map.get(item.id)
        row.update(
            is_installed=install is not None,
            installed_deck_id=install.local_deck_id if install else None,
            is_owner=item.owner_user_id == user_id,
        )
        payload_items.append(row)
    payload = {"items": payload_items}
    if page is not None:
        payload["pagination"] = pagination(page, total, has_more=has_more if curated is not None else None)
        if curated_requested:
            payload["curated_sections"] = curated
    return payload
