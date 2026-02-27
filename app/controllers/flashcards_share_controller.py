"""Share/marketplace business logic extracted from flashcards routes."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.controllers import flashcards_marketplace_controller as marketplace_ctrl
from app.controllers import flashcards_note_controller as note_ctrl
from app.controllers.deck_controller import (
    collect_ancestor_ids,
    collect_subtree_ids,
)
from models import db
from models.card_progress import CardProgress
from models.deck import Deck
from models.flashcard import (
    Card,
    DeckInstall,
    DeckMarketplaceItem,
    DeckReview,
    FieldDef,
    MediaAsset,
    Note,
    NoteType,
    NoteTypeInstall,
    NoteTypeReview,
    Template,
)

DEFAULT_VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}


class ShareControllerError(Exception):
    """Domain error for flashcard share/deck flows."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
        error: str = "VALIDATION_ERROR",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.field = field
        self.error = error


def validate_note_type_publish_requirements(note_type: NoteType) -> str | None:
    if not (note_type.name or "").strip():
        return "Title is required for publish."
    if not (note_type.description or "").strip():
        return "Description is required for publish."
    if not (note_type.primary_category or "").strip():
        return "primary_category is required for publish."
    preview_text = (note_type.preview_text or "").strip()
    preview_image = (note_type.preview_image_url or "").strip()
    if not preview_text and not preview_image:
        return "Preview text or preview image is required for publish."
    if not (note_type.version or "").strip():
        return "Version is required for publish."
    if note_type.pricing_mode == "paid" and int(note_type.price_cents or 0) <= 0:
        return "Paid note type must have a positive price."
    if not note_type.field_defs:
        return "At least one field is required for publish."
    if not note_type.templates:
        return "At least one card template is required for publish."
    return None


def apply_note_type_marketplace_payload(
    note_type: NoteType,
    payload: dict[str, Any],
    *,
    allow_set_official: bool,
    publish_statuses_visible: set[str] | None = None,
) -> str | None:
    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES

    if "title" in payload or "name" in payload:
        new_name = (payload.get("title") or payload.get("name") or "").strip()
        if not new_name:
            return "Title is required."
        existing = NoteType.query.filter(
            NoteType.user_id == note_type.user_id,
            NoteType.name == new_name,
            NoteType.id != note_type.id,
        ).first()
        if existing:
            return "Another note type already uses this title."
        note_type.name = new_name

    if "description" in payload:
        note_type.description = (payload.get("description") or "").strip() or None
    if "primary_category" in payload:
        note_type.primary_category = (payload.get("primary_category") or "").strip() or None
    if "tags" in payload:
        note_type.tags = marketplace_ctrl.normalize_marketplace_tags(payload.get("tags"))
    if "preview_text" in payload:
        note_type.preview_text = (payload.get("preview_text") or "").strip() or None
    if "preview_image_url" in payload:
        note_type.preview_image_url = (payload.get("preview_image_url") or "").strip() or None
    if "version" in payload:
        note_type.version = (payload.get("version") or "").strip() or "1.0.0"
    if "changelog" in payload:
        note_type.changelog = (payload.get("changelog") or "").strip() or None

    pricing_mode, price_cents, pricing_error = marketplace_ctrl.normalize_pricing(
        payload,
        current_mode=str(note_type.pricing_mode or "free"),
        current_price_cents=int(note_type.price_cents or 0),
    )
    if pricing_error:
        return pricing_error
    note_type.pricing_mode = pricing_mode
    note_type.price_cents = price_cents

    if "is_official" in payload:
        if not allow_set_official:
            return "Only admin can set official flag."
        note_type.is_official = bool(payload.get("is_official"))

    if "publish_status" in payload:
        candidate_status = str(payload.get("publish_status") or "").strip().lower()
        if candidate_status not in {"private", "published", "unlisted", "archived"}:
            return "publish_status is invalid."
        if candidate_status in visible_statuses:
            err = validate_note_type_publish_requirements(note_type)
            if err:
                return err
            if note_type.publish_status not in visible_statuses:
                note_type.published_at = datetime.utcnow()
            note_type.archived_at = None
        elif candidate_status == "archived":
            note_type.archived_at = datetime.utcnow()
        note_type.publish_status = candidate_status

    return None


