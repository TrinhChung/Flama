// @vitest-environment jsdom

import { describe, expect, it, vi } from 'vitest'
import { applyCardContentPatch } from './contentPatchAdapter'
import { createPersistedSession } from './studySessionEngine'
import type { StudySessionSnapshot } from '../types'
import {
  dispatchStudyCardUpdate,
  STUDY_CARD_UPDATED_EVENT,
  STUDY_SYNC_CHANNEL_NAME,
} from '@/entities/flashcard/model/studySyncEvents'
import { adaptStudySessionToRenderPayload } from '../renderer/studyRendererAdapter'

function createTestSnapshot(): StudySessionSnapshot {
  return {
    schema_version: 'study-session.v2',
    session_id: 'sess-adv-001',
    user_id: 42,
    session_token: 'tok-adv',
    snapshot_hash: 'hash-adv',
    scope: { type: 'deck', id: '10', name: 'Adversarial Test Deck' },
    server_now_utc: '2026-10-04T12:00:00.000Z',
    expires_at: '2026-10-05T12:00:00.000Z',
    timezone: 'Asia/Tokyo',
    day_boundary_hour_local: 4,
    learn_ahead_seconds: 1200,
    scheduler_algorithm: 'legacy-anki',
    algorithm_version: '1.0.0',
    queue_contract_version: 'flama-queue.v1',
    policies: {
      'pol-1': {
        algorithm_key: 'legacy-anki',
        algorithm_version: '1.0.0',
        config_schema_version: 'scheduler-config.v1',
        config_hash: 'pol-1',
        timezone: 'Asia/Tokyo',
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
        card_id: 'card-alpha',
        note_id: 'note-100',
        template_id: 'tpl-1',
        source_deck_id: 10,
        local_deck_id: 10,
        composition_id: 'standard',
        note_type_id: 'nt-1',
        created_at: '2026-10-01T00:00:00.000Z',
        policy_key: 'pol-1',
        template_key: 'tpl-key-1',
        content_key: 'content-initial-100',
        base_revision: 1,
        base_state_hash: 'state-hash-1',
        can_edit_card: true,
        state: {
          type: 'new',
          step_index: 0,
          due_at: '2026-10-04T12:00:00.000Z',
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
        card_id: 'card-beta',
        note_id: 'note-100',
        template_id: 'tpl-2',
        source_deck_id: 10,
        local_deck_id: 10,
        composition_id: 'reverse',
        note_type_id: 'nt-1',
        created_at: '2026-10-01T00:00:00.000Z',
        policy_key: 'pol-1',
        template_key: 'tpl-key-1',
        content_key: 'content-initial-100',
        base_revision: 1,
        base_state_hash: 'state-hash-2',
        can_edit_card: true,
        state: {
          type: 'new',
          step_index: 0,
          due_at: '2026-10-04T12:00:00.000Z',
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
        card_id: 'card-broken-content',
        note_id: 'note-999',
        template_id: 'tpl-1',
        source_deck_id: 10,
        local_deck_id: 10,
        composition_id: 'standard',
        note_type_id: 'nt-1',
        created_at: '2026-10-01T00:00:00.000Z',
        policy_key: 'pol-1',
        template_key: 'tpl-key-1',
        content_key: 'non-existent-content-key',
        base_revision: 1,
        base_state_hash: 'state-hash-3',
        can_edit_card: true,
        state: {
          type: 'new',
          step_index: 0,
          due_at: '2026-10-04T12:00:00.000Z',
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
        card_id: 'card-missing-template',
        note_id: 'note-101',
        template_id: 'tpl-missing',
        source_deck_id: 10,
        local_deck_id: 10,
        composition_id: 'standard',
        note_type_id: 'nt-1',
        created_at: '2026-10-01T00:00:00.000Z',
        policy_key: 'pol-1',
        template_key: 'non-existent-template-key',
        content_key: 'content-101',
        base_revision: 1,
        base_state_hash: 'state-hash-4',
        can_edit_card: true,
        state: {
          type: 'new',
          step_index: 0,
          due_at: '2026-10-04T12:00:00.000Z',
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
      'tpl-key-1': {
        schema_version: 'study-template.v1',
        renderer_abi: 'flama-client-mustache.v1',
        id: 'tpl-1',
        version: 'ver-tpl-1',
        front_source: '<div>{{Front}}</div>',
        back_source: '<div>{{Back}}</div>',
        front_inline_scripts: [],
        back_inline_scripts: [],
        shared_css: '',
        field_defs: [
          { name: 'Front', field_type: 'text' },
          { name: 'Back', field_type: 'text' },
          { name: 'Audio', field_type: 'audio' },
          { name: 'Image', field_type: 'image' },
        ],
      },
    },
    contents: {
      'content-initial-100': {
        schema_version: 'study-content.v1',
        renderer_abi: 'flama-client-mustache.v1',
        id: 'note-100',
        note_id: 'note-100',
        version: 'ver-init',
        field_values: {
          Front: 'Inu',
          Back: 'Dog',
          Reading: 'いぬ',
        },
        render_context: {
          Front: 'Inu',
          Back: 'Dog',
          Reading: 'いぬ',
        },
        media: [],
      },
      'content-101': {
        schema_version: 'study-content.v1',
        renderer_abi: 'flama-client-mustache.v1',
        id: 'note-101',
        note_id: 'note-101',
        version: 'ver-init-101',
        field_values: {
          Front: 'Neko',
          Back: 'Cat',
        },
        render_context: {
          Front: 'Neko',
          Back: 'Cat',
        },
        media: [],
      },
    },
    compositions: {},
  }
}

describe('Adversarial: applyCardContentPatch', () => {
  it('Challenge 1: Non-existent cardId returns exact same reference with updated: false', () => {
    const session = createPersistedSession(createTestSnapshot())
    const result = applyCardContentPatch(session, 'ghost-card-404', { Front: 'Ghost' })

    expect(result.updated).toBe(false)
    expect(result.affectedCardIds).toHaveLength(0)
    expect(result.nextSession).toBe(session) // Reference equality
  })

  it('Challenge 2: Handles broken content reference gracefully without throwing', () => {
    const session = createPersistedSession(createTestSnapshot())
    const result = applyCardContentPatch(session, 'card-broken-content', { Front: 'Broken' })

    // card-broken-content has a content_key not in contents; should gracefully skip
    expect(result.updated).toBe(false)
    expect(result.affectedCardIds).toHaveLength(0)
    expect(result.nextSession).toBe(session)
  })

  it('Challenge 3: Handles missing template reference gracefully without throwing', () => {
    const session = createPersistedSession(createTestSnapshot())
    // card-missing-template has template_key not in templates
    const result = applyCardContentPatch(session, 'card-missing-template', { Front: 'Kitten' })

    expect(result.updated).toBe(true)
    expect(result.affectedCardIds).toEqual(['card-missing-template'])
    const card = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-missing-template')
    const updatedContent = result.nextSession.snapshot.contents[card!.content_key]
    expect(updatedContent.field_values.Front).toBe('Kitten')
    expect(updatedContent.render_context.Front).toBe('Kitten')
  })

  it('Challenge 4: Partial fields update preserves untouched fields', () => {
    const session = createPersistedSession(createTestSnapshot())
    const result = applyCardContentPatch(session, 'card-alpha', { Front: 'Chó' })

    expect(result.updated).toBe(true)
    const card = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-alpha')
    const content = result.nextSession.snapshot.contents[card!.content_key]

    expect(content.field_values.Front).toBe('Chó')
    expect(content.field_values.Back).toBe('Dog') // Preserved!
    expect(content.field_values.Reading).toBe('いぬ') // Preserved!
  })

  it('Challenge 5: Shared noteId updates both cards and synchronizes their content_key', () => {
    const session = createPersistedSession(createTestSnapshot())
    const result = applyCardContentPatch(
      session,
      'card-alpha',
      { Front: 'Canine', Back: 'Chó' },
      { noteId: 'note-100' },
    )

    expect(result.updated).toBe(true)
    expect(result.affectedCardIds).toEqual(['card-alpha', 'card-beta'])

    const alpha = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-alpha')
    const beta = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-beta')

    expect(alpha!.content_key).toBe(beta!.content_key)
    const content = result.nextSession.snapshot.contents[alpha!.content_key]
    expect(content.field_values.Front).toBe('Canine')
    expect(content.field_values.Back).toBe('Chó')
  })

  it('Challenge 6: Synthesizes multiple media URLs and correctly infers MIME types', () => {
    const session = createPersistedSession(createTestSnapshot())
    const multiMediaPayload = {
      Front: 'Look at <img src="/media/proxy/img_asset_001" /> and listen <audio src="/media/proxy/audio_asset_002" />',
      VoiceAudio: '/media/proxy/audio_asset_003',
      CustomImage: '/media/proxy/img_asset_004',
    }

    const result = applyCardContentPatch(session, 'card-alpha', multiMediaPayload)
    expect(result.updated).toBe(true)

    const card = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-alpha')
    const content = result.nextSession.snapshot.contents[card!.content_key]

    expect(content.media.length).toBe(4)

    const audio3 = content.media.find((m) => m.id === 'audio_asset_003')
    expect(audio3?.mime_type).toBe('audio/mpeg')
    expect(audio3?.field_name).toBe('VoiceAudio')

    const img4 = content.media.find((m) => m.id === 'img_asset_004')
    expect(img4?.mime_type).toBe('image/jpeg')
    expect(img4?.field_name).toBe('CustomImage')
  })

  it('Challenge 7: De-duplicates identical proxy URLs across fields', () => {
    const session = createPersistedSession(createTestSnapshot())
    const duplicateProxy = {
      Front: 'Link 1: /media/proxy/asset_shared_dup',
      Back: 'Link 2: /media/proxy/asset_shared_dup',
    }

    const result = applyCardContentPatch(session, 'card-alpha', duplicateProxy)
    const card = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-alpha')
    const content = result.nextSession.snapshot.contents[card!.content_key]

    const dupAssets = content.media.filter((m) => m.id === 'asset_shared_dup')
    expect(dupAssets.length).toBe(1) // No duplicates
  })

  it('Challenge 8: Deterministic digest recalculation and pure immutability', () => {
    const session = createPersistedSession(createTestSnapshot())
    const initialClone = JSON.parse(JSON.stringify(session))

    const res1 = applyCardContentPatch(session, 'card-alpha', { Front: 'Test1' })
    const res2 = applyCardContentPatch(session, 'card-alpha', { Front: 'Test1' })

    const card1 = res1.nextSession.snapshot.cards.find((c) => c.card_id === 'card-alpha')
    const card2 = res2.nextSession.snapshot.cards.find((c) => c.card_id === 'card-alpha')

    // Deterministic hash
    expect(card1!.content_key).toBe(card2!.content_key)

    // Verify session object was never mutated
    expect(session.snapshot.cards[0].content_key).toBe(initialClone.snapshot.cards[0].content_key)
    expect(session.snapshot.contents['content-initial-100'].field_values).toEqual(
      initialClone.snapshot.contents['content-initial-100'].field_values,
    )
  })

  it('Challenge 9: XSS / Malicious HTML in field values safely handled', () => {
    const session = createPersistedSession(createTestSnapshot())
    const xssPayload = {
      Front: '<script>alert("xss")</script><img src=x onerror=alert(1)>',
    }

    const result = applyCardContentPatch(session, 'card-alpha', xssPayload)
    expect(result.updated).toBe(true)

    const card = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-alpha')
    const content = result.nextSession.snapshot.contents[card!.content_key]
    expect(content.field_values.Front).toBe(xssPayload.Front)
  })
})

describe('Adversarial: dispatchStudyCardUpdate & Event Synchronization', () => {
  it('Challenge 10: Dispatches window CustomEvent and notifies in-window listener', () => {
    const windowListener = vi.fn()
    window.addEventListener(STUDY_CARD_UPDATED_EVENT, windowListener)

    const testPayload = {
      cardId: 'card-sync-test',
      noteId: 'note-sync-1',
      fieldValues: { Word: 'TestSync' },
    }

    dispatchStudyCardUpdate(testPayload)

    expect(windowListener).toHaveBeenCalledTimes(1)
    const event = windowListener.mock.calls[0][0] as CustomEvent
    expect(event.detail).toEqual(testPayload)

    window.removeEventListener(STUDY_CARD_UPDATED_EVENT, windowListener)
  })

  it('Challenge 11: sends the exact CARD_UPDATED payload and closes its channel', () => {
    const postMessage = vi.fn()
    const close = vi.fn()
    const channel = vi.fn(function () { return { postMessage, close } })
    vi.stubGlobal('BroadcastChannel', channel)
    try {
      dispatchStudyCardUpdate({
        cardId: 'card-bc-1',
        noteId: 'note-bc-1',
        fieldValues: { Meaning: 'BroadcastTest' },
      })
      expect(channel).toHaveBeenCalledWith(STUDY_SYNC_CHANNEL_NAME)
      expect(postMessage).toHaveBeenCalledExactlyOnceWith({
        type: 'CARD_UPDATED',
        cardId: 'card-bc-1',
        noteId: 'note-bc-1',
        fieldValues: { Meaning: 'BroadcastTest' },
        media: undefined,
      })
      expect(close).toHaveBeenCalledOnce()
    } finally {
      vi.unstubAllGlobals()
    }
  })
})

describe('Adversarial: studyRendererAdapter', () => {
  it('Challenge 12: Throws explicitly when renderer_abi mismatches', () => {
    const template = {
      schema_version: 'study-template.v1' as const,
      renderer_abi: 'flama-client-mustache.v1' as const,
      id: 'tpl-1',
      version: 'v1',
      front_source: '{{A}}',
      back_source: '{{B}}',
      front_inline_scripts: [],
      back_inline_scripts: [],
      shared_css: '',
      field_defs: [],
    }
    const corruptContent = {
      schema_version: 'study-content.v1' as const,
      renderer_abi: 'corrupted-abi.v99' as any,
      id: 'c-1',
      note_id: 'n-1',
      version: 'v1',
      field_values: {},
      render_context: {},
      media: [],
    }

    expect(() => {
      adaptStudySessionToRenderPayload(template, corruptContent, 'front')
    }).toThrow('Study renderer ABI mismatch.')
  })

  it('Challenge 13: Correctly computes live patch and inline scripts flags', () => {
    const templateWithScript = {
      schema_version: 'study-template.v1' as const,
      renderer_abi: 'flama-client-mustache.v1' as const,
      id: 'tpl-script',
      version: 'v1',
      front_source: '{{A}}',
      back_source: '{{B}}',
      front_inline_scripts: ['<script>window.customHook = 1</script>'],
      back_inline_scripts: [],
      shared_css: '',
      field_defs: [{ name: 'A', field_type: 'text' }],
    }
    const content = {
      schema_version: 'study-content.v1' as const,
      renderer_abi: 'flama-client-mustache.v1' as const,
      id: 'c-1',
      note_id: 'n-1',
      version: 'v1',
      field_values: { A: 'Hello' },
      render_context: { A: 'Hello' },
      media: [],
    }

    const payload = adaptStudySessionToRenderPayload(templateWithScript, content, 'front')
    expect(payload.has_inline_script).toBe(true)
    expect(payload.supports_live_patch).toBe(false)
    expect(payload.html).toContain('Hello')
    expect(payload.html).toContain('<script>window.customHook = 1</script>')
  })
})

describe('Adversarial: Deep Edge Cases & FSD Boundary Verification', () => {
  it('Challenge 14: Empty newFieldValues produces valid session preserving all fields', () => {
    const session = createPersistedSession(createTestSnapshot())
    const result = applyCardContentPatch(session, 'card-alpha', {})

    expect(result.updated).toBe(true)
    const card = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-alpha')
    const content = result.nextSession.snapshot.contents[card!.content_key]
    expect(content.field_values.Front).toBe('Inu')
    expect(content.field_values.Back).toBe('Dog')
  })

  it('Challenge 15: Nested dot keys in field values are parsed safely into render_context', () => {
    const session = createPersistedSession(createTestSnapshot())
    const result = applyCardContentPatch(session, 'card-alpha', {
      'meta.difficulty': 'JLPT N3',
      'meta.notes': 'Common noun',
    })

    expect(result.updated).toBe(true)
    const card = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-alpha')
    const content = result.nextSession.snapshot.contents[card!.content_key]
    expect(content.field_values['meta.difficulty']).toBe('JLPT N3')
    expect((content.render_context as any).meta?.difficulty).toBe('JLPT N3')
    expect((content.render_context as any).meta?.notes).toBe('Common noun')
  })

  it('Challenge 16: Custom media in options.media overrides content media cleanly', () => {
    const session = createPersistedSession(createTestSnapshot())
    const customMedia = [
      {
        id: 'cust-voice-01',
        field_name: 'Pronunciation',
        filename: 'pronounce.mp3',
        mime_type: 'audio/mpeg',
        sha256: 'sha-p',
        proxy_url: '/media/proxy/cust-voice-01',
      },
    ]

    const result = applyCardContentPatch(
      session,
      'card-alpha',
      { Front: 'Test Custom Media' },
      { media: customMedia },
    )

    expect(result.updated).toBe(true)
    const card = result.nextSession.snapshot.cards.find((c) => c.card_id === 'card-alpha')
    const content = result.nextSession.snapshot.contents[card!.content_key]
    expect(content.media).toEqual(customMedia)
  })

  it('Challenge 17: only Study and app composition import study modules', async () => {
    const fs = await import('node:fs')
    const path = await import('node:path')
    const ts = await import('typescript')
    const srcDir = path.resolve(__dirname, '../../..')
    const violations: string[] = []

    function walkDir(dir: string) {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const fullPath = path.join(dir, entry.name)
        if (entry.isDirectory()) {
          walkDir(fullPath)
          continue
        }
        if (!/\.tsx?$/.test(entry.name) || /\.test\.tsx?$/.test(entry.name)) continue
        const relativePath = path.relative(srcDir, fullPath).replace(/\\/g, '/')
        if (relativePath.startsWith('features/study/') || relativePath.startsWith('app/') ||
            relativePath === 'App.tsx' || relativePath === 'main.tsx') continue

        const source = ts.createSourceFile(fullPath, fs.readFileSync(fullPath, 'utf8'), ts.ScriptTarget.Latest, true)
        const checkImport = (specifier: import('typescript').Expression | undefined) => {
          if (!specifier || !ts.isStringLiteral(specifier)) return
          const imported = specifier.text
          const resolved = imported.startsWith('@/') ? imported.slice(2)
            : imported.startsWith('.') ? path.relative(srcDir, path.resolve(path.dirname(fullPath), imported)).replace(/\\/g, '/')
            : imported
          if (resolved.startsWith('features/study/')) violations.push(`${relativePath}: ${imported}`)
        }
        const visit = (node: import('typescript').Node) => {
          if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) checkImport(node.moduleSpecifier)
          if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) checkImport(node.arguments[0])
          ts.forEachChild(node, visit)
        }
        visit(source)
      }
    }
    walkDir(srcDir)
    expect(violations).toEqual([])
  }, 20000)
})
