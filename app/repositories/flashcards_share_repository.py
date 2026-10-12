"""Repository for flashcards sharing functionality.

This module encapsulates all direct ORM queries and database context mapping 
for flashcards sharing, cloning, installing, and marketplace interactions.
"""

from __future__ import annotations

from typing import Any, List, Optional
from datetime import datetime
from collections import defaultdict

from sqlalchemy import and_, literal, or_, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import GenericFunction
from sqlalchemy.types import Boolean

from models import db
from models.study_progress_subject import StudyProgressSubject
from models.deck import Deck
from models.study_application import StudyApplication
from models.deck_release import DeckRelease
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_template_pin import DeckReleaseTemplatePin
from models.flashcard import (
    Card,
    DeckCloneAddedFieldDef,
    DeckCloneDeckMap,
    DeckCloneFieldDefOverride,
    DeckCloneFieldOrderOverride,
    DeckCloneNoteFieldOverride,
    DeckInstall,
    DeckMarketplaceItem,
    DeckReview,
    FieldDef,
    Note,
    NoteType,
    NoteTypeInstall,
    NoteTypeReview,
    Template,
)


class _pin_has_application(GenericFunction):
    """Test a frozen applications_json key on MySQL and SQLite."""

    type = Boolean()
    inherit_cache = True


@compiles(_pin_has_application, "mysql")
def _mysql_pin_has_application(element, compiler, **kw):
    document, application_id = [compiler.process(value, **kw) for value in element.clauses]
    return f"JSON_CONTAINS_PATH({document}, 'one', CONCAT('$.\"', {application_id}, '\"'))"


@compiles(_pin_has_application, "sqlite")
def _sqlite_pin_has_application(element, compiler, **kw):
    document, application_id = [compiler.process(value, **kw) for value in element.clauses]
    return f"json_type({document}, '$.\"' || {application_id} || '\"') IS NOT NULL"


def clone_source_card_visibility(install, *, card=Card, note=Note):
    """Set-wise source membership for installed releases and timestamp fallback.

    ``install`` may be DeckInstall, an ORM alias, or a loaded row. Callers
    still constrain owner/deck scope and must propagate include_retired_cards
    to the outer statement: a frozen release may pin a retired application.
    """
    def column(name):
        value = getattr(install, name)
        return value if hasattr(value, "__clause_element__") else literal(value)

    release_id = column("applied_release_id")
    releases = DeckRelease.__table__
    memberships = DeckReleaseEntityMembership.__table__
    pins = DeckReleaseTemplatePin.__table__
    has_release = select(releases.c.id).where(releases.c.id == release_id).exists()
    initialized = select(releases.c.id).where(
        releases.c.id == release_id, releases.c.template_pins_initialized.is_(True),
    ).exists()
    pinned_application = select(pins.c.deck_release_id).where(
        pins.c.deck_release_id == release_id,
        pins.c.source_template_id == card.template_id,
        _pin_has_application(pins.c.applications_json, card.application_id),
    ).exists()
    presentation = or_(
        and_(initialized, pinned_application),
        and_(~initialized, card.application_status == "ACTIVE"),
    )
    release_mode = and_(column("version_mode") == "release", has_release)
    membership = select(memberships.c.id).select_from(
        memberships.join(releases, releases.c.id == release_id),
    ).where(
        memberships.c.deck_item_id == column("deck_item_id"),
        memberships.c.entity_kind == "note", memberships.c.entity_id == note.id,
        memberships.c.introduced_sequence <= releases.c.sequence_no,
        or_(memberships.c.removed_sequence.is_(None), memberships.c.removed_sequence > releases.c.sequence_no),
    ).exists()
    snapshot_at = db.func.coalesce(column("base_snapshot_at"), column("installed_at"))
    legacy_membership = or_(
        snapshot_at.is_(None), and_(note.created_at <= snapshot_at, card.created_at <= snapshot_at),
    )
    return and_(presentation, or_(and_(release_mode, membership), and_(~release_mode, legacy_membership)))


