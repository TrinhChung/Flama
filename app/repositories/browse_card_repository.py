"""Data-access helpers for browse card detail and edit flows."""

from __future__ import annotations

import json

from sqlalchemy import and_, case, false, func, literal, or_, select
from sqlalchemy.orm import aliased, selectinload

from app.repositories import vocabulary_repository as vocabulary_ctrl
from models import db
from models.deck import Deck
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.card import get_card
from models.flashcard import Card, Note, NoteType
from models.field_def import FieldDef


TEXT_FIELD_TYPES = {"text", "richtext", "markdown", "array"}


def _dialect_name() -> str:
    return str(db.session.get_bind().dialect.name or "").lower()


def _json_path(field_name: str) -> str:
    """Build a quoted JSON member path accepted by SQLite and MySQL."""

    return f"$.{json.dumps(str(field_name), ensure_ascii=False)}"


def _json_extract_text(json_expr, path_expr):
    extracted = func.json_extract(json_expr, path_expr)
    if _dialect_name() in {"mysql", "mariadb"}:
        return case(
            (func.json_type(extracted) == "NULL", None),
            else_=func.json_unquote(extracted),
        )
    return db.cast(extracted, db.Text)


def _json_scalar_text(json_expr):
    return _json_extract_text(json_expr, literal("$"))


def owned_note_word_expression():
    """Return the first non-empty live text field without loading Note rows."""

    field_def = aliased(FieldDef)
    escaped_name = func.replace(
        func.replace(field_def.name, "\\", "\\\\"),
        '"',
        '\\"',
    )
    dynamic_path = literal('$."').concat(escaped_name).concat(literal('"'))
    value_expr = _json_extract_text(Note.field_values, dynamic_path)
    return (
        select(value_expr)
        .where(
            field_def.note_type_id == Note.note_type_id,
            field_def.field_type.in_(sorted(TEXT_FIELD_TYPES)),
            value_expr.isnot(None),
            func.trim(value_expr) != "",
        )
        .order_by(
            field_def.position.asc(),
            func.lower(field_def.name).asc(),
            field_def.id.asc(),
        )
        .limit(1)
        .correlate(Note)
        .scalar_subquery()
    )


def load_initial_release_field_names(
    *,
    deck_item_id: str,
    through_sequence: int,
) -> dict[str, str]:
    """Load sparse field identity metadata, never source Note rows."""

    rows = (
        db.session.query(
            DeckReleaseChange.field_def_id,
            DeckReleaseChange.entity_id,
            DeckReleaseChange.after_value,
        )
        .join(DeckRelease, DeckRelease.id == DeckReleaseChange.release_id)
        .filter(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckReleaseChange.release_sequence_no <= int(through_sequence),
            DeckReleaseChange.entity_kind == "field_def",
            DeckReleaseChange.property_key == "name",
            DeckReleaseChange.operation.in_(["add", "set"]),
        )
        .order_by(
            DeckReleaseChange.release_sequence_no.asc(),
            DeckReleaseChange.id.asc(),
        )
        .all()
    )
    names: dict[str, str] = {}
    for field_def_id, entity_id, after_value in rows:
        stable_id = str(field_def_id or entity_id or "").strip()
        field_name = str(after_value or "").strip()
        if stable_id and field_name:
            names.setdefault(stable_id, field_name)
    return names


def load_clone_added_field_names(*, deck_install_id: str) -> dict[str, str]:
    return {
        str(row.id): str(row.name)
        for row in DeckCloneAddedFieldDef.query.filter_by(
            deck_install_id=deck_install_id
        ).all()
    }


