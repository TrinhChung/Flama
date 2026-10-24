"""Browse Notes directly, including Notes with no template application."""

from types import SimpleNamespace

from sqlalchemy import case

from app.repositories import browse_note_repository as repository
from app.services import browse_card_service as shared
from models import db
from models.note import Note


_ROW_FIELDS = ("note_id", "deck_id", "deck_name", "word", "reading", "meaning", "tags", "status", "due_label")


def _row(payload):
    return {key: payload[key] for key in _ROW_FIELDS}


def _detail(payload):
    payload = dict(payload)
    payload["row"] = _row(payload.pop("card"))
    return payload


def _context(*, user_id, admin_mode, timezone_name, query_args, scope_only=False):
    return shared._build_browse_query(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, query_args=query_args, notes_only=True, scope_only=scope_only)


def list_notes(*, user_id, admin_mode, timezone_name, query_args):
    context = _context(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, query_args=query_args)
    if context is None:
        return {"items": [], "page": max(1, int(query_args.get("page") or 1)),
            "per_page": max(1, min(500, int(query_args.get("per_page") or 100))),
            "total": 0, "pages": 0, "has_next": False}
    total = repository.count_notes(context.query)
    if total == 0:
        return {"items": [], "page": context.page, "per_page": context.per_page,
            "total": 0, "pages": 0, "has_next": False}
    scope_cases = [(condition, str(scope.install.id)) for scope, condition in context.clone_scope_conditions]
    scope_id = case(*scope_cases, else_=None) if scope_cases else db.literal(None)
    query = repository.order_notes(context, user_id=user_id)
    pagination = repository.note_page(query, page=context.page, per_page=context.per_page,
        install_id=scope_id.label("browse_install_id"), user_id=user_id,
        pinned_installs={str(scope.install.id) for scope in context.clone_scopes if scope.install.applied_release_id})
    pagination.total = total
    scopes = {str(scope.install.id): scope for scope in context.clone_scopes}
    references = [repository.BrowseNoteReference(note, None if admin_mode or note.user_id == user_id else scopes.get(install_id))
                  for note, install_id in pagination.items]
    with shared._study_authority_conflict():
        shared.note_analytics_read_repository.raise_for_violation(shared.browse_card_repository.page_window_integrity(
            db.session, learner_user_id=user_id, card_ids=[], note_ids=[ref.note_id for ref in references]))
        options_by_deck = {}
        options = {}
        for ref in references:
            deck_id = shared._clone_local_deck_id(ref.clone_scope, ref.note) if ref.clone_scope else ref.note.deck_id
            if deck_id not in options_by_deck:
                options_by_deck[deck_id] = shared.resolve_deck_options(user_id=user_id, deck_id=deck_id,
                    deck_obj=context.deck_by_id.get(deck_id), runtime_settings=context.runtime_settings)
            options[ref.id] = options_by_deck[deck_id]
        reads = shared.load_study_authority_card_reads(db.session, learner_user_id=user_id,
            cards=references, now_utc=context.now, timezone_name=timezone_name, deck_options_by_card_id=options)

    overrides, release_values = _page_overlay_values(references)
    rows = []
    schemas = {}
    for ref in references:
        overlay = None
        if ref.clone_scope:
            install = ref.clone_scope.install
            overlay = shared._clone_overlay_fields(card_obj=ref, clone_scope=ref.clone_scope,
                base_field_values=release_values.get((str(install.applied_release_id or ""), ref.note_id)),
                note_override_rows=overrides.get((str(install.id), ref.note_id), []), schema_views=schemas)
        row = shared.vocabulary_ctrl.build_browse_row(ref, context.deck_lookup, context.now,
            progress_obj=shared._authority_progress_view(reads[ref.id]), timezone_name=timezone_name,
            display_triplet=overlay.display_triplet if overlay else None)
        if overlay:
            shared._apply_clone_card_fields(row, overlay=overlay, deck_lookup=context.deck_lookup)
        rows.append(_row(row))
    return {"items": rows, "page": context.page, "per_page": context.per_page,
        "total": total, "pages": pagination.pages, "has_next": pagination.has_next}


