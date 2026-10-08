// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TemplateApplication } from '@/entities/card-template'
import { TemplateApplicationsPanel, type TemplateApplicationsPanelProps } from './TemplateApplicationsPanel'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const row: TemplateApplication = {
  id: 'application/1', application_id: 'application/1', note_type_id: 'nt/1', template_id: 'template/1',
  occurrence_key: 'listening', status_code: 'ACTIVE', display_name: 'Luyện nghe', position: 2, is_default: true,
  input_bindings: { Word: 'field/1' }, input_schema: [{ key: 'Word', label: 'Từ', type: 'text', required: true }], warnings: [],
  template: {
    id: 'template/1', owner_user_id: 1, name: 'Mẫu dùng chung', description: '', primary_category: null,
    origin: 'authored', source_template_id: null, source_version_id: null, current_version_id: 'v1',
    front_html: '{{Word}}', back_html: '{{Word}}', shared_css: '', input_schema: [{ key: 'Word', label: 'Từ', type: 'text', required: true }],
    archived_at: null, created_at: null, updated_at: null,
  },
}
const fields = [{ id: 'field/1', name: 'Renamed Word', field_type: 'text' }, { id: 'field/2', name: 'Image', field_type: 'image' }]
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
const flush = async () => { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) }); await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) }) }
const button = (text: string) => Array.from(document.querySelectorAll('button')).find((item) => item.textContent === text)!
const choose = async (value: string) => { await act(async () => { const select = document.querySelector('select')!; select.value = value; select.dispatchEvent(new Event('change', { bubbles: true })) }) }

