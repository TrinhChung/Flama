// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setCsrfToken } from '@/shared/api/client'
import type { TemplateApplication } from '@/entities/card-template'
import { NoteTypeTemplateMappingPage } from './index'

const preview = vi.hoisted(() => vi.fn())
vi.mock('@/entities/flashcard/ui/CardPreviewPanel', () => ({ CardPreviewPanel: preview }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const fields = [
  { id: 'f1', name: 'Renamed Word', field_type: 'text', position: 0 },
  { id: 'f2', name: 'Alternate', field_type: 'text', position: 1 },
  { id: 'image', name: 'Picture', field_type: 'image', position: 2 },
]
const fixture = (id = 'a1'): TemplateApplication => ({
  id, application_id: id, note_type_id: 'n1', template_id: 't1', occurrence_key: id, status_code: 'ACTIVE',
  display_name: id === 'a1' ? 'Vocabulary' : 'Reverse', position: 0, is_default: false,
  input_bindings: { Word: id === 'a1' ? 'f1' : 'f2' }, input_schema: [{ key: 'Word', label: 'Word', type: 'text', required: true }], warnings: [],
  template: { id: 't1', owner_user_id: 1, name: 'Shared design', description: '', primary_category: null,
    origin: 'authored', source_template_id: null, source_version_id: null, current_version_id: 'v1',
    input_schema: [{ key: 'Word', label: 'Word', type: 'text', required: true }], front_html: '{{Word}}', back_html: '{{Word}}', shared_css: '',
    archived_at: null, created_at: null, updated_at: null },
})
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const flush = async (ms = 20) => { await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) }) }
const button = (label: string) => [...document.querySelectorAll('button')].find((item) => item.textContent?.trim() === label)!
async function choose(value: string) { await act(async () => { const select = document.querySelector('select')!; select.value = value; select.dispatchEvent(new Event('change', { bubbles: true })) }) }
async function changeName(value: string) { await act(async () => { const input = document.querySelector<HTMLInputElement>('#application-display-name')!; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value); input.dispatchEvent(new Event('input', { bubbles: true })) }) }

describe('Note Type application mapping workspace', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let router: ReturnType<typeof createMemoryRouter>
  let applications: TemplateApplication[]
  let fetchMock: ReturnType<typeof vi.fn>
  let failedSave: boolean
  beforeEach(() => {
    vi.clearAllMocks(); setCsrfToken('test'); applications = [fixture(), fixture('a2')]; failedSave = false
    preview.mockReturnValue(null)
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST' && String(url).endsWith('/preview')) return json({ front_html: 'compiled', back_html: 'compiled', front_renderer_payload: { front: true }, back_renderer_payload: { back: true } })
      if (init?.method === 'PATCH') {
        if (failedSave) return json({ error: 'INPUT_TYPE_MISMATCH', message: 'Changed by another tab', field: 'Word' }, 400)
        const id = String(url).split('/').at(-1)!
        applications = applications.map((item) => item.id === id ? { ...item, ...JSON.parse(String(init.body)) } : item)
        return json(applications.find((item) => item.id === id))
      }
      if (String(url).includes('template-applications')) return json({ schema_version: 'template-applications.v2', items: applications })
      return json({ id: 'n1', name: 'Japanese vocabulary', field_defs: fields })
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); router?.dispose(); container.remove(); document.body.innerHTML = ''; vi.unstubAllGlobals() })
  async function render(id = 'a1') {
    router = createMemoryRouter([
      { path: '/flashcards/note-types/:id/templates/:applicationId', element: <NoteTypeTemplateMappingPage /> },
      { path: '/flashcards/note-types/:id/fields', element: <p>Field configuration</p> },
      { path: '/flashcards/note-types/:id/templates', element: <p>Application list</p> },
    ], { initialEntries: [`/flashcards/note-types/n1/templates/${id}`] })
    await act(async () => root.render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>)); await flush()
  }
  it('reads by application ID, preserves renamed field identity and links to design with return context', async () => {
    await render('a2')
    expect(document.querySelector('select')!.value).toBe('f2')
    expect(document.querySelector('a[href^="/card-templates/t1?"]')?.getAttribute('href')).toContain('returnTo=')
    await choose('f1'); await act(async () => button('Lưu mapping').click()); await flush()
    const [url, options] = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH')!
    expect(url).toContain('/template-applications/a2')
    expect(JSON.parse(String(options.body))).toEqual({ input_bindings: { Word: 'f1' }, display_name: 'Reverse' })
    expect(applications[0].input_bindings).toEqual({ Word: 'f1' })
    expect(applications[1].input_bindings).toEqual({ Word: 'f1' })
  })
  it('renders unbound recommended inputs empty in preview without saving and allows an explicit save', async () => {
    await render(); await choose(''); await flush(430)
    const [, options] = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST').at(-1)!
    expect(JSON.parse(String(options.body)).sample_values).toEqual({ Word: '' })
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PATCH')).toBe(false)
    expect(button('Lưu mapping').disabled).toBe(false)
    expect(preview).toHaveBeenLastCalledWith(expect.objectContaining({ frontPayload: { front: true }, fieldDefs: [{ id: 'f_0', name: 'Word', field_type: 'text', position: 0 }] }), undefined)
  })
  it('keeps a dirty name and mapping across background refetches', async () => {
    await render(); await changeName('My local use'); await choose('f2')
    applications[0] = { ...applications[0], display_name: 'Server rename' }
    await act(async () => { await client.invalidateQueries({ queryKey: ['card-template'] }) }); await flush()
    expect(document.querySelector<HTMLInputElement>('#application-display-name')!.value).toBe('My local use')
    expect(document.querySelector('select')!.value).toBe('f2')
  })
  it('blocks navigation until saving succeeds, and keeps draft plus dialog on server failure', async () => {
    await render(); await choose('f2'); failedSave = true
    await act(async () => { document.querySelector<HTMLAnchorElement>('a[href$="/fields"]')!.click() }); await flush()
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Thay đổi chưa được lưu')
    await act(async () => button('Lưu và tiếp tục').click()); await flush()
    expect(document.body.textContent).toContain('Changed by another tab')
    expect(router.state.location.pathname).toContain('/templates/a1')
    failedSave = false; await act(async () => button('Lưu và tiếp tục').click()); await flush()
    expect(router.state.location.pathname).toBe('/flashcards/note-types/n1/fields')
    expect(applications[0].input_bindings).toEqual({ Word: 'f2' })
  })
  it('blocks invalid stale mappings, permits cleanup of removed input keys and rejects cross-scope route IDs', async () => {
    applications[0].input_bindings = { Word: 'missing', Removed: 'f1' }
    await render()
    expect(button('Lưu mapping').disabled).toBe(true)
    expect(document.body.textContent).toContain('Removed')
    await act(async () => { await router.navigate('/flashcards/note-types/n1/templates/not-owned') }); await flush()
    expect(document.body.textContent).toContain('Không tìm thấy lần dùng template')
    expect(document.querySelector('select')).toBeNull()
  })
  it('resolves application and allows saving when accessed via composite ID or template ID', async () => {
    // Access using composite ID: comp:notetype:n1:template:t1
    await render('comp:notetype:n1:template:t1')
    expect(document.querySelector('select')).not.toBeNull()
    expect(document.querySelector('select')!.value).toBe('f1')
    await choose('f2'); await act(async () => button('Lưu mapping').click()); await flush()
    const [url, options] = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH')!
    expect(url).toContain('/template-applications/a1')
    expect(JSON.parse(String(options.body))).toEqual({ input_bindings: { Word: 'f2' }, display_name: 'Vocabulary' })
  })
})
