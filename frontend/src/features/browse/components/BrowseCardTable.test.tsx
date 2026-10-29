// @vitest-environment jsdom

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import type { BrowseCardRow } from '../types'
import { BrowseCardTable, type BrowseCardTableProps } from './BrowseCardTable'

const formatter = vi.hoisted(() => ({ statusLabel: vi.fn() }))
vi.mock('../utils/formatter', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../utils/formatter')>()
  formatter.statusLabel.mockImplementation(actual.statusLabel)
  return { ...actual, statusLabel: formatter.statusLabel }
})

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function makeCard(id: string, word: string): BrowseCardRow {
  return {
    card_id: id,
    note_id: `note-${id}`,
    deck_id: 1,
    deck_name: 'Deck',
    word,
    reading: `${word}-reading`,
    meaning: `${word}-meaning`,
    tags: [],
    status: 'learn',
    due_label: 'Hôm nay',
  }
}

describe('BrowseCardTable', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    formatter.statusLabel.mockClear()
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    document.body.innerHTML = ''
  })

  function makeProps(overrides: Partial<BrowseCardTableProps> = {}): BrowseCardTableProps {
    return {
      cards: [],
      isPending: false,
      error: null,
      onRetry: vi.fn(),
      total: 0,
      pages: 1,
      page: 1,
      setPage: vi.fn(),
      perPage: 20,
      onPerPageChange: vi.fn(),
      selectedCardSet: new Set(),
      selectedCount: 0,
      allSelected: false,
      onToggleSelectAll: vi.fn(),
      onToggleCardSelected: vi.fn(),
      activeCardId: null,
      onActivateCard: vi.fn(),
      sortBy: 'due',
      sortDir: 'asc',
      onSortChange: vi.fn(),
      arrayViewMode: 'normal',
      ...overrides,
    }
  }

  async function render(props: BrowseCardTableProps) {
    await act(async () => {
      root.render(<BrowseCardTable {...props} />)
    })
  }

  function header(text: string) {
    return Array.from(container.querySelectorAll('th')).find((th) => th.textContent?.includes(text))!
  }

  it('renders loading indicator when the first page is pending', async () => {
    await render(makeProps({ isPending: true }))
    expect(container.textContent).toContain('Đang tìm thẻ...')
  })

  it('renders empty table state when there are no cards', async () => {
    await render(makeProps())
    expect(container.textContent).toContain('Không tìm thấy thẻ nào')
  })

  it('shows the API error instead of an empty list and retries on demand', async () => {
    const onRetry = vi.fn()
    await render(makeProps({ error: new Error('Invalid status filter.'), onRetry }))

    const alert = container.querySelector('[role="alert"]')!
    expect(alert.textContent).toContain('Không tải được danh sách thẻ')
    expect(alert.textContent).toContain('Invalid status filter.')
    expect(container.textContent).not.toContain('Không tìm thấy thẻ nào')

    await act(async () => alert.querySelector('button')!.click())
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders cards and handles transition from pending to loaded without hook ordering errors', async () => {
    await render(makeProps({ isPending: true }))
    expect(container.textContent).toContain('Đang tìm thẻ...')

    await render(makeProps({
      total: 1,
      cards: [{ ...makeCard('101', '日本語'), reading: 'にほんご', meaning: 'Japanese language' }],
    }))

    expect(container.textContent).toContain('日本語')
    expect(container.textContent).toContain('にほんご')
    expect(container.textContent).toContain('Japanese language')
  })

  it('offers sorting only on the columns the API can sort by', async () => {
    const onSortChange = vi.fn()
    await render(makeProps({ onSortChange, sortBy: 'word', sortDir: 'desc' }))

    for (const text of ['Đọc', 'Ý nghĩa', 'Trạng thái']) {
      const th = header(text)
      expect(th.className).not.toContain('cursor-pointer')
      expect(th.querySelector('svg')).toBeNull()
      await act(async () => th.click())
    }
    expect(onSortChange).not.toHaveBeenCalled()

    expect(header('Từ vựng').textContent).toContain('▼')
    await act(async () => header('Từ vựng').click())
    await act(async () => header('Đến hạn').click())
    expect(onSortChange.mock.calls).toEqual([['word'], ['due']])
  })

  it('re-renders only the rows whose selection or active state changed', async () => {
    const cards = [makeCard('1', 'a'), makeCard('2', 'b'), makeCard('3', 'c')]
    const props = makeProps({ cards, total: 3 })
    await render(props)
    expect(formatter.statusLabel).toHaveBeenCalledTimes(3)

    formatter.statusLabel.mockClear()
    await render({ ...props })
    expect(formatter.statusLabel).not.toHaveBeenCalled()

    await render({ ...props, activeCardId: '2', selectedCardSet: new Set(['3']), selectedCount: 1 })
    expect(formatter.statusLabel).toHaveBeenCalledTimes(2)
    const checkboxes = container.querySelectorAll('tbody [role="checkbox"]')
    expect(checkboxes[2].getAttribute('aria-checked')).toBe('true')
    expect(checkboxes[0].getAttribute('aria-checked')).toBe('false')
  })

  it('reports row clicks and checkbox toggles by card id', async () => {
    const onActivateCard = vi.fn()
    const onToggleCardSelected = vi.fn()
    await render(makeProps({ cards: [makeCard('7', 'x')], total: 1, onActivateCard, onToggleCardSelected }))

    await act(async () => container.querySelector<HTMLElement>('tbody tr td:nth-child(2)')!.click())
    expect(onActivateCard).toHaveBeenCalledWith('7')

    await act(async () => container.querySelector<HTMLElement>('tbody [role="checkbox"]')!.click())
    expect(onToggleCardSelected).toHaveBeenCalledWith('7', true)
    expect(onActivateCard).toHaveBeenCalledTimes(1)
  })

  it('marks changed published content while retaining the personal display value', async () => {
    const card = { ...makeCard('7', 'Personal word'), base_changed: true }
    await render(makeProps({ cards: [card], total: 1 }))
    expect(container.querySelector('tbody')?.textContent).toContain('Personal word')
    expect(container.querySelector('tbody [title="Bản gốc đã thay đổi"]')).not.toBeNull()
    await render(makeProps({ cards: [{ ...card, base_changed: false }], total: 1 }))
    expect(container.querySelector('tbody [title="Bản gốc đã thay đổi"]')).toBeNull()
  })
})
