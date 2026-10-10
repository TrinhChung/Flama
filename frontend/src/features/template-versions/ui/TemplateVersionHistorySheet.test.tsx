// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import type { TemplateLibraryDetail, TemplateVersionDetail, TemplateVersionList } from '@/entities/card-template'
import { TemplateVersionHistorySheet } from './TemplateVersionHistorySheet'
import type { TemplateVersionSource } from '../model/types'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { TemplateDetailPage } from '@/features/template-library/pages/TemplateDetailPage'

const api = vi.hoisted(() => ({ get: vi.fn(), mutate: vi.fn(), request: vi.fn(), json: vi.fn() }))
vi.mock('@/app/api', () => ({ appApi: { get: api.get, mutate: api.mutate } }))
vi.mock('@/shared/api/client', async (original) => ({ ...await original<typeof import('@/shared/api/client')>(), apiRequest: api.request, apiJson: api.json }))
vi.mock('@/entities/flashcard/ui/CardPreviewPanel', () => ({ CardPreviewPanel: () => null }))
vi.mock('@/components/ambient-background', () => ({ AmbientBackground: () => null }))

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
const current = { front_html: 'saved', back_html: 'back', shared_css: '' }
const versions: TemplateVersionDetail[] = [3, 2, 1].map((n) => ({
  id: `v${n}`, template_id: 't1', version_no: n, content_hash: `hash${n}`,
  change_note: n === 2 ? 'Second change' : '', origin: n === 1 ? 'market_copy' : 'edit',
  created_at: '2026-10-07T12:00:00Z', created_by: { id: 1, username: 'author' }, is_current: n === 3,
  ...current, front_html: `front${n}`, input_schema: [],
}))
function button(text: string) {
  const item = [...document.querySelectorAll('button')].find((el) => el.textContent?.trim() === text)
  expect(item, text).toBeDefined()
  return item!
}
async function flush() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 15)) }) }
describe('TemplateVersionHistorySheet', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let source: TemplateVersionSource
  const restored = vi.fn()
  const pending = vi.fn()
  beforeEach(() => {
    vi.clearAllMocks()
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    source = {
      listKey: ['history', 't1'], detailKey: (id) => ['history', 't1', id],
      list: vi.fn().mockResolvedValue({ schema_version: 'template-versions.v2', template_id: 't1', current_version_id: 'v3', items: versions } satisfies TemplateVersionList),
      get: vi.fn().mockImplementation(async (id) => versions.find((version) => version.id === id)),
      restore: vi.fn().mockResolvedValue({ id: 't1', note_type_id: null, name: 'Card', ...current, position: 0, is_default: false, updated_at: null }),
    }
  })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = '' })
  async function render(open = true) {
    await act(async () => root.render(<QueryClientProvider client={client}><TemplateVersionHistorySheet open={open} onOpenChange={vi.fn()} source={source} current={current} onRestored={restored} onRestorePendingChange={pending} /></QueryClientProvider>))
    await flush()
  }
  async function choose(n: number) {
    const option = [...document.querySelectorAll('button')].find((el) => el.getAttribute('aria-pressed') !== null && el.textContent?.includes(`Phiên bản ${n}`))!
    await act(async () => option.click()); await flush()
  }
  async function restore() { await act(async () => button('Khôi phục phiên bản này').click()); await act(async () => button('Khôi phục').click()); await flush() }
  it('does not fetch when closed', async () => { await render(false); expect(source.list).not.toHaveBeenCalled(); expect(source.get).not.toHaveBeenCalled() })
  it('lists current, creator, change note and origins and compares selected source', async () => {
    await render(); expect(document.body.textContent).toContain('Hiện tại'); expect(document.body.textContent).toContain('Bản nhận marketplace'); expect(document.body.textContent).toContain('Second change')
    await choose(1); expect(source.get).toHaveBeenCalledWith('v1', expect.any(AbortSignal)); expect(document.body.textContent).toContain('So sánh Phiên bản 1 → Trình soạn hiện tại')
    await choose(3); expect([...document.querySelectorAll('button')].some((el) => el.textContent === 'Khôi phục phiên bản này')).toBe(false)
  })
  it('restores once only after confirmation', async () => {
    await render(); await choose(2); await restore()
    expect(source.restore).toHaveBeenCalledExactlyOnceWith('v2'); expect(restored).toHaveBeenCalledTimes(1); expect(toast.success).toHaveBeenCalledWith('Đã khôi phục phiên bản 2.')
    expect(pending.mock.calls.map(([value]) => value)).toEqual([true, false])
  })
  it('keeps the draft callback untouched on restore failure', async () => {
    vi.mocked(source.restore).mockRejectedValue(new Error('x')); await render(); await choose(2); await restore()
    expect(restored).not.toHaveBeenCalled(); expect(toast.error).toHaveBeenCalledWith('Không thể khôi phục', { description: 'x' })
  })
  it('shows empty and load/detail errors without stale comparison', async () => {
    vi.mocked(source.list).mockResolvedValue({ schema_version: 'template-versions.v2', template_id: 't1', current_version_id: null, items: [] })
    await render(); expect(document.body.textContent).toContain('Chưa có phiên bản nào.')
  })
  it('shows list fetch failures', async () => {
    vi.mocked(source.list).mockRejectedValue(new Error('history unavailable')); await render(); expect(document.body.textContent).toContain('history unavailable')
  })
  it('hides the previous comparison while a newly selected detail fails', async () => {
    await render(); await choose(1); expect(document.body.textContent).toContain('So sánh Phiên bản 1')
    vi.mocked(source.get).mockRejectedValueOnce(new Error('detail unavailable')); await choose(2)
    expect(document.body.textContent).toContain('detail unavailable'); expect(document.body.textContent).not.toContain('So sánh Phiên bản 1')
  })
  it('does not apply a restore response after its template sheet unmounts', async () => {
    let resolve!: (value: Awaited<ReturnType<TemplateVersionSource['restore']>>) => void
    vi.mocked(source.restore).mockImplementation(() => new Promise((done) => { resolve = done }))
    await render(); await choose(2); await act(async () => button('Khôi phục phiên bản này').click()); await act(async () => button('Khôi phục').click())
    await act(async () => root.render(<div>Other template</div>))
    await act(async () => resolve({ id: 't1', note_type_id: null, name: 'Card', ...current, position: 0, is_default: false, updated_at: null }))
    expect(restored).not.toHaveBeenCalled()
  })
})

