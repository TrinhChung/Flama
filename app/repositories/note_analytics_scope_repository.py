"""Note-grain analytics scopes with exact presentation multiplicities.

Progress belongs to a learner/Note, so expand neither presentation IDs nor
availability for siblings. Owned multiplicity is the NoteType's ACTIVE
application count. Installed membership
retains the canonical release/timestamp predicate, then groups before progress;
counting Notes (``by_note``) tests it once per Note, without multiplicity.

Counts read progress rows as stored; the offline ``study-authority-read-audit``
re-derives them. Study and Browse keep their own bounded evidence checks.
"""


from app.repositories.flashcards_share_repository import source_deck_map_condition
from app.repositories.field_value_query_repository import author_note_column, author_note_visible
from sqlalchemy import and_, func, literal, not_, null, or_, select, union_all
from sqlalchemy.orm import aliased

from models.card import Card
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_release import DeckRelease
from models.note import Note
from models.study_application import StudyApplication


def _active_note_types_subquery():
    application = StudyApplication.__table__
    return (
        select(application.c.note_type_id)
        .where(application.c.status_code == "ACTIVE")
        .distinct()
        .subquery("active_note_types")
    )


def owned_note_scope(
    *,
    learner_user_id,
    deck_ids=None,
    owned_by_any_user=False,
    by_note=False,
    require_deck=False,
):
    """One row per owned Note with at least one ACTIVE presentation.

    A Card is a Note shown through one ACTIVE application of its NoteType
    (ADR P11), so a Note's multiplicity is its type's ACTIVE application count.
    """
    deck_id = author_note_column("deck_id")
    notes = select(Note.id, deck_id.label("deck_id"), Note.note_type_id).where(author_note_visible())
    if not owned_by_any_user:
        notes = (
            notes
            .with_hint(Note, "USE INDEX (ix_notes_user_deck)", dialect_name="mysql")
            .where(Note.user_id == int(learner_user_id))
        )
    if deck_ids is not None:
        notes = notes.where(deck_id.in_(deck_ids))
    elif require_deck:
        notes = notes.where(deck_id.isnot(None))
    notes = notes.subquery("analytics_owned_notes")
    application = StudyApplication.__table__
    active_count = literal(1) if by_note else func.count()
    applications = (
        select(application.c.note_type_id, active_count.label("active_count"))
        .where(application.c.status_code == "ACTIVE")
        .group_by(application.c.note_type_id)
        .subquery("analytics_application_counts")
    )
    return (
        select(notes.c.deck_id, notes.c.id.label("note_id"), applications.c.active_count.label("card_count"))
        .select_from(notes)
        .join(applications, applications.c.note_type_id == notes.c.note_type_id)
        .subquery("analytics_owned_note_counts")
    )


def _installed_source(*, learner_user_id, deck_ids=None, by_note=False):
    """Canonical release membership; no progress joins or state hydration.

    Card rows, or with ``by_note`` the Notes showing at least one of them.
    """
    from app.repositories.flashcards_share_repository import (
        clone_source_card_visibility, clone_source_note_visibility,
    )

    rel = aliased(DeckRelease)
    if by_note:
        active_nt = _active_note_types_subquery()
        statement = (
            select(
                DeckCloneDeckMap.local_deck_id.label("deck_id"), Note.id.label("note_id"),
            )
            .select_from(Note)
            .outerjoin(active_nt, active_nt.c.note_type_id == Note.note_type_id)
        )
        visible = clone_source_note_visibility(
            DeckInstall, note=Note, release=rel, active_note_type_id=active_nt.c.note_type_id,
        )
    else:
        statement = select(
            DeckCloneDeckMap.local_deck_id.label("deck_id"),
            Card.note_id.label("note_id"), Card.application_id.label("application_id"),
        ).select_from(Card).join(Note, Card.note_id == Note.id)
        visible = clone_source_card_visibility(DeckInstall, card=Card, note=Note, release=rel)
    statement = (
        statement
        .join(DeckCloneDeckMap, source_deck_map_condition(user_id=learner_user_id))
        .join(DeckInstall, DeckInstall.id == DeckCloneDeckMap.deck_install_id)
        .outerjoin(rel, rel.id == DeckInstall.applied_release_id)
        .where(
            DeckInstall.user_id == int(learner_user_id),
            DeckInstall.clone_mode == "logical_overlay",
            DeckInstall.local_deck_id.isnot(None),
            DeckCloneDeckMap.local_deck_id.isnot(None),
            or_(DeckInstall.source_owner_user_id.is_(None),
                Note.user_id == DeckInstall.source_owner_user_id),
            visible,
        )
    )
    if deck_ids is not None:
        statement = statement.where(DeckCloneDeckMap.local_deck_id.in_(deck_ids))
    return statement


