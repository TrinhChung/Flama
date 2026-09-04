// @vitest-environment jsdom

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { BrowseCardTable } from './BrowseCardTable'

describe('BrowseCardTable', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    document.body.innerHTML = ''
  })

  function createMockBrowseState(overrides: Partial<any> = {}) {
    return {
      cardsQuery: { isPending: false, data: { total: 0, pages: 1 } },
      cards: [],
      selectedCards: [],
      setSelectedCards: vi.fn(),
      activeCardId: null,
      setActiveCardId: vi.fn(),
      setIsCreatingCard: vi.fn(),
      page: 1,
      setPage: vi.fn(),
      perPage: 20,
      handlePerPageChange: vi.fn(),
      allSelected: false,
      handleToggleSelectAllCards: vi.fn(),
      setMobileTab: vi.fn(),
      sortBy: 'word',
      setSortBy: vi.fn(),
      sortDir: 'asc',
      setSortDir: vi.fn(),
      ...overrides,
    } as any
  }

  it('renders loading indicator when cardsQuery is pending', async () => {
    const mockBrowse = createMockBrowseState({
      cardsQuery: { isPending: true },
    })

    await act(async () => {
      root.render(<BrowseCardTable browse={mockBrowse} />)
    })

    expect(container.textContent).toContain('Đang tìm thẻ...')
  })

  it('renders empty table state when there are no cards', async () => {
    const mockBrowse = createMockBrowseState({
      cardsQuery: { isPending: false, data: { total: 0, pages: 1 } },
      cards: [],
    })

    await act(async () => {
      root.render(<BrowseCardTable browse={mockBrowse} />)
    })

    expect(container.textContent).toContain('Không tìm thấy thẻ nào')
  })

  it('renders cards and handles transition from pending to loaded without hook ordering errors', async () => {
    const mockBrowsePending = createMockBrowseState({
      cardsQuery: { isPending: true },
    })

    await act(async () => {
      root.render(<BrowseCardTable browse={mockBrowsePending} />)
    })
    expect(container.textContent).toContain('Đang tìm thẻ...')

    // Transition to loaded state
    const mockBrowseLoaded = createMockBrowseState({
      cardsQuery: { isPending: false, data: { total: 1, pages: 1 } },
      cards: [
        {
          card_id: '101',
          word: '日本語',
          reading: 'にほんご',
          meaning: 'Japanese language',
          status: 'learning',
          due_label: 'Hôm nay',
        },
      ],
    })

    await act(async () => {
      root.render(<BrowseCardTable browse={mockBrowseLoaded} />)
    })

    expect(container.textContent).toContain('日本語')
    expect(container.textContent).toContain('にほんご')
    expect(container.textContent).toContain('Japanese language')
  })
})
