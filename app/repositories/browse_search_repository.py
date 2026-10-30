"""Set-based clone search over checkpoints, later release deltas and overlays."""

from sqlalchemy import String, and_, case, func, literal, or_, select, true, union_all
from sqlalchemy.orm import aliased

from app.repositories.browse_card_repository import _json_extract_text, _json_scalar_text
from app.repositories.field_value_query_repository import field_identity_path, note_field_text_expression
from models import db
from models.note import Note
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from app.services.note_base_context import published_base_enabled


def _field_relation(specs):
    names = ('source_field_id', 'checkpoint_name', 'identity_key')
    rows = [select(*(literal(spec.get(name), type_=String(255)).label(name) for name in names))
            for spec in specs]
    return (union_all(*rows) if len(rows) > 1 else rows[0]).subquery('browse_search_fields')


def _release_relations(*, deck_item_id, target_sequence, scope_condition):
    scope_notes = select(Note.id).where(scope_condition).distinct().cte()
    checkpoint = DeckReleaseNoteCheckpoint
    ranked_checkpoints = select(
        checkpoint.id.label('id'), checkpoint.source_note_id.label('note_id'),
        checkpoint.release_sequence_no.label('sequence'),
        func.row_number().over(partition_by=checkpoint.source_note_id,
            order_by=(checkpoint.release_sequence_no.asc(), checkpoint.id.asc())).label('rank'),
    ).join(DeckRelease, DeckRelease.id == checkpoint.release_id).join(
        scope_notes, scope_notes.c.id == checkpoint.source_note_id,
    ).where(
        DeckRelease.deck_item_id == deck_item_id, DeckRelease.status == 'published',
        checkpoint.release_sequence_no <= target_sequence,
    ).cte()
    baseline = select(ranked_checkpoints.c.id, ranked_checkpoints.c.note_id,
        ranked_checkpoints.c.sequence).where(ranked_checkpoints.c.rank == 1).subquery('browse_checkpoints')

    change = DeckReleaseChange
    field_id = func.coalesce(change.field_def_id, func.substr(change.property_key, 7))
    # Exclude history already represented by each Note's checkpoint BEFORE
    # ranking. Initial atomic histories must not be replayed per Note/field.
    ranked_changes = select(
        change.id.label('id'), change.entity_id.label('note_id'), field_id.label('field_id'),
        func.row_number().over(partition_by=(change.entity_id, field_id),
            order_by=(change.release_sequence_no.desc(), change.id.desc())).label('rank'),
    ).join(DeckRelease, DeckRelease.id == change.release_id).join(
        scope_notes, scope_notes.c.id == change.entity_id,
    ).outerjoin(
        baseline, baseline.c.note_id == change.entity_id,
    ).where(
        DeckRelease.deck_item_id == deck_item_id, DeckRelease.status == 'published',
        change.entity_kind == 'note_field', change.release_sequence_no <= target_sequence,
        change.release_sequence_no > func.coalesce(baseline.c.sequence, 0),
        or_(change.field_def_id.isnot(None), change.property_key.like('field:%')),
    ).cte()
    latest = select(ranked_changes.c.id, ranked_changes.c.note_id,
        ranked_changes.c.field_id).where(ranked_changes.c.rank == 1).subquery('browse_changes')
    return scope_notes, baseline, latest


def _changed_text(operation, value, *, release=False):
    return case(
        (operation.in_(['add', 'set'] if release else ['set']),
         func.coalesce(_json_scalar_text(value), '')),
        (operation == 'remove', literal('')), else_=None,
    )


def clone_note_search_ids(*, scope_condition, field_specs, deck_install_id,
                          deck_item_id, target_sequence, keyword_like):
    """Return matching identities; all filtering happens before pagination.

    Window relations carry only IDs, not JSON payloads. Each Note's checkpoint
    is read once before expanding its active fields; only effective deltas are
    ranked, then their payload is fetched by primary key.
    """
    fields = _field_relation(field_specs)
    source_id, identity = fields.c.source_field_id, fields.c.identity_key
    if db.session.get_bind().dialect.name in {'mysql', 'mariadb'}:
        source_id = source_id.collate('utf8mb4_unicode_ci')
        identity = identity.collate('utf8mb4_unicode_ci')
    query = select(Note.id.label('note_id')).select_from(Note)
    if not published_base_enabled() and deck_item_id and target_sequence is not None:
        scope_notes, baseline, latest = _release_relations(deck_item_id=deck_item_id,
            target_sequence=target_sequence, scope_condition=scope_condition)
        checkpoint_content = aliased(DeckReleaseNoteCheckpoint)
        change_content = aliased(DeckReleaseChange)
        query = query.join(scope_notes, scope_notes.c.id == Note.id).outerjoin(baseline, baseline.c.note_id == Note.id).outerjoin(
            checkpoint_content, checkpoint_content.id == baseline.c.id,
        ).outerjoin(fields, true()).outerjoin(latest, and_(
            latest.c.note_id == Note.id, latest.c.field_id == source_id,
        )).outerjoin(change_content, change_content.id == latest.c.id)
        base = func.coalesce(
            _changed_text(change_content.operation, change_content.after_value, release=True),
            _json_extract_text(checkpoint_content.field_values, field_identity_path(fields.c.checkpoint_name)),
        )
    else:
        query = query.where(scope_condition).outerjoin(fields, true())
        base = note_field_text_expression(fields.c.source_field_id, include_draft=False)
    override = aliased(DeckCloneNoteFieldOverride)
    query = query.outerjoin(override, and_(
        override.deck_install_id == str(deck_install_id), override.source_note_id == Note.id,
        override.field_identity_key == identity,
    ))
    value = func.coalesce(_changed_text(override.operation, override.value), base, '')
    return query.where(func.lower(value).like(keyword_like, escape='\\')).distinct()