describe('TemplateApplicationsPanel', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let current: TemplateApplication
  let props: TemplateApplicationsPanelProps
  let fetchMock: ReturnType<typeof vi.fn>
  let failure: { error: string; message: string; field?: string } | null
  const render = async () => {
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter><TemplateApplicationsPanel {...props} /></MemoryRouter></QueryClientProvider>))
    await flush()
  }
  beforeEach(() => {
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    current = structuredClone(row)
    props = { noteTypeId: 'nt/1', onChanged: vi.fn() }
    failure = null
    fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (method === 'GET') return String(url).includes('template-applications')
        ? json({ schema_version: 'template-applications.v2', items: [current] }) : json({ field_defs: fields })
      if (failure) return json(failure, 400)
      if (method === 'PATCH') current = { ...current, ...JSON.parse(String(init?.body)) }
      if (method === 'DELETE') current = { ...current, status_code: 'RETIRED' }
      if (method === 'POST') current = { ...current, ...JSON.parse(String(init?.body)), status_code: 'ACTIVE' }
      return json(current, method === 'POST' ? 201 : 200)
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => { act(() => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = ''; vi.unstubAllGlobals() })
  it('loads active/retired applications and links to canonical template identity', async () => {
    await render()
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/note-types/nt%2F1/template-applications?include_retired=true'))).toBe(true)
    expect(document.body.textContent).toContain('ACTIVE')
    expect(document.body.textContent).toContain('Luyện nghe · listening')
    expect(document.querySelector('a[href="/card-templates/template%2F1"]')?.textContent).toBe('Mẫu dùng chung')
    current = { ...current, status_code: 'RETIRED' }
    await act(async () => { await client.invalidateQueries({ queryKey: ['card-template'] }) }); await flush()
    expect(document.body.textContent).toContain('RETIRED')
    expect(button('Gắn lại')).toBeDefined()
  })
  it('PATCHes only bindings/name, keeps stable IDs after rename, and permits recommended unbound', async () => {
    await render()
    await act(async () => button('Sửa ánh xạ').click())
    expect(document.querySelector('select')!.value).toBe('field/1')
    expect(document.querySelector('select')!.textContent).toContain('Renamed Word')
    await choose('')
    expect(document.body.textContent).toContain('vẫn có thể sử dụng')
    expect(button('Lưu ánh xạ').disabled).toBe(false)
    await act(async () => button('Lưu ánh xạ').click()); await flush()
    const [url, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'PATCH')!
    expect(String(url)).toContain('/api/note-types/nt%2F1/template-applications/application%2F1')
    expect(JSON.parse(String(init.body))).toEqual({ input_bindings: { Word: null }, display_name: 'Luyện nghe' })
    expect(current.id).toBe(row.id)
    expect(current.template).toEqual(row.template)
    expect(props.onChanged).toHaveBeenCalledOnce()
  })
  it('retires through confirmation while preserving progress and reattaches the same occurrence/ID', async () => {
    await render()
    await act(async () => button('Gỡ mẫu').click())
    expect(document.body.textContent).toContain('Tiến độ đã học được giữ lại.')
    const dialog = document.querySelector('[role="dialog"]')!
    await act(async () => Array.from(dialog.querySelectorAll('button')).find((item) => item.textContent === 'Gỡ mẫu')!.click()); await flush()
    const [url, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'DELETE')!
    expect(String(url)).toContain('/template-applications/application%2F1')
    expect(init.body).toBeUndefined()
    expect(current.status_code).toBe('RETIRED')
    await act(async () => button('Gắn lại').click()); await flush()
    const [, postInit] = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(JSON.parse(String(postInit.body))).toEqual({
      template_id: row.template_id, occurrence_key: row.occurrence_key, input_bindings: row.input_bindings,
      display_name: row.display_name, position: row.position, is_default: row.is_default,
    })
    expect(current.id).toBe(row.id)
    expect(current.status_code).toBe('ACTIVE')
  })
  it('keeps the editor mapping when the server rejects a scope change', async () => {
    failure = { error: 'FIELD_OUT_OF_SCOPE', message: 'Trường vừa bị gỡ.', field: 'Word' }
    await render()
    await act(async () => button('Sửa ánh xạ').click())
    await act(async () => button('Lưu ánh xạ').click()); await flush()
    expect(document.body.textContent).toContain('Trường vừa bị gỡ.')
    expect(document.querySelector('select')!.value).toBe('field/1')
    expect(button('Lưu ánh xạ')).toBeDefined()
    expect(props.onChanged).not.toHaveBeenCalled()
  })
  it('does not replace an open mapping draft on application query refetch', async () => {
    props.fields = fields; await render()
    expect(fetchMock.mock.calls.filter(([url]) => !String(url).includes('template-applications'))).toHaveLength(0)
    await act(async () => button('Sửa ánh xạ').click())
    await choose('')
    await act(async () => { await client.invalidateQueries({ queryKey: ['card-template'] }) }); await flush()
    expect(document.querySelector('select')!.value).toBe('')
    expect(button('Lưu ánh xạ').disabled).toBe(false)
  })
  it('blocks stale IDs and wrong field types instead of silently dropping them', async () => {
    current = { ...current, input_bindings: { Word: 'foreign' } }
    await render()
    await act(async () => button('Sửa ánh xạ').click())
    expect(document.querySelector('select')!.value).toBe('foreign')
    expect(button('Lưu ánh xạ').disabled).toBe(true)
    expect(document.body.textContent).toContain('Trường không thuộc loại thẻ đã chọn.')
    await choose('field/2')
    expect(button('Lưu ánh xạ').disabled).toBe(true)
    expect(document.body.textContent).toContain('Kiểu trường không phù hợp.')
  })
  it('edits valid prototype-named inputs without treating inherited properties as bindings', async () => {
    current = { ...current, input_bindings: {}, input_schema: ['__proto__', 'constructor', 'toString'].map((key) => ({
      key, label: key, type: 'text', required: true,
    })) }
    await render()
    await act(async () => button('Sửa ánh xạ').click())
    expect(Array.from(document.querySelectorAll('select')).map((select) => select.value)).toEqual(['', '', ''])
    expect(button('Lưu ánh xạ').disabled).toBe(false)
    await choose('field/1')
    await act(async () => button('Lưu ánh xạ').click()); await flush()
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'PATCH')!
    const bindings = JSON.parse(String(init.body)).input_bindings
    expect(Object.hasOwn(bindings, '__proto__')).toBe(true)
    expect(bindings.__proto__).toBe('field/1')
    expect(Object.getPrototypeOf(bindings)).toBe(Object.prototype)
  })
})
