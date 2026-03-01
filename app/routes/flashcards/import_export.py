"""Sub-module for flashcard routes."""

from __future__ import annotations

import logging
from datetime import datetime
from flask import jsonify, request, redirect, url_for, flash, render_template, send_file, current_app
from flask_login import current_user, login_required
from sqlalchemy.exc import OperationalError
from models import db
from models.flashcard import *
from models.deck import Deck
from models.card_progress import CardProgress
from app.utils.permissions import is_admin_user

# Import everything from core module so routes can use helpers
from . import *

from app.routes.flashcards import (
    _api_error,
    _audit,
    _collect_accessible_decks_for_import,
    _deck_path_label,
    _default_uniqueness_fields,
    _get_note_type_or_404,
    _infer_default_note_type_id_for_deck,
    _parse_bool,
    _recompute_deck_item_market_stats,
    _recompute_note_type_market_stats,
    _resolve_import_execution_payload,
    _resolve_single_note_type_for_deck,
    _serialize_note_type_for_import,
    _touch_note_type_install_usage,
)



@flashcards_bp.route("/flashcards/decks/<int:deck_id>/share", methods=["GET", "POST"])
@login_required
def share_deck_page(deck_id: int):
    deck = Deck.query.get_or_404(deck_id)
    
    # Validation 1: Ownership
    from app.services.deck_access_policy import can_user_edit_deck
    if not can_user_edit_deck(current_user, deck):
        flash("Bạn không có quyền chia sẻ deck này.", "danger")
        return redirect(url_for("main.dashboard"))

    # Validation 2: Is downloaded deck (cannot re-share a downloaded deck)
    if deck.owner_user_id == current_user.id:
        from models.flashcard import DeckInstall
        # If user has an install record for this exact local deck, block re-sharing
        if DeckInstall.query.filter_by(user_id=current_user.id, local_deck_id=deck.id).first():
            flash("Bạn không thể chia sẻ lại deck đã được cài đặt từ Marketplace.", "danger")
            return redirect(url_for("main.dashboard"))
        
    # Validation 3: Child deck of a shared deck cannot be shared
    from models.flashcard import DeckMarketplaceItem
    current_parent = deck.parent_id
    while current_parent is not None:
        parent_deck = Deck.query.get(current_parent)
        if not parent_deck:
            break
        if DeckMarketplaceItem.query.filter_by(source_deck_id=parent_deck.id).first():
            flash(f"Deck cha '{parent_deck.name}' đã được chia sẻ. Không thể chia sẻ riêng lẻ deck con.", "warning")
            return redirect(url_for("main.dashboard"))
        current_parent = parent_deck.parent_id

    # Existing marketplace item
    existing_item = DeckMarketplaceItem.query.filter_by(source_deck_id=deck.id).first()
    existing_item_was_found = existing_item is not None

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        preview_text = request.form.get("preview_text", "").strip()
        primary_category = request.form.get("primary_category", "Japanese").strip()
        tags_raw = request.form.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        pricing_mode = request.form.get("pricing_mode", "free")
        # Ensure only published free, logic can be updated for payment later
        price_cents = int(request.form.get("price_cents", 0)) if pricing_mode == "paid" else 0
        
        if not title:
            flash("Tên hiển thị không được để trống.", "danger")
            return render_template("flashcards/shared_deck_publish.html", deck=deck, existing_item=existing_item)

        resolved_note_type_id, resolve_error = _resolve_single_note_type_for_deck(
            deck_id=deck.id,
            owner_user_id=current_user.id,
        )
        if resolve_error:
            flash(resolve_error, "danger")
            return render_template("flashcards/shared_deck_publish.html", deck=deck, existing_item=existing_item)            
        if not existing_item:
            existing_item = DeckMarketplaceItem(
                source_deck_id=deck.id,
                owner_user_id=current_user.id,
                is_official=is_admin_user(current_user),
                install_count=0,
                rating_avg=0.0,
                rating_count=0,
            )
            
        existing_item.title = title
        existing_item.description = description
        existing_item.preview_text = preview_text
        existing_item.primary_category = primary_category
        existing_item.tags = tags
        existing_item.pricing_mode = pricing_mode
        existing_item.price_cents = price_cents
        existing_item.source_note_type_id = resolved_note_type_id
        existing_item.publish_status = "published"

        from app.services.flashcard_import_service import share_deck_and_commit
        share_deck_and_commit(existing_item, is_new=not existing_item_was_found)
        flash("Tuyệt vời! Deck của bạn đã được chia sẻ lên Marketplace.", "success")
        return redirect(url_for("flashcards.shared_decks_page"))

    return render_template("flashcards/shared_deck_publish.html", deck=deck, existing_item=existing_item)