def clone_effective_field_text_expression(
    *,
    deck_install_id: str,
    deck_item_id: str | None,
    target_release_sequence: int | None,
    source_field_def_id: str | None,
    checkpoint_field_name: str | None,
    override_field_names: list[str] | tuple[str, ...],
):
    """Resolve one clone field at its pinned release plus current overlay.

    The expression is correlated by ``Note.id``. Release installs read their
    initial checkpoint and only the latest stable-field change through the
    applied release. A local override wins last. This keeps q/order/pagination
    inside SQL instead of hydrating the source deck in Python.
    """

    normalized_field_id = str(source_field_def_id or "").strip() or None
    normalized_names = sorted(
        {
            str(field_name).strip()
            for field_name in override_field_names
            if str(field_name).strip()
        }
    )
    base_text = literal("")

    if (
        deck_item_id
        and target_release_sequence is not None
        and normalized_field_id
    ):
        checkpoint = aliased(DeckReleaseNoteCheckpoint)
        checkpoint_release = aliased(DeckRelease)
        checkpoint_filters = (
            checkpoint.source_note_id == Note.id,
            checkpoint.release_sequence_no <= int(target_release_sequence),
            checkpoint_release.deck_item_id == str(deck_item_id),
            checkpoint_release.status == "published",
        )
        checkpoint_sequence = (
            select(checkpoint.release_sequence_no)
            .join(
                checkpoint_release,
                checkpoint_release.id == checkpoint.release_id,
            )
            .where(*checkpoint_filters)
            .order_by(
                checkpoint.release_sequence_no.asc(),
                checkpoint.id.asc(),
            )
            .limit(1)
            .correlate(Note)
            .scalar_subquery()
        )
        if checkpoint_field_name:
            checkpoint_value = (
                select(
                    _json_extract_text(
                        checkpoint.field_values,
                        literal(_json_path(checkpoint_field_name)),
                    )
                )
                .join(
                    checkpoint_release,
                    checkpoint_release.id == checkpoint.release_id,
                )
                .where(*checkpoint_filters)
                .order_by(
                    checkpoint.release_sequence_no.asc(),
                    checkpoint.id.asc(),
                )
                .limit(1)
                .correlate(Note)
                .scalar_subquery()
            )
        else:
            checkpoint_value = literal("")

        release_change = aliased(DeckReleaseChange)
        change_release = aliased(DeckRelease)
        stable_field_filter = or_(
            release_change.field_def_id == normalized_field_id,
            and_(
                release_change.field_def_id.is_(None),
                release_change.property_key == f"field:{normalized_field_id}",
            ),
        )
        change_filters = (
            release_change.entity_kind == "note_field",
            release_change.entity_id == Note.id,
            stable_field_filter,
            release_change.release_sequence_no <= int(target_release_sequence),
            release_change.release_sequence_no
            > func.coalesce(checkpoint_sequence, 0),
            change_release.deck_item_id == str(deck_item_id),
            change_release.status == "published",
        )
        latest_operation = (
            select(release_change.operation)
            .join(change_release, change_release.id == release_change.release_id)
            .where(*change_filters)
            .order_by(
                release_change.release_sequence_no.desc(),
                release_change.id.desc(),
            )
            .limit(1)
            .correlate(Note)
            .scalar_subquery()
        )
        latest_value = (
            select(_json_scalar_text(release_change.after_value))
            .join(change_release, change_release.id == release_change.release_id)
            .where(*change_filters)
            .order_by(
                release_change.release_sequence_no.desc(),
                release_change.id.desc(),
            )
            .limit(1)
            .correlate(Note)
            .scalar_subquery()
        )
        base_text = case(
            (latest_operation.in_(["add", "set"]), latest_value),
            (latest_operation == "remove", literal("")),
            else_=checkpoint_value,
        )
    elif checkpoint_field_name:
        base_text = _json_extract_text(
            Note.field_values,
            literal(_json_path(checkpoint_field_name)),
        )

    note_override = aliased(DeckCloneNoteFieldOverride)
    identity_filters = []
    if normalized_field_id:
        identity_filters.append(
            note_override.source_field_def_id == normalized_field_id
        )
    if normalized_names:
        identity_filters.append(
            and_(
                note_override.source_field_def_id.is_(None),
                note_override.field_name.in_(normalized_names),
            )
        )
    if not identity_filters:
        return func.coalesce(base_text, "")

    override_filters = (
        note_override.deck_install_id == str(deck_install_id),
        note_override.source_note_id == Note.id,
        or_(*identity_filters),
    )
    override_operation = (
        select(note_override.operation)
        .where(*override_filters)
        .order_by(note_override.created_at.desc(), note_override.id.desc())
        .limit(1)
        .correlate(Note)
        .scalar_subquery()
    )
    override_value = (
        select(_json_scalar_text(note_override.value))
        .where(*override_filters)
        .order_by(note_override.created_at.desc(), note_override.id.desc())
        .limit(1)
        .correlate(Note)
        .scalar_subquery()
    )
    return func.coalesce(
        case(
            (override_operation == "set", override_value),
            (override_operation == "remove", literal("")),
            else_=base_text,
        ),
        "",
    )


