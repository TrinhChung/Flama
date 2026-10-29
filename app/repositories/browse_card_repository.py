"""Data-access helpers for browse card detail and edit flows."""

from __future__ import annotations

import json

from sqlalchemy import and_, case, false, func, literal, or_, select, tuple_
from sqlalchemy.orm import aliased, contains_eager, load_only, selectinload

from app.repositories import vocabulary_repository as vocabulary_ctrl
from app.repositories.field_value_query_repository import note_field_text_expression
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
from models.study_application import StudyApplication
from models.template import Template
from app.services.note_base_context import published_base_enabled


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
    value_expr = note_field_text_expression(field_def.id)
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
    field_identity_key: str,
):
    """Resolve one clone field at its pinned release plus current overlay.

    The expression is correlated by ``Note.id``. Release installs read their
    initial checkpoint and only the latest stable-field change through the
    applied release. A local override wins last. This keeps q/order/pagination
    inside SQL instead of hydrating the source deck in Python.
    """

    normalized_field_id = str(source_field_def_id or "").strip() or None
    base_text = literal("")

    if (
        not published_base_enabled()
        and
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
        # Resolve operation and value in the same lookup. An explicit clear
        # yields ""; only a missing/unhandled change falls back to checkpoint.
        latest_value = (
            select(case(
                (release_change.operation.in_(["add", "set"]),
                 func.coalesce(_json_scalar_text(release_change.after_value), "")),
                (release_change.operation == "remove", literal("")),
                else_=None,
            ))
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
        base_text = func.coalesce(latest_value, checkpoint_value)
    elif normalized_field_id:
        base_text = note_field_text_expression(normalized_field_id, include_draft=False)

    note_override = aliased(DeckCloneNoteFieldOverride)
    override_filters = (
        note_override.deck_install_id == str(deck_install_id),
        note_override.source_note_id == Note.id,
        note_override.field_identity_key == field_identity_key,
    )
    override_value = (
        select(case(
            (note_override.operation == "set", func.coalesce(_json_scalar_text(note_override.value), "")),
            (note_override.operation == "remove", literal("")),
            else_=None,
        ))
        .where(*override_filters)
        .order_by(note_override.created_at.desc(), note_override.id.desc())
        .limit(1)
        .correlate(Note)
        .scalar_subquery()
    )
    return func.coalesce(override_value, base_text, "")


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
            # The joined Note fills Card.note; no second read of notes.
            contains_eager(Card.note).selectinload(Note.note_type).selectinload(NoteType.field_defs),
            contains_eager(Card.note).selectinload(Note.media_assets),
            selectinload(Card.template),
        )
    ))


def browse_page_load_options():
    """Loader options for a Browse page query that already joins ``Note``.

    ``Card`` is the ``card_presentations`` view over ``notes``, so the page
    query's own ``Note`` join fills ``Card.note`` instead of a third read of
    ``notes``. A row needs only the NoteType name and field order and the
    Template name.
    """
    return (
        contains_eager(Card.note).selectinload(Note.note_type).options(
            load_only(NoteType.id, NoteType.user_id, NoteType.name, NoteType.field_schema_revision),
            selectinload(NoteType.field_defs),
        ),
        selectinload(Card.template).load_only(Template.id, Template.name),
    )


def one_visible_card_per_note(query):
    """Choose a preview only from the caller's already-visible presentations.

    Historical cutover pairs and clone timestamp bounds differ per Note. A
    NoteType-wide default must never remove a Note that has another visible
    presentation. This is a SQL subquery, not a persisted cache or table.
    """
    ranked = (
        query.order_by(None)
        .join(StudyApplication, StudyApplication.id == Card.application_id)
        .with_entities(
            Card.note_id.label("note_id"),
            Card.application_id.label("application_id"),
            func.row_number().over(
                partition_by=Card.note_id,
                order_by=(StudyApplication.is_default.desc(),
                          StudyApplication.position.asc(), StudyApplication.id.asc()),
            ).label("preview_rank"),
        )
        .subquery("browse_note_previews")
    )
    return query.filter(tuple_(Card.note_id, Card.application_id).in_(
        select(ranked.c.note_id, ranked.c.application_id).where(ranked.c.preview_rank == 1)
    ))


def count_distinct_cards(query) -> int:
    """Exact filtered total for pagination; integrity is checked per page window."""

    return int(query.order_by(None).with_entities(func.count(func.distinct(Card.id))).scalar() or 0)


def order_browse_cards_by_deck(
    query,
    *,
    learner_user_id: int,
    sort_dir: str,
    source_to_local_deck_id: dict[int, int],
    deck_name_lookup: dict[int, str],
):
    """Sort by the same effective deck names used to build Browse rows.

    Owned Notes keep their own deck even if that deck is also an install's
    source. For foreign Notes, the first resolved source/local mapping is the
    same one the page formatter uses. Resolve names before LIMIT/OFFSET.
    """
    query = query.outerjoin(Deck, Note.deck_id == Deck.id)
    name_cases = [
        (
            and_(Note.user_id != int(learner_user_id), Note.deck_id == source_deck_id),
            literal(deck_name_lookup[local_deck_id]),
        )
        for source_deck_id, local_deck_id in sorted(source_to_local_deck_id.items())
        if deck_name_lookup.get(local_deck_id)
    ]
    name = case(*name_cases, else_=Deck.name) if name_cases else Deck.name
    return query.order_by(
        name.desc() if sort_dir == "desc" else name.asc(),
        Card.updated_at.desc(),
    )


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
