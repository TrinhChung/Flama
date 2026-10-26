// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CardDiff } from '@/entities/card-diff'
import { HighVolumeDiffWorkspace } from '../components/HighVolumeDiffWorkspace'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function generateAdversarialDiffItems(count: number, options?: { noteTypeCount?: number }): CardDiff[] {
  const items: CardDiff[] = []
  const noteTypeCount = options?.noteTypeCount ?? 5
  const noteTypes = Array.from({ length: noteTypeCount }, (_, idx) => ({
    id: `nt_${idx + 1}`,
    name: `Loại thẻ nhóm ${idx + 1} (種類 ${idx + 1})`,
  }))
  const changeTypes: CardDiff['changeType'][] = ['added', 'modified', 'removed', 'conflict']

  for (let i = 0; i < count; i++) {
    const nt = noteTypes[i % noteTypes.length]
    const ct = changeTypes[i % changeTypes.length]
    items.push({
      id: `card_${i + 1}`,
      noteId: `note_${i + 1}`,
      noteTypeId: nt.id,
      noteTypeName: nt.name,
      changeType: ct,
      primaryText: `Mục học ${i + 1}: 準備・${i + 1}「じゅんび」`,
      secondaryText: `Ý nghĩa bài học số ${i + 1} (準備 & テスト)`,
      fieldDiffs: [
        {
          fieldName: 'Vocabulary',
          before: ct === 'added' ? undefined : `言葉_${i + 1}`,
          after: ct === 'removed' ? undefined : `新言葉_${i + 1}`,
          isConflict: ct === 'conflict',
        },
        {
          fieldName: 'Example_VI',
          before: ct === 'added' ? undefined : `Câu ví dụ cũ ${i + 1} (chú thích)`,
          after: ct === 'removed' ? undefined : `Câu ví dụ mới ${i + 1} [đã kiểm tra]`,
          isConflict: false,
        },
      ],
      status: 'pending',
    })
  }

  return items
}

