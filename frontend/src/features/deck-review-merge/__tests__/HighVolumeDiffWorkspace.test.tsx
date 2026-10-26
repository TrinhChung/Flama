// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CardDiff } from '@/entities/card-diff'
import { HighVolumeDiffWorkspace } from '../components/HighVolumeDiffWorkspace'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function generateMockDiffItems(count: number): CardDiff[] {
  const items: CardDiff[] = []
  const noteTypes = [
    { id: 'nt_vocab', name: 'Từ vựng N3 Chuẩn' },
    { id: 'nt_kanji', name: 'Kanji N3' },
    { id: 'nt_grammar', name: 'Ngữ pháp N2' },
  ]
  const changeTypes: CardDiff['changeType'][] = ['added', 'modified', 'removed']

  for (let i = 0; i < count; i++) {
    const nt = noteTypes[i % noteTypes.length]
    const ct = changeTypes[i % changeTypes.length]
    items.push({
      id: `card_${i + 1}`,
      noteId: `note_${i + 1}`,
      noteTypeId: nt.id,
      noteTypeName: nt.name,
      changeType: ct,
      primaryText: `Mục học ${i + 1} (じゅんび ${i + 1})`,
      secondaryText: `Ý nghĩa bài học số ${i + 1}`,
      fieldDiffs: [
        {
          fieldName: 'Example_VI',
          before: ct === 'added' ? undefined : `Câu ví dụ cũ ${i + 1}`,
          after: ct === 'removed' ? undefined : `Câu ví dụ mới cập nhật ${i + 1}`,
          isConflict: false,
        },
      ],
      status: 'pending',
    })
  }

  return items
}

