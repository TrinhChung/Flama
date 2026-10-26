// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { DeckStructuralDependenciesCard } from '../components/DeckStructuralDependenciesCard'
import type { NoteTypeDependency } from '../model/types'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('DeckStructuralDependenciesCard — Adversarial Stress Suite', () => {
  let root: Root
  let container: HTMLDivElement

  beforeEach(() => {
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    document.body.innerHTML = ''
  })

  it('ADVERSARIAL: Malicious HTML and Script injection inputs are strictly sanitized and never evaluated', async () => {
    const maliciousNoteTypes: NoteTypeDependency[] = [
      {
        note_type_id: 'nt_evil_<script>',
        note_type_name: '<script>alert("xss")</script><img src=x onerror=alert(1)>',
        note_count: 50,
        pinned_version_label: '<b onmouseover="steal()">v1.0</b>',
        latest_version_label: '<svg onload=malicious()>',
        status: 'update_available',
        has_draft_changes: false,
        templates: [
          {
            template_id: 'tmpl_iframe',
            template_name: '<iframe src="javascript:alert(1)"></iframe>',
            occurrence_key: '"><script>evil()</script>',
            pinned_version_label: 'v1.0',
            latest_version_label: 'v2.0',
            status: 'update_available',
            has_newer_release: true,
            has_uncommitted_draft: false,
          },
        ],
      },
    ]

    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle='<script>console.error("deck_xss")</script>'
          currentVersionLabel='<marquee>v0.9</marquee>'
          noteTypes={maliciousNoteTypes}
        />
      )
    })

    // DOM tree MUST NOT contain executable script, img, iframe, or marquee tags
    expect(container.querySelectorAll('script').length).toBe(0)
    expect(container.querySelectorAll('img').length).toBe(0)
    expect(container.querySelectorAll('iframe').length).toBe(0)
    expect(container.querySelectorAll('marquee').length).toBe(0)
    expect(container.querySelectorAll('svg[onload]').length).toBe(0)

    // Text content MUST safely contain the string literals without tag execution
    expect(container.textContent).toContain('<script>alert("xss")</script>')
    expect(container.textContent).toContain('<iframe src="javascript:alert(1)"></iframe>')
    expect(container.textContent).toContain('"><script>evil()</script>')
  })

  it('ADVERSARIAL: Raw Mustache tags and code snippets are never rendered as active code or in pre/code blocks', async () => {
    const mustachePayloads: NoteTypeDependency[] = [
      {
        note_type_id: 'nt_mustache',
        note_type_name: '{{#Cards}}{{Front}} -> {{Back}}{{/Cards}}',
        note_count: 100,
        pinned_version_label: '{{version}}',
        latest_version_label: '{{{raw_version}}}',
        status: 'synced',
        has_draft_changes: false,
        templates: [
          {
            template_id: 'tmpl_mustache_expr',
            template_name: '{{^Condition}}Fallback{{/Condition}}',
            occurrence_key: '{{key}}',
            pinned_version_label: 'v1',
            latest_version_label: 'v1',
            status: 'synced',
            has_newer_release: false,
            has_uncommitted_draft: false,
          },
        ],
      },
    ]

    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="{{DeckExpression}}"
          noteTypes={mustachePayloads}
        />
      )
    })

    // Strictly no <pre> or <code> elements for code diffs
    expect(container.querySelectorAll('pre').length).toBe(0)
    expect(container.querySelectorAll('code').length).toBe(0)

    // Rendered as plain text safely
    expect(container.textContent).toContain('{{#Cards}}{{Front}} -> {{Back}}{{/Cards}}')
    expect(container.textContent).toContain('{{^Condition}}Fallback{{/Condition}}')
  })

  it('ADVERSARIAL: JSON diff ASTs and patch fragments are treated strictly as text without diff tables', async () => {
    const jsonDiffPayloads: NoteTypeDependency[] = [
      {
        note_type_id: 'nt_json_diff',
        note_type_name: '{"diff_match_patch": [{"op": "replace", "path": "/schema", "value": "text"}]}',
        note_count: 42,
        pinned_version_label: 'v1.0',
        latest_version_label: 'v2.0',
        status: 'update_available',
        has_draft_changes: true,
        templates: [
          {
            template_id: 'tmpl_patch',
            template_name: '@@ -1,5 +1,6 @@ -div.card +div.card-active',
            occurrence_key: 'patch_1',
            pinned_version_label: 'v1.0',
            latest_version_label: 'v1.0',
            status: 'synced',
            has_newer_release: false,
            has_uncommitted_draft: false,
          },
        ],
      },
    ]

    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle='{"deck_patch": true}'
          noteTypes={jsonDiffPayloads}
        />
      )
    })

    // Verify absence of code diff structures
    expect(container.querySelectorAll('table.diff').length).toBe(0)
    expect(container.querySelectorAll('.diff-line').length).toBe(0)
    expect(container.querySelectorAll('pre').length).toBe(0)
    expect(container.querySelectorAll('code').length).toBe(0)
  })

  it('ADVERSARIAL: Extreme boundary values for note counts and nullish labels', async () => {
    const boundaryNoteTypes: NoteTypeDependency[] = [
      {
        note_type_id: 'nt_zero',
        note_type_name: 'Empty Note Type',
        note_count: 0,
        pinned_version_label: null,
        latest_version_label: null,
        status: 'synced',
        has_draft_changes: false,
        templates: [], // No templates attached
      },
      {
        note_type_id: 'nt_huge',
        note_type_name: 'Massive Note Type',
        note_count: 99_999_999,
        pinned_version_label: undefined,
        latest_version_label: 'v99.0.0',
        status: 'update_available',
        has_draft_changes: false,
        templates: [
          {
            template_id: 'tmpl_null_pin',
            template_name: 'Orphan Template',
            occurrence_key: undefined,
            pinned_version_label: null,
            latest_version_label: undefined,
            status: 'synced',
            has_newer_release: false,
            has_uncommitted_draft: false,
          },
        ],
      },
    ]

    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="Boundary Deck"
          currentVersionLabel={null}
          noteTypes={boundaryNoteTypes}
        />
      )
    })

    // Handles 0 count and massive count
    expect(container.textContent).toContain('(0 thẻ)')
    expect(container.textContent).toContain('(99999999 thẻ)')

    // Handles nullish pin labels by showing default "Chưa ghim"
    expect(container.textContent).toContain('pin: Chưa ghim')

    // Note type with 0 templates should not crash or render empty template headers
    expect(container.querySelector('[data-testid="note-type-item-nt_zero"]')).not.toBeNull()
    expect(container.querySelector('[data-testid="note-type-item-nt_zero"]')?.textContent).not.toContain('Mẫu thẻ gắn kèm:')
  })

  it('ADVERSARIAL: High volume stress test (50 note types with 5 templates each = 250 items)', async () => {
    const largeNoteTypes: NoteTypeDependency[] = Array.from({ length: 50 }, (_, i) => ({
      note_type_id: `nt_stress_${i}`,
      note_type_name: `Stress Note Type ${i}`,
      note_count: i * 100,
      pinned_version_label: `v1.${i}.0`,
      latest_version_label: i % 2 === 0 ? `v1.${i + 1}.0` : `v1.${i}.0`,
      status: i % 2 === 0 ? 'update_available' : 'synced',
      has_draft_changes: false,
      templates: Array.from({ length: 5 }, (_, j) => ({
        template_id: `tmpl_stress_${i}_${j}`,
        template_name: `Template ${i}-${j}`,
        occurrence_key: `key_${j}`,
        pinned_version_label: `v1.0`,
        latest_version_label: `v1.0`,
        status: 'synced',
        has_newer_release: false,
        has_uncommitted_draft: false,
      })),
    }))

    const start = performance.now()
    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="High Volume Deck"
          noteTypes={largeNoteTypes}
        />
      )
    })
    const duration = performance.now() - start

    // Must render swiftly under 5000ms (resilient against heavy parallel worker CPU load in JSDOM)
    expect(duration).toBeLessThan(5000)

    // All 50 note types rendered
    const ntElements = container.querySelectorAll('[data-testid^="note-type-item-"]')
    expect(ntElements.length).toBe(50)

    // All 250 templates rendered
    const tplElements = container.querySelectorAll('[data-testid^="template-item-"]')
    expect(tplElements.length).toBe(250)
  })

  it('ADVERSARIAL: Fallback anchor links when navigation callbacks are omitted', async () => {
    const singleNt: NoteTypeDependency[] = [
      {
        note_type_id: 'nt_fallback_123',
        note_type_name: 'Fallback Note Type',
        note_count: 10,
        pinned_version_label: 'v1.0',
        latest_version_label: 'v1.0',
        status: 'synced',
        has_draft_changes: false,
        templates: [
          {
            template_id: 'tmpl_fallback_456',
            template_name: 'Fallback Template',
            occurrence_key: 'main',
            pinned_version_label: 'v1.0',
            latest_version_label: 'v1.0',
            status: 'synced',
            has_newer_release: false,
            has_uncommitted_draft: false,
          },
        ],
      },
    ]

    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="Anchor Fallback Deck"
          noteTypes={singleNt}
          // callbacks intentionally omitted
        />
      )
    })

    const ntAnchor = container.querySelector<HTMLAnchorElement>(
      '[data-testid="navigate-note-type-nt_fallback_123"]'
    )
    expect(ntAnchor).not.toBeNull()
    expect(ntAnchor?.tagName).toBe('A')
    expect(ntAnchor?.getAttribute('href')).toBe('/note-types/nt_fallback_123')
    expect(ntAnchor?.getAttribute('target')).toBe('_blank')
    expect(ntAnchor?.getAttribute('rel')).toBe('noreferrer')

    const tplAnchor = container.querySelector<HTMLAnchorElement>(
      '[data-testid="navigate-template-tmpl_fallback_456"]'
    )
    expect(tplAnchor).not.toBeNull()
    expect(tplAnchor?.tagName).toBe('A')
    expect(tplAnchor?.getAttribute('href')).toBe('/card-templates/tmpl_fallback_456')
    expect(tplAnchor?.getAttribute('target')).toBe('_blank')
    expect(tplAnchor?.getAttribute('rel')).toBe('noreferrer')
  })
})
