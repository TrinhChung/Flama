// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { NoteTypeDetailPage } from './NoteTypeDetailPage'

const fields = [
  { id: 'f1', name: 'Kanji', field_type: 'text', required: true, identity_role: 'primary', position: 0 },
  { id: 'f2', name: 'Meaning', field_type: 'markdown', required: false, identity_role: null, position: 1 },
]
vi.mock('@/app/api', () => ({ appApi: { get: vi.fn(async (path: string) => path.endsWith('/fields') ? { items: fields } :
  { id: 'nt-1', name: 'Từ vựng', publish_status: 'private', field_defs: fields }), mutate: vi.fn() } }))
vi.mock('@/shared/api/client', async (original) => ({ ...await original<typeof import('@/shared/api/client')>(),
  apiRequest: vi.fn().mockResolvedValue({ items: [] }), apiJson: vi.fn() }))
vi.mock('@/components/ambient-background', () => ({ AmbientBackground: () => null }))

describe('Note Type setup replaces the old card design editor', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient
  beforeEach(async () => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    await i18n.changeLanguage('vi')
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
    await act(async () => root.render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={['/flashcards/note-types/nt-1']}>
      <Routes><Route path="/flashcards/note-types/:id" element={<NoteTypeDetailPage />} /></Routes>
    </MemoryRouter></QueryClientProvider>))
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)) })
  })
  afterEach(async () => { await act(async () => root.unmount()); queryClient.clear(); container.remove(); document.body.innerHTML = '' })

  it('opens data fields by default with two route tabs and no duplicate HTML/CSS workspace', () => {
    expect(container.querySelector('h1')?.textContent).toBe('Từ vựng')
    const current = container.querySelector('nav a[aria-current="page"]')
    expect(current?.textContent).toContain('Trường dữ liệu')
    expect(current?.getAttribute('href')).toBe('/flashcards/note-types/nt-1/fields')
    expect(container.querySelector('nav a[href$="/templates"]')?.textContent).toContain('Templates')
    expect(container.querySelector('#edit-field-name')).not.toBeNull()
    expect(container.textContent).not.toContain('Front HTML')
    expect(container.textContent).not.toContain('Back HTML')
    expect(container.querySelector('[data-slot="tabs-trigger"]')).toBeNull()
  })

  it('exposes field search, input demo, share, help and rename in the new setup', () => {
    expect(container.querySelector('input[aria-label="Tìm trường…"]')).not.toBeNull()
    expect(container.textContent).toContain('Cách nhập liệu')
    expect(container.querySelector('a[href="/marketplace/note-types/publish?id=nt-1"]')).not.toBeNull()
    expect(container.querySelector('a[href="/flashcards/note-types/guide"]')).not.toBeNull()
    expect(Array.from(container.querySelectorAll('button')).some((button) => button.textContent === 'Đổi tên')).toBe(true)
  })

  it('keeps the primary identity field text, required and protected from deletion', () => {
    expect((container.querySelector('#edit-field-type') as HTMLSelectElement).disabled).toBe(true)
    expect(container.querySelector('#edit-field-required')?.getAttribute('aria-checked')).toBe('true')
    const deleteButton = Array.from(container.querySelectorAll('button')).find((button) => button.textContent?.includes('Xóa trường'))
    expect(deleteButton?.disabled).toBe(true)
  })
})
