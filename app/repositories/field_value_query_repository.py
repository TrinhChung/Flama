"""SQL readers for the single ID-keyed live Note value store.

Names are boundary labels. Predicates extract values by the active schema ID,
so UUID keys, deleted fields and retained historical labels are not searchable.
"""
from __future__ import annotations

import json
import re

from sqlalchemy import Boolean, Integer, Text, case, cast, exists, func, literal, or_, select, type_coerce
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import FunctionElement

from models import db
from models.field_def import FieldDef
from models.note import Note
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from app.services.note_base_context import published_base_enabled


def field_identity_path(identity):
    if isinstance(identity, str):
        return literal("$." + json.dumps(identity, ensure_ascii=False))
    escaped = func.replace(func.replace(identity, "\\", "\\\\"), '"', '\\"')
    return literal('$."').concat(escaped).concat(literal('"'))


def join_author_draft(query, draft, user_id):
    """Materialize sparse IDs once; avoid a Draft PK miss for every Base Note.

    DISTINCT prevents MySQL from merging this small key relation back into
    per-Note InnoDB probes. Values stay in the existing table and are fetched
    only for matching keys. No persistent projection or index is introduced.
    """
    from models.note_draft import NoteDraft
    owner = Note.__table__.alias('draft_key_owner')
    keys = select(NoteDraft.note_id).join(owner, owner.c.id == NoteDraft.note_id).where(
        owner.c.user_id == user_id).distinct().subquery('author_draft_keys')
    return query.outerjoin(keys, keys.c.note_id == Note.id).outerjoin(draft, draft.note_id == keys.c.note_id)


def note_field_json_expression(identity, *, note_model=Note, include_draft=True, draft_model=None):
    """Extract raw JSON, preserving numbers, lists, null and missing values."""
    base = func.json_extract(note_model.field_values_by_id, field_identity_path(identity))
    if not include_draft or not published_base_enabled():
        return base
    from models.note_draft import NoteDraft
    draft = draft_model if draft_model is not None else aliased(NoteDraft)
    path = field_identity_path(identity)
    delta = func.json_extract(draft.field_values_by_id, path)
    operation = func.json_unquote(func.json_extract(delta, '$.op'))
    value = func.json_extract(delta, '$.value')
    if draft_model is not None:
        return case((draft_model.note_id.is_(None), base), (operation == 'remove', None),
            (operation == 'set', value), else_=base)
    return case((exists(select(draft.note_id).where(draft.note_id == note_model.id,
        operation == 'remove').correlate_except(draft)), None),
        else_=func.coalesce(select(value).where(draft.note_id == note_model.id,
            operation == 'set').correlate_except(draft).scalar_subquery(), base))


def note_field_text_expression(identity, *, note_model=Note, include_draft=True, draft_model=None):
    value = note_field_json_expression(identity, note_model=note_model, include_draft=include_draft, draft_model=draft_model)
    if db.session.get_bind().dialect.name in {"mysql", "mariadb"}:
        return case((func.json_type(value) == "NULL", None), else_=func.json_unquote(value))
    return cast(value, Text)


def note_field_typed_expression(identity, *, note_model=Note):
    value = note_field_json_expression(identity, note_model=note_model)
    if db.session.get_bind().dialect.name == "sqlite":
        value = func.json_quote(value)
    return type_coerce(value, db.JSON)


def note_field_document_expression(identity, *, note_model=Note, draft_model=None, include_draft=True):
    value = note_field_json_expression(identity, note_model=note_model, draft_model=draft_model, include_draft=include_draft)
    return func.json_quote(value) if db.session.get_bind().dialect.name == "sqlite" else value


def author_note_visible(*, note_model=Note, draft_model=None):
    """Author-only filter; never use it on a learner's source Note branch."""
    if not published_base_enabled():
        return literal(True)
    if draft_model is not None:
        return or_(draft_model.op.is_(None), draft_model.op != 'delete') & note_model.deleted_at.is_(None)
    from models.note_draft import NoteDraft
    draft = aliased(NoteDraft)
    return ~exists(select(draft.note_id).where(draft.note_id == note_model.id,
        draft.op == 'delete').correlate(note_model)) & note_model.deleted_at.is_(None)


def author_note_column(name, *, note_model=Note, draft_model=None):
    base = getattr(note_model, name)
    if not published_base_enabled():
        return base
    from models.note_draft import NoteDraft
    draft = draft_model if draft_model is not None else aliased(NoteDraft)
    column = getattr(draft, name)
    resolved = func.coalesce(column, base) if draft_model is not None else func.coalesce(
        select(column).where(draft.note_id == note_model.id).correlate(note_model).scalar_subquery(), base)
    if name == 'updated_at':
        if draft_model is not None:
            return case((base.is_(None), column), (column > base, column), else_=base)
        return case((resolved > base, resolved), else_=base)
    if name == "deck_id":
        meta = func.json_extract(draft.field_values_by_id, '$."meta:deck_id"')
        condition = func.json_unquote(func.json_extract(meta, '$.op')) == 'set'
        value = func.json_extract(meta, '$.value')
        target = case((func.json_type(value) == 'NULL', None), else_=cast(func.json_unquote(value), Integer))
        if draft_model is not None:
            return case((draft.note_id.is_(None), base), (condition, target), else_=resolved)
        return case((exists(select(draft.note_id).where(draft.note_id == note_model.id,
            condition).correlate(note_model)), select(target).where(draft.note_id == note_model.id,
                condition).correlate(note_model).scalar_subquery()), else_=resolved)
    return resolved