def get_note_type_by_user_and_name(user_id: int, name: str) -> Optional[NoteType]:
    """Retrieve a note type by user ID and exact name."""
    return NoteType.query.filter_by(user_id=user_id, name=name).first()

def get_deck_install_by_user_and_item(user_id: int, deck_item_id: str) -> Optional[DeckInstall]:
    """Retrieve a user's deck install record for a specific marketplace item."""
    return (
        DeckInstall.query.filter_by(user_id=user_id, deck_item_id=deck_item_id)
        .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
        .first()
    )

def get_deck_review_by_user_and_item(user_id: int, deck_item_id: str) -> Optional[DeckReview]:
    """Retrieve a user's review for a specific marketplace deck item."""
    return DeckReview.query.filter_by(user_id=user_id, deck_item_id=deck_item_id).first()

def get_note_type_install_by_user_and_source(user_id: int, source_note_type_id: str) -> Optional[NoteTypeInstall]:
    """Retrieve a user's note type install record for a specific source."""
    return NoteTypeInstall.query.filter_by(
        user_id=user_id,
        source_note_type_id=source_note_type_id
    ).first()

def get_note_type_review_by_user_and_item(user_id: int, note_type_id: str) -> Optional[NoteTypeReview]:
    """Retrieve a user's review for a specific marketplace note type."""
    return NoteTypeReview.query.filter_by(user_id=user_id, note_type_id=note_type_id).first()

def get_clone_deck_maps(install_id: str, local_deck_ids: List[int] = None) -> List[DeckCloneDeckMap]:
    """Retrieve clone map rows for a specific installation and optionally specific local deck IDs."""
    query = DeckCloneDeckMap.query.filter_by(deck_install_id=install_id)
    if local_deck_ids is not None:
        query = query.filter(DeckCloneDeckMap.local_deck_id.in_(local_deck_ids))
    return query.order_by(DeckCloneDeckMap.local_deck_id.asc(), DeckCloneDeckMap.source_deck_id.asc()).all()

def get_clone_deck_map(install_id: str, source_deck_id: int) -> Optional[DeckCloneDeckMap]:
    """Retrieve a specific clone map row by install and source deck."""
    return (
        DeckCloneDeckMap.query.filter_by(
            deck_install_id=install_id,
            source_deck_id=source_deck_id
        )
        .order_by(DeckCloneDeckMap.created_at.asc(), DeckCloneDeckMap.id.asc())
        .first()
    )

def get_clone_field_overrides(install_id: str) -> List[DeckCloneFieldDefOverride]:
    """Retrieve field type configuration overrides for a cloned installation."""
    return DeckCloneFieldDefOverride.query.filter_by(deck_install_id=install_id).all()

def get_clone_field_override(install_id: str, source_field_def_id: str) -> Optional[DeckCloneFieldDefOverride]:
    """Retrieve a specific field definition override."""
    return DeckCloneFieldDefOverride.query.filter_by(
        deck_install_id=install_id,
        source_field_def_id=source_field_def_id
    ).first()

def get_clone_added_field_defs(install_id: str) -> List[DeckCloneAddedFieldDef]:
    """Retrieve custom fields added to a cloned installation."""
    return (
        DeckCloneAddedFieldDef.query.filter_by(deck_install_id=install_id)
        .order_by(
            DeckCloneAddedFieldDef.position.asc(), 
            DeckCloneAddedFieldDef.created_at.asc(), 
            DeckCloneAddedFieldDef.id.asc()
        )
        .all()
    )

def get_clone_added_field_def_by_id(install_id: str, added_def_id: str) -> Optional[DeckCloneAddedFieldDef]:
    return DeckCloneAddedFieldDef.query.filter_by(
        deck_install_id=install_id,
        id=added_def_id,
    ).first()

def get_clone_field_order_override(install_id: str) -> Optional[DeckCloneFieldOrderOverride]:
    """Retrieve the sorted order of fields for a cloned note type schema."""
    return DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=install_id).first()