def make_unique_note_type_name(user_id: int, base_name: str) -> str:
    candidate = base_name.strip() or "Installed NoteType"
    if not NoteType.query.filter_by(user_id=user_id, name=candidate).first():
        return candidate
    counter = 2
    while True:
        candidate_with_counter = f"{candidate} ({counter})"
        if not NoteType.query.filter_by(user_id=user_id, name=candidate_with_counter).first():
            return candidate_with_counter
        counter += 1


def clone_note_type_for_user(source_note_type: NoteType, user_id: int) -> NoteType:
    clone = NoteType(
        user_id=user_id,
        name=make_unique_note_type_name(user_id, source_note_type.name),
        description=source_note_type.description,
        primary_category=source_note_type.primary_category,
        tags=list(source_note_type.tags or []),
        preview_text=source_note_type.preview_text,
        preview_image_url=source_note_type.preview_image_url,
        pricing_mode="free",
        price_cents=0,
        version=source_note_type.version or "1.0.0",
        changelog=source_note_type.changelog,
        publish_status="private",
        is_official=False,
        install_count=0,
        active_usage_count=0,
        rating_avg=0.0,
        rating_count=0,
    )
    db.session.add(clone)
    db.session.flush()

    for field_def in sorted(source_note_type.field_defs, key=lambda item: item.position):
        db.session.add(
            FieldDef(
                note_type_id=clone.id,
                name=field_def.name,
                field_type=field_def.field_type,
                position=field_def.position,
                required=bool(field_def.required),
            )
        )

    for template in sorted(source_note_type.templates, key=lambda item: item.position):
        db.session.add(
            Template(
                note_type_id=clone.id,
                name=template.name,
                front_html=template.front_html,
                back_html=template.back_html,
                shared_css=template.shared_css,
                position=template.position,
                is_default=bool(template.is_default),
            )
        )

    return clone


def touch_note_type_install_usage(
    *,
    user_id: int,
    installed_note_type_id: str,
    activity_at: datetime | None = None,
) -> None:
    install = NoteTypeInstall.query.filter_by(
        user_id=user_id,
        installed_note_type_id=installed_note_type_id,
    ).first()
    if not install:
        return
    now = activity_at or datetime.utcnow()
    if install.first_use_at is None:
        install.first_use_at = now
    install.last_activity_at = now


def note_type_reps_for_user(*, user_id: int, installed_note_type_id: str) -> int:
    result = (
        db.session.query(db.func.coalesce(db.func.sum(CardProgress.reps), 0))
        .select_from(CardProgress)
        .join(Card, CardProgress.card_id == Card.id)
        .join(Note, Card.note_id == Note.id)
        .filter(
            CardProgress.user_id == user_id,
            Note.note_type_id == installed_note_type_id,
        )
        .scalar()
    )
    return int(result or 0)


def is_note_type_install_active(
    install: NoteTypeInstall,
    *,
    now: datetime,
    note_type_active_note_threshold: int = 3,
    note_type_active_review_threshold: int = 3,
    note_type_active_days_threshold: int = 3,
) -> bool:
    if not install.installed_note_type_id:
        return False
    note_count = Note.query.filter_by(
        user_id=install.user_id,
        note_type_id=install.installed_note_type_id,
    ).count()
    review_reps = note_type_reps_for_user(
        user_id=install.user_id,
        installed_note_type_id=install.installed_note_type_id,
    )
    first_use = install.first_use_at
    used_days = bool(
        first_use
        and now - first_use >= timedelta(days=note_type_active_days_threshold)
    )
    return (
        note_count >= note_type_active_note_threshold
        or review_reps >= note_type_active_review_threshold
        or used_days
    )


