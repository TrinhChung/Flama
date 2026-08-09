"""Sub-module for flashcard routes."""

from __future__ import annotations

from datetime import datetime
from flask import jsonify, request, redirect, url_for, flash, render_template
from flask_login import current_user, login_required
from typing import Any
from models import db
from models.flashcard import *
from models.deck import Deck
from app.services import marketplace_taxonomy_service
from app.utils.permissions import is_admin_user, is_creator_user

# Import everything from core module so routes can use helpers
from . import *

from app.routes.flashcards import (
    _api_error,
    _apply_deck_marketplace_payload,
    _apply_note_type_marketplace_payload,
    _collect_accessible_decks_for_import,
    _deck_path_label,
    _default_uniqueness_fields,
    _get_note_type_or_404,
    _infer_default_note_type_id_for_deck,
    _parse_bool,
    _recompute_note_type_market_stats,
    _resolve_single_note_type_for_deck,
    _serialize_note_type_for_import,
)


def _build_taxonomy_template_context(*, content_type: str, item: Any | None = None, form_state: dict[str, Any] | None = None) -> dict[str, Any]:
    taxonomy_initial = (
        marketplace_taxonomy_service.get_item_taxonomy(item, content_type=content_type)
        if item is not None
        else marketplace_taxonomy_service.empty_taxonomy_metadata()
    )
    if form_state:
        normalized, _ = marketplace_taxonomy_service.normalize_taxonomy_payload(form_state, content_type=content_type)
        taxonomy_initial = normalized
    return {
        "taxonomy_schema": marketplace_taxonomy_service.build_taxonomy_schema(content_type=content_type),
        "taxonomy_initial": taxonomy_initial,
    }


def _share_form_payload_from_request() -> dict[str, Any]:
    return {
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "preview_text": request.form.get("preview_text", "").strip(),
        "pricing_mode": request.form.get("pricing_mode", "free").strip(),
        "price_amount_minor": request.form.get("price_amount_minor", request.form.get("price_cents", 0)),
        "tags": [item.strip() for item in request.form.get("tags", "").split(",") if item.strip()],
        "taxonomy_domain": request.form.get("taxonomy_domain", "").strip(),
        "taxonomy_subject": request.form.get("taxonomy_subject", "").strip(),
        "taxonomy_difficulty_band": request.form.get("taxonomy_difficulty_band", "").strip(),
        "taxonomy_framework": request.form.get("taxonomy_framework", "").strip(),
        "taxonomy_framework_level": request.form.get("taxonomy_framework_level", "").strip(),
        "taxonomy_framework_track": request.form.get("taxonomy_framework_track", "").strip(),
        "learning_goals": request.form.getlist("learning_goals"),
        "primary_topics": request.form.getlist("primary_topics"),
        "format_features": request.form.getlist("format_features"),
        "taxonomy_audience": request.form.get("taxonomy_audience", "").strip(),
        "taxonomy_best_used_for": request.form.get("taxonomy_best_used_for", "").strip(),
    }


def _build_deck_share_form_state(deck: Deck, existing_item: DeckMarketplaceItem | None) -> dict[str, Any]:
    taxonomy = (
        marketplace_taxonomy_service.get_item_taxonomy(existing_item, content_type="deck_marketplace_item")
        if existing_item is not None
        else marketplace_taxonomy_service.empty_taxonomy_metadata()
    )
    return {
        "title": existing_item.title if existing_item is not None else deck.name,
        "description": existing_item.description if existing_item is not None else "",
        "preview_text": existing_item.preview_text if existing_item is not None else "",
        "pricing_mode": existing_item.pricing_mode if existing_item is not None else "free",
        "price_amount_minor": int(existing_item.price_amount_minor or 0) if existing_item is not None else 0,
        "version": existing_item.version if existing_item is not None else "1.0.0",
        "changelog": existing_item.changelog if existing_item is not None else "",
        "tags": list(existing_item.tags or []) if existing_item is not None else [],
        "taxonomy_domain": taxonomy.get("domain") or "",
        "taxonomy_subject": taxonomy.get("subject") or "",
        "taxonomy_difficulty_band": taxonomy.get("difficulty_band") or "",
        "taxonomy_framework": taxonomy.get("framework") or "",
        "taxonomy_framework_level": taxonomy.get("framework_level") or "",
        "taxonomy_framework_track": taxonomy.get("framework_track") or "",
        "learning_goals": list(taxonomy.get("learning_goals") or []),
        "primary_topics": list(taxonomy.get("primary_topics") or []),
        "format_features": list(taxonomy.get("format_features") or []),
        "taxonomy_audience": taxonomy.get("audience") or "",
        "taxonomy_best_used_for": "",
    }


