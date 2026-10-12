"""Explicit NOTE progress fixtures using strict production codecs.

No legacy persistence model or compatibility Card write is introduced. Each
learner/Note has one current state; callers choose the exact scheduler values.
"""
from datetime import datetime
from types import SimpleNamespace

from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress
from models.card import Card
from models.study_progress_subject import StudyProgressSubject
from tests.study_note_fixtures import mapper_state_input


def subject_values(*, user_id, note_id, now=None, **state):
    now = now or datetime(2026, 1, 1)
    raw = mapper_state_input(id=1, user_id=user_id, card_id='fixture-input',
                             created_at=now, updated_at=now, **state)
    mapped = map_card_progress(raw, card_created_at=now, card_order_key='fixture-input')
    if not isinstance(mapped, MappedCardProgress):
        raise ValueError(f'Invalid explicit NOTE fixture: {mapped.code}')
    values = dict(learner_user_id=user_id, logical_note_key=str(note_id).encode(), live_note_id=str(note_id),
        status_code='MIRRORED_SINGLE', authority_revision=raw.revision, contributor_count=1,
        created_at=now, updated_at=now, history_completeness_code='HISTORY_IMPORTED_PARTIAL',
        current_provenance_code='UNKNOWN_LEGACY', state_payload=mapped.state.payload,
        state_payload_size=mapped.state.size)
    values.update({key: getattr(mapped, key) for key in ('algorithm_key','algorithm_version','state_schema_version',
        'storage_codec','algorithm_state_hash','semantic_state_hash')})
    values.update({key: getattr(mapped.availability, key) for key in ('projection_version','normalized_queue','due_at',
        'due_day','is_suspended','is_buried','buried_until_day')})
    return values


def stage_note_state(session, *, user_id, card_id=None, note_id=None, **state):
    if note_id is None:
        card = session.get(Card, card_id)
        if card is None:
            raise ValueError('Fixture needs a current derived presentation.')
        note_id = card.note_id
    values = subject_values(user_id=user_id, note_id=note_id, **state)
    subject = session.query(StudyProgressSubject).filter_by(
        learner_user_id=user_id, logical_note_key=str(note_id).encode()).one_or_none()
    if subject is None:
        subject = StudyProgressSubject(**values)
        session.add(subject)
    else:
        for key,value in values.items():
            setattr(subject,key,value)
    return subject
