// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TemplateApplication, TemplateLibraryDetail } from '@/entities/card-template'
import { AttachTemplateDialog, type AttachTemplateDialogProps } from './AttachTemplateDialog'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
vi.mock('sonner', () => ({ toast: { success: vi.fn() } }))

const template: TemplateLibraryDetail = {
  id: 'template/shared', owner_user_id: 1, name: 'Vocabulary Card', description: '', primary_category: 'Vocabulary',
  origin: 'authored', source_template_id: null, source_version_id: null, current_version_id: 'version-1',
  front_html: '{{Word}}', back_html: '{{Meaning}}', shared_css: '',
  input_schema: [{ key: 'Word', label: 'Word', type: 'text', required: true }, { key: 'Meaning', label: 'Meaning', type: 'markdown', required: false }],
  archived_at: null, created_at: null, updated_at: null, application_count: 0, note_type_count: 0, applications: [],
}
const noteTypes = { items: [{
  id: 'nt/1', name: 'Japanese', is_marketplace_install: false,
  field_defs: [{ id: 'field-word', name: 'Word', field_type: 'text', position: 0 }],
}] }
const application = (body: Record<string, unknown>): TemplateApplication => ({
  id: 'server/application', application_id: 'server/application', note_type_id: 'nt/1', template_id: String(body.template_id),
  occurrence_key: String(body.occurrence_key), status_code: 'ACTIVE', display_name: String(body.display_name),
  position: 0, is_default: false, input_bindings: body.input_bindings as TemplateApplication['input_bindings'],
  input_schema: template.input_schema, warnings: [], template,
})
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
const flush = async () => { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) }); await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) }) }
const button = (text: string) => Array.from(document.querySelectorAll('button')).find((item) => item.textContent === text)!
const pickTemplate = async () => {
  await act(async () => document.querySelector<HTMLButtonElement>('button[aria-pressed]')!.click())
  await flush()
}
const setInput = async (element: HTMLInputElement, value: string) => { await act(async () => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(element, value)
  element.dispatchEvent(new Event('input', { bubbles: true }))
}) }