def _build_note_type_share_form_state(note_type: NoteType) -> dict[str, Any]:
    taxonomy = marketplace_taxonomy_service.get_item_taxonomy(note_type, content_type="note_type")
    return {
        "title": note_type.name or "",
        "description": note_type.description or "",
        "preview_text": note_type.preview_text or "",
        "pricing_mode": note_type.pricing_mode or "free",
        "price_amount_minor": int(note_type.price_amount_minor or 0),
        "version": note_type.version or "1.0.0",
        "changelog": note_type.changelog or "",
        "tags": list(note_type.tags or []),
        "taxonomy_domain": taxonomy.get("domain") or "",
        "taxonomy_subject": taxonomy.get("subject") or "",
        "taxonomy_difficulty_band": taxonomy.get("difficulty_band") or "",
        "taxonomy_framework": taxonomy.get("framework") or "",
        "taxonomy_framework_level": taxonomy.get("framework_level") or "",
        "taxonomy_framework_track": taxonomy.get("framework_track") or "",
        "learning_goals": list(taxonomy.get("learning_goals") or []),
        "primary_topics": list(taxonomy.get("primary_topics") or []),
        "format_features": list(taxonomy.get("format_features") or []),
        "taxonomy_audience": taxonomy.get("audience") or "",
        "taxonomy_best_used_for": taxonomy.get("best_used_for") or "",
    }


def _render_share_deck_publish_page(
    *,
    deck: Deck,
    existing_item: DeckMarketplaceItem | None,
    form_state: dict[str, Any] | None = None,
):
    resolved_form_state = form_state or _build_deck_share_form_state(deck, existing_item)
    return render_template(
        "flashcards/shared_deck_publish.html",
        deck=deck,
        existing_item=existing_item,
        form_state=resolved_form_state,
        taxonomy_content_type="deck_marketplace_item",
        **_build_taxonomy_template_context(
            content_type="deck_marketplace_item",
            item=existing_item,
            form_state=resolved_form_state,
        ),
    )


def _render_share_note_type_publish_page(
    *,
    note_type: NoteType,
    form_state: dict[str, Any] | None = None,
):
    resolved_form_state = form_state or _build_note_type_share_form_state(note_type)
    return render_template(
        "flashcards/shared_note_type_publish.html",
        note_type=note_type,
        form_state=resolved_form_state,
        taxonomy_content_type="note_type",
        **_build_taxonomy_template_context(
            content_type="note_type",
            item=note_type,
            form_state=resolved_form_state,
        ),
    )