describe('HighVolumeDiffWorkspace', () => {
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

  it('renders 1,000 mocked items with virtualization (<150 DOM rows rendered)', async () => {
    const items = generateMockDiffItems(1000)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    const workspace = container?.querySelector('[data-testid="high-volume-diff-workspace"]')
    expect(workspace).toBeDefined()

    // Check that toolbar summary shows total 1,000 items
    expect(container?.textContent).toContain('1000')

    // Count rendered card items in the DOM
    const renderedCardItems = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
    expect(renderedCardItems).toBeDefined()
    // Virtualization constraint: MUST be strictly under 150 DOM nodes
    expect(renderedCardItems!.length).toBeGreaterThan(0)
    expect(renderedCardItems!.length).toBeLessThan(150)
  })

  it('filters items by change type (added, modified, removed)', async () => {
    const items = generateMockDiffItems(30)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    // Click on "Thêm mới" (added) filter button
    const addedButton = Array.from(container?.querySelectorAll('button') || []).find((b) =>
      b.textContent?.includes('Thêm mới'),
    )
    expect(addedButton).toBeDefined()

    await act(async () => {
      addedButton?.click()
    })

    // Check that rendered cards have "Thêm mới" badge and no "Đã sửa" badge
    const visibleBadges = Array.from(
      container?.querySelectorAll('[data-testid^="card-diff-item-"]') || [],
    ).map((el) => el.textContent)

    expect(visibleBadges.every((txt) => txt?.includes('Thêm mới'))).toBe(true)

    // Click on "Đã sửa" (modified) filter button
    const modifiedButton = Array.from(container?.querySelectorAll('button') || []).find((b) =>
      b.textContent?.includes('Đã sửa'),
    )
    await act(async () => {
      modifiedButton?.click()
    })

    const modifiedBadges = Array.from(
      container?.querySelectorAll('[data-testid^="card-diff-item-"]') || [],
    ).map((el) => el.textContent)

    expect(modifiedBadges.every((txt) => txt?.includes('Đã sửa'))).toBe(true)
  })

  it('filters items by Note Type dropdown', async () => {
    const items = generateMockDiffItems(30)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    const select = container?.querySelector('select#note-type-filter') as HTMLSelectElement
    expect(select).toBeDefined()

    // Select 'nt_kanji'
    await act(async () => {
      select.value = 'nt_kanji'
      select.dispatchEvent(new Event('change', { bubbles: true }))
    })

    expect(container?.textContent).toContain('Kanji N3')
    const noteTypeGroups = container?.querySelectorAll('[data-testid^="note-type-group-"]')
    expect(noteTypeGroups?.length).toBe(1)
    expect(noteTypeGroups?.[0].getAttribute('data-testid')).toBe('note-type-group-nt_kanji')
  })

  it('filters items by search input', async () => {
    vi.useFakeTimers()
    const items = generateMockDiffItems(20)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    const searchInput = container?.querySelector(
      'input[aria-label="Tìm kiếm nội dung thẻ"]',
    ) as HTMLInputElement
    expect(searchInput).toBeDefined()

    await act(async () => {
      searchInput.value = 'Mục học 5'
      searchInput.dispatchEvent(new Event('change', { bubbles: true }))
      searchInput.dispatchEvent(new Event('input', { bubbles: true }))
      vi.advanceTimersByTime(250)
    })

    expect(container?.textContent).toContain('Mục học 5')
    vi.useRealTimers()
  })

  it('supports selecting individual cards (cherry-pick) and displays batch action bar', async () => {
    const items = generateMockDiffItems(10)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    // Initially batch action bar should not be visible
    expect(container?.querySelector('[data-testid="batch-action-bar"]')).toBeNull()

    // Click checkbox of card_1
    const cardCheckbox = container?.querySelector(
      '[data-testid="card-checkbox-card_1"]',
    ) as HTMLButtonElement
    expect(cardCheckbox).toBeDefined()

    await act(async () => {
      cardCheckbox.click()
    })

    // Batch action bar should now appear
    const batchBar = container?.querySelector('[data-testid="batch-action-bar"]')
    expect(batchBar).not.toBeNull()
    expect(batchBar?.textContent).toContain('Đã chọn 1')
  })

  it('executes batch approve and batch reject callback handlers', async () => {
    const items = generateMockDiffItems(10)
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

    // Select card_1 and card_2
    const card1 = container?.querySelector(
      '[data-testid="card-checkbox-card_1"]',
    ) as HTMLButtonElement
    const card2 = container?.querySelector(
      '[data-testid="card-checkbox-card_2"]',
    ) as HTMLButtonElement

    await act(async () => {
      card1.click()
      card2.click()
    })

    const approveBtn = container?.querySelector(
      '[data-testid="batch-approve-btn"]',
    ) as HTMLButtonElement
    expect(approveBtn).toBeDefined()

    await act(async () => {
      approveBtn.click()
    })

    expect(onApprove).toHaveBeenCalledWith(expect.arrayContaining(['card_1', 'card_2']))

    // Click reject
    const rejectBtn = container?.querySelector(
      '[data-testid="batch-reject-btn"]',
    ) as HTMLButtonElement
    await act(async () => {
      rejectBtn.click()
    })

    expect(onReject).toHaveBeenCalledWith(expect.arrayContaining(['card_1', 'card_2']))
  })

  it('supports group-level approve and reject actions', async () => {
    const items = generateMockDiffItems(12)
    const onApproveGroup = vi.fn()
    const onRejectGroup = vi.fn()

    await act(async () => {
      root?.render(
        <HighVolumeDiffWorkspace
          items={items}
          onApproveGroup={onApproveGroup}
          onRejectGroup={onRejectGroup}
        />,
      )
    })

    const groupApproveBtn = container?.querySelector(
      '[data-testid="approve-group-nt_vocab"]',
    ) as HTMLButtonElement
    expect(groupApproveBtn).toBeDefined()

    await act(async () => {
      groupApproveBtn.click()
    })

    expect(onApproveGroup).toHaveBeenCalledWith(
      'nt_vocab',
      expect.arrayContaining(['card_1', 'card_4']),
    )

    const groupRejectBtn = container?.querySelector(
      '[data-testid="reject-group-nt_vocab"]',
    ) as HTMLButtonElement
    await act(async () => {
      groupRejectBtn.click()
    })

    expect(onRejectGroup).toHaveBeenCalledWith(
      'nt_vocab',
      expect.arrayContaining(['card_1', 'card_4']),
    )
  })

  it('bypasses virtualization on Ctrl+F / Cmd+F find keydown', async () => {
    const items = generateMockDiffItems(500)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    const initialRendered = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
    expect(initialRendered!.length).toBeLessThan(150)

    // Trigger Ctrl+F
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }))
    })

    // Now all non-collapsed items are rendered
    const expandedRendered = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
    expect(expandedRendered!.length).toBe(500)
  })

  it('supports Shift+Click range selection across cards', async () => {
    const items = generateMockDiffItems(10)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    const card1 = container?.querySelector(
      '[data-testid="card-checkbox-card_1"]',
    ) as HTMLButtonElement
    const card4 = container?.querySelector(
      '[data-testid="card-checkbox-card_4"]',
    ) as HTMLButtonElement

    // Click card 1
    await act(async () => {
      card1.click()
    })

    // Shift-Click card 4
    await act(async () => {
      card4.dispatchEvent(new MouseEvent('click', { bubbles: true, shiftKey: true }))
    })

    const batchBar = container?.querySelector('[data-testid="batch-action-bar"]')
    expect(batchBar?.textContent).toContain('Đã chọn 4')
  })
})
