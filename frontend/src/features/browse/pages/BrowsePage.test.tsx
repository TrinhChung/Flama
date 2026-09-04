// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrowsePage } from './BrowsePage'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  mockUrlDeckId: null as string | null,
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  }
})

vi.mock('../hooks/useBrowseState', () => ({
  useBrowseState: () => ({
    urlDeckId: mocks.mockUrlDeckId,
    audioPlayerRef: { current: null },
    setIsTtsModalOpen: vi.fn(),
    isLocalAudioModalOpen: false,
    setIsLocalAudioModalOpen: vi.fn(),
    localAudioEngineId: 'voicevox',
    setLocalAudioEngineId: vi.fn(),
    localAudioDefaultVoiceId: '3',
    setLocalAudioDefaultVoiceId: vi.fn(),
    localAudioTargetCardIds: [],
    setLocalAudioTargetCardIds: vi.fn(),
    selectedCards: [],
    activeCardId: null,
    availableSourceFieldNames: [],
    availableAudioFieldNames: [],
    mobileTab: 'cards',
    setMobileTab: vi.fn(),
    cardsQuery: { data: { items: [] }, refetch: vi.fn() },
    selectedDeckId: 1,
    setWorksheetTargetDeckId: vi.fn(),
    setWorksheetTargetCardIds: vi.fn(),
    setIsWorksheetModalOpen: vi.fn(),
    setStrokeModalMode: vi.fn(),
    setIsStrokeModalOpen: vi.fn(),
    isStrokeModalOpen: false,
    strokeModalMode: 'batch',
    strokeModalCardId: null,
    isWorksheetModalOpen: false,
    cardDetailQuery: { refetch: vi.fn() },
  }),
}))

vi.mock('../components/BrowseDeckSidebar', () => ({
  BrowseDeckSidebar: () => <div data-testid="mock-deck-sidebar" />,
}))
vi.mock('../components/BrowseToolbar', () => ({
  BrowseToolbar: () => <div data-testid="mock-toolbar" />,
}))
vi.mock('../components/BrowseCardTable', () => ({
  BrowseCardTable: () => <div data-testid="mock-card-table" />,
}))
vi.mock('../components/BrowseCardEditor', () => ({
  BrowseCardEditor: () => <div data-testid="mock-card-editor" />,
}))
vi.mock('../components/BrowseTtsModal', () => ({
  BrowseTtsModal: () => null,
}))
vi.mock('../components/BrowseStrokeModal', () => ({
  BrowseStrokeModal: () => null,
}))
vi.mock('@/features/worksheets', () => ({
  DeckWorksheetModal: () => null,
}))
vi.mock('@/features/audio/components/LocalAudioDialog', () => ({
  LocalAudioDialog: () => null,
}))
vi.mock('@/features/guide', () => ({
  ContextHelpButton: () => <div data-testid="mock-guide-button" />,
}))
vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: {
      user: { id: 1, username: 'testuser' },
      links: { dashboard: '/dashboard' },
    },
  }),
}))

describe('BrowsePage Header Navigation (Issue #135)', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    mocks.navigate.mockReset()
    mocks.mockUrlDeckId = null
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  it('always renders the Home ("Trang chủ") button linking to /dashboard in standalone mode', async () => {
    mocks.mockUrlDeckId = null

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <BrowsePage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    // Find dedicated Home button linking to /dashboard
    const allHomeLinks = Array.from(container.querySelectorAll('a[href="/dashboard"]'))
    const dedicatedHomeBtn = allHomeLinks.find((el) => el.textContent?.includes('Trang chủ'))
    expect(dedicatedHomeBtn).toBeDefined()
    expect(dedicatedHomeBtn?.getAttribute('href')).toBe('/dashboard')

    // Back to study button should NOT be present when urlDeckId is absent
    const backToStudyBtn = Array.from(container.querySelectorAll('button')).find((btn) =>
      btn.textContent?.includes('Quay lại bài học'),
    )
    expect(backToStudyBtn).toBeUndefined()
  })

  it('renders both Home and "Quay lại bài học" buttons when entered with urlDeckId', async () => {
    mocks.mockUrlDeckId = '42'

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <BrowsePage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    // 1. Home link must be present and point directly to /dashboard
    const allHomeLinks = Array.from(container.querySelectorAll('a[href="/dashboard"]'))
    const dedicatedHomeBtn = allHomeLinks.find((el) => el.textContent?.includes('Trang chủ'))
    expect(dedicatedHomeBtn).toBeDefined()
    expect(dedicatedHomeBtn?.getAttribute('href')).toBe('/dashboard')

    // 2. Back to study button must be present
    const backToStudyBtn = Array.from(container.querySelectorAll('button')).find((btn) =>
      btn.textContent?.includes('Quay lại bài học') || btn.textContent?.includes('Bài học'),
    )
    expect(backToStudyBtn).toBeDefined()

    // 3. Clicking "Quay lại bài học" navigates back to /study?deck_id=42
    await act(async () => {
      backToStudyBtn?.click()
    })
    expect(mocks.navigate).toHaveBeenCalledWith('/study?deck_id=42')
  })

  it('preserves the Brand logo link to home at all times', async () => {
    mocks.mockUrlDeckId = '42'

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <BrowsePage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    // Brand logo image should be present inside a link pointing to /dashboard
    const logoImg = container.querySelector('img[src="/logo.png"]')
    expect(logoImg).not.toBeNull()
    const brandLink = logoImg?.closest('a')
    expect(brandLink?.getAttribute('href')).toBe('/dashboard')
    expect(brandLink?.textContent).toContain('Flama')
  })
})
