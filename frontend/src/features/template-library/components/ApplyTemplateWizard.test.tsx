// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import type { TemplateApplication, TemplateLibraryDetail } from '@/entities/card-template'
import { ApplyTemplateWizard, type ApplyTemplateWizardProps } from './ApplyTemplateWizard'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
vi.mock('sonner', () => ({ toast: { success: vi.fn() } }))

const template: TemplateLibraryDetail = {
  id: 'template/shared', owner_user_id: 1, name: 'Dùng chung', description: '', primary_category: null,
  origin: 'authored', source_template_id: null, source_version_id: null, current_version_id: 'version-1',
  front_html: '{{Word}}', back_html: '{{word}}', shared_css: '',
  input_schema: [{ key: 'Word', label: 'Từ', type: 'text', required: true }, { key: 'word', label: 'Từ khác', type: 'text', required: false }],
  archived_at: null, created_at: null, updated_at: null, application_count: 0, note_type_count: 0, applications: [],
}
const noteTypes = { items: [
  { id: 'nt/owned', name: 'Của tôi', is_marketplace_install: false, field_defs: [{ id: 'owned-text', name: ' Word ', field_type: 'text', position: 0 }] },
  { id: 'nt/installed', name: 'Đã cài', is_marketplace_install: true, field_defs: [{ id: 'installed-image', name: 'Word', field_type: 'image', position: 0 }, { id: 'installed-text', name: 'Other', field_type: 'text', position: 1 }] },
] }
const application = (body: Record<string, unknown>): TemplateApplication => ({
  id: 'application-1', application_id: 'application-1', note_type_id: 'nt/owned', template_id: String(body.template_id),
  occurrence_key: String(body.occurrence_key), status_code: 'ACTIVE', display_name: String(body.display_name),
  position: 0, is_default: false, input_bindings: body.input_bindings as TemplateApplication['input_bindings'],
  input_schema: template.input_schema, warnings: [], template,
})
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
const flush = async () => { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) }); await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) }) }
const button = (text: string) => Array.from(document.querySelectorAll('button')).find((item) => item.textContent === text)!
const input = (labelText: string) => document.getElementById(Array.from(document.querySelectorAll('label')).find((label) => label.textContent === labelText)!.htmlFor) as HTMLInputElement
const select = async (element: HTMLSelectElement, value: string) => { await act(async () => { element.value = value; element.dispatchEvent(new Event('change', { bubbles: true })) }); await flush() }

