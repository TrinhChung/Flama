// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import '@/shared/config/i18n'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchLibraryTemplate, fetchTemplateLibrary, updateLibraryTemplate, type TemplateLibraryDetail, type TemplateLibraryResponse } from '@/entities/card-template'
import { fetchTemplateListing, updateTemplateListing } from '../api/templateMarketApi'
import type { TemplateListing } from '../model/types'
import { PublishTemplateDialog } from './PublishTemplateDialog'

vi.mock('@/entities/card-template', async (original) => ({
  ...await original<typeof import('@/entities/card-template')>(),
  fetchLibraryTemplate: vi.fn(), fetchTemplateLibrary: vi.fn(), updateLibraryTemplate: vi.fn(),
}))
vi.mock('../api/templateMarketApi', async (original) => ({
  ...await original<typeof import('../api/templateMarketApi')>(),
  fetchTemplateListing: vi.fn(), updateTemplateListing: vi.fn(),
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const listing = (overrides: Partial<TemplateListing> = {}): TemplateListing => ({
  template_id: 'tpl-1', can_publish: true, block_code: null, block_reason: null, missing_requirements: [],
  marketplace_status: 'private', pricing_mode: 'free', price_amount_minor: 0, price_display: 'Miễn phí',
  published_at: null, current_release: null, has_unpublished_changes: true, install_count: 0, ...overrides,
})
const template = { id: 'tpl-1', name: 'Kanji Card', description: 'Thẻ kanji', primary_category: 'Kanji / Hán tự', origin: 'authored' } as TemplateLibraryDetail

async function flush() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) }) }
function button(label: string) { return [...document.querySelectorAll('button')].find((el) => el.textContent?.trim() === label) }
async function type(selector: string, value: string) {
  await act(async () => {
    const input = document.querySelector<HTMLInputElement>(selector)!
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

describe('PublishTemplateDialog', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  beforeEach(() => {
    vi.clearAllMocks()
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    vi.mocked(fetchLibraryTemplate).mockResolvedValue(template)
  })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = '' })
  async function render(templateId?: string) {
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter><PublishTemplateDialog open onOpenChange={() => {}} templateId={templateId} /></MemoryRouter></QueryClientProvider>))
    await flush()
  }

  it('refuses to publish or sell a template downloaded from the marketplace', async () => {
    vi.mocked(fetchTemplateListing).mockResolvedValue(listing({ can_publish: false, block_code: 'MARKET_TEMPLATE_REPUBLISH_FORBIDDEN', block_reason: 'x' }))
    await render('tpl-1')
    expect(document.body.textContent).toContain('Đây là giao diện tải về từ chợ nên không thể đăng hay bán lại.')
    expect(button('Đăng lên chợ')).toBeUndefined()
    expect(updateTemplateListing).not.toHaveBeenCalled()
  })

  it('lists a paid template at the entered price without rewriting unchanged details', async () => {
    vi.mocked(fetchTemplateListing).mockResolvedValue(listing())
    vi.mocked(updateTemplateListing).mockResolvedValue(listing({ marketplace_status: 'published', pricing_mode: 'paid', price_amount_minor: 25000 }))
    await render('tpl-1')
    await act(async () => document.querySelector<HTMLInputElement>('input[name="market-template-pricing"][value="paid"]')!.click())
    await type('#market-template-price', '500')
    await act(async () => button('Đăng lên chợ')!.click())
    expect(document.body.textContent).toContain('Giá bán tối thiểu là 1.000 đ.')
    expect(updateTemplateListing).not.toHaveBeenCalled()
    await type('#market-template-price', '25000')
    await act(async () => button('Đăng lên chợ')!.click())
    await flush()
    expect(updateLibraryTemplate).not.toHaveBeenCalled()
    expect(updateTemplateListing).toHaveBeenCalledWith('tpl-1', { marketplace_status: 'published', pricing_mode: 'paid', price_amount_minor: 25000 })
  })

  it('saves a new category on the template before listing it', async () => {
    vi.mocked(fetchTemplateListing).mockResolvedValue(listing())
    vi.mocked(updateTemplateListing).mockResolvedValue(listing({ marketplace_status: 'published' }))
    await render('tpl-1')
    await act(async () => button('Từ vựng')!.click())
    await act(async () => button('Đăng lên chợ')!.click())
    await flush()
    expect(updateLibraryTemplate).toHaveBeenCalledWith('tpl-1', { primary_category: 'Từ vựng' })
    expect(updateTemplateListing).toHaveBeenCalledWith('tpl-1', { marketplace_status: 'published', pricing_mode: 'free', price_amount_minor: 0 })
  })

  it('unlists a listed template', async () => {
    vi.mocked(fetchTemplateListing).mockResolvedValue(listing({ marketplace_status: 'published', install_count: 3 }))
    vi.mocked(updateTemplateListing).mockResolvedValue(listing())
    await render('tpl-1')
    expect(document.body.textContent).toContain('Đang đăng trên chợ · 3 lượt tải')
    await act(async () => button('Gỡ khỏi chợ')!.click())
    await flush()
    expect(updateTemplateListing).toHaveBeenCalledWith('tpl-1', { marketplace_status: 'private' })
  })

  it('offers only the author\'s own templates when none is preselected', async () => {
    vi.mocked(fetchTemplateLibrary).mockResolvedValue({ schema_version: 'template-library.v2', items: [{ ...template, application_count: 0, note_type_count: 0 }] } as unknown as TemplateLibraryResponse)
    vi.mocked(fetchTemplateListing).mockResolvedValue(listing())
    await render()
    expect(vi.mocked(fetchTemplateLibrary).mock.calls[0][0]).toMatchObject({ group: 'mine' })
    expect(document.body.textContent).toContain('Bản tải về từ chợ không thể đăng hay bán lại.')
    await act(async () => [...document.querySelectorAll('button')].find((el) => el.textContent?.includes('Kanji Card'))!.click())
    await flush()
    expect(fetchTemplateListing).toHaveBeenCalledWith('tpl-1', expect.anything())
    expect(button('Đăng lên chợ')).toBeDefined()
  })
})
