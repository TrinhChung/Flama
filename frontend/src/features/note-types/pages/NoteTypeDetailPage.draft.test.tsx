// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { NoteTypeDetailPage } from './NoteTypeDetailPage'
import type { FieldDefItem } from '../hooks/useNoteTypeFields'

const state = vi.hoisted(() => ({ fields: [] as FieldDefItem[], noteName: 'Vocabulary', get: vi.fn(), mutate: vi.fn() }))
vi.mock('@/app/api', () => ({ appApi: { get: state.get, mutate: state.mutate } }))
vi.mock('@/shared/api/client', async (original) => ({ ...await original<typeof import('@/shared/api/client')>(),
  apiRequest: vi.fn().mockResolvedValue({ items: [] }), apiJson: vi.fn() }))
vi.mock('@/components/ambient-background', () => ({ AmbientBackground: () => null }))

function setValue(element: HTMLInputElement | HTMLSelectElement, value: string) {
  const prototype = element instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(element, value)
  element.dispatchEvent(new Event(element instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }))
}

describe('Note Type field draft lifecycle', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient
  const flush = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 25)) })
  const fieldName = () => container.querySelector('#edit-field-name') as HTMLInputElement
  const button = (text: string, scope: ParentNode = document.body) => {
    const found = Array.from(scope.querySelectorAll('button')).find((item) => item.textContent?.trim() === text)
    expect(found, `Button ${text}`).toBeDefined()
    return found!
  }
  const click = async (text: string, scope?: ParentNode) => { await act(async () => button(text, scope).click()); await flush() }
  const editName = async (value: string) => { await act(async () => setValue(fieldName(), value)) }
  const selectMeaning = async () => {
    const selected = Array.from(container.querySelectorAll<HTMLButtonElement>('button[aria-pressed]')).find((item) => item.textContent?.startsWith('Meaning'))!
    await act(async () => selected.click()); await flush()
  }
  beforeEach(async () => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    await i18n.changeLanguage('vi')
    state.noteName = 'Vocabulary'
    state.fields = [
      { id: 'f1', name: 'Word', field_type: 'text', required: true, identity_role: 'primary', position: 0 },
      { id: 'f2', name: 'Meaning', field_type: 'markdown', required: false, identity_role: null, position: 1 },
    ]
    state.get.mockReset(); state.mutate.mockReset()
    state.get.mockImplementation(async (path: string) => path.endsWith('/fields') ? { items: structuredClone(state.fields) } :
      { id: 'nt-1', name: state.noteName, publish_status: 'private', field_defs: structuredClone(state.fields) })
    state.mutate.mockImplementation(async (path: string, method: string, payload: Partial<FieldDefItem>) => {
      if (path.endsWith('/reorder')) {
        for (const item of payload as unknown as Array<{ id: string; position: number }>) state.fields.find((field) => field.id === item.id)!.position = item.position
        return { success: true }
      }
      if (path.endsWith('/fields') && method === 'POST') {
        const field = { id: 'f3', position: 2, ...payload } as FieldDefItem
        state.fields.push(field); return structuredClone(field)
      }
      if (path === '/note-types/nt-1') { state.noteName = payload.name!; return { id: 'nt-1', name: payload.name } }
      const field = state.fields.find((item) => path.endsWith(`/${item.id}`))!
      if (method === 'DELETE') { state.fields = state.fields.filter((item) => item.id !== field.id); return { success: true } }
      Object.assign(field, payload); return { field: structuredClone(field) }
    })
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    await act(async () => root.render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={['/flashcards/note-types/nt-1']}>
      <Routes><Route path="/flashcards/note-types/:id" element={<NoteTypeDetailPage />} />
        <Route path="/flashcards/note-types/:id/templates" element={<p>Templates destination</p>} /></Routes>
    </MemoryRouter></QueryClientProvider>))
    await flush()
    expect(fieldName().value).toBe('Word')
  })
  afterEach(async () => { await act(async () => root.unmount()); queryClient.clear(); container.remove(); document.body.innerHTML = ''; vi.restoreAllMocks() })

  it('preserves the current field draft through metadata rename and field refetch', async () => {
    await editName('Unfinished word')
    await click('Đổi tên')
    await act(async () => setValue(document.querySelector('#note-type-name') as HTMLInputElement, 'Renamed vocabulary'))
    await click('Lưu tên')
    await act(async () => { await queryClient.invalidateQueries({ queryKey: ['note-type-fields', 'nt-1'] }) })
    await flush()
    expect(container.querySelector('h1')?.textContent).toBe('Renamed vocabulary')
    expect(fieldName().value).toBe('Unfinished word')
    expect(state.mutate).toHaveBeenCalledWith('/note-types/nt-1', 'PATCH', { name: 'Renamed vocabulary' })
  })

  it('does not replace a dirty draft with changed server data', async () => {
    await editName('Local draft')
    state.fields[0].name = 'Server word'
    await act(async () => { await queryClient.invalidateQueries({ queryKey: ['note-type-fields', 'nt-1'] }) })
    await flush()
    expect(fieldName().value).toBe('Local draft')
  })

  it('refreshes a pristine field when its saved content changes', async () => {
    state.fields[0].name = 'Server word'
    await act(async () => { await queryClient.invalidateQueries({ queryKey: ['note-type-fields', 'nt-1'] }) })
    await flush()
    expect(fieldName().value).toBe('Server word')
  })

  it('offers stay, discard and save before selecting another field', async () => {
    await editName('Renamed word')
    await selectMeaning()
    expect(fieldName().value).toBe('Renamed word')
    await click('Tiếp tục chỉnh sửa')
    expect(fieldName().value).toBe('Renamed word')
    await selectMeaning()
    await click('Lưu và tiếp tục')
    expect(state.mutate).toHaveBeenCalledWith('/note-types/nt-1/fields/f1', 'PATCH', {
      name: 'Renamed word', field_type: 'text', required: true, identity_role: 'primary',
    })
    expect(fieldName().value).toBe('Meaning')
  })

  it('discards only the unsaved field draft before a tab change', async () => {
    await editName('Discard me')
    await act(async () => (container.querySelector('nav a[href$="/templates"]') as HTMLAnchorElement).click())
    await click('Bỏ thay đổi và tiếp tục')
    expect(container.textContent).toContain('Templates destination')
    expect(state.mutate).not.toHaveBeenCalled()
  })

  it('keeps draft and server error when save fails during navigation', async () => {
    state.mutate.mockRejectedValueOnce(new Error('Name already exists'))
    await editName('Duplicate')
    await selectMeaning()
    await click('Lưu và tiếp tục')
    expect(fieldName().value).toBe('Duplicate')
    expect(document.body.textContent).toContain('Name already exists')
    expect(document.querySelector('[data-slot="dialog-content"]')).not.toBeNull()
  })

  it('protects an unsaved field before reorder and only commits positions upon explicit save', async () => {
    await editName('Saved identity')
    const down = container.querySelector('button[aria-label="Di chuyển xuống"]') as HTMLButtonElement
    await act(async () => down.click())
    await click('Lưu và tiếp tục')
    expect(state.fields.find((field) => field.id === 'f1')?.name).toBe('Saved identity')
    expect(fieldName().value).toBe('Saved identity')
    // Moving field does not auto-save to server
    expect(state.mutate).not.toHaveBeenCalledWith('/note-types/nt-1/fields/reorder', 'POST', expect.anything())
    // Explicitly click "Lưu trường" (unified save button) to persist
    await click('Lưu trường')
    expect(state.mutate).toHaveBeenCalledWith('/note-types/nt-1/fields/reorder', 'POST', [{ id: 'f2', position: 0 }, { id: 'f1', position: 1 }])
  })

  it('activates save upon reorder and allows discarding without server call', async () => {
    const down = container.querySelector('button[aria-label="Di chuyển xuống"]') as HTMLButtonElement
    await act(async () => down.click())
    expect(state.mutate).not.toHaveBeenCalledWith('/note-types/nt-1/fields/reorder', 'POST', expect.anything())
    expect(button('Lưu trường', container).disabled).toBe(false)
    await act(async () => (container.querySelector('nav a[href$="/templates"]') as HTMLAnchorElement).click())
    await click('Bỏ thay đổi và tiếp tục')
    expect(container.textContent).toContain('Templates destination')
    expect(state.mutate).not.toHaveBeenCalledWith('/note-types/nt-1/fields/reorder', 'POST', expect.anything())
  })

  it('creates a typed field without storing samples or editor options', async () => {
    await click('Thêm')
    await act(async () => {
      setValue(container.querySelector('#new-field-name') as HTMLInputElement, 'Picture')
      setValue(container.querySelector('#new-field-type') as HTMLSelectElement, 'image')
    })
    await click('Dùng mẫu')
    const submit = container.querySelector('form button[type="submit"]') as HTMLButtonElement
    await act(async () => submit.click()); await flush()
    expect(state.mutate).toHaveBeenCalledWith('/note-types/nt-1/fields', 'POST', { name: 'Picture', field_type: 'image', required: false, identity_role: null })
    expect(fieldName().value).toBe('Picture')
    expect(state.fields.find((field) => field.id === 'f3')?.field_type).toBe('image')
  })

  it('blocks browser reload only while a field draft is dirty', async () => {
    await editName('Changed')
    const event = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
    await click('Lưu trường')
    const clean = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(clean)
    expect(clean.defaultPrevented).toBe(false)
  })

  it('keeps sample values per field without making field configuration dirty', async () => {
    await selectMeaning()
    await click('Dùng mẫu')
    const sample = (container.querySelector('#field-editor-sample') as HTMLTextAreaElement).value
    const word = Array.from(container.querySelectorAll('button[aria-pressed]')).find((item) => item.textContent?.startsWith('Word')) as HTMLButtonElement
    await act(async () => word.click()); await flush()
    expect(document.querySelector('[data-slot="dialog-content"]')).toBeNull()
    await selectMeaning()
    expect((container.querySelector('#field-editor-sample') as HTMLTextAreaElement).value).toBe(sample)
    expect(button('Lưu trường', container).disabled).toBe(true)
    expect(state.mutate).not.toHaveBeenCalled()
  })
})