def _page_overlay_values(references):
    from app.repositories import flashcards_share_repository
    from app.services import deck_release_service

    release_notes, installs = {}, {}
    clone_note_ids = set()
    clone_installs = set()
    for ref in references:
        if not ref.clone_scope:
            continue
        install = ref.clone_scope.install
        clone_installs.add(str(install.id))
        clone_note_ids.add(ref.note_id)
        if install.applied_release_id:
            release_id = str(install.applied_release_id)
            release_notes.setdefault(release_id, set()).add(ref.note_id)
            installs[release_id] = install
    overrides = flashcards_share_repository.get_clone_note_field_overrides_batch(
        sorted(clone_installs), sorted(clone_note_ids)) if clone_installs else {}
    values = {}
    for release_id, note_ids in release_notes.items():
        resolved = deck_release_service.get_note_values_for_ids_at_release(installs[release_id].applied_release, note_ids)
        values.update({(release_id, str(note_id)): payload for note_id, payload in resolved.items()})
    return overrides, values


def selected_note_values(*, user_id, admin_mode, timezone_name, note_ids):
    """Authorized, pinned content for selected-Note tools, without templates."""
    ids = list(dict.fromkeys(str(value) for value in note_ids))
    if not ids:
        return []
    if len(ids) > 500:
        raise shared.BrowseApiError("Too many selected Notes", status=400)
    context = _context(user_id=user_id, admin_mode=admin_mode, timezone_name=timezone_name,
        query_args={}, scope_only=True)
    if context is None:
        raise shared.BrowseApiError("Note not found", status=404)
    scope_cases = [(condition, str(scope.install.id)) for scope, condition in context.clone_scope_conditions]
    install_id = case(*scope_cases, else_=None) if scope_cases else db.literal(None)
    page = repository.note_page(context.query.filter(Note.id.in_(ids)).order_by(Note.id),
        page=1, per_page=len(ids), install_id=install_id, user_id=user_id,
        pinned_installs={str(scope.install.id) for scope in context.clone_scopes if scope.install.applied_release_id})
    scopes = {str(scope.install.id): scope for scope in context.clone_scopes}
    references = {str(note.id): repository.BrowseNoteReference(note,
        None if admin_mode or note.user_id == user_id else scopes.get(scope)) for note, scope in page.items}
    if set(references) != set(ids):
        raise shared.BrowseApiError("Note not found", status=404)
    overrides, release_values = _page_overlay_values(references.values())
    schemas = {}
    result = []
    for note_id in ids:
        ref = references[note_id]
        note = ref.note
        values, note_type, deck_id = None, note.note_type, note.deck_id
        if ref.clone_scope:
            install = ref.clone_scope.install
            overlay = shared._clone_overlay_fields(card_obj=ref, clone_scope=ref.clone_scope,
                base_field_values=release_values.get((str(install.applied_release_id or ""), note_id)),
                note_override_rows=overrides.get((str(install.id), note_id), []), schema_views=schemas)
            values = overlay.values
            note_type = SimpleNamespace(id=note.note_type_id, name=note.note_type.name, field_defs=overlay.ordered_defs)
            deck_id = overlay.local_deck_id
        result.append(SimpleNamespace(id=note_id, note_type_id=note.note_type_id, note_type=note_type,
            deck_id=deck_id, field_values=values if values is not None else dict(note.field_values or {}),
            tags=note.tags, created_at=note.created_at, updated_at=note.updated_at))
    return result


def authorized_note(*, user_id, admin_mode, timezone_name, note_id):
    note = repository.load_note_reference(note_id)
    if note is None:
        raise shared.BrowseApiError("Note not found", status=404)
    if admin_mode or note.user_id == user_id:
        # The ownership check already authorizes this Note. Resolving every
        # installed deck again would add unrelated scope queries to each edit.
        return repository.BrowseNoteReference(note), None
    context = _context(user_id=user_id, admin_mode=admin_mode, timezone_name=timezone_name,
        query_args={}, scope_only=True)
    if context is None or not context.query.filter(Note.id == note.id).with_entities(Note.id).first():
        raise shared.BrowseApiError("Note not found", status=404)
    scope = None
    if not admin_mode and note.user_id != user_id:
        for candidate, condition in context.clone_scope_conditions:
            if Note.query.filter(Note.id == note.id, condition).with_entities(Note.id).first():
                scope = candidate
                break
        if scope is None:
            raise shared.BrowseApiError("Note not found", status=404)
    return repository.BrowseNoteReference(note, scope), context