def get_clone_note_field_overrides(install_id: str, source_note_id: str) -> List[DeckCloneNoteFieldOverride]:
    """Retrieve note-specific data overrides (value changes/removals) for a cloned note."""
    return (
        DeckCloneNoteFieldOverride.query.filter_by(
            deck_install_id=install_id,
            source_note_id=source_note_id,
        )
        .order_by(DeckCloneNoteFieldOverride.created_at.asc(), DeckCloneNoteFieldOverride.id.asc())
        .all()
    )

def get_clone_note_field_overrides_batch(
    install_ids: List[str], source_note_ids: List[str]
) -> Dict[Tuple[str, str], List[DeckCloneNoteFieldOverride]]:
    """Batch retrieve note field overrides for multiple (install_id, source_note_id) pairs in one query."""
    if not install_ids or not source_note_ids:
        return {}
    rows = (
        DeckCloneNoteFieldOverride.query.filter(
            DeckCloneNoteFieldOverride.deck_install_id.in_(install_ids),
            DeckCloneNoteFieldOverride.source_note_id.in_(source_note_ids),
        )
        .order_by(DeckCloneNoteFieldOverride.created_at.asc(), DeckCloneNoteFieldOverride.id.asc())
        .all()
    )
    result: Dict[Tuple[str, str], List[DeckCloneNoteFieldOverride]] = {}
    for row in rows:
        key = (str(row.deck_install_id), str(row.source_note_id))
        result.setdefault(key, []).append(row)
    return result

def get_clone_note_field_override(install_id: str, source_note_id: str, field_name: str) -> Optional[DeckCloneNoteFieldOverride]:
    """Retrieve a specific note field override."""
    return DeckCloneNoteFieldOverride.query.filter_by(
        deck_install_id=install_id,
        source_note_id=source_note_id,
        field_name=field_name,
    ).first()

def get_user_deck_installs_covering_deck(user_id: int, ancestor_ids: List[int]) -> List[DeckInstall]:
    """Returns all DeckInstalls where the given user installed a deck targeting any of the ancestor IDs."""
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

def get_clone_scope_cards(source_deck_ids: List[int], source_owner_user_id: Optional[int], base_snapshot_at: Optional[datetime]) -> Any:
    """Returns a base query for clone scope cards."""
    query = Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id.in_(source_deck_ids))
    if source_owner_user_id is not None:
        query = query.filter(Note.user_id == source_owner_user_id)
    if base_snapshot_at is not None:
        query = query.filter(
            Note.created_at <= base_snapshot_at,
            Card.created_at <= base_snapshot_at,
        )
    return query

def get_field_defs_for_note_type(note_type_id: str, snapshot_at: Optional[datetime] = None) -> List[FieldDef]:
    """Retrieves field definitions for a specific note type."""
    query = FieldDef.query.filter(FieldDef.note_type_id == note_type_id)
    if snapshot_at is not None:
        query = query.filter(FieldDef.created_at <= snapshot_at)
    return query.order_by(FieldDef.position.asc(), FieldDef.created_at.asc(), FieldDef.id.asc()).all()

def find_logical_overlay_installs_for_card(user_id: int, source_deck_id: int) -> List[tuple[DeckInstall, int]]:
    """Retrieves all logical overlay installs pointing to a specific source deck."""
    return (
        db.session.query(DeckInstall, DeckCloneDeckMap.local_deck_id)
        .join(DeckCloneDeckMap, DeckCloneDeckMap.deck_install_id == DeckInstall.id)
        .filter(
            DeckInstall.user_id == user_id,
            DeckInstall.clone_mode == "logical_overlay",
            DeckCloneDeckMap.source_deck_id == source_deck_id,
        )
        .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
        .all()
    )

