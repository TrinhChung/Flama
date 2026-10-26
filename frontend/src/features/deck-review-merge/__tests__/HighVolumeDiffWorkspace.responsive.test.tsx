// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { CardDiff } from '@/entities/card-diff'
import { HighVolumeDiffWorkspace } from '../components/HighVolumeDiffWorkspace'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function generateMockItems(count: number): CardDiff[] {
  const items: CardDiff[] = []
  for (let i = 0; i < count; i++) {
    items.push({
      id: `card_${i + 1}`,
      noteId: `note_${i + 1}`,
      noteTypeId: 'nt_vocab',
      noteTypeName: 'Từ vựng N3 Chuẩn',
      changeType: i % 2 === 0 ? 'added' : 'modified',
      primaryText: `Mục học ${i + 1}`,
      secondaryText: `Ý nghĩa bài học ${i + 1}`,
      fieldDiffs: [
        {
          fieldName: 'Meaning',
          before: 'Nghĩa cũ',
          after: 'Nghĩa mới',
          isConflict: false,
        },
      ],
      status: 'pending',
    })
  }
  return items
}

describe('HighVolumeDiffWorkspace — Responsive Multi-Device Tests (R4)', () => {
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

  it('Mobile (375px): renders full-width search input, wrapping filter pills, >=44px checkbox hit-box, and sticky bottom action bar', async () => {
    window.innerWidth = 375
    window.innerHeight = 667
    window.dispatchEvent(new Event('resize'))

    const items = generateMockItems(10)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    // 1. Search input wrapper is full width on mobile with sm:w-72 (w-full sm:w-72)
    const searchContainer = container?.querySelector('.sm\\:w-72')
    expect(searchContainer).not.toBeNull()
    expect(searchContainer?.className).toContain('w-full')
    expect(searchContainer?.className).toContain('sm:w-72')

    // 2. Filter pills container has flex-wrap to prevent horizontal blowout on mobile
    const pillsContainer = container?.querySelector('.border-t.border-border\\/50')
    expect(pillsContainer).not.toBeNull()
    expect(pillsContainer?.className).toContain('flex-wrap')

    // 3. Checkbox hit-box touch target >= 44x44px (min-h-[44px] min-w-[44px])
    const checkboxBtn = container?.querySelector('[data-testid^="card-checkbox-"]') as HTMLButtonElement
    expect(checkboxBtn).not.toBeNull()
    expect(checkboxBtn.className).toContain('min-h-[44px]')
    expect(checkboxBtn.className).toContain('min-w-[44px]')

    // Select a card to trigger BatchActionBar
    await act(async () => {
      checkboxBtn.click()
    })

    // 4. BatchActionBar is present with sticky positioning
    const batchBar = container?.querySelector('[data-testid="batch-action-bar"]') as HTMLDivElement
    expect(batchBar).not.toBeNull()
    expect(batchBar.className).toContain('sticky')
    expect(batchBar.className).toContain('bottom-3')
    expect(batchBar.className).toContain('z-30')

    // Action buttons have mobile touch target >= 38px
    const approveBtn = container?.querySelector('[data-testid="batch-approve-btn"]') as HTMLButtonElement
    expect(approveBtn.className).toContain('min-h-[38px]')
  })

  it('Tablet (768px): maintains balanced search bar and filter controls', async () => {
    window.innerWidth = 768
    window.innerHeight = 1024
    window.dispatchEvent(new Event('resize'))

    const items = generateMockItems(15)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    const toolbar = container?.querySelector('[data-testid="diff-filter-toolbar"]')
    expect(toolbar).not.toBeNull()

    // Note type selector has max-w-full and truncate
    const select = container?.querySelector('select#note-type-filter') as HTMLSelectElement
    expect(select.className).toContain('truncate')
    expect(select.className).toContain('max-w-full')

    // Action buttons in toolbar have tablet/desktop scaling
    const selectAllBtn = container?.querySelector('button[aria-label="Chọn tất cả thẻ đang hiển thị"]')
    expect(selectAllBtn?.className).toContain('sm:h-7')
    expect(selectAllBtn?.className).toContain('sm:min-h-[28px]')
  })

  it('Laptop (1366x768): uses viewport-adaptive container height to prevent pushing action bar off-screen', async () => {
    window.innerWidth = 1366
    window.innerHeight = 768
    window.dispatchEvent(new Event('resize'))

    const items = generateMockItems(50)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    const scrollContainer = container?.querySelector('[data-testid="virtualized-diff-container"]') as HTMLDivElement
    expect(scrollContainer).not.toBeNull()

    // Max height style is viewport-adaptive by default
    expect(scrollContainer.style.maxHeight).toContain('380px')
    expect(scrollContainer.style.maxHeight).toContain('calc(100dvh - 280px)')

    // Container also carries responsive max-h utility classes
    expect(scrollContainer.className).toContain('max-h-[58vh]')
    expect(scrollContainer.className).toContain('sm:max-h-[65vh]')
    expect(scrollContainer.className).toContain('lg:max-h-[calc(100dvh-20rem)]')

    // Select an item to verify BatchActionBar is within container context
    const firstCheckbox = container?.querySelector('[data-testid^="card-checkbox-"]') as HTMLButtonElement
    await act(async () => {
      firstCheckbox.click()
    })

    const batchBar = container?.querySelector('[data-testid="batch-action-bar"]')
    expect(batchBar).not.toBeNull()
  })

  it('Desktop (1920x1080): enforces max-w-7xl mx-auto to prevent extreme stretching', async () => {
    window.innerWidth = 1920
    window.innerHeight = 1080
    window.dispatchEvent(new Event('resize'))

    const items = generateMockItems(10)

    await act(async () => {
      root?.render(<HighVolumeDiffWorkspace items={items} />)
    })

    const workspace = container?.querySelector('[data-testid="high-volume-diff-workspace"]') as HTMLDivElement
    expect(workspace).not.toBeNull()
    expect(workspace.className).toContain('max-w-7xl')
    expect(workspace.className).toContain('mx-auto')
    expect(workspace.className).toContain('w-full')
  })
})