class _JsonLeafLike(FunctionElement):
    type = Boolean()
    # The numeric/boolean branch depends on the literal search term.
    inherit_cache = False


class _EffectiveExtras(FunctionElement):
    type = db.JSON()
    inherit_cache = True


@compiles(_EffectiveExtras, "mysql")
@compiles(_EffectiveExtras, "mariadb")
def _mysql_effective_extras(element, compiler, **kw):
    arguments = [compiler.process(value, **kw) for value in element.clauses]
    base, note_id, note_type_id = arguments[:3]
    joined = len(arguments) == 4
    document = arguments[3] if joined else 'fv_draft.field_values_by_id'
    path = "CONCAT('$.\"extra:', SHA2(CONCAT(" + note_type_id + ", CHAR(0), fv_key.label), 256), '\"')"
    delta = "JSON_EXTRACT(" + document + ", " + path + ")"
    operation = "JSON_UNQUOTE(JSON_EXTRACT(" + delta + ", '$.op'))"
    value = "JSON_EXTRACT(" + delta + ", '$.value')"
    quoted_label = "CONCAT('$.\"', REPLACE(REPLACE(fv_key.label, CHAR(92), CONCAT(CHAR(92),CHAR(92))), CHAR(34), CONCAT(CHAR(92),CHAR(34))), '\"')"
    retained_source = ("JSON_TABLE(JSON_KEYS(" + base
        + "), '$[*]' COLUMNS(label VARCHAR(255) PATH '$')) AS fv_key")
    replacement_source = ("JSON_TABLE(" + document + ", '$.*' COLUMNS(label VARCHAR(255) PATH '$.label' NULL ON EMPTY,"
        + " operation VARCHAR(16) PATH '$.op', changed_value JSON PATH '$.value' NULL ON EMPTY)) AS fv_op")
    prefix = '' if joined else 'note_drafts AS fv_draft JOIN '
    predicate = '' if joined else 'fv_draft.note_id = ' + note_id + ' AND '
    suffix = '' if joined else ' ON TRUE'
    retained = ("COALESCE((SELECT JSON_OBJECTAGG(fv_key.label, JSON_EXTRACT(" + base + ", " + quoted_label
        + ")) FROM " + prefix + retained_source + suffix + " WHERE " + predicate + delta + " IS NULL), JSON_OBJECT())")
    replacements = ("COALESCE((SELECT JSON_OBJECTAGG(fv_op.label, fv_op.changed_value) FROM "
        + prefix + replacement_source + suffix + " WHERE " + predicate
        + "fv_op.label IS NOT NULL AND fv_op.operation = 'set'), JSON_OBJECT())")
    present = document + ' IS NOT NULL' if joined else (
        "EXISTS(SELECT fv_present.note_id FROM note_drafts AS fv_present WHERE fv_present.note_id = " + note_id + ")")
    return "CASE WHEN " + present + " THEN JSON_MERGE_PATCH(" + retained + ", " + replacements + ") ELSE " + base + " END"



def note_extras_expression(*, note_model=Note, draft_model=None, include_draft=True):
    if not include_draft or not published_base_enabled():
        return note_model.field_values_extras
    arguments = (note_model.field_values_extras, note_model.id, note_model.note_type_id)
    return _EffectiveExtras(*arguments, draft_model.field_values_by_id) if draft_model is not None else _EffectiveExtras(*arguments)


@compiles(_JsonLeafLike, "sqlite")
def _sqlite_leaf_like(element, compiler, **kw):
    document, pattern = [compiler.process(value, **kw) for value in element.clauses]
    return ("EXISTS (SELECT 1 FROM json_tree(" + document + ") AS fv_leaf "
            "WHERE fv_leaf.atom IS NOT NULL AND lower(CASE fv_leaf.type "
            "WHEN 'true' THEN 'true' WHEN 'false' THEN 'false' ELSE CAST(fv_leaf.atom AS TEXT) END) "
            "LIKE " + pattern + " ESCAPE '\\')")


