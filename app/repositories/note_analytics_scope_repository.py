"""Note-grain analytics scopes with exact presentation multiplicities.

Progress belongs to a learner/Note, so expand neither presentation IDs nor
availability for siblings. Owned membership is counted algebraically from
active applications and the immutable P11 cutover sets. Installed membership
retains the canonical release/timestamp predicate, then groups before progress.

Counts read progress rows as stored; the offline ``study-authority-read-audit``
re-derives them. Study and Browse keep their own bounded evidence checks.
"""

from sqlalchemy import and_, case, func, literal, not_, null, or_, select, union_all

from models.card import Card, PresentationAlias, cutover_applications, cutover_notes
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.note import Note
from models.study_application import StudyApplication


def owned_note_scope(*, learner_user_id, deck_ids=None, owned_by_any_user=False, presence_only=False):
    """One row per owned Note with at least one ACTIVE presentation.

    P11 membership: an original Note/original application pair exists only
    with an alias. Every other pair exists. For an original Note, count new
    applications plus aliases of original active applications. For a new
    Note, count all active applications. Alias counts are scoped to the same
    requested Notes, never a whole-store scan for a small learner/deck.
    ``presence_only`` keeps the same Notes but reports ``card_count = 1``, for
    readers that weigh each Note once (Note-unit counts).
    """
    notes = select(Note.id, Note.deck_id, Note.note_type_id)
    if not owned_by_any_user:
        notes = notes.where(Note.user_id == int(learner_user_id))
    if deck_ids is not None:
        notes = notes.where(Note.deck_id.in_(deck_ids))
    notes = notes.subquery("analytics_owned_notes")
    application = StudyApplication.__table__
    aliases = PresentationAlias.__table__
    applications = (
        select(
            application.c.note_type_id,
            func.count().label("active_count"),
            func.sum(case((cutover_applications.c.application_id.is_(None), 1), else_=0))
            .label("new_count"),
        )
        .select_from(application.outerjoin(
            cutover_applications, cutover_applications.c.application_id == application.c.id,
        ))
        .where(application.c.status_code == "ACTIVE")
        .group_by(application.c.note_type_id)
        .subquery("analytics_application_counts")
    )
    # The few ACTIVE original applications, materialized once (DISTINCT blocks
    # derived-table merging) so each alias probes a small in-memory key rather
    # than two InnoDB primary keys.
    original_applications = (
        select(application.c.id.label("application_id"), application.c.note_type_id)
        .select_from(application.join(
            cutover_applications, cutover_applications.c.application_id == application.c.id,
        ))
        .where(application.c.status_code == "ACTIVE")
        .distinct()
        .subquery("analytics_original_applications")
    )
    if presence_only:
        # count > 0 exactly when the Note is new (active_count >= 1 via the
        # inner join), its type has a new application, or one alias of an
        # ACTIVE original application exists, so probe for a single alias
        # instead of counting all of them. OR stops before the probe.
        has_original_alias = (
            select(literal(1))
            .select_from(aliases.join(
                original_applications,
                original_applications.c.application_id == aliases.c.application_id,
            ))
            .where(aliases.c.note_id == notes.c.id,
                   original_applications.c.note_type_id == notes.c.note_type_id)
            .exists()
        )
        return (
            select(notes.c.deck_id, notes.c.id.label("note_id"), literal(1).label("card_count"))
            .select_from(notes)
            .join(applications, applications.c.note_type_id == notes.c.note_type_id)
            .outerjoin(cutover_notes, cutover_notes.c.note_id == notes.c.id)
            .where(or_(cutover_notes.c.note_id.is_(None), applications.c.new_count > 0,
                       has_original_alias))
            .subquery("analytics_owned_note_counts")
        )
    # Read only for cutover Notes (see `count`), so no cutover_notes join here.
    original_aliases = (
        select(notes.c.id.label("note_id"), func.count().label("alias_count"))
        # Measured MySQL otherwise starts from applications and reads each
        # wide Note again for every sibling. Scope Notes first, then probe
        # their alias prefix; SQLite retains its own planner. NO_BNL keeps the
        # application probe a key lookup: a hash join loses the Note order and
        # turns the GROUP BY into a temporary table.
        .prefix_with("/*+ NO_BNL(analytics_original_applications) */ STRAIGHT_JOIN", dialect="mysql")
        .select_from(notes)
        .join(aliases, aliases.c.note_id == notes.c.id)
        .join(original_applications, and_(
            original_applications.c.application_id == aliases.c.application_id,
            original_applications.c.note_type_id == notes.c.note_type_id,
        ))
        .group_by(notes.c.id)
        .subquery("analytics_original_alias_counts")
    )
    count = case(
        (cutover_notes.c.note_id.is_(None), applications.c.active_count),
        else_=applications.c.new_count + func.coalesce(original_aliases.c.alias_count, 0),
    )
    return (
        select(notes.c.deck_id, notes.c.id.label("note_id"), count.label("card_count"))
        .select_from(notes)
        .join(applications, applications.c.note_type_id == notes.c.note_type_id)
        .outerjoin(cutover_notes, cutover_notes.c.note_id == notes.c.id)
        .outerjoin(original_aliases, original_aliases.c.note_id == notes.c.id)
        .where(count > 0)
        .subquery("analytics_owned_note_counts")
    )