def first_non_empty_text_expression(field_expressions: list):
    candidates = [
        func.nullif(func.trim(func.coalesce(expression, "")), "")
        for expression in field_expressions
    ]
    if not candidates:
        return literal("")
    return func.coalesce(*candidates, "")


def effective_fields_search_condition(
    field_expressions: list,
    *,
    keyword_like: str,
):
    if not field_expressions:
        return false()
    return or_(
        *[
            func.lower(func.coalesce(expression, "")).like(
                keyword_like,
                escape="\\",
            )
            for expression in field_expressions
        ]
    )


def load_card_for_browse_update(*, card_id: str) -> Card | None:
    """Return a browse card with note, note type, media, and template preloaded."""
    return get_card(db.session, card_id, query=(
        Card.query.join(Note, Card.note_id == Note.id)
        .options(
            selectinload(Card.note).selectinload(Note.note_type).selectinload(NoteType.field_defs),
            selectinload(Card.note).selectinload(Note.media_assets),
            selectinload(Card.template),
        )
    ))


def page_total_and_integrity(query, *, eligible=None, violation=None) -> tuple[int, int]:
    """Return exact filtered total for pagination without full-collection preflight scan."""

    count_query = query.order_by(None)
    if eligible is not None:
        count_query = count_query.filter(eligible)
    row = count_query.with_entities(
        func.count(func.distinct(Card.id)),
    ).one()
    return int(row[0] or 0), 0


def page_window_integrity(
    session,
    *,
    learner_user_id: int,
    card_ids: list[int | str] | None = None,
    note_ids: list[str] | set[str] | None = None,
) -> int:
    """Boundary integrity check applied only to records returned in the current page window."""
    if note_ids is None:
        if not card_ids:
            return 0
        from models.card import card_key_pairs
        pairs = card_key_pairs(session, card_ids)
        resolved_note_ids = sorted({pair[0] for pair in pairs.values() if pair[0]})
    else:
        resolved_note_ids = sorted({str(nid) for nid in note_ids if nid})

    if not resolved_note_ids:
        return 0

    from models.flashcard import Note
    from models.study_progress_subject import StudyProgressSubject
    from app.repositories import note_analytics_read_repository
    from sqlalchemy import LargeBinary, cast

    subject = aliased(StudyProgressSubject)
    violation_expr = note_analytics_read_repository.subject_integrity_violation(
        subject,
        note_id=Note.id,
        learner_user_id=learner_user_id,
    )
    row = session.execute(
        select(func.max(violation_expr))
        .select_from(Note)
        .outerjoin(subject, and_(
            subject.learner_user_id == int(learner_user_id),
            subject.logical_note_key == cast(Note.id, LargeBinary),
        ))
        .where(Note.id.in_(resolved_note_ids))
    ).one()
    return int(row[0] or 0)


def load_accessible_browse_decks(*, user_id: int, admin_mode: bool) -> list[Deck]:
    return vocabulary_ctrl.collect_accessible_browse_decks(
        user_id=user_id,
        admin_mode=admin_mode,
    )


def deck_lookup_for_browse(*, user_id: int, admin_mode: bool) -> dict[int, str]:
    return {
        deck.id: deck.name
        for deck in load_accessible_browse_decks(user_id=user_id, admin_mode=admin_mode)
    }


def accessible_browse_deck_ids(*, user_id: int, admin_mode: bool) -> set[int]:
    return {
        int(deck.id)
        for deck in load_accessible_browse_decks(user_id=user_id, admin_mode=admin_mode)
        if deck.id is not None
    }


def get_deck(*, deck_id: int) -> Deck | None:
    return db.session.get(Deck, deck_id)


def commit_changes() -> None:
    db.session.commit()


def rollback_changes() -> None:
    db.session.rollback()