describe('AttachTemplateDialog', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let props: AttachTemplateDialogProps
  let fetchMock: ReturnType<typeof vi.fn>
  let existing: TemplateApplication[]
  let post: (body: Record<string, unknown>) => Response | Promise<Response>
  let detailFailure: boolean
  const render = async () => {
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter><AttachTemplateDialog {...props} /></MemoryRouter></QueryClientProvider>))
    await flush()
  }
  beforeEach(() => {
    vi.clearAllMocks()
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    props = { open: true, noteTypeId: 'nt/1', onOpenChange: vi.fn(), onApplied: vi.fn() }
    existing = []; detailFailure = false
    post = (body) => json(application(body), 201)
    fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return post(JSON.parse(String(init.body)))
      if (String(url).includes('template-applications')) return json({ schema_version: 'template-applications.v2', items: existing })
      if (String(url) === '/api/note-types') return json(noteTypes)
      if (String(url).includes('/api/card-templates/template%2Fshared')) return detailFailure
        ? json({ error: 'FAILED', message: 'Không tải được thiết kế.' }, 500) : json(template)
      return json({ schema_version: 'template-library.v2', items: [template, { ...template, id: 'archived', name: 'Archived', archived_at: '2026-10-08' }] })
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => { act(() => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = ''; vi.unstubAllGlobals(); vi.restoreAllMocks() })
  it('chooses a library design and atomically attaches suggested stable ID bindings in the fixed Note Type', async () => {
    await render()
    expect(document.body.textContent).toContain('Vocabulary Card')
    expect(document.body.textContent).toContain('Vocabulary')
    expect(document.body.textContent).toContain('2 inputs')
    expect(document.body.textContent).not.toContain('Archived')
    await pickTemplate()
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/card-templates/template%2Fshared')).toBe(true)
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
    await act(async () => button('Tiếp tục').click()); await flush()
    expect(document.querySelectorAll('[role="dialog"]')).toHaveLength(1)
    expect(document.body.textContent).not.toContain('Chọn loại thẻ')
    expect(document.body.textContent).not.toContain('Mã lần gắn')
    expect(Array.from(document.querySelectorAll('select')).map((select) => select.value)).toEqual(['field-word', ''])
    expect(button('Gắn và lưu mapping').disabled).toBe(false)
    await setInput(document.querySelector('input')!, 'Reading practice')
    await act(async () => button('Gắn và lưu mapping').click()); await flush()
    const [url, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(String(url)).toBe('/api/note-types/nt%2F1/template-applications')
    expect(JSON.parse(String(init.body))).toEqual({ template_id: template.id, occurrence_key: 'compat', display_name: 'Reading practice', input_bindings: { Word: 'field-word', Meaning: null } })
    expect(props.onApplied).toHaveBeenCalledWith(expect.objectContaining({ id: 'server/application' }))
    expect(props.onOpenChange).toHaveBeenCalledWith(false)
  })
  it('offers the existing use by application ID and generates a duplicate occurrence only on an explicit choice', async () => {
    existing = [application({ template_id: template.id, occurrence_key: 'compat', display_name: 'Reading practice', input_bindings: { Word: 'field-word' } })]
    const generated = '00000000-0000-4000-8000-000000000001'
    const uuid = vi.spyOn(crypto, 'randomUUID').mockReturnValue(generated)
    await render(); await pickTemplate()
    expect(document.body.textContent).toContain('Template này đã có trong Note Type.')
    expect(document.querySelector('a[href="/flashcards/note-types/nt%2F1/templates/server%2Fapplication"]')?.textContent).toContain('Mở lần dùng hiện có: Reading practice')
    expect(uuid).not.toHaveBeenCalled()
    await act(async () => button('Gắn thêm lần nữa').click()); await flush()
    expect(uuid).toHaveBeenCalledOnce()
    expect(document.body.textContent).not.toContain(generated)
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
    await act(async () => button('Gắn và lưu mapping').click()); await flush()
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(JSON.parse(String(init.body)).occurrence_key).toBe(generated)
  })
  it('cancels selection or mapping without creating an empty application', async () => {
    await render(); await pickTemplate()
    await act(async () => button('Tiếp tục').click()); await flush()
    await act(async () => button('Chọn template khác').click())
    expect(document.body.textContent).toContain('Chọn template')
    await act(async () => button('Hủy').click())
    expect(props.onOpenChange).toHaveBeenCalledWith(false)
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0)
  })
  it('keeps the mapping after APPLICATION_EXISTS and links to the newly discovered existing use', async () => {
    post = (body) => {
      existing = [application(body)]
      return json({ error: 'APPLICATION_EXISTS', message: 'Conflict' }, 409)
    }
    const uuid = vi.spyOn(crypto, 'randomUUID')
    await render(); await pickTemplate()
    await act(async () => button('Tiếp tục').click()); await flush()
    await act(async () => button('Gắn và lưu mapping').click()); await flush()
    expect(document.body.textContent).toContain('Lần gắn này đã tồn tại.')
    expect(document.querySelector('select')!.value).toBe('field-word')
    expect(document.querySelector('a[href="/flashcards/note-types/nt%2F1/templates/server%2Fapplication"]')).not.toBeNull()
    expect(props.onOpenChange).not.toHaveBeenCalled()
    expect(uuid).not.toHaveBeenCalled()
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
  })
  it('searches by name and excludes archived templates even when the library response includes them', async () => {
    await render()
    await setInput(document.querySelector('input[type="search"]')!, 'Vocabulary')
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 270)) }); await flush()
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/card-templates?q=Vocabulary')).toBe(true)
    expect(document.body.textContent).not.toContain('Archived')
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('include_archived'))).toHaveLength(0)
  })
  it('blocks mapping until the selected detail is loaded and supports retry', async () => {
    detailFailure = true
    await render(); await pickTemplate()
    expect(document.body.textContent).toContain('Không tải được thiết kế.')
    expect(button('Tiếp tục').disabled).toBe(true)
    detailFailure = false
    await act(async () => button('Thử lại').click()); await flush()
    expect(button('Tiếp tục').disabled).toBe(false)
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0)
  })
})