@compiles(_JsonLeafLike, "mysql")
@compiles(_JsonLeafLike, "mariadb")
def _mysql_leaf_like(element, compiler, **kw):
    document, pattern = list(element.clauses)
    # Native JSON_SEARCH avoids nested correlated JSON_TABLE materialization.
    # Search string leaves, including native nested arrays, never member keys.
    # https://dev.mysql.com/doc/refman/8.0/en/json-search-functions.html
    search_document = compiler.process(document, **kw)
    search_pattern = compiler.process(pattern, **kw)
    scalar_document = compiler.process(document, **kw)
    scalar_text = compiler.process(document, **kw)
    scalar_pattern = compiler.process(pattern, **kw)
    native = ("JSON_SEARCH(lower(CAST(" + search_document + " AS CHAR)), 'one', " + search_pattern
        + ") IS NOT NULL OR (JSON_TYPE(" + scalar_document + ") IN ('INTEGER', 'DOUBLE', 'BOOLEAN', 'DECIMAL') "
        + "AND lower(JSON_UNQUOTE(" + scalar_text + ")) LIKE " + scalar_pattern + " ESCAPE '\\\\')")
    needle = str(getattr(pattern, "value", "") or "").lower().strip("%")
    numeric_or_boolean = bool(needle and (re.fullmatch(r"[-+0-9.e]+", needle)
        or any(needle in word for word in ("true", "false"))))
    if not numeric_or_boolean:
        return "(" + native + ")"
    # JSON_SEARCH handles string leaves. For numbers/booleans, remove complete
    # JSON string tokens (including escaped quotes/backslashes) and null tokens
    # before substring matching. Valid JSON then contains only scalar tokens
    # and delimiters; structural keys cannot match. This avoids nested
    # correlated JSON_TABLE, which MySQL rejects in Browse's ranked CTE.
    # https://dev.mysql.com/doc/refman/8.0/en/regexp.html
    unquoted = func.replace(func.regexp_replace(cast(document, Text),
        literal(r'"(?:[^"\\]|\\.)*"'), literal('')), literal('null'), literal(''))
    scalar_leaves = compiler.process(func.lower(unquoted), **kw)
    return "(" + native + " OR " + scalar_leaves + " LIKE " + compiler.process(pattern, **kw) + " ESCAPE '\\\\')"


def note_values_search_condition(*, keyword_like: str, note_model=Note, draft_model=None, include_draft=True):
    """Search active field values and retained extras; exclude structural keys."""
    field = aliased(FieldDef)
    owned_note = aliased(Note)
    active = exists(select(literal(1)).select_from(field)
        .join(owned_note, field.note_type_id == owned_note.note_type_id).where(
        owned_note.id == note_model.id,
        _JsonLeafLike(note_field_document_expression(field.id, note_model=owned_note, include_draft=include_draft), literal(keyword_like)),
    ).correlate(note_model))
    if draft_model is not None:
        active = exists(select(literal(1)).select_from(field).where(
            field.note_type_id == note_model.note_type_id,
            _JsonLeafLike(note_field_document_expression(field.id, note_model=note_model,
                draft_model=draft_model), literal(keyword_like)),
        ).correlate(note_model, draft_model))
    added = aliased(DeckCloneAddedFieldDef)
    added_note = aliased(DeckCloneAddedNote)
    deck_map = aliased(DeckCloneDeckMap)
    belongs_to_install = or_(
        exists(select(literal(1)).where(added_note.note_id == note_model.id,
            added_note.deck_install_id == added.deck_install_id).correlate(note_model, added)),
        exists(select(literal(1)).where(deck_map.local_deck_id == note_model.deck_id,
            deck_map.deck_install_id == added.deck_install_id).correlate(note_model, added)),
    )
    added_identity = literal("added:").concat(added.deck_install_id).concat(literal(":")).concat(added.id)
    local_added = exists(select(literal(1)).where(belongs_to_install,
        _JsonLeafLike(note_field_document_expression(added_identity, note_model=note_model,
            draft_model=draft_model, include_draft=include_draft), literal(keyword_like)),
    ).correlate(note_model, *([draft_model] if draft_model is not None else [])))
    return or_(active, local_added, _JsonLeafLike(note_extras_expression(note_model=note_model,
        draft_model=draft_model, include_draft=include_draft), literal(keyword_like)))


def published_note_values_search_condition(*, field_ids, keyword_like, note_model=Note):
    """Public search uses published identities and raw Base, never drafts."""
    return or_(*[_JsonLeafLike(note_field_json_expression(identity, note_model=note_model,
        include_draft=False), literal(keyword_like)) for identity in field_ids],
        _JsonLeafLike(note_model.field_values_extras, literal(keyword_like)))


def named_field_json_expression(field_name: str, *, note_model=Note):
    """Resolve a current label to its scoped ID without hydrating Note rows."""
    field = aliased(FieldDef)
    declared = (select(note_field_typed_expression(field.id, note_model=note_model))
        .where(field.note_type_id == note_model.note_type_id, field.name == field_name)
        .correlate(note_model).limit(1).scalar_subquery())
    # Cross-model duplicate detection also covers schemaless retained extras.
    # A declared label always takes priority, including an explicit JSON null.
    extra = (func.json_extract(note_extras_expression(note_model=note_model), field_identity_path(field_name))
        if published_base_enabled() else note_model.field_values_extras[field_name])
    return type_coerce(func.coalesce(declared, extra), db.JSON)