def get_notes_for_user_and_deck(user_id: int, deck_id: int) -> List[Note]:
    """Retrieves all notes created by a user in a specific deck."""
    return (
        Note.query.filter(
            Note.user_id == user_id,
            Note.deck_id == deck_id,
        )
        .order_by(Note.created_at.asc(), Note.id.asc())
        .all()
    )

def get_source_notes_for_clone_scope(
    source_deck_id: int,
    source_owner_user_id: Optional[int],
    source_note_type_id: Optional[str],
    snapshot_at: Optional[datetime]
) -> List[Note]:
    """Retrieves source notes matching clone scope constraints."""
    query = Note.query.filter(Note.deck_id == source_deck_id)
    if source_owner_user_id is not None:
        query = query.filter(Note.user_id == source_owner_user_id)
    if source_note_type_id:
        query = query.filter(Note.note_type_id == source_note_type_id)
    if snapshot_at is not None:
        query = query.filter(Note.created_at <= snapshot_at)
    return query.order_by(Note.created_at.asc(), Note.id.asc()).all()

def delete_notes_by_ids(note_ids: List[str]) -> None:
    """Deletes notes matching the specified IDs without synchronizing session state."""
    if note_ids:
        Note.query.filter(Note.id.in_(note_ids)).delete(synchronize_session=False)

def _card_reps_query(user_id: int):
    """Per-presentation reps from the current Note authority only."""
    from app.repositories.study_authority_repository import read_study_authority_route

    read_study_authority_route(db.session, learner_user_id=user_id)
    reps = db.cast(StudyProgressSubject.state_payload["reps"].as_string(), db.Integer)
    return (
        db.session.query(db.func.coalesce(db.func.sum(reps), 0))
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .join(StudyProgressSubject, db.and_(
            StudyProgressSubject.learner_user_id == user_id,
            StudyProgressSubject.live_note_id == Card.note_id,
        ))
        .filter(StudyProgressSubject.semantic_state_hash.isnot(None))
    )


def get_note_type_reps_for_user(user_id: int, installed_note_type_id: str) -> int:
    """Calculates total review reps for a user across all cards using a specific note type."""
    result = (
        _card_reps_query(user_id)
        .filter(Note.note_type_id == installed_note_type_id)
        .scalar()
    )
    return int(result or 0)

def count_notes_by_note_type_for_user(user_id: int, note_type_id: str) -> int:
    """Counts the number of notes a user has of a specific note type."""
    return Note.query.filter_by(
        user_id=user_id,
        note_type_id=note_type_id,
    ).count()

def get_note_type_installs_by_source(source_note_type_id: str) -> List[NoteTypeInstall]:
    """Retrieves all installations of a specific source note type."""
    return NoteTypeInstall.query.filter_by(source_note_type_id=source_note_type_id).all()

def get_note_type_market_rating_stats(note_type_id: str) -> tuple[float, int]:
    """Calculates average rating and total review count for a marketplace note type."""
    rating_avg, rating_count = (
        db.session.query(
            db.func.coalesce(db.func.avg(NoteTypeReview.rating), 0.0),
            db.func.count(NoteTypeReview.id),
        )
        .filter(NoteTypeReview.note_type_id == note_type_id)
        .first()
    )
    return float(rating_avg or 0.0), int(rating_count or 0)

def get_deck_reps_for_user_in_source_scope(
    user_id: int, 
    source_deck_ids: List[int],
    source_owner_user_id: Optional[int] = None,
    base_snapshot_at: Optional[datetime] = None
) -> int:
    """Calculates total review reps for a user within a cloned deck scope."""
    query = _card_reps_query(user_id).filter(Note.deck_id.in_(source_deck_ids))
    if source_owner_user_id is not None:
        query = query.filter(Note.user_id == source_owner_user_id)
    if base_snapshot_at is not None:
        query = query.filter(
            Note.created_at <= base_snapshot_at,
            Card.created_at <= base_snapshot_at,
        )
    return int(query.scalar() or 0)