def _share_deck_page_impl(deck: Deck):
    from app.services.deck_access_policy import can_user_edit_deck

    if not can_user_edit_deck(current_user, deck):
        flash("You do not have permission to share this deck.", "danger")
        return redirect(url_for("main.dashboard"))

    if deck.owner_user_id == current_user.id:
        from models.flashcard import DeckInstall

        if DeckInstall.query.filter_by(user_id=current_user.id, local_deck_id=deck.id).first():
            flash("Installed marketplace decks cannot be re-shared.", "danger")
            return redirect(url_for("main.dashboard"))

    from models.flashcard import DeckMarketplaceItem

    current_parent = deck.parent_id
    while current_parent is not None:
        parent_deck = Deck.query.get(current_parent)
        if not parent_deck:
            break
        if DeckMarketplaceItem.query.filter_by(source_deck_id=parent_deck.id).first():
            flash(f"Parent deck '{parent_deck.name}' is already shared.", "warning")
            return redirect(url_for("main.dashboard"))
        current_parent = parent_deck.parent_id

    existing_item = DeckMarketplaceItem.query.filter_by(source_deck_id=deck.id).first()
    existing_item_was_found = existing_item is not None

    if request.method == "POST":
        form_state = _share_form_payload_from_request()
        form_state["version"] = (
            request.form.get("version")
            or (existing_item.version if existing_item else "1.0.0")
            or "1.0.0"
        ).strip()
        form_state["changelog"] = request.form.get("changelog", "").strip()
        form_state["publish_status"] = "published"

        if not form_state["title"]:
            flash("Title is required.", "danger")
            return _render_share_deck_publish_page(
                deck=deck,
                existing_item=existing_item,
                form_state=form_state,
            )

        resolved_note_type_id, resolve_error = _resolve_single_note_type_for_deck(
            deck_id=deck.id,
            owner_user_id=current_user.id,
        )
        if resolve_error:
            flash(resolve_error, "danger")
            return _render_share_deck_publish_page(
                deck=deck,
                existing_item=existing_item,
                form_state=form_state,
            )

        if not existing_item:
            existing_item = DeckMarketplaceItem(
                source_deck_id=deck.id,
                owner_user_id=current_user.id,
                is_official=is_admin_user(current_user),
                install_count=0,
                rating_avg=0.0,
                rating_count=0,
            )

        payload = dict(form_state)
        payload["source_deck_id"] = deck.id
        payload["source_note_type_id"] = resolved_note_type_id
        payload["publish_status"] = "published"
        metadata_error = _apply_deck_marketplace_payload(existing_item, payload)
        if metadata_error:
            flash(metadata_error, "danger")
            return _render_share_deck_publish_page(
                deck=deck,
                existing_item=existing_item,
                form_state=form_state,
            )

        from app.services.flashcard_import_service import share_deck_and_commit

        share_deck_and_commit(existing_item, is_new=not existing_item_was_found)
        flash("Deck listing updated in study catalog.", "success")
        return redirect(url_for("flashcards.shared_decks_page"))

    return _render_share_deck_publish_page(deck=deck, existing_item=existing_item)


def _share_note_type_page_impl(note_type: NoteType):
    if request.method == "POST":
        form_state = _share_form_payload_from_request()
        form_state["version"] = (request.form.get("version") or note_type.version or "1.0.0").strip()
        form_state["changelog"] = request.form.get("changelog", "").strip()
        form_state["publish_status"] = "published"
        payload = dict(form_state)
        payload["name"] = form_state.get("title") or note_type.name
        payload["publish_status"] = "published"

        metadata_error = _apply_note_type_marketplace_payload(note_type, payload)
        if metadata_error:
            flash(metadata_error, "danger")
            return _render_share_note_type_publish_page(note_type=note_type, form_state=form_state)

        from app.services.note_type_service import update_note_type_and_commit

        update_note_type_and_commit(note_type)
        flash("Template listing updated in study catalog.", "success")
        return redirect(url_for("flashcards.shared_note_type_detail_page", note_type_id=note_type.id))

    return _render_share_note_type_publish_page(note_type=note_type)



@flashcards_bp.route("/flashcards/decks/<int:deck_id>/share", methods=["GET", "POST"])
@login_required
def share_deck_page(deck_id: int):
    deck = Deck.query.get_or_404(deck_id)
    return _share_deck_page_impl(deck)