def recompute_note_type_market_stats(
    note_type: NoteType,
    *,
    note_type_active_note_threshold: int = 3,
    note_type_active_review_threshold: int = 3,
    note_type_active_days_threshold: int = 3,
) -> None:
    now = datetime.utcnow()
    installs = NoteTypeInstall.query.filter_by(source_note_type_id=note_type.id).all()
    note_type.install_count = len(installs)
    note_type.active_usage_count = sum(
        1
        for install in installs
        if is_note_type_install_active(
            install,
            now=now,
            note_type_active_note_threshold=note_type_active_note_threshold,
            note_type_active_review_threshold=note_type_active_review_threshold,
            note_type_active_days_threshold=note_type_active_days_threshold,
        )
    )

    rating_avg, rating_count = (
        db.session.query(
            db.func.coalesce(db.func.avg(NoteTypeReview.rating), 0.0),
            db.func.count(NoteTypeReview.id),
        )
        .filter(NoteTypeReview.note_type_id == note_type.id)
        .first()
    )
    note_type.rating_avg = float(rating_avg or 0.0)
    note_type.rating_count = int(rating_count or 0)


def can_user_rate_note_type(
    note_type: NoteType,
    *,
    user_id: int,
    note_type_active_note_threshold: int = 3,
    note_type_active_review_threshold: int = 3,
    note_type_active_days_threshold: int = 3,
) -> bool:
    if note_type.user_id == user_id:
        return False
    install = NoteTypeInstall.query.filter_by(
        source_note_type_id=note_type.id,
        user_id=user_id,
    ).first()
    if not install:
        return False
    return is_note_type_install_active(
        install,
        now=datetime.utcnow(),
        note_type_active_note_threshold=note_type_active_note_threshold,
        note_type_active_review_threshold=note_type_active_review_threshold,
        note_type_active_days_threshold=note_type_active_days_threshold,
    )


def validate_deck_publish_requirements(deck_item: DeckMarketplaceItem) -> str | None:
    if not (deck_item.title or "").strip():
        return "Title is required for publish."
    if not (deck_item.description or "").strip():
        return "Description is required for publish."
    if not (deck_item.primary_category or "").strip():
        return "primary_category is required for publish."
    if not (deck_item.preview_text or "").strip() and int(deck_item.sample_cards_count or 0) <= 0:
        return "Preview text or sample_cards_count > 0 is required for publish."
    if not (deck_item.version or "").strip():
        return "Version is required for publish."
    if deck_item.pricing_mode == "paid" and int(deck_item.price_cents or 0) <= 0:
        return "Paid deck must have a positive price."
    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        return "source_note_type_id is required for publish."
    source_note_type = NoteType.query.get(source_note_type_id)
    if not source_note_type:
        return "source_note_type_id not found for publish."
    if not source_note_type.templates:
        return "source_note_type_id must reference a note type that has at least one template."
    return None


def apply_deck_marketplace_payload(
    deck_item: DeckMarketplaceItem,
    payload: dict[str, Any],
    *,
    allow_set_official: bool,
    publish_statuses_visible: set[str] | None = None,
) -> str | None:
    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES

    if "title" in payload:
        title = (payload.get("title") or "").strip()
        if not title:
            return "title is required."
        deck_item.title = title
    if "description" in payload:
        deck_item.description = (payload.get("description") or "").strip()
    if "primary_category" in payload:
        category = (payload.get("primary_category") or "").strip()
        if not category:
            return "primary_category is required."
        deck_item.primary_category = category
    if "tags" in payload:
        deck_item.tags = marketplace_ctrl.normalize_marketplace_tags(payload.get("tags"))
    if "preview_text" in payload:
        deck_item.preview_text = (payload.get("preview_text") or "").strip() or None
    if "sample_cards_count" in payload:
        try:
            deck_item.sample_cards_count = max(0, int(payload.get("sample_cards_count") or 0))
        except (TypeError, ValueError):
            return "sample_cards_count must be an integer."
    if "source_deck_id" in payload:
        source_deck_id_raw = payload.get("source_deck_id")
        if source_deck_id_raw in (None, ""):
            deck_item.source_deck_id = None
        else:
            try:
                deck_item.source_deck_id = int(source_deck_id_raw)
            except (TypeError, ValueError):
                return "source_deck_id must be an integer."
    if "source_note_type_id" in payload:
        deck_item.source_note_type_id = (payload.get("source_note_type_id") or "").strip() or None
    if "version" in payload:
        deck_item.version = (payload.get("version") or "").strip() or "1.0.0"
    if "changelog" in payload:
        deck_item.changelog = (payload.get("changelog") or "").strip() or None

    pricing_mode, price_cents, pricing_error = marketplace_ctrl.normalize_pricing(
        payload,
        current_mode=str(deck_item.pricing_mode or "free"),
        current_price_cents=int(deck_item.price_cents or 0),
    )
    if pricing_error:
        return pricing_error
    deck_item.pricing_mode = pricing_mode
    deck_item.price_cents = price_cents

    if "is_official" in payload:
        if not allow_set_official:
            return "Only admin can set official flag."
        deck_item.is_official = bool(payload.get("is_official"))

    if "publish_status" in payload:
        candidate_status = str(payload.get("publish_status") or "").strip().lower()
        if candidate_status not in {"private", "published", "unlisted", "archived"}:
            return "publish_status is invalid."
        if candidate_status in visible_statuses:
            err = validate_deck_publish_requirements(deck_item)
            if err:
                return err
            if deck_item.publish_status not in visible_statuses:
                deck_item.published_at = datetime.utcnow()
            deck_item.archived_at = None
        elif candidate_status == "archived":
            deck_item.archived_at = datetime.utcnow()
        deck_item.publish_status = candidate_status

    return None


