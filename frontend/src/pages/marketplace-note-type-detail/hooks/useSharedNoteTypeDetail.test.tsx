// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import '@/shared/config/i18n'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { noteTypeDetailApi } from '../api/noteTypeDetailApi'
import { useSharedNoteTypeDetail } from './useSharedNoteTypeDetail'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (original) => ({
  ...await original<typeof import('react-router-dom')>(),
  useNavigate: () => mockNavigate,
}))
vi.mock('../api/noteTypeDetailApi', () => ({
  noteTypeDetailApi: { detail: vi.fn(), preview: vi.fn(), status: vi.fn(), publishOptions: vi.fn() },
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))

let hook: ReturnType<typeof useSharedNoteTypeDetail>
function Probe() {
  hook = useSharedNoteTypeDetail()
  return null
}
async function settle() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) }) }

describe('Note Type publish status from the detail page', () => {
  let container: HTMLDivElement
  let root: Root
  let client: QueryClient
  beforeEach(async () => {
    vi.clearAllMocks()
    vi.mocked(noteTypeDetailApi.detail).mockResolvedValue({ id: 'nt-1', templates: [] } as never)
    vi.mocked(noteTypeDetailApi.status).mockResolvedValue({})
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    await act(async () => root.render(
      <QueryClientProvider client={client}><MemoryRouter initialEntries={['/marketplace/note-types/nt-1']}>
        <Routes><Route path="/marketplace/note-types/:id" element={<Probe />} /></Routes>
      </MemoryRouter></QueryClientProvider>,
    ))
    await settle()
  })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove() })

  it('withdraws without consulting the template listings', async () => {
    await act(async () => hook.publishStatusMutation.mutate('private'))
    await settle()
    expect(noteTypeDetailApi.status).toHaveBeenCalledWith('nt-1', { publish_status: 'private' })
    expect(noteTypeDetailApi.publishOptions).not.toHaveBeenCalled()
  })

  it('republishes directly when every own template is still listed', async () => {
    vi.mocked(noteTypeDetailApi.publishOptions).mockResolvedValue({ templates: [{ is_owned: true, requires_publication: false }] })
    await act(async () => hook.publishStatusMutation.mutate('published'))
    await settle()
    expect(noteTypeDetailApi.status).toHaveBeenCalledWith('nt-1', { publish_status: 'published' })
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('sends the author to the publish form when an own template needs a price again', async () => {
    vi.mocked(noteTypeDetailApi.publishOptions).mockResolvedValue({ templates: [{ is_owned: true, requires_publication: true }] })
    await act(async () => hook.publishStatusMutation.mutate('published'))
    await settle()
    expect(noteTypeDetailApi.status).not.toHaveBeenCalled()
    expect(mockNavigate).toHaveBeenCalledWith('/marketplace/note-types/publish?id=nt-1&edit=1')
  })
})
