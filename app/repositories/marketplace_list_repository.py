"""Visibility, scalar filters and stable ordering for marketplace lists."""

from sqlalchemy import func, or_
from sqlalchemy.orm import defer, joinedload

from models.deck_marketplace_item import DeckMarketplaceItem


def visible_items_query(
    model, *, user_id, owner_column, pricing_mode="", min_price=None, max_price=None,
):
    # Both unlisted listings and the owner's private/archived listings have
    # always been visible through this authenticated list contract.
    query = model.query.filter(
        or_(model.publish_status.in_(("published", "unlisted")), owner_column == user_id)
    ).options(joinedload(model.owner))
    if model is DeckMarketplaceItem:
        query = query.options(defer(model.preview_samples_json))
    if pricing_mode in {"free", "paid"}:
        query = query.filter(model.pricing_mode == pricing_mode)
    if min_price is not None:
        query = query.filter(func.coalesce(model.price_amount_minor, 0) >= min_price)
    if max_price is not None:
        query = query.filter(func.coalesce(model.price_amount_minor, 0) <= max_price)
    return query


def ordered_items_query(query, model, sort_key):
    key = (sort_key or "popular").strip().lower()
    if key == "top_rated":
        columns = (model.rating_avg, model.rating_count, model.active_usage_count)
    elif key == "newest":
        columns = (model.created_at,)
    elif key == "recently_updated":
        columns = (model.updated_at,)
    else:
        columns = (model.active_usage_count, model.install_count, model.rating_avg)
    return query.order_by(
        *(column.desc() for column in columns), model.updated_at.desc(), model.id.asc(),
    )
