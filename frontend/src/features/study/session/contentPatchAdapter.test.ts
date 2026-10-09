// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { applyCardContentPatch } from './contentPatchAdapter'
import { createPersistedSession } from './studySessionEngine'
import type { PersistedStudySession } from './sessionStore'
import type { StudySessionSnapshot } from '../types'
import { canonicalDigest } from './canonicalDigest'

function createSampleSnapshot(): StudySessionSnapshot {
  return {
    schema_version: 'study-session.v2',
    session_id: 'session-123',
    user_id: 1,
    session_token: 'token',
    snapshot_hash: 'hash',
    scope: { type: 'deck', id: '1', name: 'Deck 1' },
    server_now_utc: '2026-09-08T00:00:00.000Z',
    expires_at: '2026-09-09T00:00:00.000Z',
    timezone: 'UTC',
    day_boundary_hour_local: 4,
    learn_ahead_seconds: 1200,
    scheduler_algorithm: 'legacy-anki',
    algorithm_version: '1.0.0',
    queue_contract_version: 'flama-queue.v1',
    policies: {
      policy: {
        algorithm_key: 'legacy-anki',
        algorithm_version: '1.0.0',
        config_schema_version: 'scheduler-config.v1',
        config_hash: 'policy',
        timezone: 'UTC',
        preset_id: null,
        config: {
          learning_steps_ms: [60_000, 600_000],
          graduating_interval_days: 1,
          easy_interval_days: 5,
          relearning_steps_ms: [600_000],
          minimum_interval_days: 1,
          starting_ease: 2.5,
          easy_bonus: 1.3,
          interval_modifier: 1,
          hard_factor: 1.2,
          new_interval_factor: 0,
          min_ease: 1.3,
          max_interval_days: 36_500,
          day_boundary_hour_local: 4,
          learn_ahead_seconds: 1200,
          leech_threshold: 8,
          leech_suspend: true,
          scheduler_mode: 'legacy',
          review_fuzz_factor: null,
          fsrs_next_states: null,
        },
      },
    },
    cards: [
      {
        card_id: 'card-1',
        note_id: 'note-1',
        template_id: 'template-1',
        source_deck_id: 1,
        local_deck_id: 1,
        composition_id: 'standard',
        note_type_id: 'type-1',
        created_at: '2026-09-01T00:00:00.000Z',
        policy_key: 'policy',
        template_key: 'template',
        content_key: 'content-1',
        base_revision: 0,
        base_state_hash: 'base',
        can_edit_card: true,
        state: {
          type: 'new',
          step_index: 0,
          due_at: '2026-09-08T00:00:00.000Z',
          due_day: null,
          interval_days: 0,
          ease: 2.5,
          reps: 0,
          lapses: 0,
          last_review_at: null,
          review_kind: 'review',
          scheduler_mode: 'legacy',
          suspended: false,
          suspension_reason: null,
          leeched: false,
          memory_state: null,
        },
      },
      {
        card_id: 'card-2',
        note_id: 'note-1',
        template_id: 'template-2',
        source_deck_id: 1,
        local_deck_id: 1,
        composition_id: 'reverse',
        note_type_id: 'type-1',
        created_at: '2026-09-01T00:00:00.000Z',
        policy_key: 'policy',
        template_key: 'template',
        content_key: 'content-1',
        base_revision: 0,
        base_state_hash: 'base',
        can_edit_card: true,
        state: {
          type: 'new',
          step_index: 0,
          due_at: '2026-09-08T00:00:00.000Z',
          due_day: null,
          interval_days: 0,
          ease: 2.5,
          reps: 0,
          lapses: 0,
          last_review_at: null,
          review_kind: 'review',
          scheduler_mode: 'legacy',
          suspended: false,
          suspension_reason: null,
          leeched: false,
          memory_state: null,
        },
      },
      {
        card_id: 'card-3',
        note_id: 'note-2',
        template_id: 'template-1',
        source_deck_id: 1,
        local_deck_id: 1,
        composition_id: 'standard',
        note_type_id: 'type-1',
        created_at: '2026-09-01T00:00:00.000Z',
        policy_key: 'policy',
        template_key: 'template',
        content_key: 'content-2',
        base_revision: 0,
        base_state_hash: 'base',
        can_edit_card: true,
        state: {
          type: 'new',
          step_index: 0,
          due_at: '2026-09-08T00:00:00.000Z',
          due_day: null,
          interval_days: 0,
          ease: 2.5,
          reps: 0,
          lapses: 0,
          last_review_at: null,
          review_kind: 'review',
          scheduler_mode: 'legacy',
          suspended: false,
          suspension_reason: null,
          leeched: false,
          memory_state: null,
        },
      },
    ],
    templates: {
      template: {
        schema_version: 'study-template.v1',
        renderer_abi: 'flama-client-mustache.v1',
        id: 'template-1',
        version: 'v1',
        front_source: '{{Word}}',
        back_source: '{{Meaning}}',
        front_inline_scripts: [],
        back_inline_scripts: [],
        shared_css: '',
        field_defs: [
          { name: 'Word', field_type: 'text' },
          { name: 'Meaning', field_type: 'text' },
          { name: 'Audio', field_type: 'audio' },
        ],
      },
    },
    contents: {
      'content-1': {
        schema_version: 'study-content.v1',
        renderer_abi: 'flama-client-mustache.v1',
        id: 'note-1',
        note_id: 'note-1',
        version: 'v1',
        field_values: { Word: 'cat', Meaning: 'mèo' },
        render_context: { Word: 'cat', Meaning: 'mèo' },
        media: [],
      },
      'content-2': {
        schema_version: 'study-content.v1',
        renderer_abi: 'flama-client-mustache.v1',
        id: 'note-2',
        note_id: 'note-2',
        version: 'v1',
        field_values: { Word: 'dog', Meaning: 'chó' },
        render_context: { Word: 'dog', Meaning: 'chó' },
        media: [],
      },
    },
    compositions: {},
  }
}

