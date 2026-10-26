// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CascadingSyncSummaryModal } from '../components/CascadingSyncSummaryModal'
import type { CascadingSyncSummary } from '../model/types'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const sampleSummary: CascadingSyncSummary = {
  deck_id: 'deck_1',
  deck_title: 'Complete Japanese N2 Advanced Vocabulary and Expression Mastery Course with Kanji & Context Sentences',
  version_label: 'v2.0',
  from_version_label: 'v1.0',
  cards_updated: 1500,
  cards_added: 900,
  cards_modified: 500,
  cards_removed: 100,
  progress_preserved_count: 2400,
  note_types_updated: [
    {
      id: 'nt_1',
      name: 'Advanced Compound Kanji Note Type with Stroke Order, Radicals, and Vocabulary Associations',
      version: 'v2.0',
    },
  ],
  templates_updated: [
    {
      id: 'tpl_1',
      name: 'Front Kanji Recognition Card with Audio Pitch Accent and Interactive Stroke Animation',
      from_version: 'v1.0',
      to_version: 'v2.0',
    },
  ],
}

describe('CascadingSyncSummaryModal — Responsive Multi-Device Tests (R4)', () => {
  let root: Root
  let container: HTMLDivElement

  beforeEach(() => {
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    document.body.innerHTML = ''
  })

  it('Mobile (375px): wraps synchronized card stats without blowout, adds truncate/break-words, and optimizes touch targets', async () => {
    window.innerWidth = 375
    window.innerHeight = 667
    window.dispatchEvent(new Event('resize'))

    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={sampleSummary}
        />
      )
    })

    // 1. Deck title has break-words and title attribute
    const deckTitleEl = document.body.querySelector('span.break-words')
    expect(deckTitleEl).not.toBeNull()
    expect(deckTitleEl?.getAttribute('title')).toContain('Complete Japanese N2')

    // 2. SRS banner spacing: gap-2 sm:gap-3, p-3 sm:p-4
    const srsBanner = document.body.querySelector('[data-testid="srs-progress-guarantee"]') as HTMLDivElement
    expect(srsBanner).not.toBeNull()
    expect(srsBanner.className).toContain('gap-2')
    expect(srsBanner.className).toContain('sm:gap-3')
    expect(srsBanner.className).toContain('p-3')
    expect(srsBanner.className).toContain('sm:p-4')

    // 3. Cards sync stat row has flex-wrap gap-1 and pb-2 sm:pb-3 to prevent crushing on <375px
    const cardStatRow = document.body.querySelector('[data-testid="cards-sync-stat"]') as HTMLDivElement
    expect(cardStatRow).not.toBeNull()
    expect(cardStatRow.className).toContain('flex-wrap')
    expect(cardStatRow.className).toContain('gap-1')
    expect(cardStatRow.className).toContain('pb-2')
    expect(cardStatRow.className).toContain('sm:pb-3')

    // 4. Note type name has truncate and title attribute
    const ntList = document.body.querySelector('[data-testid="note-types-sync-list"]') as HTMLDivElement
    const ntNameEl = ntList.querySelector('span.truncate')
    expect(ntNameEl).not.toBeNull()
    expect(ntNameEl?.getAttribute('title')).toContain('Advanced Compound Kanji')

    // 5. Template name has truncate and title attribute
    const tplList = document.body.querySelector('[data-testid="templates-sync-list"]') as HTMLDivElement
    const tplNameEl = tplList.querySelector('span.truncate')
    expect(tplNameEl).not.toBeNull()
    expect(tplNameEl?.getAttribute('title')).toContain('Front Kanji Recognition')

    // 6. Footer action buttons touch target: h-9 sm:h-8
    const closeBtn = document.body.querySelector('[data-testid="close-modal-btn"]') as HTMLButtonElement
    const startStudyBtn = document.body.querySelector('[data-testid="start-study-btn"]') as HTMLButtonElement
    expect(closeBtn.className).toContain('h-9')
    expect(closeBtn.className).toContain('sm:h-8')
    expect(startStudyBtn.className).toContain('h-9')
    expect(startStudyBtn.className).toContain('sm:h-8')
  })

  it('Desktop (1024px): displays full summary with balanced action row and badge counters', async () => {
    window.innerWidth = 1024
    window.innerHeight = 768
    window.dispatchEvent(new Event('resize'))

    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={sampleSummary}
        />
      )
    })

    const modal = document.body.querySelector('[data-testid="cascading-sync-modal"]')
    expect(modal).not.toBeNull()

    // Breakdown numbers are present
    expect(document.body.textContent).toContain('+900')
    expect(document.body.textContent).toContain('~500')
    expect(document.body.textContent).toContain('-100')
    expect(document.body.textContent).toContain('2,400 thẻ học giữ nguyên vẹn')
  })
})