def get_deck_reps_for_user_in_subtree(user_id: int, subtree_deck_ids: List[int]) -> int:
    """Calculates total review reps for a user within a local deck subtree."""
    if not subtree_deck_ids:
        return 0
        
    flashcard_reps = (
        _card_reps_query(user_id)
        .filter(Note.deck_id.in_(subtree_deck_ids))
        .scalar()
    ) or 0
    return int(flashcard_reps)

def get_deck_installs_by_item(deck_item_id: str) -> List[DeckInstall]:
    """Retrieves all installations of a specific marketplace deck item."""
    return DeckInstall.query.filter_by(deck_item_id=deck_item_id).all()

def get_deck_market_rating_stats(deck_item_id: str) -> tuple[float, int]:
    """Calculates average rating and total review count for a marketplace deck item."""
    rating_avg, rating_count = (
        db.session.query(
            db.func.coalesce(db.func.avg(DeckReview.rating), 0.0),
            db.func.count(DeckReview.id),
        )
        .filter(DeckReview.deck_item_id == deck_item_id)
        .first()
    )
    return float(rating_avg or 0.0), int(rating_count or 0)

def resolve_single_note_type_for_deck(deck_id: int, owner_user_id: Optional[int] = None) -> List[str]:
    """Finds all distinct note type IDs used by notes within a specific deck."""
    query = db.session.query(Note.note_type_id).filter(Note.deck_id == deck_id)
    if owner_user_id is not None:
        query = query.filter(Note.user_id == owner_user_id)
    return sorted({row[0] for row in query.distinct().all() if row[0]})

def count_notes_using_note_type_in_deck(
    deck_id: int, 
    user_id: int, 
    note_type_id: str, 
    exclude_note_id: Optional[str] = None
) -> List[str]:
    """Finds all distinct note type IDs used in a deck (with optional exclusion)."""
    query = db.session.query(Note.note_type_id).filter(
        Note.deck_id == deck_id,
        Note.user_id == user_id,
    )
    if exclude_note_id:
        query = query.filter(Note.id != exclude_note_id)
    return {row[0] for row in query.distinct().all() if row[0]}

