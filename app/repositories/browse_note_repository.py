"""Note-grain Browse reads. No presentation, application or template expansion."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from sqlalchemy import and_, case, func, literal, not_, or_, select, true, union_all
from sqlalchemy.orm import load_only, selectinload

from models import db
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType


@dataclass
class BrowseNoteReference:
    """Authorized Note context for shared content/authority helpers.

    The compatibility helpers consume id/note, not a persisted Card. This
    reference is constructed only after the Note's scope has been checked.
    """

    note: Note
    clone_scope: Any = None
    template = None

    @property
    def id(self):
        return str(self.note.id)

    @property
    def note_id(self):
        return str(self.note.id)

    @property
    def created_at(self):
        return self.note.created_at

    @property
    def updated_at(self):
        if self.clone_scope:
            return self.note.updated_at
        from app.services.note_draft_service import effective_note_updated_at
        return effective_note_updated_at(self.note)


_LIVE_VALUE_COLUMNS = (Note.field_values_by_id, Note.field_values_codec, Note.field_values_extras)


def load_note(note_id, *, include_media=True, include_live_values=True):
    query = Note.query.options(selectinload(Note.note_type).options(
        load_only(NoteType.id, NoteType.user_id, NoteType.name, NoteType.field_schema_revision),
        selectinload(NoteType.field_defs)))
    if include_media:
        query = query.options(selectinload(Note.media_assets))
    if not include_live_values:
        query = query.options(load_only(Note.id, Note.user_id, Note.note_type_id, Note.deck_id,
            Note.tags, Note.created_at, Note.updated_at, Note.content_revision))
    return query.filter(Note.id == note_id).first()


def load_note_reference(note_id, *, include_media=True, include_live_values=True):
    note = load_note(note_id, include_media=include_media, include_live_values=include_live_values)
    if note is not None:
        return note
    # Resolve an old bookmark's identity without loading a presentation or its
    # template. Authorization is always checked on the resulting Note.
    from models.card import card_key_pairs
    pair = card_key_pairs(db.session, [note_id]).get(str(note_id))
    return load_note(pair[0], include_media=include_media, include_live_values=include_live_values) if pair else None


def ensure_live_values(note):
    """Hydrate all deferred value columns together for owner/snapshot reads."""
    from sqlalchemy import inspect
    missing = inspect(note).unloaded.intersection(column.key for column in _LIVE_VALUE_COLUMNS)
    if missing:
        # Keep the optimistic-lock token in the same row read as its values,
        # including under a connection configured for READ COMMITTED.
        db.session.refresh(note, attribute_names=[column.key for column in _LIVE_VALUE_COLUMNS]
            + [Note.content_revision.key])


def installed_scope_candidates(*, user_id, local_deck_ids):
    """Avoid probing every owned descendant for an install that cannot cover it."""
    from models.deck_install import DeckInstall
    from models.deck_clone_deck_map import DeckCloneDeckMap
    filters = (DeckInstall.user_id == user_id, DeckInstall.clone_mode == "logical_overlay")
    roots = select(DeckInstall.local_deck_id.label("deck_id")).where(*filters,
        DeckInstall.local_deck_id.in_(local_deck_ids))
    mapped = select(DeckCloneDeckMap.local_deck_id.label("deck_id")).join(
        DeckInstall, DeckInstall.id == DeckCloneDeckMap.deck_install_id).where(*filters,
        DeckCloneDeckMap.local_deck_id.in_(local_deck_ids))
    return sorted(int(row[0]) for row in db.session.execute(roots.union(mapped)) if row[0] is not None)


def installed_batch_scope_roots(*, user_id, local_deck_ids):
    """Relevant install roots in the full Browse resolver's precedence order.

    An install can present several requested branches; resolve it once and
    clip its maps afterwards. Keep nested installs as independent branches,
    as the full sidebar does, rather than hiding them under an outer install.
    """
    from models.deck_install import DeckInstall
    from models.deck_clone_deck_map import DeckCloneDeckMap
    maps = select(DeckCloneDeckMap.id).where(DeckCloneDeckMap.deck_install_id == DeckInstall.id)
    mapped = maps.where(DeckCloneDeckMap.local_deck_id.in_(local_deck_ids)).exists()
    rows = db.session.query(DeckInstall.local_deck_id).filter(
        DeckInstall.user_id == user_id,
        DeckInstall.clone_mode == "logical_overlay",
        DeckInstall.local_deck_id.isnot(None),
        or_(DeckInstall.local_deck_id.in_(local_deck_ids), mapped, ~maps.exists())).distinct().all()
    return [int(row[0]) for row in rows]


def selected_browse_decks(*, user_id, admin_mode, deck_ids, include_subdecks):
    """Read selected subtrees once; learner mixed visibility retains its resolver.

    Admin Browse permits only owned/unowned decks and cannot traverse a
    foreign child. A learner's all-owned subtree is already authorized; a
    foreign descendant needs the established ancestor/install visibility rules.
    """
    roots = set(deck_ids)
    query = Deck.query.filter(Deck.id.in_(roots), Deck.deleted_at.is_(None))
    allowed = or_(Deck.owner_user_id == user_id, Deck.owner_user_id.is_(None)) if admin_mode else Deck.owner_user_id == user_id
    decks = {int(root.id): root for root in query.filter(allowed)}
    if set(decks) != roots:
        return [] if admin_mode else None
    frontier = list(roots) if include_subdecks else []
    while frontier:
        children_query = Deck.query.filter(Deck.parent_id.in_(frontier), Deck.deleted_at.is_(None))
        children = children_query.filter(allowed).all() if admin_mode else children_query.all()
        if not admin_mode and any(child.owner_user_id != user_id for child in children):
            return None
        frontier = []
        for child in children:
            if int(child.id) not in decks:
                decks[int(child.id)] = child
                frontier.append(int(child.id))
    return list(decks.values())


def selected_owned_decks(*, user_id, deck_id, include_subdecks):
    return selected_browse_decks(user_id=user_id, admin_mode=False,
        deck_ids=[deck_id], include_subdecks=include_subdecks)


def clone_scope_roots_for_note(*, user_id, source_deck_id):
    """Keep the existing root precedence, resolving only matching maps or unmapped legacy installs."""
    from models.deck_install import DeckInstall
    from models.deck_clone_deck_map import DeckCloneDeckMap
    filters = (DeckInstall.user_id == user_id, DeckInstall.clone_mode == 'logical_overlay',
        DeckInstall.local_deck_id.isnot(None))
    roots = db.session.query(DeckInstall.local_deck_id).filter(*filters).distinct().all()
    from app.services.note_base_context import published_base_enabled
    if published_base_enabled():
        # New source subdecks deliberately have no local map yet.
        return [int(root) for (root,) in roots]
    mapped = select(DeckCloneDeckMap.id).where(DeckCloneDeckMap.deck_install_id == DeckInstall.id)
    matches = set(db.session.execute(select(DeckInstall.local_deck_id).where(*filters,
        or_(mapped.where(DeckCloneDeckMap.source_deck_id == source_deck_id).exists(), ~mapped.exists()))).scalars())
    return [int(root) for (root,) in roots if root in matches]


def detail_deck_lookup(*, reference):
    deck_id = (reference.clone_scope.source_to_local_deck_id.get(int(reference.note.deck_id or 0))
        or reference.clone_scope.install.local_deck_id) if reference.clone_scope else reference.note.deck_id
    from app.services.note_base_context import published_base_enabled
    if published_base_enabled() and not reference.clone_scope:
        from app.services.note_draft_service import effective_note_metadata
        deck_id = effective_note_metadata(reference.note)["deck_id"]
    rows = db.session.query(Deck.id, Deck.name).filter(Deck.id == deck_id, Deck.deleted_at.is_(None)).all()
    return dict(rows)


def note_matches_clone_scope(*, note_id, scope):
    """Authorize one Note with the same release/snapshot predicate as the list."""
    from app.services import flashcards_share

    filters = [Note.id == note_id, Note.deck_id.in_(scope.source_deck_ids)]
    if scope.source_owner_user_id is not None:
        filters.append(Note.user_id == scope.source_owner_user_id)
    membership = flashcards_share.release_note_membership_filter(scope.install, Note.id)
    if membership is not None:
        filters.append(membership)
    elif scope.base_snapshot_at is not None:
        filters.append(Note.created_at <= scope.base_snapshot_at)
    return db.session.query(Note.id).filter(*filters).first() is not None


def load_voicevox_notes(ids, *, user_id, admin_mode, note_only, include_media=False):
    """Legacy Card selectors and explicit Note selectors share owner checks."""
    if note_only:
        query = Note.query.filter(Note.id.in_(ids)).options(
            selectinload(Note.note_type).selectinload(NoteType.field_defs))
        if include_media:
            query = query.options(selectinload(Note.media_assets))
    else:
        from models.card import Card, card_id_clause
        query = Card.query.join(Note, Card.note_id == Note.id).filter(card_id_clause(db.session, ids)).options(
            selectinload(Card.note).selectinload(Note.note_type).selectinload(NoteType.field_defs))
        if include_media:
            query = query.options(selectinload(Card.note).selectinload(Note.media_assets))
    if not admin_mode:
        query = query.filter(Note.user_id == user_id)
    return [BrowseNoteReference(note) for note in query.all()] if note_only else query.all()


def count_notes(query):
    # Notes and the unique learner/Note subject join have one row per Note.
    return int(query.order_by(None).with_entities(func.count(Note.id)).scalar() or 0)


def note_page(query, *, page, per_page, install_id, user_id, pinned_installs):
    # Sort/page identities first. Large field JSON is fetched only for those
    # IDs, rather than becoming part of the whole-collection sort result.
    pagination = query.with_entities(Note.id, Note.user_id, install_id).paginate(
        page=page, per_page=per_page, error_out=False, count=False,
    )
    return _hydrate_page(pagination, user_id=user_id, pinned_installs=pinned_installs)


def search_note_page(context, *, install_id, user_id, pinned_installs):
    """Evaluate matching identities once for both exact total and page.

    The ranked CTE stores identities/order only. Its aggregate LEFT JOIN page
    also returns the total for an empty or out-of-range page, without a second
    search or fetching all matching IDs into Python.
    """
    query = context.query.with_entities(Note.id.label('note_id'), Note.user_id, install_id)
    ranked = order_notes(context, user_id=user_id, query=query, with_rank=True).cte()
    totals = select(func.count().label('total')).select_from(ranked).subquery()
    start = (context.page - 1) * context.per_page
    page = select(ranked.c.note_id, ranked.c.user_id, ranked.c.browse_install_id,
        ranked.c.browse_rank).where(ranked.c.browse_rank > start,
            ranked.c.browse_rank <= start + context.per_page).subquery()
    statement = select(page.c.note_id, page.c.user_id, page.c.browse_install_id,
        totals.c.total).select_from(totals.outerjoin(page, true())).order_by(page.c.browse_rank)
    if getattr(context, 'author_draft', None) is not None:
        # Query execution options do not survive conversion into a CTE. The
        # scope already enforces these predicates; keep the global guard from
        # adding a second per-Note Draft anti-lookup to the outer SELECT.
        statement = statement.execution_options(include_deleted_drafts=True, include_deleted_notes=True)
    rows = db.session.execute(statement).all()
    total = int(rows[0].total)
    pagination = SimpleNamespace(items=[tuple(row[:3]) for row in rows if row.note_id is not None],
        total=total, page=context.page, per_page=context.per_page,
        pages=(total + context.per_page - 1) // context.per_page,
        has_next=context.page * context.per_page < total)
    return _hydrate_page(pagination, user_id=user_id, pinned_installs=pinned_installs)


def _hydrate_page(pagination, *, user_id, pinned_installs):
    pinned_ids = [note_id for note_id, owner_id, scope in pagination.items
                  if owner_id != user_id and scope in pinned_installs]
    live_ids = [note_id for note_id, _owner_id, _scope in pagination.items if note_id not in pinned_ids]
    note_type = selectinload(Note.note_type).options(
        load_only(NoteType.id, NoteType.user_id, NoteType.name, NoteType.field_schema_revision),
        selectinload(NoteType.field_defs))
    notes = {}
    for ids, pinned in ((live_ids, False), (pinned_ids, True)):
        if not ids:
            continue
        loader = Note.query.filter(Note.id.in_(ids)).options(note_type)
        if pinned:
            # The installed release supplies values; author working JSON is
            # unnecessary here and must not become a per-row lazy fallback.
            loader = loader.options(load_only(Note.id, Note.user_id, Note.note_type_id, Note.deck_id,
                Note.tags, Note.created_at, Note.updated_at, Note.content_revision))
        notes.update({str(note.id): note for note in loader.all()})
    pagination.items = [(notes[str(note_id)], scope) for note_id, _owner, scope in pagination.items]
    return pagination


def order_notes(context, *, user_id, query=None, with_rank=False):
    query = context.query if query is None else query
    draft = getattr(context, 'author_draft', None)
    order = []
    descending = context.sort_dir == "desc"
    if context.sort_by == "deck":
        names = [(db.and_(Note.user_id != user_id, condition, Note.deck_id == source), literal(context.deck_lookup[local]))
            for scope, condition in context.clone_scope_conditions
            for source, local in sorted(scope.source_to_local_deck_id.items()) if local in context.deck_lookup]
        from app.repositories.field_value_query_repository import author_note_column
        own_deck = case((Note.user_id == user_id, author_note_column("deck_id", draft_model=draft)), else_=Note.deck_id)
        query = query.outerjoin(Deck, own_deck == Deck.id)
        expression = case(*names, else_=Deck.name) if names else Deck.name
        order.append(expression.desc() if descending else expression.asc())
    elif context.sort_by == "word":
        from app.repositories.browse_card_repository import owned_note_word_expression, owned_text_field_ids
        fields = None
        if draft is not None:
            if not hasattr(context, 'owned_text_fields'):
                context.owned_text_fields = owned_text_field_ids(user_id)
            fields = context.owned_text_fields
        own = owned_note_word_expression(draft_model=draft, field_ids_by_type=fields)
        values = []
        if context.owned_visibility_condition is not None:
            values.append((context.owned_visibility_condition, own))
        values.extend((projection["condition"], projection["word"]) for projection in context.clone_projections)
        expression = func.lower(func.coalesce(case(*values, else_=own) if values else own, ""))
        order.append(expression.desc() if descending else expression.asc())
    else:
        day = case((context.normalized_progress_queue == "review", context.progress_alias.due_day), else_=None)
        due = context.progress_alias.due_at
        order.extend((day.is_(None), day.desc() if descending else day.asc(),
                      due.is_(None), due.desc() if descending else due.asc()))
    from app.repositories.field_value_query_repository import author_note_column
    updated = case((Note.user_id == user_id, author_note_column('updated_at', draft_model=draft)), else_=Note.updated_at)
    order.extend((updated.desc(), Note.id.asc()))
    if with_rank:
        return query.add_columns(func.row_number().over(order_by=order).label('browse_rank'))
    return query.order_by(*order)


def deck_counts(context, *, user_id, admin_mode, today_day_index, day_cutoff_utc):
    """One Note per local deck, independent of template membership/multiplicity.

    Like the Dashboard, counts read progress rows as stored: a damaged row
    miscounts only its own Note; the offline study-authority-read-audit finds it.
    """
    from app.repositories import note_analytics_read_repository as reads
    deck_ids = sorted(context.deck_by_id)
    owned = select(Note.id.label("note_id"), Note.deck_id.label("deck_id")).where(Note.deck_id.in_(deck_ids))
    from app.repositories.field_value_query_repository import author_note_column, author_note_visible
    from app.services.note_base_context import published_base_enabled
    if published_base_enabled():
        from sqlalchemy.orm import aliased
        from models.note_draft import NoteDraft
        from app.repositories.field_value_query_repository import join_author_draft
        draft = aliased(NoteDraft, name='browse_count_draft')
        deck = author_note_column("deck_id", draft_model=draft)
        owned = join_author_draft(select(Note.id.label("note_id"), deck.label("deck_id")), draft, user_id).where(
            deck.in_(deck_ids), author_note_visible(draft_model=draft))
    if not admin_mode:
        owned = owned.where(Note.user_id == user_id)
    branches = [owned]
    if not admin_mode:
        for scope, condition in context.clone_scope_conditions:
            mapping = [(Note.deck_id == source, local) for source, local in scope.source_to_local_deck_id.items()]
            local_deck = case(*mapping, else_=scope.install.local_deck_id) if mapping else literal(scope.install.local_deck_id)
            branches.append(select(Note.id.label("note_id"), local_deck.label("deck_id")).where(condition))
    members = union_all(*branches).subquery("browse_note_members") if len(branches) > 1 else branches[0].subquery("browse_note_members")

    scope = select(members.c.note_id, members.c.deck_id, literal(1).label("card_count"))
    if len(branches) > 1:
        scope = scope.distinct()
    rows = reads.note_rows(scope.subquery("browse_note_scope"),
        learner_user_id=user_id).subquery("browse_note_availability")
    # Match the existing deck aggregate buckets and scheduler day boundary.
    active = and_(or_(rows.c.is_suspended.is_(None), rows.c.is_suspended.is_(False)),
        not_(and_(rows.c.is_buried.is_(True), or_(rows.c.buried_until_day.is_(None), rows.c.buried_until_day >= today_day_index))))
    queue = func.lower(func.trim(func.coalesce(rows.c.queue, "new")))
    learning = queue.in_(("learn", "learning", "relearning"))
    review = queue == "review"
    due = and_(active, review, or_(rows.c.due_day <= today_day_index,
        and_(rows.c.due_day.is_(None), or_(rows.c.due_at.is_(None), rows.c.due_at < day_cutoff_utc))))
    result = db.session.execute(select(rows.c.deck_id, func.count(),
        func.sum(case((and_(active, ~learning, ~review), 1), else_=0)),
        func.sum(case((and_(active, learning), 1), else_=0)),
        func.sum(case((due, 1), else_=0))).group_by(rows.c.deck_id)).all()
    return {int(deck): dict(zip(("total", "new", "learn", "due"), map(int, (total, new, learn, due))))
            for deck, total, new, learn, due in result if deck is not None}