def get_note_detail(*, user_id, admin_mode, timezone_name, note_id):
    ref, context = authorized_note(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, note_id=note_id)
    detail = shared._build_browse_detail_payload(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, card_obj=ref)
    if ref.clone_scope:
        detail = shared._apply_clone_overlay_to_browse_payload(payload=detail, card_obj=ref,
            clone_scope=ref.clone_scope, deck_lookup=context.deck_lookup)
    return _detail(detail)


def update_note(*, user_id, admin_mode, timezone_name, note_id, payload):
    ref, _context = authorized_note(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, note_id=note_id)
    note = ref.note
    note_type = note.note_type
    try:
        values = None
        if ref.clone_scope:
            from app.services.clone_field_identity_service import lock_clone_overlay_write
            ref.clone_scope.install = lock_clone_overlay_write(ref.clone_scope.install,
                expected_revision=payload.get("expected_overlay_revision") if isinstance(payload, dict) else None)
            overlay = shared._clone_overlay_fields(card_obj=ref, clone_scope=ref.clone_scope)
            note_type = SimpleNamespace(id=note.note_type_id, field_defs=overlay.ordered_defs)
            values = overlay.values
        else:
            from app.services.note_value_precondition_service import check_note_write_preconditions
            check_note_write_preconditions(note, payload)
        validated = shared.validate_browse_card_update_request(note_type=note_type, payload=payload,
            current_values=values if values is not None else dict(note.field_values or {}),
            note_media_ids=shared._collect_note_media_refs(note))
    except shared.RequestValidationError as exc:
        raise shared.BrowseCardUpdateError(str(exc), status=exc.status, field=exc.field,
            code=exc.code, include_details=True) from exc
    if ref.clone_scope:
        result = shared._update_clone_browse_card(user_id=user_id, timezone_name=timezone_name,
            card_obj=ref, note_obj=note, clone_scope=ref.clone_scope, validated=validated)
    else:
        result = shared._update_owned_browse_card(user_id=user_id, admin_mode=admin_mode,
            timezone_name=timezone_name, card_obj=ref, note_obj=note, validated=validated)
    result["detail"] = _detail(result["detail"])
    if "row" in result:
        result["row"] = _row(result["row"])
    return result


def build_decks(*, user_id, admin_mode, timezone_name):
    context = _context(user_id=user_id, admin_mode=admin_mode, timezone_name=timezone_name,
        query_args={}, scope_only=True)
    if context is None:
        return {"decks": []}
    tree = shared.vocabulary_ctrl.build_browse_deck_tree_payload(user_id=user_id,
        admin_mode=admin_mode, timezone_name=timezone_name, progress_counts=False)
    boundary = int(context.runtime_settings.day_boundary_hour_local)
    today = shared.study_repository._today_day_index(now=context.now, timezone_name=timezone_name,
        day_boundary_hour_local=boundary)
    with shared._study_authority_conflict():
        direct = repository.deck_counts(context, user_id=user_id, admin_mode=admin_mode,
            today_day_index=today, day_cutoff_utc=shared._day_index_to_datetime(today + 1, boundary, timezone_name=timezone_name))
    flat = []

    def flatten(nodes):
        for node in nodes:
            flat.append({key: node.get(key) for key in (
                "id", "name", "path", "parent_id", "note_type_id", "note_type_name",
                "note_type_ids", "note_type_names", "has_mixed_note_types")})
            counts = dict(direct.get(int(node["id"]), {"total": 0, "new": 0, "learn": 0, "due": 0}))
            node["counts"] = counts
            flat[-1]["counts"] = counts
            flatten(node.get("children", []))
            for child in node.get("children", []):
                for key in counts:
                    counts[key] += child["counts"][key]
    flatten(tree)
    return {"decks": flat}