def resolve_single_note_type_for_deck(
    *,
    deck_id: int,
    owner_user_id: int | None = None,
) -> tuple[str | None, str | None]:
    query = db.session.query(Note.note_type_id).filter(Note.deck_id == deck_id)
    if owner_user_id is not None:
        query = query.filter(Note.user_id == owner_user_id)

    note_type_ids = sorted({row[0] for row in query.all() if row[0]})
    if not note_type_ids:
        return None, "Deck has no notes, cannot infer source_note_type_id."
    if len(note_type_ids) > 1:
        return None, "All notes in one deck must use the same template (note type)."

    resolved_note_type_id = note_type_ids[0]
    resolved_note_type = NoteType.query.get(resolved_note_type_id)
    if not resolved_note_type:
        return None, "Deck source note type not found."
    if not resolved_note_type.templates:
        return None, "Deck source note type has no templates."
    return resolved_note_type.id, None


def bind_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> str | None:
    if deck_item.source_deck_id is not None:
        inferred_note_type_id, infer_error = resolve_single_note_type_for_deck(
            deck_id=deck_item.source_deck_id,
            owner_user_id=deck_item.owner_user_id,
        )
        if infer_error and require_source_note_type and not (deck_item.source_note_type_id or "").strip():
            return infer_error
        if inferred_note_type_id:
            if deck_item.source_note_type_id and deck_item.source_note_type_id != inferred_note_type_id:
                return "source_note_type_id does not match notes inside source_deck_id."
            deck_item.source_note_type_id = inferred_note_type_id

    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        if require_source_note_type:
            return "source_note_type_id is required."
        return None

    source_note_type = NoteType.query.get(source_note_type_id)
    if not source_note_type:
        return "source_note_type_id not found."
    if not source_note_type.templates:
        return "source_note_type_id must reference a note type with at least one template."
    return None


def validate_note_type_consistency_for_deck(
    *,
    deck_id: int | None,
    note_type_id: str,
    user_id: int,
    exclude_note_id: str | None = None,
) -> str | None:
    if deck_id is None:
        return None

    query = db.session.query(Note.note_type_id).filter(
        Note.deck_id == deck_id,
        Note.user_id == user_id,
    )
    if exclude_note_id:
        query = query.filter(Note.id != exclude_note_id)

    existing_note_type_ids = {row[0] for row in query.distinct().all() if row[0]}
    if not existing_note_type_ids:
        return None
    if existing_note_type_ids == {note_type_id}:
        return None
    return "All notes in one deck must use the same template (note type)."