@flashcards_bp.route("/flashcards/note-types/<note_type_id>/share", methods=["GET", "POST"])
@login_required
def share_note_type_page(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return redirect(url_for("flashcards.note_type_manager"))
    return _share_note_type_page_impl(note_type)


@flashcards_bp.route("/flashcards/import")
@login_required
def flashcard_import_page():
    if not is_creator_user(current_user):
        flash("Bạn không có quyền truy cập trang đồng bộ Anki.", "warning")
        return redirect(url_for("main.dashboard"))
    decks = _collect_accessible_decks_for_import()
    deck_map = {deck.id: deck for deck in decks}
    deck_options = [
        {
            "id": deck.id,
            "name": deck.name,
            "path": _deck_path_label(deck, deck_map),
            "note_type_id": deck.note_type_id,
            "parent_id": deck.parent_id,
        }
        for deck in decks
    ]

    selected_deck_id: int | None = None
    selected_deck_raw = (request.args.get("deck_id") or "").strip()
    if selected_deck_raw:
        try:
            candidate = int(selected_deck_raw)
            if candidate in deck_map:
                selected_deck_id = candidate
        except (TypeError, ValueError):
            selected_deck_id = None
    if selected_deck_id is None and deck_options:
        selected_deck_id = int(deck_options[0]["id"])

    note_types = (
        NoteType.query.filter_by(user_id=current_user.id)
        .order_by(NoteType.name.asc(), NoteType.updated_at.desc())
        .all()
    )
    note_type_options = [_serialize_note_type_for_import(note_type) for note_type in note_types]
    note_type_map = {item["id"]: item for item in note_type_options}

    selected_note_type_id = (request.args.get("note_type_id") or "").strip() or None
    if selected_note_type_id and selected_note_type_id not in note_type_map:
        selected_note_type_id = None

    if selected_note_type_id is None and selected_deck_id is not None:
        inferred = _infer_default_note_type_id_for_deck(selected_deck_id)
        if inferred and inferred in note_type_map:
            selected_note_type_id = inferred

    if selected_note_type_id is None and note_type_options:
        selected_note_type_id = note_type_options[0]["id"]

    uniqueness_defaults = {
        note_type.id: _default_uniqueness_fields(note_type)
        for note_type in note_types
    }

    return render_template(
        "flashcards/import.html",
        deck_options=deck_options,
        note_type_options=note_type_options,
        initial_deck_id=selected_deck_id,
        initial_note_type_id=selected_note_type_id,
        uniqueness_defaults=uniqueness_defaults,
    )


@flashcards_bp.route("/api/flashcards/import/options")
@login_required
def flashcard_import_options():
    if not is_creator_user(current_user):
        return _api_error("FORBIDDEN", "Chỉ quản trị viên mới có quyền sử dụng tính năng đồng bộ Anki.", status=403)
    from app.services import flashcard_import_api_service

    return jsonify(
        flashcard_import_api_service.build_import_options(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            deck_id_raw=request.args.get("deck_id"),
            note_type_id_raw=request.args.get("note_type_id"),
        )
    )


@flashcards_bp.route("/api/flashcards/import/parse", methods=["POST"])
@login_required
def flashcard_import_parse():
    if not is_creator_user(current_user):
        return _api_error("FORBIDDEN", "Chỉ quản trị viên mới có quyền sử dụng tính năng đồng bộ Anki.", status=403)
    from app.services import flashcard_import_api_service

    upload = request.files.get("file")
    try:
        payload = flashcard_import_api_service.parse_import_file(
            user_id=current_user.id,
            note_type_id=str(request.form.get("note_type_id") or "").strip(),
            filename=str(getattr(upload, "filename", "") or ""),
            file_bytes=upload.read() if upload is not None else b"",
            delimiter_mode=str(
                request.form.get("delimiter_mode") or "csv"
            ).strip().lower(),
            custom_delimiter=request.form.get("custom_delimiter"),
            has_header=_parse_bool(
                request.form.get("has_header"),
                default=True,
            ),
        )
    except flashcard_import_api_service.ImportApiError as exc:
        return _api_error(
            "FIELD_NOT_FOUND" if exc.status == 404 else "VALIDATION_ERROR",
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload)

@flashcards_bp.route("/api/flashcards/import/estimate", methods=["POST"])
@login_required
def flashcard_import_estimate():
    if not is_creator_user(current_user):
        return _api_error("FORBIDDEN", "Chỉ quản trị viên mới có quyền sử dụng tính năng đồng bộ Anki.", status=403)
    from app.services import flashcard_import_api_service

    try:
        payload = flashcard_import_api_service.run_import_request(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=request.get_json(silent=True) or {},
            apply_changes=False,
        )
    except flashcard_import_api_service.ImportApiError as exc:
        return _api_error(
            "VALIDATION_ERROR",
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload)

@flashcards_bp.route("/api/flashcards/import/execute", methods=["POST"])
@login_required
def flashcard_import_execute():
    if not is_creator_user(current_user):
        return _api_error("FORBIDDEN", "Chỉ quản trị viên mới có quyền sử dụng tính năng đồng bộ Anki.", status=403)
    from app.services import flashcard_import_api_service

    try:
        payload = flashcard_import_api_service.run_import_request(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=request.get_json(silent=True) or {},
            apply_changes=True,
        )
    except flashcard_import_api_service.ImportApiError as exc:
        return _api_error(
            "VALIDATION_ERROR",
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload)

@flashcards_bp.route("/api/shared/seed-defaults", methods=["POST"])
@login_required
def seed_marketplace_defaults():
    if not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Admin only endpoint.", status=403)

    system_admin = current_user
    if not system_admin.is_admin:
        from app.services.flashcard_import_service import admin_user_set_is_admin
        admin_user_set_is_admin(system_admin)

    admin_id = system_admin.id

    note_type, _template = ensure_legacy_note_type(db.session, admin_id)
    note_type.description = note_type.description or "Official default Japanese vocabulary note type."
    note_type.primary_category = note_type.primary_category or "Japanese"
    note_type.tags = note_type.tags or ["official", "default", "japanese"]
    note_type.preview_text = note_type.preview_text or "Word / Reading / Meaning default layout."
    note_type.pricing_mode = "free"
    note_type.price_amount_minor = 0
    note_type.version = note_type.version or "1.0.0"
    note_type.is_official = True
    note_type.publish_status = "published"
    note_type.published_at = note_type.published_at or datetime.utcnow()
    _recompute_note_type_market_stats(note_type)

    deck_item = DeckMarketplaceItem.query.filter_by(
        owner_user_id=admin_id,
        is_official=True,
        title="Official Starter Deck",
    ).first()
    source_deck = Deck.query.order_by(Deck.id.asc()).first()
    if source_deck is None:
        return _api_error(
            "VALIDATION_ERROR",
            "Cannot seed official shared deck without at least one source deck.",
            status=409,
        )
    # Stamp ownership on the source deck so it is recognised as admin-owned
    if source_deck.owner_user_id is None:
        source_deck.owner_user_id = admin_id
    is_new_deck_item = False
    if deck_item is None:
        is_new_deck_item = True
        deck_item = DeckMarketplaceItem(
            owner_user_id=admin_id,
            source_deck_id=source_deck.id,
            source_note_type_id=note_type.id,
            title="Official Starter Deck",
            description="Official default deck for new users.",
            primary_category="Japanese",
            tags=["official", "default", "starter"],
            preview_text="Starter deck with basic Japanese vocabulary.",
            sample_cards_count=20,
            pricing_mode="free",
            price_amount_minor=0,
            version="1.0.0",
            publish_status="published",
            is_official=True,
            published_at=datetime.utcnow(),
        )
    from app.services.flashcard_import_service import seed_marketplace_defaults_commit
    seed_marketplace_defaults_commit(admin_id, note_type, deck_item, is_new_deck_item)
    return jsonify({"note_type_id": note_type.id, "deck_item_id": deck_item.id})
