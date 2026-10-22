// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import '@/shared/config/i18n'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { publishNoteTypeApi, type PublishTemplateOption } from '../api/publishNoteTypeApi'
import { MarketplacePublishNoteTypePage } from './MarketplacePublishNoteTypePage'

vi.mock('../api/publishNoteTypeApi', () => ({ publishNoteTypeApi: { listNoteTypes: vi.fn(), detail: vi.fn(), options: vi.fn(), publish: vi.fn() } }))
vi.mock('@/components/ambient-background', () => ({ AmbientBackground: () => null }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock('@/features/marketplace', async (original) => ({
  ...await original<typeof import('@/features/marketplace')>(),
  useTaxonomySchema: () => ({ domains: [], subjectsByDomain: () => [], frameworksForSubject: () => [], goalsForSubject: () => [], topicsForSubject: () => [], difficulties: [] }),
}))

const option = (overrides: Partial<PublishTemplateOption> = {}): PublishTemplateOption => ({
  template_id: 'own-new', source_template_id: 'own-new', name: 'Own new template', author: { id: 1, username: 'alice' },
  is_owned: true, requires_publication: true, release_id: null, marketplace_status: 'private',
  description: 'Own template description', primary_category: 'Từ vựng', pricing_mode: 'paid', price_amount_minor: 25000,
  ...overrides,
})
async function settle() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)) }) }
async function input(selector: string, value: string) {
  await act(async () => {
    const element = document.querySelector<HTMLInputElement>(selector)!
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

describe('Note type bundle publication', () => {
  let container: HTMLDivElement
  let root: Root
  let client: QueryClient
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('scrollTo', vi.fn())
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    vi.mocked(publishNoteTypeApi.listNoteTypes).mockResolvedValue({ items: [{ id: 'nt-1', name: 'Vocabulary', publish_status: 'published' }] })
    vi.mocked(publishNoteTypeApi.detail).mockResolvedValue({ id: 'nt-1', name: 'Vocabulary', title: 'Vocabulary', preview_text: 'Preview', description: 'A field structure', pricing_mode: 'paid', price_amount_minor: 15000, primary_category: 'Vocabulary', fields: [], templates: [] })
    vi.mocked(publishNoteTypeApi.options).mockResolvedValue({ note_type_id: 'nt-1', templates: [
      option(),
      option({ template_id: 'own-listed', source_template_id: 'own-listed', name: 'Own published', requires_publication: false, release_id: 'r-own', marketplace_status: 'published', price_amount_minor: 40000 }),
      option({ template_id: 'attached-bob', source_template_id: 'bob-original', name: 'Bob template', author: { id: 2, username: 'bob' }, is_owned: false, requires_publication: false, release_id: 'r-bob', marketplace_status: 'published', price_amount_minor: 30000 }),
    ] })
  })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); vi.unstubAllGlobals() })

  async function openPricing() {
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/marketplace/note-types/publish?id=nt-1&edit=1']}><Routes><Route path="/marketplace/note-types/publish" element={<MarketplacePublishNoteTypePage />} /><Route path="/marketplace/note-types/nt-1" element={<div>Published</div>} /></Routes></MemoryRouter></QueryClientProvider>))
    await settle()
    await act(async () => [...container.querySelectorAll('button')].find((button) => button.textContent?.includes('Giá bán & Đăng tải'))!.click())
    await settle()
  }

  it('publishes own new listings and preserves foreign references and independent bundle price', async () => {
    await openPricing()
    expect(container.querySelector('a[href="/marketplace/templates/bob-original"]')).not.toBeNull()
    expect(container.querySelector('#bundle-template-attached-bob-price')).toBeNull()
    expect(container.querySelector('#bundle-template-own-listed-price')).toBeNull()
    expect(container.textContent).toContain('45.000 đ')
    await input('#bundle-template-own-new-price', '12000')
    await act(async () => [...container.querySelectorAll<HTMLButtonElement>('form button')].at(-1)!.click())
    await settle()
    expect(publishNoteTypeApi.publish).toHaveBeenCalledWith('nt-1', expect.objectContaining({
      pricing_mode: 'paid', price_amount_minor: 15000,
      template_listings: [{ template_id: 'own-new', description: 'Own template description', primary_category: 'Từ vựng', pricing_mode: 'paid', price_amount_minor: 12000 }],
    }))
  })

  it('requires a valid individual paid price before publishing an unpublished template', async () => {
    await openPricing()
    await input('#bundle-template-own-new-price', '500')
    await act(async () => [...container.querySelectorAll<HTMLButtonElement>('form button')].at(-1)!.click())
    expect(publishNoteTypeApi.publish).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Giá bán tối thiểu là 1.000 đ.')
  })
})
