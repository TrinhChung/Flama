// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CascadingSyncSummaryModal } from '../components/CascadingSyncSummaryModal'
import type { CascadingSyncSummary } from '../model/types'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('CascadingSyncSummaryModal', () => {
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

  const mockSummary: CascadingSyncSummary = {
    deck_id: 'deck_n3_soumatome',
    deck_title: 'Soumatome N3 Từ vựng & Hán tự',
    version_label: 'v2.0',
    from_version_label: 'v1.2',
    cards_updated: 1250,
    cards_added: 800,
    cards_modified: 400,
    cards_removed: 50,
    progress_preserved_count: 1835,
    note_types_updated: [
      {
        id: 'nt_flama_default',
        name: 'Flama Default',
        version: 'v2.1',
      },
      {
        id: 'nt_kanji_n3',
        name: 'Kanji N3 Master',
        version: 'v1.5',
      },
    ],
    templates_updated: [
      {
        id: 'tpl_default_front_back',
        name: 'Default Front/Back',
        from_version: 'v2.0',
        to_version: 'v2.1',
      },
      {
        id: 'tpl_paired_grid',
        name: 'Paired Grid',
        from_version: 'v1.0',
        to_version: 'v1.2',
      },
    ],
  }

  it('renders synchronized component counts and version changes', async () => {
    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={mockSummary}
        />
      )
    })

    // Header and deck title
    expect(document.body.textContent).toContain('Cập nhật Deck thành công')
    expect(document.body.textContent).toContain('v1.2 → v2.0')
    expect(document.body.textContent).toContain('Soumatome N3 Từ vựng & Hán tự')

    // Cards sync stats
    expect(document.body.textContent).toContain('Thẻ học đã đồng bộ')
    expect(document.body.textContent).toContain('1,250 thẻ đã cập nhật')
    expect(document.body.textContent).toContain('+800')
    expect(document.body.textContent).toContain('~400')
    expect(document.body.textContent).toContain('-50')

    // Note types sync list
    expect(document.body.textContent).toContain('Note Types đã cập nhật (2)')
    expect(document.body.textContent).toContain('Flama Default')
    expect(document.body.textContent).toContain('v2.1')
    expect(document.body.textContent).toContain('Kanji N3 Master')
    expect(document.body.textContent).toContain('v1.5')

    // Templates sync list
    expect(document.body.textContent).toContain('Templates đã cập nhật (2)')
    expect(document.body.textContent).toContain('Default Front/Back')
    expect(document.body.textContent).toContain('v2.0 → v2.1')
    expect(document.body.textContent).toContain('Paired Grid')
    expect(document.body.textContent).toContain('v1.0 → v1.2')
  })

  it('displays prominent SRS safety reassurance banner with exact wording', async () => {
    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={mockSummary}
        />
      )
    })

    // Reassurance banner check
    expect(document.body.textContent).toContain(
      'Toàn bộ tiến độ học (SRS / Flashcards) và lịch sử ôn tập được bảo toàn 100%'
    )
    expect(document.body.textContent).toContain('1,835 thẻ học giữ nguyên vẹn')
  })

  it('triggers proper callbacks on action button clicks', async () => {
    const onOpenChange = vi.fn()
    const onStartStudy = vi.fn()
    const onClose = vi.fn()

    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={onOpenChange}
          summary={mockSummary}
          onStartStudy={onStartStudy}
          onClose={onClose}
        />
      )
    })

    // Click "Bắt đầu học ngay"
    const startStudyBtn = document.body.querySelector<HTMLButtonElement>(
      '[data-testid="start-study-btn"]'
    )
    expect(startStudyBtn).not.toBeNull()
    await act(async () => {
      startStudyBtn?.click()
    })
    expect(onStartStudy).toHaveBeenCalledTimes(1)
    expect(onOpenChange).toHaveBeenCalledWith(false)

    // Click "Đóng"
    const closeBtn = document.body.querySelector<HTMLButtonElement>(
      '[data-testid="close-modal-btn"]'
    )
    expect(closeBtn).not.toBeNull()
    await act(async () => {
      closeBtn?.click()
    })
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('returns null when summary is null', async () => {
    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={null}
        />
      )
    })

    expect(document.body.querySelector('[data-testid="cascading-sync-modal"]')).toBeNull()
  })
})
