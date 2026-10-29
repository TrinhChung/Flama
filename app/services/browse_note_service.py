"""Browse Notes directly, including Notes with no template application."""

from types import SimpleNamespace

from sqlalchemy import case

from app.repositories import browse_note_repository as repository
from app.services import browse_card_service as shared
from models import db
from models.note import Note
from app.services.note_base_context import published_base_enabled
from app.services.effective_note_reader import install_release_id, base_note_values_for_ids


_ROW_FIELDS = ("note_id", "deck_id", "deck_name", "word", "reading", "meaning", "tags", "status", "due_label")


def _row(payload):
    row = {key: payload[key] for key in _ROW_FIELDS}
    if "base_changed" in payload:
        row["base_changed"] = bool(payload["base_changed"])
    return row


def _detail(payload):
    payload = dict(payload)
    payload["row"] = _row(payload.pop("card"))
    return payload


def _context(*, user_id, admin_mode, timezone_name, query_args, scope_only=False, scope_note=None):
    return shared._build_browse_query(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, query_args=query_args, notes_only=True, scope_only=scope_only, scope_note=scope_note)


def list_notes(*, user_id, admin_mode, timezone_name, query_args):
    context = _context(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, query_args=query_args)
    if context is None:
        return {"items": [], "page": max(1, int(query_args.get("page") or 1)),
            "per_page": max(1, min(500, int(query_args.get("per_page") or 100))),
            "total": 0, "pages": 0, "has_next": False}
    scope_cases = [(condition, str(scope.install.id)) for scope, condition in context.clone_scope_conditions]
    scope_id = case(*scope_cases, else_=None) if scope_cases else db.literal(None)
    pinned_installs = {str(scope.install.id) for scope in context.clone_scopes if scope.install.applied_release_id and not published_base_enabled()}
    if context.keyword:
        pagination = repository.search_note_page(context, install_id=scope_id.label('browse_install_id'),
            user_id=user_id, pinned_installs=pinned_installs)
        total = pagination.total
    else:
        total = repository.count_notes(context.query)
        if total == 0:
            return {"items": [], "page": context.page, "per_page": context.per_page,
                "total": 0, "pages": 0, "has_next": False}
        query = repository.order_notes(context, user_id=user_id)
        pagination = repository.note_page(query, page=context.page, per_page=context.per_page,
            install_id=scope_id.label("browse_install_id"), user_id=user_id, pinned_installs=pinned_installs)
        pagination.total = total
    if not pagination.items:
        return {"items": [], "page": context.page, "per_page": context.per_page,
            "total": total, "pages": pagination.pages, "has_next": pagination.has_next}
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
                base_field_values=release_values.get((str(install_release_id(install) or ""), ref.note_id)),
                note_override_rows=overrides.get((str(install.id), ref.note_id), []), schema_views=schemas)
        row = shared.vocabulary_ctrl.build_browse_row(ref, context.deck_lookup, context.now,
            progress_obj=shared._authority_progress_view(reads[ref.id]), timezone_name=timezone_name,
            display_triplet=overlay.display_triplet if overlay else None)
        if overlay:
            shared._apply_clone_card_fields(row, overlay=overlay, deck_lookup=context.deck_lookup)
            if published_base_enabled():
                from app.services.note_base_comparison_service import overrides_base_changed
                row["base_changed"] = overrides_base_changed(install,
                    release_values.get((str(install_release_id(install) or ""), ref.note_id), {}),
                    overrides.get((str(install.id), ref.note_id), []))
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
        if published_base_enabled() or install.applied_release_id:
            release_id = str(install_release_id(install) or "")
            release_notes.setdefault(release_id, set()).add(ref.note_id)
            installs[release_id] = install
    overrides = flashcards_share_repository.get_clone_note_field_overrides_batch(
        sorted(clone_installs), sorted(clone_note_ids)) if clone_installs else {}
    values = {}
    for release_id, note_ids in release_notes.items():
        resolved = base_note_values_for_ids(installs[release_id], note_ids)
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
        pinned_installs={str(scope.install.id) for scope in context.clone_scopes if scope.install.applied_release_id and not published_base_enabled()})
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
        tags = note.tags
        if published_base_enabled() and not ref.clone_scope:
            from app.services.note_draft_service import effective_note_metadata
            metadata = effective_note_metadata(note)
            deck_id, tags = metadata["deck_id"], metadata["tags"]
        if ref.clone_scope:
            install = ref.clone_scope.install
            overlay = shared._clone_overlay_fields(card_obj=ref, clone_scope=ref.clone_scope,
                base_field_values=release_values.get((str(install_release_id(install) or ""), note_id)),
                note_override_rows=overrides.get((str(install.id), note_id), []), schema_views=schemas)
            values = overlay.values
            note_type = SimpleNamespace(id=note.note_type_id, name=note.note_type.name, field_defs=overlay.ordered_defs)
            deck_id = overlay.local_deck_id
        result.append(SimpleNamespace(id=note_id, note_type_id=note.note_type_id, note_type=note_type,
            deck_id=deck_id, field_values=values if values is not None else dict(note.field_values or {}),
            tags=tags, created_at=note.created_at, updated_at=note.updated_at))
    return result