function createSampleSession(): PersistedStudySession {
  return createPersistedSession(createSampleSnapshot())
}

describe('applyCardContentPatch', () => {
  it('returns updated: false when cardId does not match any card', () => {
    const session = createSampleSession()
    const result = applyCardContentPatch(session, 'non-existent-card', { Word: 'lion' })

    expect(result.updated).toBe(false)
    expect(result.affectedCardIds).toHaveLength(0)
    expect(result.nextSession).toBe(session)
  })

  it('updates field values and recomputes content_key for matching cardId', () => {
    const session = createSampleSession()
    const result = applyCardContentPatch(session, 'card-3', { Word: 'wolf' })

    expect(result.updated).toBe(true)
    expect(result.affectedCardIds).toEqual(['card-3'])

    // card-3 should have a new content_key
    const updatedCard = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-3')
    expect(updatedCard?.content_key).not.toBe('content-2')

    // new content entry should exist with merged field values
    const newContentKey = updatedCard!.content_key
    const newContent = result.nextSession.snapshot.contents[newContentKey]
    expect(newContent).toBeDefined()
    expect(newContent.field_values).toEqual({ Word: 'wolf', Meaning: 'chó' })
    expect(newContent.render_context.Word).toBe('wolf')

    // card-1 and card-2 should remain unaffected
    const card1 = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-1')
    expect(card1?.content_key).toBe('content-1')
  })

  it('updates all cards matching noteId when noteId option is provided', () => {
    const session = createSampleSession()
    const result = applyCardContentPatch(
      session,
      'card-1',
      { Word: 'kitten', Meaning: 'mèo con' },
      { noteId: 'note-1' },
    )

    expect(result.updated).toBe(true)
    expect(result.affectedCardIds).toEqual(['card-1', 'card-2'])

    const card1 = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-1')
    const card2 = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-2')

    expect(card1?.content_key).toBe(card2?.content_key)
    const newContent = result.nextSession.snapshot.contents[card1!.content_key]
    expect(newContent.field_values.Word).toBe('kitten')
    expect(newContent.field_values.Meaning).toBe('mèo con')
  })

  it('auto-synthesizes proxy URLs from string field values and marks audio correctly', () => {
    const session = createSampleSession()
    const audioProxyUrl = '/media/proxy/asset999audiokey'
    const result = applyCardContentPatch(session, 'card-3', {
      Audio: audioProxyUrl,
    })

    expect(result.updated).toBe(true)
    const updatedCard = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-3')
    const content = result.nextSession.snapshot.contents[updatedCard!.content_key]

    expect(content.media).toHaveLength(1)
    expect(content.media[0]).toMatchObject({
      id: 'asset999audiokey',
      field_name: 'Audio',
      mime_type: 'audio/mpeg',
      proxy_url: audioProxyUrl,
    })
  })

  it('preserves custom media assets when provided via options.media', () => {
    const session = createSampleSession()
    const customMedia = [
      {
        id: 'custom-1',
        field_name: 'Image',
        filename: 'pic.png',
        mime_type: 'image/png',
        sha256: 'sha-img',
        proxy_url: '/media/proxy/custom-1',
      },
    ]

    const result = applyCardContentPatch(
      session,
      'card-1',
      { Word: 'tiger' },
      { media: customMedia },
    )

    expect(result.updated).toBe(true)
    const card1 = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-1')
    const content = result.nextSession.snapshot.contents[card1!.content_key]
    expect(content.media).toEqual(customMedia)
  })

  it('does not mutate the original session object (pure function)', () => {
    const session = createSampleSession()
    const originalContentKey = session.snapshot.cards[0].content_key
    const originalFieldValues = { ...session.snapshot.contents[originalContentKey].field_values }

    applyCardContentPatch(session, 'card-1', { Word: 'mutated?' })

    expect(session.snapshot.cards[0].content_key).toBe(originalContentKey)
    expect(session.snapshot.contents[originalContentKey].field_values).toEqual(originalFieldValues)
  })

  it('patches bound aliases with the frozen mapping and keeps unbound inputs empty', () => {
    const session = createSampleSession()
    const template = session.snapshot.templates.template
    template.field_defs.push({ id: 'alias-term', name: 'term', field_type: 'text' },
      { id: 'alias-answer', name: 'answer', field_type: 'text' })
    const projection = {
      schema_version: 'template-input-bindings.v1' as const,
      input_bindings: { term: 'field-word', answer: null },
      field_defs: [{ id: 'field-word', name: 'Word', field_type: 'text' }],
    }
    template.binding_projection = { ...projection, fingerprint: canonicalDigest(projection) }
    session.snapshot.contents['content-2'].field_values.term = 'dog'
    session.snapshot.contents['content-2'].field_values.answer = ''
    session.snapshot.contents['content-2'].render_context.term = 'dog'
    const originalTemplate = structuredClone(template)
    const result = applyCardContentPatch(session, 'card-3', { Word: 'wolf', term: 'leak', answer: 'leak' })
    const card = result.nextSession.snapshot.cards.find((item) => item.card_id === 'card-3')!
    const content = result.nextSession.snapshot.contents[card.content_key]
    expect(content.field_values).toMatchObject({ Word: 'wolf', term: 'wolf', answer: '' })
    expect(content.render_context).toMatchObject({ term: 'wolf', answer: '' })
    expect(result.nextSession.snapshot.templates.template).toEqual(originalTemplate)
    expect(result.nextSession.snapshot.cards[2].state).toEqual(session.snapshot.cards[2].state)
    expect(session.snapshot.contents['content-2'].field_values.term).toBe('dog')
  })

  it('uses original source values when inputs bind to each other and preserves partial updates', () => {
    const session = createSampleSession()
    const template = session.snapshot.templates.template
    const projection = {
      schema_version: 'template-input-bindings.v1' as const,
      input_bindings: { Word: 'field-meaning', Meaning: 'field-word' },
      field_defs: [{ id: 'field-word', name: 'Word', field_type: 'text' },
        { id: 'field-meaning', name: 'Meaning', field_type: 'text' }],
    }
    template.binding_projection = { ...projection, fingerprint: canonicalDigest(projection) }
    const original = session.snapshot.contents['content-2']
    original.field_values = { Word: 'meaning', Meaning: 'dog' }
    original.render_context = { ...original.field_values }
    const result = applyCardContentPatch(session, 'card-3', { Word: 'wolf' })
    const content = result.nextSession.snapshot.contents[result.nextSession.snapshot.cards[2].content_key]
    expect(content.field_values).toEqual({ Word: 'meaning', Meaning: 'wolf' })
    expect(content.render_context).toEqual({ Word: 'meaning', Meaning: 'wolf' })
  })

  it('updates bound media helpers and prevents unbound helper fallback from note fields', () => {
    const session = createSampleSession()
    const template = session.snapshot.templates.template
    template.field_defs.push({ id: 'alias-voice', name: 'voice', field_type: 'audio' },
      { id: 'alias-empty', name: 'empty_voice', field_type: 'audio' })
    const projection = {
      schema_version: 'template-input-bindings.v1' as const,
      input_bindings: { voice: 'field-audio', empty_voice: null },
      field_defs: [{ id: 'field-audio', name: 'Audio', field_type: 'audio' }],
    }
    template.binding_projection = { ...projection, fingerprint: canonicalDigest(projection) }
    const result = applyCardContentPatch(session, 'card-3', {
      Audio: '/media/proxy/new-audio', empty_voice: '/media/proxy/secret', empty_voice_url: '/media/proxy/secret',
    })
    const content = result.nextSession.snapshot.contents[result.nextSession.snapshot.cards[2].content_key]
    expect(content.render_context.voice_url).toBe('/media/proxy/new-audio')
    expect(content.render_context.voice).toContain('src="/media/proxy/new-audio"')
    expect(content.render_context.empty_voice).toBe('')
    expect(content.render_context.empty_voice_url).toBe('')
    expect(content.render_context.empty_voice_urls).toEqual([])
  })
})