def _combine(owned, installed, *, per_deck, by_note=False):
    """Inputs have disjoint application sets; combine Note-level weights.

    Counting Notes needs no multiplicity: the owned and installed rows of one
    Note merge into a row of weight 1.
    """
    owned_rows = select(
        owned.c.deck_id if per_deck else null().label("deck_id"),
        owned.c.note_id, owned.c.card_count,
    )
    rows = union_all(owned_rows, installed).subquery("analytics_note_weights")
    weight = literal(1) if by_note else func.sum(rows.c.card_count)
    return (
        select(rows.c.deck_id, rows.c.note_id, weight.label("card_count"))
        .group_by(rows.c.deck_id, rows.c.note_id)
        .subquery("analytics_note_scope")
    )


def deck_note_scope(*, learner_user_id, deck_ids, overlay=None, owned_by_any_user=False, by_note=False):
    """One row per effective deck/Note; duplicate installations count once.

    With ``by_note`` the overlay holds Notes (``_overlay_scope(by_note=True)``):
    an installed Note that is also owned in the same deck is that owned row.
    """
    owned = owned_note_scope(
        learner_user_id=learner_user_id,
        deck_ids=deck_ids,
        owned_by_any_user=owned_by_any_user,
        by_note=by_note,
        require_deck=True,
    )
    if overlay is None:
        return owned
    if by_note:
        installed = overlay.with_only_columns(
            DeckCloneDeckMap.local_deck_id.label("deck_id"), Note.id.label("note_id"),
            literal(1).label("card_count"),
        )
        return _combine(owned, installed, per_deck=True, by_note=True)
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


def collection_note_scope(session, *, learner_user_id, deck_ids=None, by_note=False):
    """One row per visible Note, with Card multiplicity deduped across installs.

    Owned active presentations are present once. Installed applications absent
    from that owned scope (including retired pins) are counted distinctly per
    Note across all selected installations. Different pin subsets therefore
    form a union, rather than a max/sum of each installation's count. With
    ``by_note`` every visible Note weighs 1 and no Card row is built.
    """
    owned = owned_note_scope(learner_user_id=learner_user_id, deck_ids=deck_ids, by_note=by_note)
    has_install = session.execute(select(DeckInstall.id).where(
        DeckInstall.user_id == int(learner_user_id),
        DeckInstall.clone_mode == "logical_overlay", DeckInstall.local_deck_id.isnot(None),
    ).limit(1)).first()
    if has_install is None:
        weight = literal(1) if by_note else owned.c.card_count
        return select(null().label("deck_id"), owned.c.note_id, weight.label("card_count")).subquery("analytics_note_scope")

    installed = _installed_source(learner_user_id=learner_user_id, deck_ids=deck_ids, by_note=by_note)
    if by_note:
        # An installed Note the learner owns in scope is the owned row.
        installed = installed.with_only_columns(
            null().label("deck_id"), Note.id.label("note_id"), literal(1).label("card_count"),
        )
        return _combine(owned, installed, per_deck=False, by_note=True)
    duplicate = and_(Note.user_id == int(learner_user_id), Card.application_status == "ACTIVE")
    if deck_ids is not None:
        # NULL physical decks are outside any requested deck scope.
        duplicate = and_(duplicate, Note.deck_id.isnot(None), Note.deck_id.in_(deck_ids))
    installed = installed.with_only_columns(
        null().label("deck_id"), Card.note_id.label("note_id"),
        func.count(func.distinct(Card.application_id)).label("card_count"),
    ).where(not_(duplicate)).group_by(Card.note_id)
    return _combine(owned, installed, per_deck=False)
