"""SQL readers for the single ID-keyed live Note value store.

Names are boundary labels. Predicates extract values by the active schema ID,
so UUID keys, deleted fields and retained historical labels are not searchable.
"""
from __future__ import annotations

import json
import re

from sqlalchemy import Boolean, Text, case, cast, exists, func, literal, or_, select, type_coerce
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import FunctionElement

from models import db
from models.field_def import FieldDef
from models.note import Note
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap


def field_identity_path(identity):
    if isinstance(identity, str):
        return literal("$." + json.dumps(identity, ensure_ascii=False))
    escaped = func.replace(func.replace(identity, "\\", "\\\\"), '"', '\\"')
    return literal('$."').concat(escaped).concat(literal('"'))


def note_field_json_expression(identity, *, note_model=Note):
    """Extract raw JSON, preserving numbers, lists, null and missing values."""
    return func.json_extract(note_model.field_values_by_id, field_identity_path(identity))


def note_field_text_expression(identity, *, note_model=Note):
    value = note_field_json_expression(identity, note_model=note_model)
    if db.session.get_bind().dialect.name in {"mysql", "mariadb"}:
        return case((func.json_type(value) == "NULL", None), else_=func.json_unquote(value))
    return cast(value, Text)


def note_field_typed_expression(identity, *, note_model=Note):
    value = note_field_json_expression(identity, note_model=note_model)
    if db.session.get_bind().dialect.name == "sqlite":
        value = func.json_quote(value)
    return type_coerce(value, db.JSON)


def note_field_document_expression(identity, *, note_model=Note):
    value = note_field_json_expression(identity, note_model=note_model)
    return func.json_quote(value) if db.session.get_bind().dialect.name == "sqlite" else value


class _JsonLeafLike(FunctionElement):
    type = Boolean()
    # The numeric/boolean branch depends on the literal search term.
    inherit_cache = False


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
    aggregates = []
    for path in ("$**[*]", "$**.*"):
        # A scalar aggregate prevents MySQL from decorrelating this JSON_TABLE
        # into the incorrect nested EXISTS materialization seen in qualification.
        like_sql = compiler.process(pattern, **kw)
        document_sql = compiler.process(document, **kw)
        aggregates.append("coalesce((SELECT max(lower(fv_leaf.atom) LIKE " + like_sql
            + " ESCAPE '\\\\') FROM JSON_TABLE(JSON_ARRAY(" + document_sql + "), '" + path
            + "' COLUMNS(atom LONGTEXT PATH '$' NULL ON ERROR)) AS fv_leaf), 0) = 1")
    return "(" + " OR ".join([native, *aggregates]) + ")"


def note_values_search_condition(*, keyword_like: str, note_model=Note):
    """Search active field values and retained extras; exclude structural keys."""
    field = aliased(FieldDef)
    owned_note = aliased(Note)
    active = exists(select(literal(1)).select_from(field)
        .join(owned_note, field.note_type_id == owned_note.note_type_id).where(
        owned_note.id == note_model.id,
        _JsonLeafLike(note_field_document_expression(field.id, note_model=owned_note), literal(keyword_like)),
    ).correlate(note_model))
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
        _JsonLeafLike(note_field_document_expression(added_identity, note_model=note_model), literal(keyword_like)),
    ).correlate(note_model))
    return or_(active, local_added, _JsonLeafLike(note_model.field_values_extras, literal(keyword_like)))


def named_field_json_expression(field_name: str, *, note_model=Note):
    """Resolve a current label to its scoped ID without hydrating Note rows."""
    field = aliased(FieldDef)
    declared = (select(note_field_typed_expression(field.id, note_model=note_model))
        .where(field.note_type_id == note_model.note_type_id, field.name == field_name)
        .correlate(note_model).limit(1).scalar_subquery())
    # Cross-model duplicate detection also covers schemaless retained extras.
    # A declared label always takes priority, including an explicit JSON null.
    return type_coerce(func.coalesce(declared, note_model.field_values_extras[field_name]), db.JSON)