def get_max_deck_position(parent_deck_id: Optional[int]) -> int:
    """Finds the maximum position value among sibling decks."""
    query = db.session.query(db.func.max(Deck.position))
    if parent_deck_id is None:
        max_pos = query.filter(Deck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(Deck.parent_id == parent_deck_id).scalar()
    return int(max_pos or 0)

def get_deck_with_notes_by_user_and_id(user_id: int, deck_id: int) -> Optional[Deck]:
    """Retrieves a deck if it belongs to the user."""
    return Deck.query.filter_by(
        id=deck_id,
        owner_user_id=user_id,
        deleted_at=None,
    ).first()

def get_templates_by_note_type(note_type_id: str, *, applications=None) -> List[Template]:
    """List unique active attached definitions, including independent templates."""
    rows = get_template_applications_by_note_type(note_type_id) if applications is None else applications
    result = []
    seen = set()
    for template, _application in rows:
        if template.id not in seen:
            result.append(template)
            seen.add(template.id)
    return result


def get_template_applications_by_note_type(note_type_id: str):
    return db.session.query(Template, StudyApplication).join(
        StudyApplication, StudyApplication.template_id == Template.id,
    ).filter(
        StudyApplication.note_type_id == note_type_id,
        StudyApplication.status_code == "ACTIVE",
    ).order_by(StudyApplication.position, Template.created_at, Template.id, StudyApplication.id).all()

def get_cards_for_note(note_id: str) -> List[Card]:
    """Retrieves all cards belonging to a specific note."""
    return Card.query.filter_by(note_id=note_id).all()


def get_note_type_by_id(note_type_id: str) -> Optional[NoteType]:
    """Back-compat lookup for note type by ID."""
    return db.session.get(NoteType, note_type_id)


def get_note_type_by_name(user_id: int, name: str) -> Optional[NoteType]:
    """Back-compat lookup for note type by user/name."""
    return get_note_type_by_user_and_name(user_id, name)


def check_note_type_name_exists(
    user_id: int,
    name: str,
    exclude_note_type_id: Optional[str] = None,
) -> bool:
    """Returns True if another note type already uses the same name."""
    query = NoteType.query.filter(
        NoteType.user_id == user_id,
        NoteType.name == name,
    )
    if exclude_note_type_id:
        query = query.filter(NoteType.id != exclude_note_type_id)
    return query.first() is not None


def get_note_type_ids_for_decks_notes(
    deck_ids: List[int],
    owner_user_id: Optional[int] = None,
) -> List[str]:
    """Returns distinct note_type IDs used by notes across a deck set."""
    normalized_deck_ids = sorted({int(deck_id) for deck_id in deck_ids if deck_id is not None})
    if not normalized_deck_ids:
        return []
    query = db.session.query(Note.note_type_id).filter(Note.deck_id.in_(normalized_deck_ids))
    if owner_user_id is not None:
        query = query.filter(Note.user_id == owner_user_id)
    return sorted({str(row[0]) for row in query.distinct().all() if row and row[0]})


def get_note_type_ids_for_deck_notes(
    deck_id: int,
    owner_user_id: Optional[int] = None,
) -> List[str]:
    """Returns distinct note_type IDs used by notes in a single deck."""
    return get_note_type_ids_for_decks_notes([deck_id], owner_user_id)


def get_note_type_ids_for_user_deck_notes(
    deck_id: int,
    user_id: int,
    exclude_note_id: Optional[str] = None,
) -> set[str]:
    """Returns distinct note_type IDs for a user's notes in one deck."""
    return count_notes_using_note_type_in_deck(
        deck_id=deck_id,
        user_id=user_id,
        note_type_id="",
        exclude_note_id=exclude_note_id,
    )


def get_next_deck_position(parent_deck_id: Optional[int]) -> int:
    """Returns next sibling position under parent deck."""
    return get_max_deck_position(parent_deck_id) + 1


def get_preview_note_by_id(
    note_id: str,
    note_type_id: str,
    deck_ids: List[int],
    owner_user_id: Optional[int],
) -> Optional[Note]:
    """Returns one preview note by ID constrained to deck scope."""
    if not deck_ids:
        return None
    query = Note.query.filter(
        Note.id == note_id,
        Note.note_type_id == note_type_id,
        Note.deck_id.in_(deck_ids),
    )
    if owner_user_id is not None:
        query = query.filter(Note.user_id == owner_user_id)
    return query.first()


def get_first_preview_note(
    note_type_id: str,
    deck_ids: List[int],
    owner_user_id: Optional[int],
) -> Optional[Note]:
    """Returns first preview note in scoped deck(s)."""
    if not deck_ids:
        return None
    query = Note.query.filter(
        Note.note_type_id == note_type_id,
        Note.deck_id.in_(deck_ids),
    )
    if owner_user_id is not None:
        query = query.filter(Note.user_id == owner_user_id)
    return query.order_by(Note.created_at.asc(), Note.id.asc()).first()


def get_notes_for_user_deck(user_id: int, deck_id: int) -> List[Note]:
    """Back-compat alias used by cutover flow."""
    return get_notes_for_user_and_deck(user_id, deck_id)


def get_source_notes_for_cutover(
    source_deck_id: int,
    source_owner_user_id: Optional[int],
    source_note_type_id: Optional[str],
    snapshot_at: Optional[datetime],
) -> List[Note]:
    """Back-compat alias used by cutover flow."""
    return get_source_notes_for_clone_scope(
        source_deck_id=source_deck_id,
        source_owner_user_id=source_owner_user_id,
        source_note_type_id=source_note_type_id,
        snapshot_at=snapshot_at,
    )


def batch_get_deck_publish_facts(
    *,
    user_id: int,
    deck_ids: list[int],
) -> tuple[dict[int, int], dict[int, set[str]]]:
    """Read direct card counts and NoteType membership in one note scan.

    Callers supply the existing visible-owned deck scope. LEFT JOIN retains
    NoteTypes on notes without cards; COUNT(Card.id) counts every presentation.
    """
    normalized_deck_ids = sorted({int(deck_id) for deck_id in deck_ids if deck_id is not None})
    if not normalized_deck_ids:
        return {}, {}
    rows = db.session.query(
        Note.deck_id, Note.note_type_id, db.func.count(Card.id),
    ).select_from(Note).outerjoin(
        Card, Card.note_id == Note.id,
    ).filter(
        Note.user_id == user_id,
        Note.deck_id.in_(normalized_deck_ids),
    ).group_by(Note.deck_id, Note.note_type_id).all()
    card_counts: dict[int, int] = defaultdict(int)
    note_types: dict[int, set[str]] = defaultdict(set)
    for deck_id, note_type_id, card_count in rows:
        if deck_id is not None:
            # Keep the old card-count map's absence for zero-card decks.
            if card_count:
                card_counts[int(deck_id)] += int(card_count)
            if note_type_id:
                note_types[int(deck_id)].add(str(note_type_id))
    return dict(card_counts), dict(note_types)


def batch_get_cards_count_by_deck_ids(
    *,
    user_id: int,
    deck_ids: list[int],
) -> dict[int, int]:
    """Retrieve direct card counts grouped by deck_id for a given user."""
    normalized_deck_ids = sorted({int(d) for d in deck_ids if d is not None})
    if not normalized_deck_ids:
        return {}
    rows = (
        db.session.query(
            Note.deck_id,
            db.func.count(Card.id),
        )
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .filter(
            Note.user_id == user_id,
            Note.deck_id.in_(normalized_deck_ids),
        )
        .group_by(Note.deck_id)
        .all()
    )
    return {int(row[0]): int(row[1] or 0) for row in rows if row and row[0] is not None}


def batch_get_deck_note_types(
    *,
    user_id: int,
    deck_ids: list[int],
) -> dict[int, set[str]]:
    """Retrieve mapping of deck_id to set of note_type_ids used by notes in each deck."""
    normalized_deck_ids = sorted({int(d) for d in deck_ids if d is not None})
    if not normalized_deck_ids:
        return {}
    rows = (
        db.session.query(Note.deck_id, Note.note_type_id)
        .filter(
            Note.user_id == user_id,
            Note.deck_id.in_(normalized_deck_ids),
        )
        .distinct()
        .all()
    )
    result: dict[int, set[str]] = defaultdict(set)
    for row in rows:
        if row and row[0] is not None and row[1]:
            result[int(row[0])].add(str(row[1]))
    return dict(result)


def batch_get_installed_note_type_ids(note_type_ids: set[str] | list[str]) -> set[str]:
    """Filter note_type_ids to those that were installed from Marketplace."""
    normalized_nt_ids = sorted({str(nt) for nt in note_type_ids if nt})
    if not normalized_nt_ids:
        return set()
    rows = (
        db.session.query(NoteTypeInstall.installed_note_type_id)
        .filter(NoteTypeInstall.installed_note_type_id.in_(normalized_nt_ids))
        .all()
    )
    return {str(row[0]) for row in rows if row and row[0]}


def batch_get_active_template_note_type_ids(note_type_ids: set[str] | list[str]) -> set[str]:
    """Filter note_type_ids to those having active templates in study_applications."""
    normalized_nt_ids = sorted({str(nt) for nt in note_type_ids if nt})
    if not normalized_nt_ids:
        return set()
    rows = (
        db.session.query(StudyApplication.note_type_id)
        .join(Template, StudyApplication.template_id == Template.id)
        .filter(
            StudyApplication.note_type_id.in_(normalized_nt_ids),
            StudyApplication.status_code == "ACTIVE",
        )
        .distinct()
        .all()
    )
    return {str(row[0]) for row in rows if row and row[0]}
