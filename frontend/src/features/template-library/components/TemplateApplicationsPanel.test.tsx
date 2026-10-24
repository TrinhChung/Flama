// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TemplateApplication, TemplateBindings } from '@/entities/card-template'
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
const openActions = async () => {
  await act(async () => document.querySelector<HTMLButtonElement>('[data-slot="dropdown-menu-trigger"]')!.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0 })))
  await flush()
}
const menuItem = (text: string) => Array.from(document.querySelectorAll<HTMLElement>('[role="menuitem"]')).find((item) => item.textContent === text)!

describe('TemplateApplicationsPanel', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let current: TemplateApplication
  let additional: TemplateApplication[]
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
    current = structuredClone(row); additional = []
    props = { noteTypeId: 'nt/1', onChanged: vi.fn() }
    failure = null
    fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (method === 'GET') return String(url).includes('template-applications')
        ? json({ schema_version: 'template-applications.v2', items: [current, ...additional] }) : json({ field_defs: fields })
      if (failure) return json(failure, 400)
      if (method === 'PATCH') current = { ...current, ...JSON.parse(String(init?.body)) }
      if (method === 'DELETE') {
        if (String(url).includes('/templates/')) return json({ success: true, deleted_id: 'template/1' })
        current = { ...current, status_code: 'RETIRED' }
      }
      if (method === 'POST') current = { ...current, ...JSON.parse(String(init?.body)), status_code: 'ACTIVE' }
      return json(current, method === 'POST' ? 201 : 200)
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => { act(() => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = ''; vi.unstubAllGlobals() })
  it('opens the exact application mapping and keeps the use name separate from its design', async () => {
    additional = [{ ...structuredClone(row), id: 'application/2', application_id: 'application/2', display_name: 'Luyện đọc', is_default: false }]
    await render()
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/note-types/nt%2F1/template-applications?include_retired=true'))).toBe(true)
    expect(document.querySelector('a[href="/flashcards/note-types/nt%2F1/templates/application%2F1"]')?.textContent).toContain('Luyện nghe')
    expect(document.querySelector('a[href="/flashcards/note-types/nt%2F1/templates/application%2F2"]')?.textContent).toContain('Luyện đọc')
    expect(document.body.textContent).toContain('Thiết kế: Mẫu dùng chung')
    expect(document.body.textContent).toContain('Đã ánh xạ 1/1 inputs')
    expect(document.body.textContent).not.toContain('listening')
    expect(document.querySelector('select')).toBeNull()
    await openActions()
    expect(document.querySelector('a[href="/card-templates/template%2F1"]')?.textContent).toBe('Sửa thiết kế')
  })
  it('counts bindings with advisory type mismatches and marks stale IDs or unknown keys for repair', async () => {
    current.input_schema = [...row.input_schema, { key: 'Audio', label: 'Audio', type: 'audio', required: false }]
    current.input_bindings = { Word: 'field/1', Audio: null }
    await render()
    expect(document.body.textContent).toContain('Đã ánh xạ 1/2 inputs')
    expect(document.body.textContent).toContain('Còn 1 input để trống')
    current.input_bindings = { Word: 'field/2', Audio: null }
    await act(async () => { await client.invalidateQueries({ queryKey: ['card-template'] }) }); await flush()
    expect(document.body.textContent).toContain('Đã ánh xạ 1/2 inputs')
    expect(document.body.textContent).not.toContain('Cần sửa mapping')
    const invalidBindings: TemplateBindings[] = [{ Word: 'foreign' }, { Word: 'field/1', Removed: 'field/1' }]
    for (const bindings of invalidBindings) {
      current.input_bindings = bindings
      await act(async () => { await client.invalidateQueries({ queryKey: ['card-template'] }) }); await flush()
      expect(document.body.textContent).toContain('Cần sửa mapping')
    }
  })
  it('does not treat inherited prototype keys as mapped inputs', async () => {
    current.input_schema = ['__proto__', 'constructor', 'toString'].map((key) => ({ key, label: key, type: 'text', required: true }))
    current.input_bindings = {}
    await render()
    expect(document.body.textContent).toContain('Đã ánh xạ 0/3 inputs')
    expect(document.body.textContent).toContain('Còn 3 input để trống')
    expect(document.body.textContent).not.toContain('Cần sửa mapping')
  })
  it('PATCHes only the chosen default and preserves IDs, source and bindings', async () => {
    current.is_default = false
    await render(); await openActions()
    await act(async () => menuItem('Đặt làm mặc định').click()); await flush()
    const [url, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'PATCH')!
    expect(String(url)).toContain('/api/note-types/nt%2F1/template-applications/application%2F1')
    expect(JSON.parse(String(init.body))).toEqual({ is_default: true })
    expect(current.id).toBe(row.id)
    expect(current.input_bindings).toEqual(row.input_bindings)
    expect(current.template).toEqual(row.template)
    expect(props.onChanged).toHaveBeenCalledOnce()
  })
  it('retires through confirmation and restores the same occurrence/ID while preserving history', async () => {
    await render(); await openActions()
    await act(async () => menuItem('Gỡ mẫu').click()); await flush()
    expect(document.body.textContent).toContain('Tiến độ đã học được giữ lại.')
    const dialog = document.querySelector('[role="dialog"]')!
    await act(async () => Array.from(dialog.querySelectorAll('button')).find((item) => item.textContent === 'Gỡ mẫu')!.click()); await flush()
    const [url, init] = fetchMock.mock.calls.find(([, options]) => options?.method === 'DELETE')!
    expect(String(url)).toContain('/template-applications/application%2F1')
    expect(init.body).toBeUndefined()
    expect(current.status_code).toBe('RETIRED')
    const removed = document.querySelector('details')!
    expect(removed.open).toBe(false)
    expect(removed.querySelector('summary')?.textContent).toBe('Template đã gỡ · 1')
    await act(async () => { removed.open = true; button('Gắn lại').click() }); await flush()
    const [, postInit] = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(JSON.parse(String(postInit.body))).toEqual({
      template_id: row.template_id, occurrence_key: row.occurrence_key, input_bindings: row.input_bindings,
      display_name: row.display_name, position: row.position, is_default: row.is_default,
    })
    expect(current.id).toBe(row.id)
    expect(current.status_code).toBe('ACTIVE')
  })
  it('keeps the retire confirmation open on error and does not report a successful change', async () => {
    failure = { error: 'FAILED', message: 'Không thể gỡ.' }
    await render(); await openActions()
    await act(async () => menuItem('Gỡ mẫu').click()); await flush()
    const dialog = document.querySelector('[role="dialog"]')!
    await act(async () => Array.from(dialog.querySelectorAll('button')).find((item) => item.textContent === 'Gỡ mẫu')!.click()); await flush()
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Không thể gỡ.')
    expect(current.status_code).toBe('ACTIVE')
    expect(props.onChanged).not.toHaveBeenCalled()
  })
  it('deletes active template after confirmation', async () => {
    await render(); await openActions()
    await act(async () => menuItem('Xóa template').click()); await flush()
    expect(document.body.textContent).toContain('Xóa template khỏi cấu trúc thẻ?')
    const dialog = document.querySelector('[role="dialog"]')!
    await act(async () => Array.from(dialog.querySelectorAll('button')).find((item) => item.textContent === 'Xóa template')!.click()); await flush()
    const [url, init] = fetchMock.mock.calls.find(([callUrl, options]) => options?.method === 'DELETE' && String(callUrl).includes('/templates/'))!
    expect(String(url)).toContain('/note-types/nt%2F1/templates/template%2F1')
    expect(init.body).toBeUndefined()
    expect(props.onChanged).toHaveBeenCalledOnce()
  })
  it('keeps delete confirmation open on error', async () => {
    failure = { error: 'FAILED', message: 'Không thể xóa template mặc định.' }
    await render(); await openActions()
    await act(async () => menuItem('Xóa template').click()); await flush()
    const dialog = document.querySelector('[role="dialog"]')!
    await act(async () => Array.from(dialog.querySelectorAll('button')).find((item) => item.textContent === 'Xóa template')!.click()); await flush()
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Không thể xóa template mặc định.')
    expect(props.onChanged).not.toHaveBeenCalled()
  })
  it('allows deleting retired template from details section', async () => {
    current.status_code = 'RETIRED'
    await render()
    const removed = document.querySelector('details')!
    await act(async () => { removed.open = true })
    const retiredTrigger = removed.querySelector<HTMLButtonElement>('[data-slot="dropdown-menu-trigger"]')!
    await act(async () => retiredTrigger.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0 })))
    await flush()
    await act(async () => menuItem('Xóa template').click()); await flush()
    expect(document.body.textContent).toContain('Xóa template khỏi cấu trúc thẻ?')
    const dialog = document.querySelector('[role="dialog"]')!
    await act(async () => Array.from(dialog.querySelectorAll('button')).find((item) => item.textContent === 'Xóa template')!.click()); await flush()
    const [url] = fetchMock.mock.calls.find(([callUrl, options]) => options?.method === 'DELETE' && String(callUrl).includes('/templates/'))!
    expect(String(url)).toContain('/note-types/nt%2F1/templates/template%2F1')
    expect(props.onChanged).toHaveBeenCalledOnce()
  })
  it('uses supplied field definitions without fetching another detail record', async () => {
    props.fields = fields
    await render()
    expect(fetchMock.mock.calls.filter(([url]) => !String(url).includes('template-applications'))).toHaveLength(0)
    expect(document.body.textContent).toContain('Đã ánh xạ 1/1 inputs')
  })
})