describe('ApplyTemplateWizard', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let props: ApplyTemplateWizardProps
  let fetchMock: ReturnType<typeof vi.fn>
  let post: (body: Record<string, unknown>) => Response | Promise<Response>
  const render = async () => {
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter><ApplyTemplateWizard {...props} /></MemoryRouter></QueryClientProvider>))
    await flush()
  }
  beforeEach(() => {
    vi.clearAllMocks()
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    props = { open: true, template, onOpenChange: vi.fn(), onApplied: vi.fn() }
    post = (body) => json(application(body), 201)
    fetchMock = vi.fn(async (_url: string, init?: RequestInit) => init?.method === 'POST'
      ? post(JSON.parse(String(init.body))) : json(noteTypes))
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => { act(() => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = ''; vi.unstubAllGlobals() })
  it('selects a NoteType, suggests repeated exact type IDs and POSTs only attachment fields', async () => {
    await render()
    expect(document.body.textContent).toContain('Chọn loại thẻ')
    await select(document.querySelector('select')!, 'nt/owned')
    await act(async () => button('Tiếp tục').click())
    expect(Array.from(document.querySelectorAll('select')).slice(1).map((item) => item.value)).toEqual(['owned-text', 'owned-text'])
    await act(async () => button('Gắn mẫu').click()); await flush()
    const [url, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(String(url)).toContain('/api/note-types/nt%2Fowned/template-applications')
    expect(JSON.parse(String(init.body))).toEqual({ template_id: template.id, occurrence_key: 'compat', display_name: template.name, input_bindings: { Word: 'owned-text', word: 'owned-text' } })
    expect(props.onApplied).toHaveBeenCalledWith(expect.objectContaining({ template_id: template.id }))
    expect(props.onOpenChange).toHaveBeenCalledWith(false)
    expect(toast.success).toHaveBeenCalledWith('Đã gắn mẫu vào loại thẻ.', expect.objectContaining({ action: expect.objectContaining({ label: 'Mở loại thẻ' }) }))
  })
  it('cancels Next native activation and only attaches on a separate explicit submit click', async () => {
    await render()
    await select(document.querySelector('select')!, 'nt/owned')
    const next = button('Tiếp tục')
    const click = new MouseEvent('click', { bubbles: true, cancelable: true })
    let nativeActionAllowed = true
    await act(async () => { nativeActionAllowed = next.dispatchEvent(click) })
    await flush()
    expect(nativeActionAllowed).toBe(false)
    expect(click.defaultPrevented).toBe(true)
    expect(next.isConnected).toBe(false)
    expect(button('Gắn mẫu')).not.toBe(next)
    expect(button('Gắn mẫu').type).toBe('submit')
    expect(document.body.textContent).toContain('Ánh xạ trường')
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0)
    expect(props.onApplied).not.toHaveBeenCalled()
    expect(props.onOpenChange).not.toHaveBeenCalled()
    await act(async () => button('Gắn mẫu').click()); await flush()
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
    expect(props.onOpenChange).toHaveBeenCalledWith(false)
  })
  it('supports installed initial selection and recommended unbound inputs', async () => {
    props.initialNoteTypeId = 'nt/installed'
    await render()
    expect(document.body.textContent).toContain('Ánh xạ trường')
    expect(document.body.textContent).toContain('Bản cài từ marketplace')
    expect(document.body.textContent).toContain('vẫn có thể sử dụng')
    expect(document.body.textContent).not.toContain('Chọn loại thẻ')
    expect(document.body.textContent).not.toContain('Mã lần gắn')
    expect(button('Quay lại')).toBeUndefined()
    const mapping = document.querySelectorAll('select')[0]
    expect(mapping.value).toBe('')
    expect(mapping.querySelector<HTMLOptionElement>('option[value="installed-image"]')!.disabled).toBe(true)
    expect(button('Gắn mẫu').disabled).toBe(false)
    await act(async () => button('Gắn mẫu').click()); await flush()
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(JSON.parse(String(init.body)).input_bindings).toEqual({ Word: null, word: null })
  })
  it('clears previous NoteType IDs when changing selection and blocks incompatible selections', async () => {
    await render()
    await select(document.querySelector('select')!, 'nt/owned')
    await act(async () => button('Tiếp tục').click())
    await select(document.querySelector('select')!, 'nt/installed')
    expect(Array.from(document.querySelectorAll('select')).slice(1).map((item) => item.value)).toEqual(['', ''])
    await select(document.querySelectorAll('select')[1], 'installed-image')
    expect(button('Gắn mẫu').disabled).toBe(true)
    expect(document.body.textContent).toContain('Kiểu trường không phù hợp.')
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0)
  })
  it('keeps mapping after conflict and offers the existing server application without creating another occurrence', async () => {
    props.initialNoteTypeId = 'nt/owned'
    post = () => json({ error: 'APPLICATION_EXISTS', message: 'Conflict' }, 409)
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => init?.method === 'POST'
      ? post(JSON.parse(String(init.body))) : String(url).includes('template-applications')
        ? json({ schema_version: 'template-applications.v2', items: [application({ template_id: template.id, display_name: 'Existing use', occurrence_key: 'compat', input_bindings: {} })] })
        : json(noteTypes))
    await render()
    await act(async () => button('Gắn mẫu').click()); await flush()
    expect(document.body.textContent).toContain('Lần gắn này đã tồn tại.')
    expect(document.querySelectorAll('select')[0].value).toBe('owned-text')
    expect(props.onOpenChange).not.toHaveBeenCalled()
    expect(document.querySelector('a[href="/flashcards/note-types/nt%2Fowned/templates/application-1"]')?.textContent).toContain('Mở lần dùng hiện có')
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
    expect(document.body.textContent).not.toContain('Mã lần gắn')
  })
  it('shows field-specific server scope errors without discarding mapping', async () => {
    props.initialNoteTypeId = 'nt/owned'
    post = () => json({ error: 'FIELD_OUT_OF_SCOPE', message: 'Field was removed', field: 'Word' }, 400)
    await render()
    await act(async () => button('Gắn mẫu').click()); await flush()
    expect(document.body.textContent).toContain('Field was removed')
    expect(document.querySelectorAll('select')[0].value).toBe('owned-text')
    expect(document.querySelectorAll('select')[0].getAttribute('aria-invalid')).toBe('true')
  })
  it('resets on reopen and ignores a late response for a previous template', async () => {
    let resolvePost!: (response: Response) => void
    let submitted!: Record<string, unknown>
    post = (body) => { submitted = body; return new Promise((resolve) => { resolvePost = resolve }) }
    props.initialNoteTypeId = 'nt/owned'; await render()
    await act(async () => button('Gắn mẫu').click())
    props = { ...props, open: false }; await render()
    props = { ...props, open: true, template: { ...template, id: 'other', name: 'Other' } }; await render()
    expect(input('Tên lần dùng').value).toBe('Other')
    expect(button('Gắn mẫu').disabled).toBe(false)
    await act(async () => resolvePost(json(application(submitted), 201))); await flush()
    expect(props.onOpenChange).not.toHaveBeenCalled()
    expect(toast.success).not.toHaveBeenCalled()
    expect(input('Tên lần dùng').value).toBe('Other')
  })
  it('blocks an unavailable fixed Note Type without offering another context', async () => {
    props.initialNoteTypeId = 'foreign'
    await render()
    expect(document.body.textContent).toContain('Note Type này không khả dụng.')
    expect(document.querySelector('select')).toBeNull()
    expect(button('Gắn mẫu').disabled).toBe(true)
  })
  it('blocks archived templates', async () => {
    props.template = { ...template, archived_at: '2026-10-08' }
    await render()
    await select(document.querySelector('select')!, 'nt/owned')
    await act(async () => button('Tiếp tục').click())
    expect(button('Gắn mẫu').disabled).toBe(true)
    expect(document.body.textContent).toContain('Bỏ lưu trữ để gắn mẫu.')
  })
  it('suggests and submits own bindings for prototype-named schema keys', async () => {
    const keys = ['__proto__', 'constructor', 'toString']
    props.initialNoteTypeId = 'nt/owned'
    props.template = { ...template, input_schema: keys.map((key) => ({ key, label: key, type: 'text', required: true })) }
    const specialNoteTypes = { items: [{ ...noteTypes.items[0], field_defs: keys.map((key, position) => ({
      id: `field-${position}`, name: key, field_type: 'text', position,
    })) }] }
    fetchMock.mockImplementation(async (_url: string, init?: RequestInit) => init?.method === 'POST'
      ? post(JSON.parse(String(init.body))) : json(specialNoteTypes))
    await render()
    expect(Array.from(document.querySelectorAll('select')).map((select) => select.value)).toEqual(['field-0', 'field-1', 'field-2'])
    expect(button('Gắn mẫu').disabled).toBe(false)
    await act(async () => button('Gắn mẫu').click()); await flush()
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')!
    const bindings = JSON.parse(String(init.body)).input_bindings
    expect(Object.keys(bindings)).toEqual(keys)
    expect(bindings).toEqual(Object.fromEntries(keys.map((key, index) => [key, `field-${index}`])))
  })
  it('accepts an explicit generated occurrence without exposing technical input controls', async () => {
    props.initialNoteTypeId = 'nt/owned'
    props.initialOccurrenceKey = 'generated-occurrence'
    await render()
    expect(document.body.textContent).not.toContain('Mã lần gắn')
    await act(async () => button('Gắn mẫu').click()); await flush()
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(JSON.parse(String(init.body)).occurrence_key).toBe('generated-occurrence')
  })
  it('prevents dismissing or submitting again while the attachment is pending', async () => {
    let resolvePost!: (response: Response) => void
    let submitted!: Record<string, unknown>
    props.initialNoteTypeId = 'nt/owned'
    post = (body) => { submitted = body; return new Promise((resolve) => { resolvePost = resolve }) }
    await render()
    await act(async () => button('Gắn mẫu').click())
    expect(button('Hủy').disabled).toBe(true)
    expect(document.querySelector('[data-slot="dialog-close"]')).toBeNull()
    await act(async () => {
      document.querySelector('[role="dialog"]')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
      document.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    })
    expect(props.onOpenChange).not.toHaveBeenCalled()
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
    await act(async () => resolvePost(json(application(submitted), 201))); await flush()
    expect(props.onApplied).toHaveBeenCalledOnce()
  })
})
