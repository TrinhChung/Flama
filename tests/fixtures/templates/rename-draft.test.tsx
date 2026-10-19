// @vitest-environment jsdom
// Review reproducer: copy into frontend/.review-template-code/ before running Vitest.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { NoteTypeDetailPage } from '@/features/note-types/pages/NoteTypeDetailPage'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const state = vi.hoisted(() => ({
  name: 'Card 1',
  get: vi.fn(),
  rename: vi.fn(),
}))
vi.mock('@/app/api', () => ({ appApi: { get: state.get, mutate: vi.fn().mockResolvedValue({}) } }))
vi.mock('@/shared/api/client', async (original) => ({
  ...await original<typeof import('@/shared/api/client')>(),
  apiRequest: vi.fn().mockResolvedValue({ items: [] }),
  apiJson: state.rename,
}))
vi.mock('@/features/note-types/components/NoteTypeLivePreview', () => ({ NoteTypeLivePreview: () => null }))
vi.mock('@/components/ambient-background', () => ({ AmbientBackground: () => null }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const flush = async () => { await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) }) }
function setValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')!.set!.call(element, value)
  element.dispatchEvent(new Event('input', { bubbles: true }))
}
function button(label: string) {
  const found = [...document.querySelectorAll('button')].find(element => element.textContent?.trim() === label)
  expect(found, `button ${label}`).toBeDefined()
  return found!
}

it('preserves unsaved HTML when renaming the same template', async () => {
  state.get.mockImplementation(async () => ({
    id: 'nt-1', name: 'Vocabulary', publish_status: 'private', field_defs: [],
    templates: [{ id: 't1', name: state.name, front_html: '{{Kanji}}', back_html: '{{Meaning}}', shared_css: '', is_default: true }],
  }))
  state.rename.mockImplementation(async (_url, _method, body) => {
    state.name = body.name
    return { id: 't1', name: body.name }
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const container = document.createElement('div')
  document.body.append(container)
  const root = createRoot(container)
  try {
    await act(async () => root.render(
      <QueryClientProvider client={client}><MemoryRouter initialEntries={['/note-types/nt-1']}>
        <Routes><Route path="/note-types/:id" element={<NoteTypeDetailPage />} /></Routes>
      </MemoryRouter></QueryClientProvider>,
    ))
    await flush()
    const textarea = container.querySelector('textarea')!
    expect(textarea.value).toBe('{{Kanji}}')
    await act(async () => setValue(textarea, '<b>UNSAVED DRAFT</b>'))
    expect(textarea.value).toBe('<b>UNSAVED DRAFT</b>')
    await act(async () => button('Đổi tên').click())
    await act(async () => setValue(document.querySelector<HTMLInputElement>('#template-name-input')!, 'Renamed'))
    await act(async () => button('Lưu tên').click())
    await flush()
    expect(state.rename).toHaveBeenCalledWith('/api/note-types/nt-1/templates/t1', 'PATCH', { name: 'Renamed' })
    expect(state.get.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(container.querySelector('textarea')!.value).toBe('<b>UNSAVED DRAFT</b>')
  } finally {
    await act(async () => root.unmount())
    client.clear()
    container.remove()
    document.body.innerHTML = ''
  }
})