@flashcards_bp.route("/flashcards/import")
@login_required
def flashcard_import_page():
    decks = _collect_accessible_decks_for_import()
    deck_map = {deck.id: deck for deck in decks}
    deck_options = [
        {
            "id": deck.id,
            "name": deck.name,
            "path": _deck_path_label(deck, deck_map),
            "note_type_id": deck.note_type_id,
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

@flashcards_bp.route("/api/flashcards/import/parse", methods=["POST"])
@login_required
def flashcard_import_parse():
    note_type_id = (request.form.get("note_type_id") or "").strip()
    note_type = _get_note_type_or_404(note_type_id)
    if note_type is None:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404, field="note_type_id")

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return _api_error("VALIDATION_ERROR", "Import file is required.", field="file")

    delimiter_mode = (request.form.get("delimiter_mode") or "csv").strip().lower()
    custom_delimiter = request.form.get("custom_delimiter")
    has_header = _parse_bool(request.form.get("has_header"), default=True)

    try:
        delimiter = resolve_delimiter(delimiter_mode, custom_delimiter)
    except ImportValidationError as exc:
        return _api_error("VALIDATION_ERROR", str(exc), field="delimiter_mode")

    file_bytes = upload.read()
    try:
        summary = create_import_session(
            user_id=current_user.id,
            filename=upload.filename,
            file_bytes=file_bytes,
            delimiter=delimiter,
            has_header=has_header,
            field_count=len(note_type.field_defs),
        )
    except ImportValidationError as exc:
        return _api_error("VALIDATION_ERROR", str(exc))

    suggestions = suggest_mapping(
        field_defs=note_type.field_defs,
        has_header=has_header,
        header=summary.get("header") or [],
        column_count=int(summary.get("column_count") or 0),
    )

    return jsonify(
        {
            "token": summary.get("token"),
            "delimiter": delimiter,
            "has_header": has_header,
            "columns": summary.get("columns") or [],
            "column_count": int(summary.get("column_count") or 0),
            "total_rows": int(summary.get("total_rows") or 0),
            "preview_rows": summary.get("preview_rows") or [],
            "warnings": summary.get("warnings") or [],
            "suggested_mapping": suggestions,
        }
    )

@flashcards_bp.route("/api/flashcards/import/estimate", methods=["POST"])
@login_required
def flashcard_import_estimate():
    payload = request.get_json(silent=True) or {}
    try:
        session_meta, note_type, target_deck_id = _resolve_import_execution_payload(payload)
        report = run_import(
            user_id=current_user.id,
            session_meta=session_meta,
            note_type=note_type,
            target_deck_id=target_deck_id,
            mode=(payload.get("import_mode") or "upsert"),
            uniqueness_fields=payload.get("uniqueness_fields") or [],
            raw_mapping=payload.get("mapping") if isinstance(payload.get("mapping"), dict) else {},
            dont_overwrite_empty=_parse_bool(payload.get("dont_overwrite_empty"), default=True),
            confirm_column_mismatch=_parse_bool(payload.get("confirm_column_mismatch"), default=False),
            apply_changes=False,
            chunk_size=payload.get("chunk_size"),
        )
    except ImportValidationError as exc:
        return _api_error("VALIDATION_ERROR", str(exc))

    return jsonify(report)

@flashcards_bp.route("/api/flashcards/import/execute", methods=["POST"])
@login_required
def flashcard_import_execute():
    payload = request.get_json(silent=True) or {}
    try:
        session_meta, note_type, target_deck_id = _resolve_import_execution_payload(payload)
        report = run_import(
            user_id=current_user.id,
            session_meta=session_meta,
            note_type=note_type,
            target_deck_id=target_deck_id,
            mode=(payload.get("import_mode") or "upsert"),
            uniqueness_fields=payload.get("uniqueness_fields") or [],
            raw_mapping=payload.get("mapping") if isinstance(payload.get("mapping"), dict) else {},
            dont_overwrite_empty=_parse_bool(payload.get("dont_overwrite_empty"), default=True),
            confirm_column_mismatch=_parse_bool(payload.get("confirm_column_mismatch"), default=False),
            apply_changes=True,
            chunk_size=payload.get("chunk_size"),
        )
    except ImportValidationError as exc:
        return _api_error("VALIDATION_ERROR", str(exc))

    summary = report.get("summary") or {}
    if int(summary.get("inserted") or 0) > 0 or int(summary.get("updated") or 0) > 0:
        _touch_note_type_install_usage(user_id=current_user.id, installed_note_type_id=note_type.id)
        install_rows = NoteTypeInstall.query.filter_by(
            user_id=current_user.id,
            installed_note_type_id=note_type.id,
        ).all()
        for install in install_rows:
            source_note_type = NoteType.query.get(install.source_note_type_id)
            if source_note_type:
                _recompute_note_type_market_stats(source_note_type)

    from app.services.flashcard_import_service import flashcard_import_execute_commit
    flashcard_import_execute_commit(note_type, target_deck_id, report.get("mode"), summary)
    return jsonify(report)

@flashcards_bp.route("/api/shared/seed-defaults", methods=["POST"])
@login_required
def seed_marketplace_defaults():
    if not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Admin only endpoint.", status=403)

    import os
    from models.user import User
    admin_email = os.environ.get("ADMIN_EMAIL", "chungtrinh2k2@gmail.com")
    admin_user_name = os.environ.get("ADMIN_USERNAME") or os.environ.get("ADMIN_USER", "chungtrinh2k2")
    admin_password = os.environ.get("ADMIN_PASSWORD", "chungtrinh1904")

    from app.services.flashcard_import_service import admin_user_ensure_created
    system_admin = admin_user_ensure_created(admin_email, admin_user_name, admin_password)
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
    note_type.price_cents = 0
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
            price_cents=0,
            version="1.0.0",
            publish_status="published",
            is_official=True,
            published_at=datetime.utcnow(),
        )
    from app.services.flashcard_import_service import seed_marketplace_defaults_commit
    seed_marketplace_defaults_commit(admin_id, note_type, deck_item, is_new_deck_item)
    return jsonify({"note_type_id": note_type.id, "deck_item_id": deck_item.id})

