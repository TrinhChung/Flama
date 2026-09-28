import { describe, expect, it } from 'vitest'
import {
  ClientAlgorithmContractError,
  ClientAlgorithmUnavailableError,
  resolveClientAlgorithm,
  validateSnapshotAlgorithmContract,
} from '../scheduler/algorithmRegistry'
import { canonicalDigest } from './canonicalDigest'
import { normalizePersistedStudySession } from './sessionRestore'

import { FROZEN_TEMPLATE_VERSION, FROZEN_CONTENT_VERSION, studySnapshotFixture as snapshot } from './studySessionTestFixture'
const FROZEN_BINDING_FINGERPRINT = 'sha256-fcc37db709986454b8f9f41ee8761518992b282185bb140812749a562580142d'


type StoredEventFixture = {
  event_id: string
  sequence: number
  card_id: string
  rating: string
  policy_key: string
  scheduler_offset_ms: number
  duration_ms: number
  action_key?: string
  action_contract_version?: string
  trigger_key?: string
  trigger_contract_version?: string
  algorithm_key?: string
  algorithm_version?: string
  config_schema_version?: string
  config_hash?: string
  study_session_id?: string
  authority_mode?: string
  enrollment_epoch?: string
  logical_note_key?: string
  subject_generation?: string
  base_authority_revision?: string
  base_authority_state_hash?: string
  operation_key?: string
}

function persistedSession() {
  const events: StoredEventFixture[] = [{
    event_id: '00000000-0000-4000-8000-000000000001',
    sequence: 1,
    card_id: 'card-1',
    rating: 'good',
    policy_key: 'policy',
    scheduler_offset_ms: 1000,
    duration_ms: 500,
  }]
  return {
    scope_key: 'user:7:deck:12',
    snapshot: snapshot(),
    events,
    touched_card_ids: [],
    opened_client_at_ms: Date.parse('2026-02-22T09:00:00.000Z'),
    status: 'active',
    commit_id: null,
    updated_at_ms: Date.parse('2026-02-22T09:00:01.000Z'),
  }
}

function addFrozenCompositionContract(stored: ReturnType<typeof persistedSession>) {
  const composition = {
    composition_id: 'comp:notetype:type-1:template:template-1',
    mode_key: 'flashcard',
    note_type_id: 'type-1',
    note_type_name: 'Basic',
    template_id: 'template-1',
    template_name: 'Front -> Back',
    is_default: true,
    context_kind: 'owned' as const,
    definition_id: 'legacy-template:template-1',
    application_id: 'comp:notetype:type-1:template:template-1',
    interaction_key: 'review.four-rating',
    trigger_key: 'scheduler.review',
    trigger_contract_version: '1',
    algorithm_key: 'legacy-anki',
    algorithm_version: '1.0.0',
  }
  stored.snapshot.composition_contract_version = 'applied-composition.compat.v1'
  stored.snapshot.selected_composition_id = composition.composition_id
  stored.snapshot.selected_composition = composition
  stored.snapshot.composition_selection_resolution = 'explicit'
  stored.snapshot.composition_binding = {
    schema_version: 'study-composition-binding.v1',
    composition_id: composition.composition_id,
    definition_id: 'legacy-template:template-1',
    definition_version: FROZEN_TEMPLATE_VERSION,
    application_id: composition.composition_id,
    application_occurrence_id: composition.composition_id,
    binding_kind: 'legacy-fielddef-direct',
    binding_fingerprint: FROZEN_BINDING_FINGERPRINT,
    field_bindings: [{
      input_id: 'legacy-field:field-1',
      field_def_id: 'field-1',
      field_name: 'Word',
      field_type: 'text',
      required: true,
    }],
  }
  stored.snapshot.cards[0].composition_id = composition.composition_id
  stored.snapshot.cards[0].template_key = `template-1:${FROZEN_TEMPLATE_VERSION}`
  stored.snapshot.cards[0].content_key = `note-1:${FROZEN_CONTENT_VERSION}`
  stored.snapshot.templates = {
    [`template-1:${FROZEN_TEMPLATE_VERSION}`]: {
      ...stored.snapshot.templates.template,
      version: FROZEN_TEMPLATE_VERSION,
      field_defs: [{
        id: 'field-1',
        name: 'Word',
        field_type: 'text',
        required: true,
        position: 0,
      }],
    },
  }
  stored.snapshot.contents = {
    [`note-1:${FROZEN_CONTENT_VERSION}`]: {
      ...stored.snapshot.contents.content,
      version: FROZEN_CONTENT_VERSION,
    },
  }
  stored.snapshot.compositions = { [composition.composition_id]: composition }
  return stored
}