describe('Template workspace history applies explicit restore to the current draft', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let navigate: ReturnType<typeof useNavigate>
  const item = (id: string, front = 'saved'): TemplateLibraryDetail => ({
    id, owner_user_id: 1, name: id, description: '', primary_category: null, origin: 'authored',
    source_template_id: null, source_version_id: null, current_version_id: 'v3',
    ...current, front_html: front, input_schema: [], archived_at: null, created_at: null, updated_at: null,
    application_count: 0, note_type_count: 0, applications: [],
  })
  function Navigation() { navigate = useNavigate(); return null }
  beforeEach(() => {
    vi.clearAllMocks()
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    api.request.mockImplementation(async (url: string) => {
      if (url.endsWith('/versions')) return { schema_version: 'template-versions.v2', template_id: 't1', current_version_id: 'v3', items: versions }
      if (url.includes('/versions/')) return versions[1]
      if (url.endsWith('/preview')) return { front_html: 'preview front', back_html: 'preview back', front_renderer_payload: null, back_renderer_payload: null }
      if (url === '/api/card-templates/t1') return item('t1')
      if (url === '/api/card-templates/t2') return item('t2', 'second')
      throw new Error(`Unexpected request: ${url}`)
    })
    api.json.mockResolvedValue({ id: 't1', name: 't1', ...current, note_type_id: null, position: 0, is_default: false, updated_at: null, current_version_id: 'v4' })
  })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = '' })
  async function start() {
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/card-templates/t1']}><Navigation /><Routes><Route path="/card-templates/:id" element={<TemplateDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>))
    await flush()
    await act(async () => {
      const textarea = container.querySelector('textarea')!
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(textarea, 'dirty draft')
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => document.querySelector<HTMLButtonElement>('[aria-label="Thao tác khác với template"]')!.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0 })))
    await flush()
    await act(async () => [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')].find((el) => el.textContent?.trim() === 'Lịch sử')!.click()); await flush()
    await act(async () => [...document.querySelectorAll('button')].find((el) => el.getAttribute('aria-pressed') !== null && el.textContent?.includes('Phiên bản 2'))!.click()); await flush()
    await act(async () => button('Khôi phục phiên bản này').click())
    await act(async () => button('Khôi phục').click()); await flush()
  }
  it('replaces dirty sources even if restored sources equal the cached server baseline', async () => {
    await start(); expect(container.querySelector('textarea')?.value).toBe('saved')
    expect(api.json).toHaveBeenCalledWith('/api/card-templates/t1/versions/v2/restore', 'POST', {})
    expect(api.request.mock.calls.filter(([url]) => url === '/api/card-templates/t1').length).toBeGreaterThanOrEqual(2)
  })
  it('keeps dirty sources on restore errors', async () => {
    api.json.mockRejectedValue(new Error('restore denied')); await start()
    expect(container.querySelector('textarea')?.value).toBe('dirty draft')
    expect(toast.error).toHaveBeenCalledWith('Không thể khôi phục', { description: 'restore denied' })
  })
  it('ignores a late restore after navigating to another template workspace', async () => {
    let resolve!: (value: unknown) => void
    api.json.mockImplementation(() => new Promise((done) => { resolve = done }))
    await start()
    await act(async () => navigate('/card-templates/t2'))
    await flush()
    expect(container.querySelector('textarea')?.value).toBe('second')
    expect(document.body.textContent).not.toContain('Lịch sử phiên bản')
    await act(async () => resolve({ id: 't1', name: 't1', ...current, note_type_id: null, position: 0, is_default: false, updated_at: null }))
    await flush()
    expect(container.querySelector('textarea')?.value).toBe('second')
    expect(toast.success).not.toHaveBeenCalled()
  })
})
