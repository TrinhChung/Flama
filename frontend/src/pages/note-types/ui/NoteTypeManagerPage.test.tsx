// @vitest-environment jsdom
import '@/shared/config/i18n'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NoteTypeCard, type NoteTypeItem } from '@/features/note-types'
import { NoteTypeManagerPage } from '../index'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const { apiRequest, apiJson, toastError } = vi.hoisted(() => ({ apiRequest: vi.fn(), apiJson: vi.fn(), toastError: vi.fn() }))
vi.mock('@/shared/api/client', () => ({ apiRequest, apiJson }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: toastError } }))
vi.mock('@/features/guide', () => ({ ContextHelpButton: () => <button>Help</button> }))
vi.mock('@/shared/components/SpotlightTour', () => ({
  SpotlightTour: ({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) => isOpen ? <button data-tour-close onClick={onClose}>Close tour</button> : null,
}))

const summary: NoteTypeItem = {
  id: 'nt-summary', name: 'Lightweight vocabulary', field_count: 5, template_count: 3,
  description: 'Summary only', publish_status: 'published', is_marketplace_install: false,
  version: '1.0.0', created_at: null, updated_at: null,
}
function Destination() { return <output data-destination>{useLocation().pathname}</output> }
let host: HTMLDivElement
let root: Root
let client: QueryClient
async function flush() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) }) }
async function renderPage() {
  await act(async () => root.render(
    <QueryClientProvider client={client}><MemoryRouter initialEntries={['/note-types']}>
      <Routes>
        <Route path="/note-types" element={<NoteTypeManagerPage />} />
        <Route path="/flashcards/note-types/:id/fields" element={<Destination />} />
      </Routes>
    </MemoryRouter></QueryClientProvider>,
  ))
  await flush()
}
beforeEach(() => {
  vi.clearAllMocks()
  localStorage.setItem('flama_notetype_spotlight_tour_v1', 'true')
  apiRequest.mockResolvedValue({ items: [summary] })
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 60_000 } } })
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
})
afterEach(async () => { await act(async () => root.unmount()); client.clear(); host.remove(); localStorage.removeItem('flama_notetype_spotlight_tour_v1') })

describe('note type manager summaries', () => {
  it('uses server counts without HTML or field arrays and avoids the full-definition cache', async () => {
    const definitions = { items: [{ id: 'nt-full', name: 'Unrelated full definition', field_defs: [], templates: [] }] }
    client.setQueryData(['note-types'], definitions)
    await renderPage()
    expect(apiRequest).toHaveBeenCalledWith('/api/note-types?summary=1', { signal: expect.any(AbortSignal) })
    expect(host.querySelector('h3')?.textContent).toBe(summary.name)
    expect(host.textContent).toContain('3 template')
    expect(host.textContent).toContain('5 trường')
    expect(host.textContent).toContain('Đã chia sẻ')
    expect(host.textContent).not.toContain('Unrelated full definition')
    expect(client.getQueryData(['note-types'])).toEqual(definitions)
    expect(client.getQueryData(['note-types', 'manager-summary'])).toEqual({ items: [summary] })
  })

  it('continues to refresh with existing broad note-type invalidations', async () => {
    await renderPage()
    apiRequest.mockResolvedValue({ items: [{ ...summary, name: 'Renamed vocabulary', field_count: 6 }] })
    await act(async () => { await client.invalidateQueries({ queryKey: ['note-types'] }) })
    await flush()
    expect(host.querySelector('h3')?.textContent).toBe('Renamed vocabulary')
    expect(host.textContent).toContain('6 trường')
  })

  it('preserves creation, trimming, invalidation, and navigation to fields', async () => {
    apiJson.mockResolvedValue({ id: 'nt-created' })
    await renderPage()
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    const input = host.querySelector('input')!
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, '  New structure  ')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => { host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })) })
    await flush()
    expect(apiJson).toHaveBeenCalledWith('/api/note-types', 'POST', { name: 'New structure' })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['note-types'] })
    expect(host.querySelector('[data-destination]')?.textContent).toBe('/flashcards/note-types/nt-created/fields')
  })

  it('keeps empty names from submitting a mutation', async () => {
    await renderPage()
    await act(async () => { host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })) })
    expect(apiJson).not.toHaveBeenCalled()
    expect(toastError).toHaveBeenCalledWith('Vui lòng nhập tên NoteType')
  })

  it('preserves the empty-list onboarding tour and stores completion', async () => {
    localStorage.removeItem('flama_notetype_spotlight_tour_v1')
    apiRequest.mockResolvedValue({ items: [] })
    await renderPage()
    expect(host.textContent).toContain('Chưa có Cấu trúc thẻ nào')
    expect(host.querySelector('[data-tour-close]')).toBeNull()
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 550)) })
    const close = host.querySelector('[data-tour-close]') as HTMLButtonElement
    expect(close).not.toBeNull()
    await act(async () => close.click())
    expect(localStorage.getItem('flama_notetype_spotlight_tour_v1')).toBe('true')
    expect(host.querySelector('[data-tour-close]')).toBeNull()
  })

  it('renders summary errors without falling back to a full-definition fetch', async () => {
    apiRequest.mockRejectedValueOnce(new Error('Summary request failed'))
    await renderPage()
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('Summary request failed')
    expect(apiRequest).toHaveBeenCalledTimes(1)
  })

  it('preserves zero counts and can still display legacy full-definition cards', async () => {
    const legacy = { id: 'legacy', name: 'Legacy card', field_defs: [{ id: 'f', name: 'Front' }], templates: [{ id: 't', name: 'Card' }] }
    await act(async () => root.render(<MemoryRouter><NoteTypeCard item={{ ...legacy, field_count: 0, template_count: 0 }} index={0} /></MemoryRouter>))
    expect(host.textContent).toContain('0 template')
    expect(host.textContent).toContain('0 trường')
    await act(async () => root.render(<MemoryRouter><NoteTypeCard item={legacy} index={0} /></MemoryRouter>))
    expect(host.textContent).toContain('1 template')
    expect(host.textContent).toContain('1 trường')
  })
})