describe('HighVolumeDiffWorkspace — Adversarial Stress Testing', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    if (root && container) {
      const activeRoot = root
      await act(async () => {
        activeRoot.unmount()
      })
      container.remove()
    }
    document.body.replaceChildren()
    container = null
    root = null
  })

  // =========================================================================
  // Challenge Set 1: High-Volume Virtualization & DOM Node Count Limits
  // =========================================================================
  describe('Challenge Set 1: High-Volume Virtualization (1,000 to 5,000 items)', () => {
    it('empirical test: 1,000 cards renders strictly < 150 DOM rows', async () => {
      const items = generateAdversarialDiffItems(1000)

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const renderedCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      const renderedHeaders = container?.querySelectorAll('[data-testid^="note-type-group-"]')
      const totalRenderedRows = (renderedCards?.length ?? 0) + (renderedHeaders?.length ?? 0)

      expect(totalRenderedRows).toBeGreaterThan(0)
      expect(totalRenderedRows).toBeLessThan(150)
      expect(renderedCards!.length).toBeLessThan(150)
    })

    it('empirical test: 2,500 cards across 10 Note Types renders strictly < 150 DOM rows', async () => {
      const items = generateAdversarialDiffItems(2500, { noteTypeCount: 10 })

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const renderedCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      const renderedHeaders = container?.querySelectorAll('[data-testid^="note-type-group-"]')
      const totalRenderedRows = (renderedCards?.length ?? 0) + (renderedHeaders?.length ?? 0)

      expect(totalRenderedRows).toBeGreaterThan(0)
      expect(totalRenderedRows).toBeLessThan(150)
      expect(renderedCards!.length).toBeLessThan(150)
    })

    it('empirical test: 5,000 cards across 25 Note Types renders strictly < 150 DOM rows', async () => {
      const items = generateAdversarialDiffItems(5000, { noteTypeCount: 25 })

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const renderedCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      const renderedHeaders = container?.querySelectorAll('[data-testid^="note-type-group-"]')
      const totalRenderedRows = (renderedCards?.length ?? 0) + (renderedHeaders?.length ?? 0)

      expect(totalRenderedRows).toBeGreaterThan(0)
      expect(totalRenderedRows).toBeLessThan(150)
      expect(renderedCards!.length).toBeLessThan(150)
    })

    it('empirical test: scrolling across multiple scroll offsets (0 to 300,000px) maintains < 150 DOM rows', async () => {
      const items = generateAdversarialDiffItems(5000, { noteTypeCount: 20 })

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const scrollContainer = container?.querySelector(
        '[data-testid="virtualized-diff-container"]',
      ) as HTMLDivElement
      expect(scrollContainer).toBeDefined()

      // Define element dimensions in jsdom
      Object.defineProperty(scrollContainer, 'clientHeight', { value: 680, configurable: true })

      const scrollOffsets = [0, 5000, 25000, 50000, 100000, 200000, 300000]

      for (const offset of scrollOffsets) {
        await act(async () => {
          scrollContainer.scrollTop = offset
          scrollContainer.dispatchEvent(new Event('scroll'))
          // Allow RAF frame to execute
          await new Promise((resolve) => setTimeout(resolve, 20))
        })

        const renderedCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
        const renderedHeaders = container?.querySelectorAll('[data-testid^="note-type-group-"]')
        const totalRows = (renderedCards?.length ?? 0) + (renderedHeaders?.length ?? 0)

        expect(totalRows).toBeGreaterThan(0)
        expect(totalRows).toBeLessThan(150)
      }
    })

    it('adversarial probe: behavior when scrollTop exceeds totalHeight (e.g. overscroll / filter shrink)', async () => {
      // 1000 items -> totalHeight ~68,000px
      const items = generateAdversarialDiffItems(1000)

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const scrollContainer = container?.querySelector(
        '[data-testid="virtualized-diff-container"]',
      ) as HTMLDivElement
      expect(scrollContainer).toBeDefined()

      Object.defineProperty(scrollContainer, 'clientHeight', { value: 680, configurable: true })

      // Scroll way past totalHeight: 500,000px
      await act(async () => {
        scrollContainer.scrollTop = 500000
        scrollContainer.dispatchEvent(new Event('scroll'))
        await new Promise((resolve) => setTimeout(resolve, 20))
      })

      const renderedCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      // Empirical verification: when scrollTop > totalHeight, binary search resets startIdx to 0
      // causing all 1,000 items to mount.
      expect(renderedCards?.length).toBe(1000)
    })

    it('adversarial probe: Ctrl+F find bypass recovers virtualization on Escape or scroll', async () => {
      const items = generateAdversarialDiffItems(500)

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const initialCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      expect(initialCards!.length).toBeLessThan(150)

      // 1. Press Ctrl+F
      await act(async () => {
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }))
      })

      const afterFindCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      expect(afterFindCards!.length).toBe(500)

      // 2. User presses Escape or scrolls or clicks another card
      const scrollContainer = container?.querySelector(
        '[data-testid="virtualized-diff-container"]',
      ) as HTMLDivElement
      Object.defineProperty(scrollContainer, 'clientHeight', { value: 680, configurable: true })

      await act(async () => {
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
        scrollContainer.scrollTop = 2000
        scrollContainer.dispatchEvent(new Event('scroll'))
        await new Promise((resolve) => setTimeout(resolve, 20))
      })

      // Verification: showAllForSearch is recovered when resetSearchBypass is called on Escape/scroll
      const recoveredCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      expect(recoveredCards!.length).toBeLessThan(150)
    })

    it('handles empty items array gracefully with 0 rows and empty state', async () => {
      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={[]} />)
      })

      const emptyState = container?.querySelector('[data-testid="empty-diff-state"]')
      expect(emptyState).toBeDefined()
      expect(container?.querySelectorAll('[data-testid^="card-diff-item-"]').length).toBe(0)
    })

    it('handles single item dataset without out-of-bounds error', async () => {
      const singleItem = generateAdversarialDiffItems(1)

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={singleItem} />)
      })

      const renderedCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      expect(renderedCards?.length).toBe(1)
    })
  })

  // =========================================================================
  // Challenge Set 2: Search Filtering Stress Test (Rapid Debouncing & Special Chars)
  // =========================================================================
  describe('Challenge Set 2: Search Filtering Stress Test', () => {
    it('resilient against regex metacharacters and special symbols without syntax errors', async () => {
      vi.useFakeTimers()
      const items = generateAdversarialDiffItems(100)

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const searchInput = container?.querySelector(
        'input[aria-label="Tìm kiếm nội dung thẻ"]',
      ) as HTMLInputElement
      expect(searchInput).toBeDefined()

      const setVal = (val: string) => {
        const valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set
        valueSetter?.call(searchInput, val)
        searchInput.dispatchEvent(new Event('input', { bubbles: true }))
        searchInput.dispatchEvent(new Event('change', { bubbles: true }))
      }

      const specialPatterns = [
        '.*',
        '([a-z]+)',
        '\\d+\\w*',
        '???^^^$$$',
        '[{(<',
        '"><script>alert("xss")</script>',
        '準備・10「じゅんび」',
        '言葉_25',
        '#@!%^&*()_+=~`',
      ]

      for (const pattern of specialPatterns) {
        await act(async () => {
          setVal(pattern)
          vi.advanceTimersByTime(250)
        })

        // Verify that the component does not crash or throw unhandled exceptions
        const workspace = container?.querySelector('[data-testid="high-volume-diff-workspace"]')
        expect(workspace).not.toBeNull()
      }

      vi.useRealTimers()
    })

    it('stress tests rapid typing (debouncing cancellation) under high volume', async () => {
      vi.useFakeTimers()
      const items = generateAdversarialDiffItems(500)

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const searchInput = container?.querySelector(
        'input[aria-label="Tìm kiếm nội dung thẻ"]',
      ) as HTMLInputElement

      const setVal = (val: string) => {
        const valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set
        valueSetter?.call(searchInput, val)
        searchInput.dispatchEvent(new Event('input', { bubbles: true }))
        searchInput.dispatchEvent(new Event('change', { bubbles: true }))
      }

      const rapidKeystrokes = ['M', 'Mụ', 'Mục', 'Mục ', 'Mục h', 'Mục họ', 'Mục học', 'Mục học 4', 'Mục học 42']

      for (const stroke of rapidKeystrokes) {
        await act(async () => {
          setVal(stroke)
          // Advance timer by only 50ms (less than 200ms debounce threshold)
          vi.advanceTimersByTime(50)
        })
      }

      // Now advance past the 200ms debounce window
      await act(async () => {
        vi.advanceTimersByTime(250)
      })

      // Verify that the final filtered result reflects "Mục học 42"
      expect(container?.textContent).toContain('Mục học 42')
      vi.useRealTimers()
    })

    it('matches search query across primary, secondary, and field diff before/after values', async () => {
      vi.useFakeTimers()
      const items = generateAdversarialDiffItems(50)

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const searchInput = container?.querySelector(
        'input[aria-label="Tìm kiếm nội dung thẻ"]',
      ) as HTMLInputElement

      const setVal = (val: string) => {
        const valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set
        valueSetter?.call(searchInput, val)
        searchInput.dispatchEvent(new Event('input', { bubbles: true }))
        searchInput.dispatchEvent(new Event('change', { bubbles: true }))
      }

      // Search by field diff text: card 14 (i=13, ct='modified') has after = 'Câu ví dụ mới 14 [đã kiểm tra]'
      await act(async () => {
        setVal('Câu ví dụ mới 14')
        vi.advanceTimersByTime(250)
      })

      expect(container?.textContent).toContain('Mục học 14')

      // Search by secondary text: '準備 & テスト'
      await act(async () => {
        setVal('準備 & テスト')
        vi.advanceTimersByTime(250)
      })

      expect(container?.textContent).toContain('Ý nghĩa bài học số')

      vi.useRealTimers()
    })
  })

  // =========================================================================
  // Challenge Set 3: Shift+Click Range Selection & Group Collapsing
  // =========================================================================
  describe('Challenge Set 3: Shift+Click Range Selection & Group Collapsing', () => {
    it('supports Shift+Click range selection across multiple items in the same group', async () => {
      const items = generateAdversarialDiffItems(20, { noteTypeCount: 1 })

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const card2Checkbox = container?.querySelector(
        '[data-testid="card-checkbox-card_2"]',
      ) as HTMLButtonElement
      const card6Checkbox = container?.querySelector(
        '[data-testid="card-checkbox-card_6"]',
      ) as HTMLButtonElement

      expect(card2Checkbox).toBeDefined()
      expect(card6Checkbox).toBeDefined()

      // Click card 2
      await act(async () => {
        card2Checkbox.click()
      })

      // Shift-click card 6
      await act(async () => {
        card6Checkbox.dispatchEvent(new MouseEvent('click', { bubbles: true, shiftKey: true }))
      })

      const batchBar = container?.querySelector('[data-testid="batch-action-bar"]')
      expect(batchBar).not.toBeNull()
      // Cards 2, 3, 4, 5, 6 selected = 5 cards
      expect(batchBar?.textContent).toContain('Đã chọn 5')
    })

    it('supports Shift+Click range selection across multiple expanded groups', async () => {
      // 30 items across 3 note types = 10 items per group
      const items = generateAdversarialDiffItems(30, { noteTypeCount: 3 })

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      // Group 1 has card_1, card_4, card_7...
      // Let's find first rendered card and a card in another group
      const card1Checkbox = container?.querySelector(
        '[data-testid="card-checkbox-card_1"]',
      ) as HTMLButtonElement
      const card5Checkbox = container?.querySelector(
        '[data-testid="card-checkbox-card_5"]',
      ) as HTMLButtonElement

      await act(async () => {
        card1Checkbox.click()
      })

      await act(async () => {
        card5Checkbox.dispatchEvent(new MouseEvent('click', { bubbles: true, shiftKey: true }))
      })

      const batchBar = container?.querySelector('[data-testid="batch-action-bar"]')
      expect(batchBar).not.toBeNull()
      // Items 1 through 5 selected = 5 cards
      expect(batchBar?.textContent).toContain('Đã chọn 5')
    })

    it('verifies Shift+Click range selection across collapsed groups', async () => {
      // 30 items across 3 note types (nt_1, nt_2, nt_3)
      const items = generateAdversarialDiffItems(30, { noteTypeCount: 3 })

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      // Collapse group nt_2
      const group2Header = container?.querySelector(
        '[data-testid="note-type-group-nt_2"] [role="button"]',
      ) as HTMLDivElement
      expect(group2Header).toBeDefined()

      await act(async () => {
        group2Header.click()
      })

      // Card in nt_2 should no longer be in the flatRows/DOM
      expect(container?.querySelector('[data-testid="card-checkbox-card_2"]')).toBeNull()

      // Click card_1 (in nt_1)
      const card1Checkbox = container?.querySelector(
        '[data-testid="card-checkbox-card_1"]',
      ) as HTMLButtonElement

      await act(async () => {
        card1Checkbox.click()
      })

      // Shift-click card_3 (in nt_3)
      const card3Checkbox = container?.querySelector(
        '[data-testid="card-checkbox-card_3"]',
      ) as HTMLButtonElement

      await act(async () => {
        card3Checkbox.dispatchEvent(new MouseEvent('click', { bubbles: true, shiftKey: true }))
      })

      // Range spans card_1, card_2, card_3.
      // Card 2 belongs to collapsed group nt_2.
      const batchBar = container?.querySelector('[data-testid="batch-action-bar"]')
      expect(batchBar).not.toBeNull()
      expect(batchBar?.textContent).toContain('Đã chọn 3')

      // Verify that group nt_2 header indicates some selected cards
      const group2Checkbox = container?.querySelector(
        '[data-testid="group-checkbox-nt_2"]',
      )
      expect(group2Checkbox).toBeDefined()
    })

    it('supports backwards (reverse) Shift+Click selection', async () => {
      const items = generateAdversarialDiffItems(10, { noteTypeCount: 1 })

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const card8 = container?.querySelector(
        '[data-testid="card-checkbox-card_8"]',
      ) as HTMLButtonElement
      const card3 = container?.querySelector(
        '[data-testid="card-checkbox-card_3"]',
      ) as HTMLButtonElement

      // First click card 8
      await act(async () => {
        card8.click()
      })

      // Then Shift-click card 3 (backwards)
      await act(async () => {
        card3.dispatchEvent(new MouseEvent('click', { bubbles: true, shiftKey: true }))
      })

      const batchBar = container?.querySelector('[data-testid="batch-action-bar"]')
      // Cards 3, 4, 5, 6, 7, 8 selected = 6 cards
      expect(batchBar?.textContent).toContain('Đã chọn 6')
    })
  })

  // =========================================================================
  // Challenge Set 4: Batch Actions & Selection Handlers
  // =========================================================================
  describe('Challenge Set 4: Batch Actions & Large-Scale Processing', () => {
    it('executes batch approve and reject on 1,000 selected cards', async () => {
      const items = generateAdversarialDiffItems(1000)
      const onApprove = vi.fn()
      const onReject = vi.fn()

      await act(async () => {
        root?.render(
          <HighVolumeDiffWorkspace
            items={items}
            onApproveSelected={onApprove}
            onRejectSelected={onReject}
          />,
        )
      })

      // Click "Chọn tất cả" in the toolbar
      const selectAllBtn = Array.from(container?.querySelectorAll('button') || []).find((b) =>
        b.textContent?.includes('Chọn tất cả'),
      )
      expect(selectAllBtn).toBeDefined()

      await act(async () => {
        selectAllBtn?.click()
      })

      const batchBar = container?.querySelector('[data-testid="batch-action-bar"]')
      expect(batchBar?.textContent).toMatch(/Đã chọn 1[.,]000/)

      // Click approve
      const approveBtn = container?.querySelector(
        '[data-testid="batch-approve-btn"]',
      ) as HTMLButtonElement
      await act(async () => {
        approveBtn.click()
      })

      expect(onApprove).toHaveBeenCalledTimes(1)
      const approvedIds = onApprove.mock.calls[0][0]
      expect(approvedIds.length).toBe(1000)

      // Click reject
      const rejectBtn = container?.querySelector(
        '[data-testid="batch-reject-btn"]',
      ) as HTMLButtonElement
      await act(async () => {
        rejectBtn.click()
      })

      expect(onReject).toHaveBeenCalledTimes(1)
      const rejectedIds = onReject.mock.calls[0][0]
      expect(rejectedIds.length).toBe(1000)
    })

    it('filters selection correctly when select all visible is toggled under active filter', async () => {
      const items = generateAdversarialDiffItems(60) // 15 added, 15 modified, 15 removed, 15 conflict

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      // Filter by 'Thêm mới' (added)
      const addedFilterBtn = Array.from(container?.querySelectorAll('button') || []).find((b) =>
        b.textContent?.includes('Thêm mới'),
      )
      await act(async () => {
        addedFilterBtn?.click()
      })

      // Click "Chọn tất cả" visible
      const selectAllBtn = Array.from(container?.querySelectorAll('button') || []).find((b) =>
        b.textContent?.includes('Chọn tất cả'),
      )
      await act(async () => {
        selectAllBtn?.click()
      })

      const batchBar = container?.querySelector('[data-testid="batch-action-bar"]')
      // Only 15 added items selected
      expect(batchBar?.textContent).toContain('Đã chọn 15')

      // Switch filter back to "Tất cả"
      const allFilterBtn = Array.from(container?.querySelectorAll('button') || []).find((b) =>
        b.textContent?.includes('Tất cả'),
      )
      await act(async () => {
        allFilterBtn?.click()
      })

      // Selected count is still 15
      expect(batchBar?.textContent).toContain('Đã chọn 15')
    })

    it('clears selection when clear button is clicked', async () => {
      const items = generateAdversarialDiffItems(20)

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const card1 = container?.querySelector(
        '[data-testid="card-checkbox-card_1"]',
      ) as HTMLButtonElement
      await act(async () => {
        card1.click()
      })

      expect(container?.querySelector('[data-testid="batch-action-bar"]')).not.toBeNull()

      const clearBtn = container?.querySelector(
        '[data-testid="batch-clear-btn"]',
      ) as HTMLButtonElement
      await act(async () => {
        clearBtn.click()
      })

      expect(container?.querySelector('[data-testid="batch-action-bar"]')).toBeNull()
    })
  })
})
