// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { DeckStructuralDependenciesCard } from '../components/DeckStructuralDependenciesCard'
import type { NoteTypeDependency } from '../model/types'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const sampleNoteTypes: NoteTypeDependency[] = [
  {
    note_type_id: 'nt_long_name_1',
    note_type_name: 'Soumatome N3 Kanji & Vocabulary with Grammar Explanations and Sentence Mining Extra Long Name',
    note_count: 500,
    pinned_version_label: 'v1.0.0',
    latest_version_label: 'v1.2.0',
    status: 'update_available',
    has_draft_changes: false,
    templates: [
      {
        template_id: 'tpl_long_name_1',
        template_name: 'Comprehensive Audio-Visual Vocabulary Recognition Card Template with Furigana Extra',
        pinned_version_label: 'v1.0.0',
        latest_version_label: 'v1.3.0',
        status: 'update_available',
        has_newer_release: true,
        has_uncommitted_draft: false,
      },
    ],
  },
]

describe('DeckStructuralDependenciesCard — Responsive Multi-Device Tests (R4)', () => {
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
  })

  it('Mobile (375px): applies text truncation, break-words, titles, and touch targets >= 36-40px on buttons', async () => {
    window.innerWidth = 375
    window.innerHeight = 667
    window.dispatchEvent(new Event('resize'))

    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="Very Long Japanese JLPT N3 Vocabulary Mastery Course with Extended Explanations and Audio Practice"
          currentVersionLabel="v1.0.0"
          noteTypes={sampleNoteTypes}
        />
      )
    })

    // 1. Deck title has break-words and title attribute
    const deckTitleEl = container.querySelector('span.break-words')
    expect(deckTitleEl).not.toBeNull()
    expect(deckTitleEl?.getAttribute('title')).toContain('Very Long Japanese JLPT N3')

    // 2. Note type item spacing: p-3 sm:p-4
    const ntItem = container.querySelector('[data-testid="note-type-item-nt_long_name_1"]') as HTMLDivElement
    expect(ntItem).not.toBeNull()
    expect(ntItem.className).toContain('p-3')
    expect(ntItem.className).toContain('sm:p-4')

    // 3. Note type title has truncate and title attribute
    const ntTitleEl = ntItem.querySelector('span.truncate')
    expect(ntTitleEl).not.toBeNull()
    expect(ntTitleEl?.getAttribute('title')).toContain('Soumatome N3 Kanji')

    // 4. Note type action CTA button has touch target h-8 sm:h-7
    const ntBtn = container.querySelector('[data-testid="navigate-note-type-nt_long_name_1"]') as HTMLElement
    expect(ntBtn.className).toContain('h-8')
    expect(ntBtn.className).toContain('sm:h-7')

    // 5. Template list spacing pl-3, item padding py-1.5 px-3
    const tplSection = ntItem.querySelector('.border-l-2') as HTMLDivElement
    expect(tplSection.className).toContain('pl-3')

    const tplItem = container.querySelector('[data-testid="template-item-tpl_long_name_1"]') as HTMLDivElement
    expect(tplItem).not.toBeNull()
    expect(tplItem.className).toContain('px-3')

    // 6. Template title has truncate and title attribute
    const tplTitleEl = tplItem.querySelector('span.truncate')
    expect(tplTitleEl).not.toBeNull()
    expect(tplTitleEl?.getAttribute('title')).toContain('Comprehensive Audio-Visual')

    // 7. Template CTA has touch padding py-1 px-1
    const tplBtn = container.querySelector('[data-testid="navigate-template-tpl_long_name_1"]') as HTMLElement
    expect(tplBtn.className).toContain('py-1')
    expect(tplBtn.className).toContain('px-1')
  })

  it('Desktop (1280px): maintains balanced layout and structural issue alert badge', async () => {
    window.innerWidth = 1280
    window.innerHeight = 800
    window.dispatchEvent(new Event('resize'))

    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="Standard JLPT Deck"
          currentVersionLabel="v2.0.0"
          noteTypes={sampleNoteTypes}
        />
      )
    })

    // Header has warning badge for structural issues
    const warningBadge = container.querySelector('span.border-amber-500\\/40')
    expect(warningBadge).not.toBeNull()
    expect(warningBadge?.textContent).toContain('Cần cập nhật cấu trúc')

    // Note type item renders correctly with version badges
    expect(container.textContent).toContain('pin: v1.0.0')
    expect(container.textContent).toContain('v2.0.0')
  })
})
