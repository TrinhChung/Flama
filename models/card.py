"""Presentation instances of a Note (ADR P11): derived from content, never stored.

A Card is one Note shown through one ACTIVE StudyApplication of the Note's
NoteType. Attaching, retiring or reordering a Template changes one application
row, never one row per Note, and creating a Note creates no Card. A Card's ID
is the presentation key ``<note_id>.<application_id>``: stable across retire
and reactivation, and computable anywhere without a lookup.

``card_presentation_aliases`` archives random IDs issued before P11. The
physical ``cards`` table is retired. Immutable history and old clients may
still name a Card by its original ID; ``card_key_pairs`` resolves either form.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import UniqueConstraint, and_, case, event, false, literal, select, tuple_
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, foreign, relationship, with_loader_criteria
from sqlalchemy.sql.functions import GenericFunction
from sqlalchemy.types import DateTime, String

from models import db
from models.note import Note
from models.study_application import StudyApplication

CARD_KEY_SEPARATOR = "."
_KEY_PART_LENGTH = 36
_LOOKUP_CHUNK = 500


class PresentationAlias(db.Model):
    """Immutable historical wire identity; new presentations are never stored.

    No content foreign keys: old IDs remain resolvable as evidence after the
    original Note, Template or application is removed.
    """

    __tablename__ = "card_presentation_aliases"

    id = db.Column(db.String(36), primary_key=True)
    note_id = db.Column(db.String(36), nullable=False)
    template_id = db.Column(db.String(36), nullable=False, index=True)
    application_id = db.Column(db.String(36), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("note_id", "application_id", name="uq_presentation_alias_note_application"),
    )


# Archived by the P11 cutover; no read depends on them. A derived Card cannot
# drift from Note x application, and the cutover archived a Card for every
# original pair (111,743 of 111,743; production still matched on 2026-10-24).
cutover_notes = db.Table(
    "card_presentation_cutover_notes",
    db.Column("note_id", db.String(36), primary_key=True),
)
cutover_applications = db.Table(
    "card_presentation_cutover_applications",
    db.Column("application_id", db.String(36), primary_key=True),
)
cutovers = db.Table(
    "card_presentation_cutovers",
    db.Column("id", db.Integer, primary_key=True),
    db.Column("captured_at", db.DateTime, nullable=False),
    db.Column("source_row_count", db.BigInteger, nullable=False),
)


class greatest(GenericFunction):
    """``GREATEST(a, b)``; SQLite spells it ``max(a, b)``."""

    type = DateTime()
    inherit_cache = True


@compiles(greatest, "sqlite")
def _sqlite_greatest(element, compiler, **kw):
    return "max(%s)" % compiler.process(element.clauses, **kw)


class card_key_note_part(GenericFunction):
    """SQL: the Note ID part of a stored presentation key."""

    type = String()
    inherit_cache = True


class card_key_application_part(GenericFunction):
    """SQL: the application ID part of a stored presentation key."""

    type = String()
    inherit_cache = True


@compiles(card_key_note_part)
def _note_part_default(element, compiler, **kw):
    return "SUBSTRING_INDEX(%s, '%s', 1)" % (compiler.process(element.clauses, **kw), CARD_KEY_SEPARATOR)


@compiles(card_key_application_part)
def _application_part_default(element, compiler, **kw):
    return "SUBSTRING_INDEX(%s, '%s', -1)" % (compiler.process(element.clauses, **kw), CARD_KEY_SEPARATOR)


@compiles(card_key_note_part, "sqlite")
def _note_part_sqlite(element, compiler, **kw):
    column = compiler.process(element.clauses, **kw)
    return "substr(%s, 1, instr(%s, '%s') - 1)" % (column, column, CARD_KEY_SEPARATOR)


@compiles(card_key_application_part, "sqlite")
def _application_part_sqlite(element, compiler, **kw):
    column = compiler.process(element.clauses, **kw)
    return "substr(%s, instr(%s, '%s') + 1)" % (column, column, CARD_KEY_SEPARATOR)


def card_key_join(key_column, entity=None):
    """Join condition from a column holding presentation keys to ``Card``.

    Joins on the key's parts, so the Note and application primary keys serve
    it; a legacy ID in the column matches nothing.
    """

    entity = Card if entity is None else entity
    return and_(
        entity.note_id == card_key_note_part(key_column),
        entity.application_id == card_key_application_part(key_column),
    )


def card_key(note_id, application_id) -> str:
    """The presentation key of ``note_id`` shown through ``application_id``."""

    return f"{note_id}{CARD_KEY_SEPARATOR}{application_id}"


def split_card_key(value) -> tuple[str, str] | None:
    """``(note_id, application_id)`` of a presentation key; None for anything else."""

    text = str(value or "")
    note_id, separator, application_id = text.partition(CARD_KEY_SEPARATOR)
    if (
        not separator
        or not note_id
        or not application_id
        or len(note_id) > _KEY_PART_LENGTH
        or len(application_id) > _KEY_PART_LENGTH
        or CARD_KEY_SEPARATOR in application_id
    ):
        return None
    return note_id, application_id


_notes = Note.__table__
_applications = StudyApplication.__table__
_aliases = PresentationAlias.__table__
_pair_join = _notes.join(_applications, _applications.c.note_type_id == _notes.c.note_type_id)
_pair_join = _pair_join.outerjoin(_aliases, and_(
    _aliases.c.note_id == _notes.c.id, _aliases.c.application_id == _applications.c.id,
))
_presentations = (
    select(
        (_notes.c.id + literal(CARD_KEY_SEPARATOR) + _applications.c.id).label("id"),
        # Preserve the old UUID tie order without replacing modern wire IDs.
        case((_aliases.c.id.isnot(None), _aliases.c.id),
             else_=(_notes.c.id + literal(CARD_KEY_SEPARATOR) + _applications.c.id)).label("order_key"),
        _notes.c.id.label("note_id"),
        _applications.c.template_id.label("template_id"),
        _applications.c.id.label("application_id"),
        _applications.c.status_code.label("application_status"),
        case((_aliases.c.id.isnot(None), _aliases.c.created_at),
             else_=greatest(_notes.c.created_at, _applications.c.created_at)).label("created_at"),
        case((_aliases.c.id.isnot(None), _aliases.c.updated_at),
             else_=greatest(_notes.c.created_at, _applications.c.created_at)).label("updated_at"),
    )
    .select_from(_pair_join)
    .subquery("card_presentations")
)

INCLUDE_RETIRED_CARDS = "include_retired_cards"


class Card(db.Model):
    """Read-only: one Note through one application of its NoteType.

    Every ORM SELECT sees only Cards of ACTIVE applications unless it sets the
    execution option ``include_retired_cards`` (release-pinned installs and
    lookups of an explicit Card ID). The criteria covers joins, IN subqueries
    and relationship loads, not a hand-built ``exists()`` over Card.
    """

    __table__ = _presentations
    __mapper_args__ = {"primary_key": [_presentations.c.id]}

    note = relationship("Note", primaryjoin=lambda: foreign(Card.note_id) == Note.id, viewonly=True)
    template = relationship(
        "Template", primaryjoin="foreign(Card.template_id) == Template.id", viewonly=True
    )
    application = relationship(
        StudyApplication,
        primaryjoin=lambda: foreign(Card.application_id) == StudyApplication.id,
        viewonly=True,
    )

    @property
    def key(self) -> str:
        return self.id


@event.listens_for(Session, "before_flush")
def _refuse_card_writes(session, _context, _instances):
    if any(isinstance(item, (Card, PresentationAlias)) for item in (*session.new, *session.dirty, *session.deleted)):
        raise TypeError(
            "Card is derived from Note x StudyApplication (ADR P11), and old aliases are immutable; "
            "create or change the Note or the application instead."
        )


@event.listens_for(Session, "do_orm_execute")
def _active_cards_and_no_bulk_writes(execute_state):
    if execute_state.is_update or execute_state.is_delete or execute_state.is_insert:
        if any(mapper.class_ in (Card, PresentationAlias) for mapper in execute_state.all_mappers):
            raise TypeError("Card is derived and old presentation aliases are immutable (ADR P11).")
        return
    if execute_state.is_select and not execute_state.execution_options.get(INCLUDE_RETIRED_CARDS):
        # A retired occurrence presents nothing new; its Cards stay addressable.
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(Card, lambda cls: cls.application_status == "ACTIVE", include_aliases=True)
        )


def forget_card_identities(session, note_ids: Iterable) -> None:
    """Keep immutable alias evidence when its content is deleted (no-op)."""


def card_scope_options(query) -> dict:
    """Execution options an outer statement needs to embed this Card ``query``.

    A query that set ``include_retired_cards`` (a release-pinned install
    scope) loses that option once embedded as a subquery; pass these options
    to the statement that embeds it so its membership is kept.
    """

    get_options = getattr(query, "get_execution_options", None)
    options = get_options() if get_options is not None else {}
    return {INCLUDE_RETIRED_CARDS: True} if options.get(INCLUDE_RETIRED_CARDS) else {}


def card_pairs_in(query, entity=None):
    """``(note_id, application_id) IN (pairs of this Card query)``: Card IDs are computed."""

    entity = Card if entity is None else entity
    pairs = query.with_entities(Card.note_id.label("note_id"), Card.application_id.label("application_id")).order_by(None).subquery()
    return tuple_(entity.note_id, entity.application_id).in_(select(pairs.c.note_id, pairs.c.application_id))


def _chunks(values, size=_LOOKUP_CHUNK):
    values = list(values)
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def card_key_pairs(session, card_ids: Iterable) -> dict[str, tuple[str, str]]:
    """``{given id: (note_id, application_id)}`` for presentation keys and legacy IDs.

    An unknown legacy ID, or one whose registry row never had an application,
    is absent from the result. Applications are not checked for being ACTIVE.
    """

    pairs: dict[str, tuple[str, str]] = {}
    legacy: list[str] = []
    for value in card_ids:
        text = str(value or "").strip()
        if not text or text in pairs:
            continue
        parsed = split_card_key(text)
        if parsed is not None:
            pairs[text] = parsed
        else:
            legacy.append(text)
    for chunk in _chunks(sorted(set(legacy))):
        for legacy_id, note_id, application_id in session.execute(
            select(PresentationAlias.id, PresentationAlias.note_id, PresentationAlias.application_id).where(
                PresentationAlias.id.in_(chunk)
            )
        ):
            if application_id:
                pairs[str(legacy_id)] = (str(note_id), str(application_id))
    return pairs


def canonical_card_ids(session, card_ids: Iterable) -> dict[str, str]:
    """``{given id: presentation key}``; legacy IDs map to their key."""

    return {given: card_key(*pair) for given, pair in card_key_pairs(session, card_ids).items()}


def card_pair_clause(pairs: Iterable[tuple[str, str]], entity=None):
    """Index-friendly WHERE clause selecting these (note_id, application_id) pairs."""

    entity = Card if entity is None else entity
    pairs = sorted({(str(note_id), str(application_id)) for note_id, application_id in pairs})
    if not pairs:
        return false()
    note_ids = sorted({note_id for note_id, _application_id in pairs})
    return and_(
        entity.note_id.in_(note_ids),
        tuple_(entity.note_id, entity.application_id).in_(pairs),
    )


def legacy_card_ids(session, card_ids: Iterable) -> list[str]:
    """Pre-P11 IDs aliasing these Cards: open sessions and history may name a Card by one."""

    pairs = sorted(set(card_key_pairs(session, card_ids).values()))
    aliases: list[str] = []
    for chunk in _chunks(pairs):
        aliases.extend(
            str(value)
            for value in session.execute(
                select(PresentationAlias.id).where(card_pair_clause(chunk, PresentationAlias))
            ).scalars()
        )
    return aliases


def note_card_ids(session, note_ids: Iterable) -> list[str]:
    """Every Card a Note has, retired occurrences included (lifecycle scope).

    A retired occurrence is no longer offered, yet its Cards still belong to
    the Note, as stored Cards did: deleting or resetting the Note covers them.
    """

    ids: list[str] = []
    for chunk in _chunks(sorted({str(value) for value in note_ids if value})):
        ids.extend(
            str(value)
            for value in session.execute(
                select(Card.id).where(Card.note_id.in_(chunk)).execution_options(**{INCLUDE_RETIRED_CARDS: True})
            ).scalars()
        )
    return ids


def card_id_clause(session, card_ids: Iterable, entity=None):
    """WHERE clause for Cards named by presentation keys or legacy IDs.

    Use this instead of ``Card.id == ...`` / ``Card.id.in_(...)``: the ID is a
    computed key, so only its parts can use an index.
    """

    return card_pair_clause(card_key_pairs(session, card_ids).values(), entity)


class CardWireIdentity:
    """Addressed presentation with its exact historical wire ID.

    Internal identity is ``key``. Keeping ``id`` untouched preserves old
    membership, snapshot hashes, receipt material and retry results.
    """

    __slots__ = ("_card", "id")

    def __init__(self, card: Card, wire_id: str):
        self._card = card
        self.id = wire_id

    @property
    def key(self) -> str:
        return self._card.id

    def __getattr__(self, name):
        return getattr(self._card, name)


def load_cards(session, card_ids: Iterable, query=None) -> dict[str, "Card | CardWireIdentity"]:
    """``{given id: Card}`` for the Cards these IDs name (legacy IDs too).

    An explicit ID stays addressable after its occurrence is retired, as a
    stored Card was: open sessions and pinned installs still resolve it. A
    ``query`` narrows the lookup (ownership, joins, eager loads).
    """

    pairs = card_key_pairs(session, card_ids)
    if not pairs:
        return {}
    by_pair = {}
    base = (Card.query if query is None else query).execution_options(**{INCLUDE_RETIRED_CARDS: True})
    for chunk in _chunks(sorted(set(pairs.values()))):
        for card in base.filter(card_pair_clause(chunk)).all():
            by_pair[(card.note_id, card.application_id)] = card
    return {
        given: (by_pair[pair] if given == by_pair[pair].id else CardWireIdentity(by_pair[pair], given))
        for given, pair in pairs.items() if pair in by_pair
    }


def get_card(session, card_id, query=None) -> "Card | None":
    """The Card named by a presentation key or a legacy ID (see ``load_cards``)."""

    return load_cards(session, [card_id], query=query).get(str(card_id or "").strip())
