// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiRequest, apiJson } from '@/shared/api/client'
import { SharedNoteTypeDetailPage } from './SharedNoteTypeDetailPage'
import { toast } from 'sonner'

vi.mock('@/shared/api/client', () => ({ apiRequest: vi.fn(), apiJson: vi.fn() }))

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
  CardPreviewPanel: ({ templates, selectedTemplateId, onSelectTemplate, frontHtml }: {
    templates: { id: string; name: string }[]
    selectedTemplateId?: string
    onSelectTemplate: (id: string) => void
    frontHtml?: string
  }) => <div data-testid="card-preview">
    <select data-testid="preview-template-selector" value={selectedTemplateId || ''} onChange={(event) => onSelectTemplate(event.target.value)}>
      {templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
    </select>
    <span>{frontHtml}</span>
  </div>,
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
        is_owned_by_author: true,
        is_installed: false,
        installed_template_id: null,
      },
      {
        id: 'tmpl-2',
        name: 'Kanji Card 2 (Installed)',
        is_owned_by_author: true,
        is_installed: true,
        installed_template_id: 'local-tmpl-222',
      },
    ],
  }

  it('renders templates with separate install buttons and handles individual template install', async () => {
    vi.mocked(apiRequest).mockResolvedValue(mockNoteTypeDetail)
    vi.mocked(apiJson).mockResolvedValue({
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
    expect([...container.querySelectorAll<HTMLOptionElement>('[data-testid="preview-template-selector"] option')].map((option) => option.value)).toEqual(['tmpl-1', 'tmpl-2'])
    expect(apiJson).toHaveBeenCalledWith('/api/marketplace/note-types/nt-101/templates/tmpl-1/preview', 'POST')

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

    expect(apiJson).toHaveBeenCalledWith(
      '/api/marketplace/note-types/nt-101/templates/tmpl-1/install',
      'POST'
    )
  })

  it('displays owner badge for owner account without install buttons', async () => {
    vi.mocked(apiRequest).mockResolvedValue({
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

  it('keeps foreign authorship on an owned note type and shows no repeated fee for existing rights', async () => {
    vi.mocked(apiRequest).mockResolvedValue({
      ...mockNoteTypeDetail,
      is_owner: true,
      templates: [
        { ...mockNoteTypeDetail.templates[0], author: { id: 1, username: 'alice' }, source_template_id: 'original-alice' },
        { ...mockNoteTypeDetail.templates[1], is_owned_by_author: false, author: { id: 2, username: 'bob' }, source_template_id: 'original-bob', pricing_mode: 'paid', price_amount_minor: 30000, already_entitled: true },
      ],
      pricing_breakdown: {
        bundle_amount_minor: 20000, template_amount_minor: 0, total_amount_minor: 20000, payment_required: true,
        templates: [{ template_id: 'original-bob', name: 'Bob original', author: { id: 2, username: 'bob' }, pricing_mode: 'paid', price_amount_minor: 30000, charge_amount_minor: 0, is_owned_by_author: false, already_entitled: true }],
      },
    })
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/marketplace/note-types/nt-101']}><Routes><Route path="/marketplace/note-types/:id" element={<SharedNoteTypeDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>))
    await settle()
    expect(container.textContent).toContain('bob')
    expect(container.textContent).toContain('20.000 đ')
    expect(container.textContent).toContain('30.000 đ')
    expect(container.textContent).toContain('bundle.already_entitled')
    expect([...container.querySelectorAll('[data-slot="badge"]')].filter((badge) => badge.textContent === 'Của bạn')).toHaveLength(1)
    expect(container.querySelector('a[href="/marketplace/templates/original-bob"]')).not.toBeNull()
  })

  it('does not report template installation success when checkout is required', async () => {
    vi.mocked(apiRequest).mockResolvedValue({ ...mockNoteTypeDetail, templates: [{ ...mockNoteTypeDetail.templates[0], pricing_mode: 'paid', price_amount_minor: 30000, already_entitled: false }] })
    vi.mocked(apiJson).mockResolvedValue({ payment_required: true, order: { active_attempt: null } })
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/marketplace/note-types/nt-101']}><Routes><Route path="/marketplace/note-types/:id" element={<SharedNoteTypeDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>))
    await settle()
    await act(async () => [...container.querySelectorAll('button')].find((button) => button.textContent?.trim() === 'bundle.buy_template')!.click())
    await settle()
    expect(apiJson).toHaveBeenCalledWith('/api/marketplace/note-types/nt-101/templates/tmpl-1/install', 'POST')
    expect(toast.success).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenCalledWith('bundle.checkout_unavailable')
  })

  it('disables both bundle install actions when a referenced template is unavailable', async () => {
    vi.mocked(apiRequest).mockResolvedValue({ ...mockNoteTypeDetail, pricing_breakdown: { available: false, bundle_amount_minor: 0, template_amount_minor: 0, total_amount_minor: 0, payment_required: false, templates: [] } })
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/marketplace/note-types/nt-101']}><Routes><Route path="/marketplace/note-types/:id" element={<SharedNoteTypeDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>))
    await settle()
    expect(container.textContent).toContain('bundle.unavailable')
    const installButtons = [...container.querySelectorAll('button')].filter((button) => button.textContent?.includes('notetype_detail.btn_install'))
    expect(installButtons).toHaveLength(2)
    expect(installButtons.every((button) => button.disabled)).toBe(true)
  })

  it('selects repeated template occurrences by application while purchasing the canonical source', async () => {
    vi.mocked(apiRequest).mockResolvedValue({
      ...mockNoteTypeDetail,
      templates: [
        { id: 'same-template', source_template_id: 'canonical-source', application_id: 'application-front', name: 'First mapping', field_bindings: { prompt: 'Word' } },
        { id: 'same-template', source_template_id: 'canonical-source', application_id: 'application-back', name: 'Second mapping', field_bindings: { prompt: 'Meaning' } },
      ],
    })
    vi.mocked(apiJson).mockImplementation(async (url, _method, body) => {
      if (url.endsWith('/preview')) {
        const application = (body as { application_id?: string } | undefined)?.application_id
        return { front_html: application === 'application-back' ? 'Mapped Meaning' : 'Mapped Word' }
      }
      return { local_template_id: 'local-installed', source_template_id: 'canonical-source', already_installed: false }
    })
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/marketplace/note-types/nt-101']}><Routes><Route path="/marketplace/note-types/:id" element={<SharedNoteTypeDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>))
    await settle()
    expect(apiJson).toHaveBeenCalledWith('/api/marketplace/note-types/nt-101/templates/canonical-source/preview', 'POST', { application_id: 'application-front' })
    for (let attempt = 0; attempt < 5 && !container.textContent?.includes('Mapped Word'); attempt++) await settle()
    expect(container.textContent).toContain('Mapped Word')

    const selector = container.querySelector<HTMLSelectElement>('[data-testid="preview-template-selector"]')!
    expect([...selector.options].map((option) => option.value)).toEqual(['application-front', 'application-back'])
    await act(async () => {
      selector.value = 'application-back'
      selector.dispatchEvent(new Event('change', { bubbles: true }))
    })
    await settle()
    expect(apiJson).toHaveBeenCalledWith('/api/marketplace/note-types/nt-101/templates/canonical-source/preview', 'POST', { application_id: 'application-back' })
    expect(selector.value).toBe('application-back')
    for (let attempt = 0; attempt < 5 && !container.textContent?.includes('Mapped Meaning'); attempt++) await settle()
    expect(container.textContent).toContain('Mapped Meaning')
    expect([...container.querySelectorAll('[data-slot="badge"]')].filter((badge) => badge.textContent === 'Đang xem')).toHaveLength(1)
    expect(container.querySelectorAll('a[href="/marketplace/templates/canonical-source"]')).toHaveLength(2)

    await act(async () => [...container.querySelectorAll<HTMLButtonElement>('button')].filter((button) => button.textContent?.includes('Thêm vào thư viện')).at(-1)!.click())
    await settle()
    expect(apiJson).toHaveBeenCalledWith('/api/marketplace/note-types/nt-101/templates/canonical-source/install', 'POST')
  })
})
