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
  LazyDeckWorksheetModal: () => null,
}))
vi.mock('@/features/audio/components/LocalAudioDialog', () => ({
  LocalAudioDialog: () => null,
}))
vi.mock('@/features/guide/components/ContextHelpButton', () => ({
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

describe('BrowsePage Header Navigation & Responsive Actions (Issue #135)', () => {
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

  it('preserves the Brand logo link to /dashboard at all times without redundant Home button', async () => {
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

    // Brand logo image links to /dashboard
    const logoImg = container.querySelector('img[src="/logo.png"]')
    expect(logoImg).not.toBeNull()
    const brandLink = logoImg?.closest('a')
    expect(brandLink?.getAttribute('href')).toBe('/dashboard')
    expect(brandLink?.textContent).toContain('Flama')

    // No separate redundant "Trang chủ" button
    const allButtons = Array.from(container.querySelectorAll('button'))
    const homeBtn = allButtons.find((btn) => btn.textContent?.includes('Trang chủ'))
    expect(homeBtn).toBeUndefined()

    // Back to study button should NOT be present when urlDeckId is absent
    const backToStudyBtn = allButtons.find((btn) => btn.textContent?.includes('Quay lại bài học'))
    expect(backToStudyBtn).toBeUndefined()
  })

  it('renders "Quay lại bài học" button when entered with urlDeckId and navigates on click', async () => {
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

    // Back to study button must be present
    const backToStudyBtn = Array.from(container.querySelectorAll('button')).find((btn) =>
      btn.textContent?.includes('Quay lại bài học') || btn.textContent?.includes('Bài học'),
    )
    expect(backToStudyBtn).toBeDefined()

    // Clicking "Quay lại bài học" navigates back to /study?deck_id=42
    await act(async () => {
      backToStudyBtn?.click()
    })
    expect(mocks.navigate).toHaveBeenCalledWith('/study?deck_id=42')
  })

  it('renders both desktop action toolbar and mobile consolidated action dropdown', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <BrowsePage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    // Desktop action container exists (hidden on small screens)
    const desktopContainer = container.querySelector('.hidden.sm\\:flex')
    expect(desktopContainer).not.toBeNull()
    expect(desktopContainer?.textContent).toContain('In bài tập')
    expect(desktopContainer?.textContent).toContain('Tạo nét SVG')

    // Mobile action dropdown trigger exists (visible on mobile only)
    const mobileContainer = container.querySelector('.flex.sm\\:hidden')
    expect(mobileContainer).not.toBeNull()
    const mobileTrigger = mobileContainer?.querySelector('button[aria-label="Menu tác vụ"]')
    expect(mobileTrigger).not.toBeNull()
    expect(mobileTrigger?.textContent).toContain('Tác vụ')
  })
})
