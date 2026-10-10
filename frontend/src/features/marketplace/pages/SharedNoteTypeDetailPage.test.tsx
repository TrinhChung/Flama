// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { appApi } from '@/app/api'
import { SharedNoteTypeDetailPage } from './SharedNoteTypeDetailPage'

vi.mock('@/app/api', () => ({
  appApi: {
    get: vi.fn(),
    mutate: vi.fn(),
  },
}))

vi.mock('react-i18next', async (importOriginal) => ({
  ...await importOriginal<typeof import('react-i18next')>(),
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) => options?.defaultValue ?? key,
    i18n: { language: 'vi' },
  }),
}))

vi.mock('@/components/ambient-background', () => ({
  AmbientBackground: () => null,
}))

vi.mock('@/entities/flashcard', () => ({
  CardPreviewPanel: () => <div data-testid="card-preview">CardPreview</div>,
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('SharedNoteTypeDetailPage', () => {
  let container: HTMLDivElement
  let root: Root
  let client: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  })

  afterEach(() => {
    act(() => root.unmount())
    client.clear()
    container.remove()
  })

  async function settle() {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30))
    })
  }

  const mockNoteTypeDetail = {
    id: 'nt-101',
    name: 'Kanji N2 Pro',
    title: 'Kanji N2 Pro',
    description: 'Chi tiết Note Type',
    primary_category: 'Kanji',
    pricing_mode: 'free',
    price_display: 'Miễn phí',
    rating_avg: 4.8,
    rating_count: 12,
    install_count: 55,
    is_installed: false,
    is_owner: false,
    is_saved: false,
    can_rate: false,
    field_defs: [
      { name: 'Kanji', label: 'Kanji', type: 'text' },
      { name: 'Onyomi', label: 'Onyomi', type: 'text' },
    ],
    templates: [
      {
        id: 'tmpl-1',
        name: 'Kanji Card 1',
        is_installed: false,
        installed_template_id: null,
      },
      {
        id: 'tmpl-2',
        name: 'Kanji Card 2 (Installed)',
        is_installed: true,
        installed_template_id: 'local-tmpl-222',
      },
    ],
  }

  it('renders templates with separate install buttons and handles individual template install', async () => {
    vi.mocked(appApi.get).mockResolvedValue(mockNoteTypeDetail)
    vi.mocked(appApi.mutate).mockResolvedValue({
      local_template_id: 'local-new-111',
      source_template_id: 'tmpl-1',
      already_installed: false,
    })

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={['/marketplace/note-types/nt-101']}>
            <Routes>
              <Route
                path="/marketplace/note-types/:id"
                element={<SharedNoteTypeDetailPage />}
              />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      )
    })
    await settle()

    expect(container.textContent).toContain('Kanji N2 Pro')
    expect(container.textContent).toContain('Kanji Card 1')
    expect(container.textContent).toContain('Kanji Card 2 (Installed)')

    // Check that tmpl-2 has the "Trong thư viện" link
    const installedLink = container.querySelector(
      'a[href="/card-templates/local-tmpl-222"]'
    )
    expect(installedLink).not.toBeNull()
    expect(installedLink?.textContent).toContain('Trong thư viện')

    // Find the "Thêm vào thư viện" button for tmpl-1
    const buttons = Array.from(container.querySelectorAll('button'))
    const addTemplateBtn = buttons.find((btn) =>
      btn.textContent?.includes('Thêm vào thư viện')
    )
    expect(addTemplateBtn).toBeDefined()

    // Click to install template
    await act(async () => {
      addTemplateBtn?.click()
    })
    await settle()

    expect(appApi.mutate).toHaveBeenCalledWith(
      '/api/shared/note-types/nt-101/templates/tmpl-1/install',
      'POST'
    )
  })

  it('displays owner badge for owner account without install buttons', async () => {
    vi.mocked(appApi.get).mockResolvedValue({
      ...mockNoteTypeDetail,
      is_owner: true,
    })

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={['/marketplace/note-types/nt-101']}>
            <Routes>
              <Route
                path="/marketplace/note-types/:id"
                element={<SharedNoteTypeDetailPage />}
              />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      )
    })
    await settle()

    expect(container.textContent).toContain('Của bạn')
    const addBtns = Array.from(container.querySelectorAll('button')).filter((b) =>
      b.textContent?.includes('Thêm vào thư viện')
    )
    expect(addBtns).toHaveLength(0)
  })
})