def authorized_note(*, user_id, admin_mode, timezone_name, note_id, include_media=True, defer_clone_values=False):
    note = repository.load_note_reference(note_id, include_media=include_media,
        include_live_values=not defer_clone_values or admin_mode)
    if note is None:
        raise shared.BrowseApiError("Note not found", status=404)
    if admin_mode or note.user_id == user_id:
        if published_base_enabled():
            from app.services.note_draft_service import effective_note_metadata
            if effective_note_metadata(note).get("op") == "delete":
                raise shared.BrowseApiError("Note not found", status=404)
        # The ownership check already authorizes this Note. Resolving every
        # installed deck again would add unrelated scope queries to each edit.
        if defer_clone_values:
            repository.ensure_live_values(note)
        return repository.BrowseNoteReference(note), None
    from app.services import flashcards_share
    with shared._study_authority_conflict():
        shared.lock_study_authority_route(db.session, learner_user_id=user_id, allow_note_authority=True)
    # Preserve install-root precedence, but a single-Note read needs neither
    # the whole accessible deck tree nor the list's progress/scheduler query.
    for root_id in repository.clone_scope_roots_for_note(user_id=user_id, source_deck_id=note.deck_id):
        scope = flashcards_share.resolve_clone_scope_for_local_deck(user_id=user_id, local_deck_id=root_id)
        if scope and scope.source_deck_ids and repository.note_matches_clone_scope(note_id=note.id, scope=scope):
            if defer_clone_values and (published_base_enabled() or not (scope.install.version_mode == 'release' and scope.install.applied_release_id)):
                repository.ensure_live_values(note)
            return repository.BrowseNoteReference(note, scope), None
    raise shared.BrowseApiError("Note not found", status=404)


def _editor_detail(*, reference, user_id, admin_mode, timezone_name):
    """Serialize the Note editor directly, without discarded live clone content or media metadata."""
    note = reference.note
    overlay = None
    if reference.clone_scope:
        overrides, release_values = _page_overlay_values([reference])
        install = reference.clone_scope.install
        overlay = shared._clone_overlay_fields(card_obj=reference, clone_scope=reference.clone_scope,
            base_field_values=release_values.get((str(install_release_id(install) or ''), reference.note_id)),
            note_override_rows=overrides.get((str(install.id), reference.note_id), []))
    values = overlay.values if overlay else dict(note.field_values or {})
    definitions = overlay.ordered_defs if overlay else note.note_type.field_defs
    fields = [{'id': str(field.id), 'name': field.name, 'field_type': field.field_type,
        'required': bool(field.required), 'position': int(field.position or 0)} for field in definitions]
    names = {field['name'] for field in fields}
    fields.extend({'name': name, 'field_type': 'text', 'required': False, 'position': 9999}
        for name in values if name not in names)
    fields.sort(key=lambda field: (field['position'], field['name'].lower()))
    deck_lookup = repository.detail_deck_lookup(reference=reference)
    now = shared._utcnow()
    progress = shared._load_mode_aware_browse_progress(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, card_obj=reference, now_utc=now)
    row = shared.vocabulary_ctrl.build_browse_row(reference, deck_lookup, now,
        progress_obj=progress, timezone_name=timezone_name, raw_values=values,
        display_triplet=overlay.display_triplet if overlay else None)
    if overlay:
        shared._apply_clone_card_fields(row, overlay=overlay, deck_lookup=deck_lookup)
    note_payload = {'id': note.id, 'note_type_id': note.note_type_id, 'note_type_name': note.note_type.name or 'NoteType',
        'deck_id': row['deck_id'], 'deck_name': row['deck_name'], 'field_values': values, 'tags': note.tags or []}
    if published_base_enabled() and not overlay:
        from app.services.note_draft_service import effective_note_metadata
        note_payload['tags'] = effective_note_metadata(note)['tags']
    if overlay:
        note_payload.update(deck_install_id=install.id, overlay_revision=int(install.overlay_revision or 0))
    else:
        note_payload.update(content_revision=int(note.content_revision or 0),
            field_schema_revision=int(note.note_type.field_schema_revision or 0))
    return {'row': _row(row), 'note': note_payload, 'fields': fields, 'can_upload_media': not bool(overlay)}


def get_note_detail(*, user_id, admin_mode, timezone_name, note_id, compact=False):
    ref, context = authorized_note(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, note_id=note_id, include_media=not compact, defer_clone_values=compact)
    if compact:
        return _editor_detail(reference=ref, user_id=user_id, admin_mode=admin_mode, timezone_name=timezone_name)
    detail = shared._build_browse_detail_payload(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, card_obj=ref)
    if ref.clone_scope:
        detail = shared._apply_clone_overlay_to_browse_payload(payload=detail, card_obj=ref,
            clone_scope=ref.clone_scope, deck_lookup=repository.detail_deck_lookup(reference=ref))
    return _detail(detail)


def update_note(*, user_id, admin_mode, timezone_name, note_id, payload, compact_detail=False):
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
            card_obj=ref, note_obj=note, clone_scope=ref.clone_scope, validated=validated,
            include_response=not compact_detail)
    else:
        result = shared._update_owned_browse_card(user_id=user_id, admin_mode=admin_mode,
            timezone_name=timezone_name, card_obj=ref, note_obj=note, validated=validated,
            include_response=not compact_detail)
    if compact_detail:
        result['detail'] = _editor_detail(reference=ref, user_id=user_id,
            admin_mode=admin_mode, timezone_name=timezone_name)
        result['row'] = result['detail']['row']
        return result
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
