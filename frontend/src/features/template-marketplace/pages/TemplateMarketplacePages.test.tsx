// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import '@/shared/config/i18n'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchMarketTemplate, fetchMarketTemplates, installMarketTemplate, previewMarketTemplate } from '../api/templateMarketApi'
import type { MarketTemplateDetail, MarketTemplateItem } from '../model/types'
import { TemplateMarketDetailPage } from './TemplateMarketDetailPage'
import { TemplateMarketplacePage } from './TemplateMarketplacePage'

vi.mock('../api/templateMarketApi', async (original) => ({
  ...await original<typeof import('../api/templateMarketApi')>(),
  fetchMarketTemplates: vi.fn(), fetchMarketTemplate: vi.fn(), previewMarketTemplate: vi.fn(), installMarketTemplate: vi.fn(),
}))
vi.mock('@/components/ambient-background', () => ({ AmbientBackground: () => null }))
vi.mock('@/entities/flashcard', () => ({ CardPreviewPanel: () => <div data-testid="card-preview" /> }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const item = (overrides: Partial<MarketTemplateItem> = {}): MarketTemplateItem => ({
  id: 'tpl-1', name: 'Kanji Card', description: 'Thẻ kanji gọn', primary_category: 'Kanji / Hán tự',
  pricing_mode: 'free', price_amount_minor: 0, price_display: 'Miễn phí', install_count: 12,
  published_at: null, version_label: '1.0.0', release_published_at: null,
  inputs: [{ key: 'word', label: 'Từ vựng', type: 'text' }], input_count: 1,
  author: { id: 1, username: 'tac-gia' }, is_owner: false, is_installed: false, installed_template_id: null,
  is_purchased: false, is_listed: true, ...overrides,
})
const detail = (overrides: Partial<MarketTemplateDetail> = {}): MarketTemplateDetail => ({
  ...item(), release_change_note: null, updated_at: null, recent_releases: [], ...overrides,
})

async function flush(ms = 30) { await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) }) }
function button(label: string) { return [...document.querySelectorAll('button')].find((el) => el.textContent?.trim() === label) }

describe('template marketplace pages', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  beforeEach(() => {
    vi.clearAllMocks()
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    vi.mocked(previewMarketTemplate).mockResolvedValue({ front_html: '<div>Từ vựng</div>', back_html: '' })
  })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = '' })
  async function render(path: string) {
    await act(async () => root.render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/marketplace/templates" element={<TemplateMarketplacePage />} />
            <Route path="/marketplace/templates/:id" element={<TemplateMarketDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ))
    await flush()
  }

  it('lists templates with category filters and searches by keyword', async () => {
    vi.mocked(fetchMarketTemplates).mockResolvedValue({
      items: [item()], categories: [{ name: 'Kanji / Hán tự', count: 1 }],
      pagination: { page: 1, page_size: 24, total: 1, has_more: false },
    })
    await render('/marketplace/templates')
    expect(container.textContent).toContain('Chợ Giao diện thẻ')
    expect(container.textContent).toContain('Kanji Card')
    expect(container.textContent).toContain('Từ vựng')
    expect(container.querySelector('a[href="/marketplace/templates/tpl-1"]')).not.toBeNull()
    expect(button('Kanji / Hán tự1') ?? [...container.querySelectorAll('button')].find((el) => el.textContent?.includes('Kanji / Hán tự'))).toBeDefined()

    await act(async () => {
      const input = container.querySelector<HTMLInputElement>('input[type="search"]')!
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'kanji')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await flush(320)
    expect(vi.mocked(fetchMarketTemplates).mock.calls.at(-1)?.[0]).toMatchObject({ q: 'kanji', sort: 'newest', page: 1 })
  })

  it('downloads a free template into the library', async () => {
    vi.mocked(fetchMarketTemplate).mockResolvedValue(detail())
    vi.mocked(installMarketTemplate).mockResolvedValue({ local_template_id: 'local-1', already_installed: false })
    await render('/marketplace/templates/tpl-1')
    expect(container.textContent).toContain('Giao diện tải về hoặc mua từ chợ chỉ để dùng — không thể đăng hay bán lại.')
    await act(async () => button('Tải về thư viện')!.click())
    await flush()
    expect(installMarketTemplate).toHaveBeenCalledWith('tpl-1')
  })

  it('asks to buy a paid template and links an installed one to the library', async () => {
    vi.mocked(fetchMarketTemplate).mockResolvedValue(detail({ pricing_mode: 'paid', price_amount_minor: 25000, price_display: '25.000 đ' }))
    await render('/marketplace/templates/tpl-1')
    expect(button('Mua · 25.000 đ')).toBeDefined()

    await act(async () => root.unmount())
    root = createRoot(container)
    client.clear()
    vi.mocked(fetchMarketTemplate).mockResolvedValue(detail({ is_installed: true, installed_template_id: 'local-1' }))
    await render('/marketplace/templates/tpl-1')
    expect(container.querySelector('a[href="/card-templates/local-1"]')).not.toBeNull()
    expect(button('Tải về thư viện')).toBeUndefined()
  })
})
