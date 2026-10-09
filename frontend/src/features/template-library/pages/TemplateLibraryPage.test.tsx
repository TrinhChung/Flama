// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchTemplateLibrary, type TemplateLibraryItem } from '@/entities/card-template'
import { TemplateLibraryPage } from './TemplateLibraryPage'
vi.mock('@/entities/card-template', async (original) => ({ ...await original<typeof import('@/entities/card-template')>(), fetchTemplateLibrary: vi.fn() }))
const template: TemplateLibraryItem = { id: 't/1', owner_user_id: 1, name: 'Reusable', description: 'Description', primary_category: null, origin: 'authored', source_template_id: null, source_version_id: null, current_version_id: 'v1', front_html: '', back_html: '', shared_css: '', archived_at: null, created_at: null, updated_at: null, application_count: 2, note_type_count: 1, input_schema: Array.from({ length: 6 }, (_, n) => ({ key: `Key${n}`, label: `Key${n}`, type: 'text', required: false })) }
async function flush(ms = 20) { await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) }) }
describe('TemplateLibraryPage', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(fetchTemplateLibrary).mockResolvedValue({ schema_version: 'template-library.v2', items: [template] }); client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); container = document.createElement('div'); document.body.append(container); root = createRoot(container) })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = '' })
  async function render() { await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter><TemplateLibraryPage /></MemoryRouter></QueryClientProvider>)); await flush() }
  it('fetches defaults and shows distinct NoteType/application counts and four tokens', async () => {
    await render(); expect(fetchTemplateLibrary).toHaveBeenCalledWith({}, expect.any(AbortSignal)); expect(container.textContent).toContain('Dùng ở 1 loại thẻ · 2 lần gắn'); expect(container.querySelectorAll('code')).toHaveLength(4); expect(container.textContent).toContain('+2'); expect(container.querySelector('a')?.getAttribute('href')).toBe('/card-templates/t%2F1')
  })
  it('supports all five groups', async () => {
    await render()
    for (const [label, group] of [['Của tôi', 'mine'], ['Marketplace', 'market'], ['Mẫu độc lập', 'standalone'], ['Đang dùng', 'in_use'], ['Tất cả', 'all']]) {
      await act(async () => [...container.querySelectorAll('button')].find((el) => el.textContent === label)!.click()); await flush()
      expect(fetchTemplateLibrary).toHaveBeenCalledWith(group === 'all' ? {} : { group }, expect.any(AbortSignal))
    }
  })
  it('makes archived templates discoverable without including them by default', async () => {
    vi.mocked(fetchTemplateLibrary).mockImplementation(async (params) => ({ schema_version: 'template-library.v2', items: params?.include_archived ? [{ ...template, archived_at: '2026-10-08T00:00:00Z' }] : [] }))
    await render()
    expect(container.querySelector('a[href="/card-templates/t%2F1"]')).toBeNull()
    await act(async () => container.querySelector<HTMLInputElement>('input[type="checkbox"]')!.click()); await flush()
    expect(fetchTemplateLibrary).toHaveBeenLastCalledWith({ include_archived: true }, expect.any(AbortSignal))
    expect(container.textContent).toContain('Đã lưu trữ')
    expect(container.querySelector('a')?.getAttribute('href')).toBe('/card-templates/t%2F1')
  })
  it('debounces the final query and waits until Japanese IME composition ends', async () => {
    await render(); const input = container.querySelector('input')!
    const enter = async (value: string) => act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value); input.dispatchEvent(new Event('input', { bubbles: true })) })
    await act(async () => input.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }))); await enter('に'); await flush(330); expect(fetchTemplateLibrary).toHaveBeenCalledTimes(1)
    await enter('日本語'); await act(async () => input.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true }))); await flush(330)
    expect(fetchTemplateLibrary).toHaveBeenLastCalledWith({ q: '日本語' }, expect.any(AbortSignal))
  })
  it('renders errors with retry and empty results', async () => {
    vi.mocked(fetchTemplateLibrary).mockRejectedValueOnce(new Error('offline')); await render(); expect(container.textContent).toContain('offline')
    vi.mocked(fetchTemplateLibrary).mockResolvedValue({ schema_version: 'template-library.v2', items: [] })
    await act(async () => [...container.querySelectorAll('button')].find((el) => el.textContent === 'Thử lại')!.click()); await flush(); expect(container.textContent).toContain('Chưa có mẫu thẻ nào.')
  })
  it('shows loading while the request remains pending', async () => { vi.mocked(fetchTemplateLibrary).mockReturnValue(new Promise(() => {})); await render(); expect(container.textContent).toContain('Đang tải mẫu thẻ…') })
})