describe('client Algorithm registry', () => {
  it('resolves only the exact retained Algorithm version', () => {
    expect(resolveClientAlgorithm('legacy-anki', '1.0.0')).toMatchObject({
      key: 'legacy-anki',
      version: '1.0.0',
    })
    expect(() => resolveClientAlgorithm('legacy-anki', '2.0.0'))
      .toThrow(ClientAlgorithmUnavailableError)
  })

  it('rejects policy identity that disagrees with the session', () => {
    const invalid = snapshot()
    invalid.policies.policy.algorithm_version = '2.0.0'
    expect(() => validateSnapshotAlgorithmContract(invalid))
      .toThrow(ClientAlgorithmContractError)
  })
})

describe('persisted study session normalization', () => {
  it('matches the backend canonical SHA-256 contract for UTF-8 material', () => {
    expect(canonicalDigest({ z: '猫', a: [true, null, 'x'] })).toBe(
      'sha256-874350020a8ee09fe053dd03644ebef3ff65adca723ae89f421cd30bbb92ef23',
    )
  })

  it('restores a complete frozen composition contract without rewriting it', () => {
    const stored = addFrozenCompositionContract(persistedSession())

    const result = normalizePersistedStudySession(stored)

    expect(result.status).toBe('restored')
    if (result.status !== 'restored') return
    expect(result.session.snapshot.selected_composition_id).toBe(
      'comp:notetype:type-1:template:template-1',
    )
    expect(result.session.snapshot.composition_binding?.binding_fingerprint).toBe(
      FROZEN_BINDING_FINGERPRINT,
    )
  })

  it('quarantines tampered frozen fingerprints and artifact relationships', () => {
    const badFingerprint = addFrozenCompositionContract(persistedSession())
    badFingerprint.snapshot.composition_binding!.binding_fingerprint = `sha256-${'0'.repeat(64)}`
    expect(normalizePersistedStudySession(badFingerprint)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'COMPOSITION_CONTRACT_MISMATCH' },
    })

    const badTemplateVersion = addFrozenCompositionContract(persistedSession())
    badTemplateVersion.snapshot.composition_binding!.definition_version = `sha256-${'2'.repeat(64)}`
    expect(normalizePersistedStudySession(badTemplateVersion)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'COMPOSITION_CONTRACT_MISMATCH' },
    })

    const badContentIdentity = addFrozenCompositionContract(persistedSession())
    badContentIdentity.snapshot.contents[`note-1:${FROZEN_CONTENT_VERSION}`].note_id = 'note-2'
    expect(normalizePersistedStudySession(badContentIdentity)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'COMPOSITION_CONTRACT_MISMATCH' },
    })
  })

  it('quarantines partial or contradictory frozen composition material', () => {
    const partial = persistedSession()
    partial.snapshot.selected_composition_id = 'comp:notetype:type-1:template:template-1'
    expect(normalizePersistedStudySession(partial)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'COMPOSITION_CONTRACT_MISMATCH' },
    })

    const contradictory = addFrozenCompositionContract(persistedSession())
    contradictory.snapshot.cards[0].composition_id = 'different-composition'
    expect(normalizePersistedStudySession(contradictory)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'COMPOSITION_CONTRACT_MISMATCH' },
    })
  })

  it('upgrades valid legacy v2 events to canonical Action metadata', () => {
    const result = normalizePersistedStudySession(persistedSession())

    expect(result.status).toBe('restored')
    if (result.status !== 'restored') return
    expect(result.migrated).toBe(true)
    expect(result.session.events[0]).toMatchObject({
      rating: 'good',
      action_key: 'review.good',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
    })
    expect(result.session.touched_card_ids).toEqual(['card-1'])
  })

  it('quarantines event metadata that disagrees with its rating', () => {
    const stored = persistedSession()
    stored.events[0] = {
      ...stored.events[0],
      action_key: 'review.easy',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
    }

    const result = normalizePersistedStudySession(stored)

    expect(result).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_CONTRACT_MISMATCH' },
    })
  })

  it('quarantines sessions requiring an unavailable Algorithm version', () => {
    const stored = persistedSession()
    stored.snapshot.algorithm_version = '2.0.0'
    stored.snapshot.policies.policy.algorithm_version = '2.0.0'

    const result = normalizePersistedStudySession(stored)

    expect(result).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'ALGORITHM_UNAVAILABLE' },
    })
  })

  it('restores exact v3 identity without rewriting it', () => {
    const stored = persistedSession()
    stored.snapshot = {
      ...stored.snapshot,
      schema_version: 'study-session.v3',
    }
    stored.events[0] = {
      ...stored.events[0],
      action_key: 'review.good',
      action_contract_version: '1',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
      algorithm_key: 'legacy-anki',
      algorithm_version: '1.0.0',
      config_schema_version: 'scheduler-config.v1',
      config_hash: 'policy',
      study_session_id: stored.snapshot.session_id,
    }

    const result = normalizePersistedStudySession(stored)
    expect(result.status).toBe('restored')
    if (result.status !== 'restored') return
    expect(result.session.snapshot.schema_version).toBe('study-session.v3')
    expect(result.session.events[0]).toMatchObject({
      action_contract_version: '1',
      config_hash: 'policy',
      study_session_id: stored.snapshot.session_id,
    })
  })

  it('restores exact v4 Note pin and quarantines epoch or operation drift', () => {
    const stored = persistedSession()
    const eventId = stored.events[0].event_id
    const pin = {
      schema_version: 'study-note-authority-pin.v1' as const,
      authority_mode: 'NOTE' as const,
      enrollment_epoch: '3',
      logical_note_key: 'note-key',
      subject_generation: '2',
      base_authority_revision: '7',
      base_authority_state_hash: '11'.repeat(32),
    }
    stored.snapshot = {
      ...stored.snapshot,
      schema_version: 'study-session.v4',
      authority_mode: 'NOTE',
      enrollment_epoch: '3',
      cards: stored.snapshot.cards.map((card) => ({
        ...card,
        authority_pin: pin,
      })),
    }
    stored.events[0] = {
      ...stored.events[0],
      action_key: 'review.good',
      action_contract_version: '1',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
      algorithm_key: 'legacy-anki',
      algorithm_version: '1.0.0',
      config_schema_version: 'scheduler-config.v1',
      config_hash: 'policy',
      study_session_id: stored.snapshot.session_id,
      ...pin,
      operation_key: eventId,
    }

    const restored = normalizePersistedStudySession(stored)
    expect(restored.status).toBe('restored')
    if (restored.status !== 'restored') return
    expect(restored.session.events[0]).toMatchObject({
      operation_key: eventId,
      base_authority_revision: '7',
    })
    expect(restored.session.events[0]).not.toHaveProperty('schema_version')

    // Pre-release builds accidentally copied the snapshot pin's schema tag
    // onto events. It was rejected before admission. Restore must retain the
    // original batch/event identities and project only the valid event wire.
    const pending = {
      ...stored, events: [], status: 'pending_commit',
      commit_id: '22222222-2222-4222-8222-222222222222',
      commit_reason: 'auto_finish', resume_after_commit: false,
      batch_sequence: 1, event_sequence: 1,
      in_flight_batches: [{
        schema_version: 'study-batch.v3',
        batch_id: '22222222-2222-4222-8222-222222222222', batch_sequence: 1,
        session_token: stored.snapshot.session_token,
        snapshot_hash: stored.snapshot.snapshot_hash,
        commit_reason: 'auto_finish', is_final: true,
        events: stored.events, final_states: [],
      }],
    }
    const recovered = normalizePersistedStudySession(pending)
    expect(recovered.status).toBe('restored')
    if (recovered.status !== 'restored') return
    const batch = recovered.session.in_flight_batches![0]
    expect(batch.batch_id).toBe(pending.commit_id)
    expect(batch.events[0].event_id).toBe(eventId)
    expect(batch.events[0]).toMatchObject({ operation_key: eventId })
    expect(batch.events[0]).not.toHaveProperty('schema_version')

    const wrongOperation = structuredClone(stored)
    wrongOperation.events[0].operation_key = 'another-operation'
    expect(normalizePersistedStudySession(wrongOperation)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_CONTRACT_MISMATCH' },
    })

    const wrongEpoch = structuredClone(stored)
    if (wrongEpoch.snapshot.schema_version !== 'study-session.v4') {
      throw new Error('Expected the v4 fixture to retain its schema.')
    }
    wrongEpoch.snapshot.enrollment_epoch = '4'
    expect(normalizePersistedStudySession(wrongEpoch)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'MALFORMED_SESSION' },
    })
  })

  it('quarantines v3 events with missing or mismatched identity', () => {
    const stored = persistedSession()
    stored.snapshot = {
      ...stored.snapshot,
      schema_version: 'study-session.v3',
    }
    stored.events[0] = {
      ...stored.events[0],
      action_key: 'review.good',
      action_contract_version: '1',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
      algorithm_key: 'legacy-anki',
      algorithm_version: '1.0.0',
      config_schema_version: 'scheduler-config.v1',
      config_hash: 'wrong-policy',
      study_session_id: stored.snapshot.session_id,
    }
    expect(normalizePersistedStudySession(stored)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_CONTRACT_MISMATCH' },
    })
    delete stored.events[0].action_contract_version
    expect(normalizePersistedStudySession(stored)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_CONTRACT_MISMATCH' },
    })
  })

  it.each([
    ['invalid UUID', { event_id: 'event-1' }, 'EVENT_ID_INVALID'],
    ['string sequence', { sequence: '1' }, 'EVENT_SEQUENCE_INVALID'],
    ['negative offset', { scheduler_offset_ms: -1 }, 'EVENT_TIME_INVALID'],
    ['string offset', { scheduler_offset_ms: '1000' }, 'EVENT_TIME_INVALID'],
    ['unknown card', { card_id: 'card-outside-session' }, 'EVENT_CONTRACT_MISMATCH'],
    ['wrong policy', { policy_key: 'other-policy' }, 'EVENT_CONTRACT_MISMATCH'],
  ])('quarantines %s without coercing replay fields', (_label, patch, reason) => {
    const stored = persistedSession()
    stored.events[0] = { ...stored.events[0], ...patch } as StoredEventFixture

    expect(normalizePersistedStudySession(stored)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason },
    })
  })

  it('quarantines duplicate ids, sequence gaps, and non-monotonic offsets', () => {
    const duplicateId = persistedSession()
    duplicateId.events.push({
      ...duplicateId.events[0],
      sequence: 2,
      scheduler_offset_ms: 2000,
    })
    expect(normalizePersistedStudySession(duplicateId)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_ID_INVALID' },
    })

    const sequenceGap = persistedSession()
    sequenceGap.events.push({
      ...sequenceGap.events[0],
      event_id: '00000000-0000-4000-8000-000000000002',
      sequence: 3,
      scheduler_offset_ms: 2000,
    })
    expect(normalizePersistedStudySession(sequenceGap)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_SEQUENCE_INVALID' },
    })

    const backwardsTime = persistedSession()
    backwardsTime.events.push({
      ...backwardsTime.events[0],
      event_id: '00000000-0000-4000-8000-000000000002',
      sequence: 2,
      scheduler_offset_ms: 999,
    })
    expect(normalizePersistedStudySession(backwardsTime)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_TIME_INVALID' },
    })
  })

  it('requires sequence one when no batch checkpoint explains prior events', () => {
    const stored = {
      ...persistedSession(),
      batch_sequence: 0,
      event_sequence: 5,
      in_flight_batches: [],
    }
    stored.events[0] = { ...stored.events[0], sequence: 5 }

    expect(normalizePersistedStudySession(stored)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_SEQUENCE_INVALID' },
    })
  })

  it('quarantines offsets outside the lease material pinned in the snapshot', () => {
    const stored = persistedSession()
    stored.events[0].scheduler_offset_ms = 24 * 60 * 60 * 1000 + 1

    expect(normalizePersistedStudySession(stored)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_TIME_INVALID' },
    })
  })

  it('rejects partial semantic metadata instead of treating it as legacy', () => {
    const stored = persistedSession()
    stored.events[0].action_key = 'review.good'

    expect(normalizePersistedStudySession(stored)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_CONTRACT_MISMATCH' },
    })
  })

  it('binds restore to the requested user and scope key', () => {
    const stored = persistedSession()

    expect(normalizePersistedStudySession(
      stored,
      'user:8:deck:12',
    )).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'SCOPE_MISMATCH' },
    })
  })

  it('round-trips batch checkpoints and pending batches without renumbering', () => {
    const stored = persistedSession()
    const pendingEvent = {
      ...stored.events[0],
      action_key: 'review.good',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
    }
    const activeEvent = {
      ...pendingEvent,
      event_id: '00000000-0000-4000-8000-000000000002',
      sequence: 2,
      scheduler_offset_ms: 2000,
    }
    stored.events = [activeEvent]
    Object.assign(stored, {
      batch_sequence: 1,
      event_sequence: 2,
      in_flight_batches: [{
        schema_version: 'study-batch.v1',
        batch_id: '22222222-2222-4222-8222-222222222222',
        batch_sequence: 1,
        session_token: 'token',
        snapshot_hash: 'snapshot-hash',
        commit_reason: 'rollover',
        is_final: false,
        events: [pendingEvent],
        final_states: [{
          card_id: 'card-1',
          base_revision: 0,
          state: stored.snapshot.cards[0].state,
        }],
      }],
    })

    const result = normalizePersistedStudySession(stored)

    expect(result.status).toBe('restored')
    if (result.status !== 'restored') return
    expect(result.session.batch_sequence).toBe(1)
    expect(result.session.event_sequence).toBe(2)
    expect(result.session.in_flight_batches).toHaveLength(1)
    expect(result.session.in_flight_batches?.[0]).toMatchObject({
      batch_id: '22222222-2222-4222-8222-222222222222',
      batch_sequence: 1,
      events: [{
        event_id: '00000000-0000-4000-8000-000000000001',
        sequence: 1,
      }],
    })
    expect(result.session.events[0]).toMatchObject({
      event_id: '00000000-0000-4000-8000-000000000002',
      sequence: 2,
    })
  })

  it('preserves and validates the frozen composition on pending batches', () => {
    const frozen = addFrozenCompositionContract(persistedSession())
    const pendingEvent = {
      ...frozen.events[0],
      action_key: 'review.good',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
    }
    const stored = {
      ...frozen,
      events: [],
      batch_sequence: 1,
      event_sequence: 1,
      in_flight_batches: [{
        schema_version: 'study-batch.v1',
        batch_id: '22222222-2222-4222-8222-222222222222',
        batch_sequence: 1,
        session_token: 'token',
        snapshot_hash: 'snapshot-hash',
        composition_id: frozen.snapshot.selected_composition_id,
        commit_reason: 'rollover',
        is_final: false,
        events: [pendingEvent],
        final_states: [{
          card_id: 'card-1',
          base_revision: 0,
          state: frozen.snapshot.cards[0].state,
        }],
      }],
    }

    const result = normalizePersistedStudySession(stored)
    expect(result.status).toBe('restored')
    if (result.status !== 'restored') return
    expect(result.session.in_flight_batches?.[0].composition_id).toBe(
      frozen.snapshot.selected_composition_id,
    )

    const missing = structuredClone(stored)
    Reflect.deleteProperty(missing.in_flight_batches[0], 'composition_id')
    expect(normalizePersistedStudySession(missing)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'COMPOSITION_CONTRACT_MISMATCH' },
    })

    const mismatched = structuredClone(stored)
    mismatched.in_flight_batches[0].composition_id = 'different-composition'
    expect(normalizePersistedStudySession(mismatched)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'COMPOSITION_CONTRACT_MISMATCH' },
    })
  })

  it('quarantines partial or ambiguous async batch metadata', () => {
    const partial = { ...persistedSession(), batch_sequence: 1 }
    expect(normalizePersistedStudySession(partial)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'BATCH_CONTRACT_MISMATCH' },
    })

    const ambiguous = {
      ...persistedSession(),
      events: [],
      batch_sequence: 1,
      in_flight_batches: [],
    }
    expect(normalizePersistedStudySession(ambiguous)).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'BATCH_CONTRACT_MISMATCH' },
    })
  })

  it('restores an acknowledged batch checkpoint without inventing history', () => {
    const stored = {
      ...persistedSession(),
      events: [],
      batch_sequence: 2,
      event_sequence: 50,
      in_flight_batches: [],
    }

    const result = normalizePersistedStudySession(stored)

    expect(result.status).toBe('restored')
    if (result.status !== 'restored') return
    expect(result.session.event_sequence).toBe(50)
    expect(result.session.events).toEqual([])
    expect(result.session.in_flight_batches).toEqual([])
  })
})