def _next_deck_position(parent_deck_id: int | None) -> int:
    query = db.session.query(db.func.max(Deck.position))
    if parent_deck_id is None:
        max_pos = query.filter(Deck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(Deck.parent_id == parent_deck_id).scalar()
    return int(max_pos or 0) + 1


def clone_deck_subtree(
    *,
    source_deck_id: int,
    parent_id: int | None,
    owner_user_id: int | None = None,
    source_owner_user_id: int | None = None,
) -> Deck:
    source_deck = Deck.query.get(source_deck_id)
    if not source_deck:
        raise ValueError(f"Deck not found: {source_deck_id}")

    cloned_deck = Deck(
        parent_id=parent_id,
        owner_user_id=owner_user_id,
        note_type_id=source_deck.note_type_id,
        name=source_deck.name,
        description=source_deck.description,
        position=_next_deck_position(parent_id),
    )
    db.session.add(cloned_deck)
    db.session.flush()

    source_notes_query = Note.query.filter(Note.deck_id == source_deck.id)
    if source_owner_user_id is not None:
        source_notes_query = source_notes_query.filter(
            Note.user_id == source_owner_user_id
        )
    source_notes = source_notes_query.order_by(Note.created_at.asc(), Note.id.asc()).all()
    for source_note in source_notes:
        cloned_field_values = dict(source_note.field_values or {})
        cloned_note = Note(
            note_type_id=source_note.note_type_id,
            user_id=owner_user_id or source_note.user_id,
            deck_id=cloned_deck.id,
            field_values=cloned_field_values,
            tags=list(source_note.tags or []),
        )
        db.session.add(cloned_note)
        db.session.flush()

        for source_asset in source_note.media_assets:
            cloned_asset = MediaAsset(
                note_id=cloned_note.id,
                field_name=source_asset.field_name,
                filename=source_asset.filename,
                mime_type=source_asset.mime_type,
                storage_path=source_asset.storage_path,
                sha256=source_asset.sha256,
                size_bytes=int(source_asset.size_bytes or 0),
            )
            db.session.add(cloned_asset)
            db.session.flush()
            current_field_value = cloned_field_values.get(source_asset.field_name)
            if current_field_value == source_asset.id:
                cloned_field_values[source_asset.field_name] = cloned_asset.id
            elif (
                isinstance(current_field_value, str)
                and current_field_value.strip() == source_asset.id
            ):
                cloned_field_values[source_asset.field_name] = cloned_asset.id

        cloned_note.field_values = cloned_field_values
        note_ctrl.create_cards_for_note(cloned_note)

    child_decks = (
        Deck.query.filter_by(parent_id=source_deck.id)
        .order_by(Deck.position.asc(), Deck.id.asc())
        .all()
    )
    for child in child_decks:
        clone_deck_subtree(
            source_deck_id=child.id,
            parent_id=cloned_deck.id,
            owner_user_id=owner_user_id,
            source_owner_user_id=source_owner_user_id,
        )

    return cloned_deck


def deck_installs_covering_deck(*, user_id: int, deck_id: int) -> list[DeckInstall]:
    ancestor_ids = collect_ancestor_ids(deck_id)
    if not ancestor_ids:
        return []
    return (
        DeckInstall.query.filter(
            DeckInstall.user_id == user_id,
            DeckInstall.local_deck_id.in_(ancestor_ids),
        )
        .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
        .all()
    )


def touch_deck_install_usage(
    *,
    user_id: int,
    local_deck_id: int,
    activity_at: datetime | None = None,
) -> None:
    installs = deck_installs_covering_deck(user_id=user_id, deck_id=local_deck_id)
    if not installs:
        return
    now = activity_at or datetime.utcnow()
    for install in installs:
        if install.first_use_at is None:
            install.first_use_at = now
        install.last_activity_at = now


def deck_reps_for_user(*, user_id: int, local_deck_id: int) -> int:
    subtree_deck_ids = collect_subtree_ids(local_deck_id)
    if not subtree_deck_ids:
        return 0

    flashcard_reps = (
        db.session.query(db.func.coalesce(db.func.sum(CardProgress.reps), 0))
        .select_from(CardProgress)
        .join(Card, CardProgress.card_id == Card.id)
        .join(Note, Card.note_id == Note.id)
        .filter(
            CardProgress.user_id == user_id,
            Note.deck_id.in_(subtree_deck_ids),
        )
        .scalar()
    ) or 0
    return int(flashcard_reps or 0)


def is_deck_install_active(
    install: DeckInstall,
    *,
    deck_active_review_threshold: int = 3,
) -> bool:
    if not install.local_deck_id:
        return False
    reps = deck_reps_for_user(user_id=install.user_id, local_deck_id=install.local_deck_id)
    return reps >= deck_active_review_threshold


def recompute_deck_item_market_stats(
    deck_item: DeckMarketplaceItem,
    *,
    deck_active_review_threshold: int = 3,
) -> None:
    installs = DeckInstall.query.filter_by(deck_item_id=deck_item.id).all()
    deck_item.install_count = len(installs)
    deck_item.active_usage_count = sum(
        1
        for install in installs
        if is_deck_install_active(
            install,
            deck_active_review_threshold=deck_active_review_threshold,
        )
    )

    rating_avg, rating_count = (
        db.session.query(
            db.func.coalesce(db.func.avg(DeckReview.rating), 0.0),
            db.func.count(DeckReview.id),
        )
        .filter(DeckReview.deck_item_id == deck_item.id)
        .first()
    )
    deck_item.rating_avg = float(rating_avg or 0.0)
    deck_item.rating_count = int(rating_count or 0)


def can_user_rate_deck(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    deck_active_review_threshold: int = 3,
) -> bool:
    if deck_item.owner_user_id == user_id:
        return False
    install = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    if not install:
        return False
    return is_deck_install_active(
        install,
        deck_active_review_threshold=deck_active_review_threshold,
    )


def is_note_type_visible_for_shared(note_type: NoteType) -> bool:
    return str(note_type.publish_status or "").strip().lower() == "published"


def is_deck_item_visible_for_shared(deck_item: DeckMarketplaceItem) -> bool:
    return str(deck_item.publish_status or "").strip().lower() == "published"


def sync_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> tuple[str | None, bool]:
    original_note_type_id = deck_item.source_note_type_id
    bind_error = bind_deck_item_source_note_type(
        deck_item,
        require_source_note_type=require_source_note_type,
    )
    changed = deck_item.source_note_type_id != original_note_type_id
    return bind_error, changed


def build_shared_deck_item_payload(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    sample_limit: int,
    deck_active_review_threshold: int = 3,
) -> dict[str, Any]:
    install = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    review = DeckReview.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    payload = marketplace_ctrl.serialize_deck_marketplace_item(deck_item)
    payload["is_installed"] = install is not None
    payload["installed_deck_id"] = install.local_deck_id if install else None
    payload["is_owner"] = deck_item.owner_user_id == user_id
    payload["can_rate"] = can_user_rate_deck(
        deck_item,
        user_id=user_id,
        deck_active_review_threshold=deck_active_review_threshold,
    )
    payload["my_review"] = (
        {
            "rating": review.rating,
            "comment": review.comment,
            "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        }
        if review
        else None
    )

    source_note_type_payload = None
    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if source_note_type_id:
        source_note_type = NoteType.query.get(source_note_type_id)
        if source_note_type:
            ordered_templates = sorted(
                source_note_type.templates,
                key=lambda item: (int(item.position or 0), str(item.name or "").lower()),
            )
            source_note_type_payload = {
                "id": source_note_type.id,
                "name": source_note_type.name,
                "title": source_note_type.name,
                "publish_status": source_note_type.publish_status,
                "templates": [
                    {
                        "id": template.id,
                        "name": template.name,
                        "position": int(template.position or 0),
                        "is_default": bool(template.is_default),
                    }
                    for template in ordered_templates
                ],
            }
    payload["source_note_type"] = source_note_type_payload
    payload["test_samples"] = marketplace_ctrl.build_shared_deck_test_samples(
        deck_item,
        limit=sample_limit,
    )
    payload["test_sample_limit"] = sample_limit
    return payload


def select_preview_note_for_shared_deck(
    deck_item: DeckMarketplaceItem,
    *,
    note_type_id: str,
    requested_note_id: str | None,
) -> Note | None:
    if deck_item.source_deck_id is None:
        return None

    deck_ids = collect_subtree_ids(deck_item.source_deck_id)
    if not deck_ids:
        return None

    if requested_note_id:
        query = Note.query.filter(
            Note.id == requested_note_id,
            Note.note_type_id == note_type_id,
            Note.deck_id.in_(deck_ids),
        )
        if deck_item.owner_user_id is not None:
            query = query.filter(Note.user_id == deck_item.owner_user_id)
        preview_note = query.first()
        if preview_note is not None:
            return preview_note

    query = Note.query.filter(
        Note.deck_id.in_(deck_ids),
        Note.note_type_id == note_type_id,
    )
    if deck_item.owner_user_id is not None:
        query = query.filter(Note.user_id == deck_item.owner_user_id)
    return query.order_by(Note.created_at.asc(), Note.id.asc()).first()


def install_shared_deck_item_for_user(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    publish_statuses_visible: set[str] | None = None,
) -> dict[str, Any]:
    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES

    status = str(deck_item.publish_status or "").strip().lower()
    if status not in visible_statuses:
        raise ShareControllerError(
            "This deck is not available for install.",
            status=409,
        )
    if deck_item.owner_user_id == user_id:
        raise ShareControllerError(
            "Owner cannot install own deck item.",
            status=409,
        )

    existing = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    if existing:
        return {
            "created": False,
            "response": {
                "deck_item_id": deck_item.id,
                "installed_deck_id": existing.local_deck_id,
                "already_installed": True,
            },
        }

    now = datetime.utcnow()
    local_deck_id = None
    if deck_item.source_deck_id is not None:
        source_deck = Deck.query.get(deck_item.source_deck_id)
        if source_deck is None:
            raise ShareControllerError(
                "Source deck not found.",
                status=404,
                error="FIELD_NOT_FOUND",
            )
        cloned_root = clone_deck_subtree(
            source_deck_id=source_deck.id,
            parent_id=None,
            owner_user_id=user_id,
            source_owner_user_id=deck_item.owner_user_id,
        )
        local_deck_id = cloned_root.id

    purchase_price_cents = int(deck_item.price_cents or 0) if deck_item.pricing_mode == "paid" else 0
    install = DeckInstall(
        deck_item_id=deck_item.id,
        user_id=user_id,
        local_deck_id=local_deck_id,
        purchase_price_cents=purchase_price_cents,
        installed_at=now,
        purchased_at=now if deck_item.pricing_mode == "paid" else None,
    )
    db.session.add(install)

    auto_note_type_install = None
    if deck_item.source_note_type_id:
        source_note_type = NoteType.query.get(deck_item.source_note_type_id)
        existing_note_install = NoteTypeInstall.query.filter_by(
            source_note_type_id=deck_item.source_note_type_id,
            user_id=user_id,
        ).first()
        if (
            source_note_type
            and existing_note_install is None
            and source_note_type.pricing_mode == "free"
            and bool(source_note_type.is_official)
            and str(source_note_type.publish_status or "").strip().lower() in visible_statuses
            and source_note_type.user_id != user_id
        ):
            installed_copy = clone_note_type_for_user(source_note_type, user_id)
            auto_note_type_install = NoteTypeInstall(
                source_note_type_id=source_note_type.id,
                installed_note_type_id=installed_copy.id,
                user_id=user_id,
                purchase_price_cents=0,
                installed_at=now,
            )
            db.session.add(auto_note_type_install)
            recompute_note_type_market_stats(source_note_type)

    recompute_deck_item_market_stats(deck_item)
    return {
        "created": True,
        "response": {
            "deck_item_id": deck_item.id,
            "installed_deck_id": local_deck_id,
            "purchase_price_cents": purchase_price_cents,
            "auto_note_type_installed": bool(auto_note_type_install),
        },
        "audit": {
            "deck_item_id": deck_item.id,
            "local_deck_id": local_deck_id,
            "price_cents": purchase_price_cents,
            "auto_note_type_install": bool(auto_note_type_install),
        },
    }