def _installed_presentations(*, learner_user_id, deck_ids=None):
    """Canonical release membership; no progress joins or state hydration."""
    from app.repositories.flashcards_share_repository import clone_source_card_visibility

    statement = (
        select(
            DeckCloneDeckMap.local_deck_id.label("deck_id"),
            Card.note_id.label("note_id"), Card.application_id.label("application_id"),
        )
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .join(DeckCloneDeckMap, DeckCloneDeckMap.source_deck_id == Note.deck_id)
        .join(DeckInstall, DeckInstall.id == DeckCloneDeckMap.deck_install_id)
        .where(
            DeckInstall.user_id == int(learner_user_id),
            DeckInstall.clone_mode == "logical_overlay",
            DeckInstall.local_deck_id.isnot(None),
            DeckCloneDeckMap.local_deck_id.isnot(None),
            or_(DeckInstall.source_owner_user_id.is_(None),
                Note.user_id == DeckInstall.source_owner_user_id),
            clone_source_card_visibility(DeckInstall),
        )
    )
    if deck_ids is not None:
        statement = statement.where(DeckCloneDeckMap.local_deck_id.in_(deck_ids))
    return statement


def _combine(owned, installed, *, per_deck):
    """Inputs have disjoint application sets; combine Note-level weights."""
    owned_rows = select(
        owned.c.deck_id if per_deck else null().label("deck_id"),
        owned.c.note_id, owned.c.card_count,
    )
    rows = union_all(owned_rows, installed).subquery("analytics_note_weights")
    return (
        select(rows.c.deck_id, rows.c.note_id, func.sum(rows.c.card_count).label("card_count"))
        .group_by(rows.c.deck_id, rows.c.note_id)
        .subquery("analytics_note_scope")
    )


def deck_note_scope(*, learner_user_id, deck_ids, overlay=None, owned_by_any_user=False,
                    presence_only=False):
    """One row per effective deck/Note; duplicate installations count once."""
    owned = owned_note_scope(
        learner_user_id=learner_user_id, deck_ids=deck_ids,
        owned_by_any_user=owned_by_any_user, presence_only=presence_only,
    )
    if overlay is None:
        return owned
    # An active owned presentation mapped back to its physical deck is already
    # counted. Retired release pins, and presentations mapped elsewhere, are not.
    duplicate = and_(Note.deck_id == DeckCloneDeckMap.local_deck_id,
                     Card.application_status == "ACTIVE")
    if not owned_by_any_user:
        duplicate = and_(duplicate, Note.user_id == int(learner_user_id))
    installed = overlay.with_only_columns(
        DeckCloneDeckMap.local_deck_id.label("deck_id"), Card.note_id.label("note_id"),
        func.count(func.distinct(Card.application_id)).label("card_count"),
    ).where(not_(duplicate)).group_by(DeckCloneDeckMap.local_deck_id, Card.note_id)
    return _combine(owned, installed, per_deck=True)


def collection_note_scope(session, *, learner_user_id, deck_ids=None, presence_only=False):
    """One row per visible Note, with Card multiplicity deduped across installs.

    Owned active presentations are present once. Installed applications absent
    from that owned scope (including retired pins) are counted distinctly per
    Note across all selected installations. Different pin subsets therefore
    form a union, rather than a max/sum of each installation's count.
    ``presence_only`` proves owned membership without counting aliases; the
    reader then weighs each Note once and ignores ``card_count``.
    """
    owned = owned_note_scope(learner_user_id=learner_user_id, deck_ids=deck_ids, presence_only=presence_only)
    has_install = session.execute(select(DeckInstall.id).where(
        DeckInstall.user_id == int(learner_user_id),
        DeckInstall.clone_mode == "logical_overlay", DeckInstall.local_deck_id.isnot(None),
    ).limit(1)).first()
    if has_install is None:
        return select(null().label("deck_id"), owned.c.note_id, owned.c.card_count).subquery("analytics_note_scope")

    duplicate = and_(Note.user_id == int(learner_user_id), Card.application_status == "ACTIVE")
    if deck_ids is not None:
        # NULL physical decks are outside any requested deck scope.
        duplicate = and_(duplicate, Note.deck_id.isnot(None), Note.deck_id.in_(deck_ids))
    installed = _installed_presentations(learner_user_id=learner_user_id, deck_ids=deck_ids)
    installed = installed.with_only_columns(
        null().label("deck_id"), Card.note_id.label("note_id"),
        func.count(func.distinct(Card.application_id)).label("card_count"),
    ).where(not_(duplicate)).group_by(Card.note_id)
    return _combine(owned, installed, per_deck=False)
