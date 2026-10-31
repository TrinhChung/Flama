// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { bootstrapQueryKey, clearAccountQueries, useBootstrap } from './bootstrap'
import { useBrowseState } from '@/features/browse'
import { useAnkiSyncPage } from '@/features/import/hooks/useAnkiSyncPage'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({
  bootstrap: vi.fn(), get: vi.fn(), checkConnection: vi.fn(),
}))
vi.mock('@/app/api', () => ({ appApi: { getBootstrap: mocks.bootstrap, get: mocks.get } }))
vi.mock('@/features/browse/api/browseApi', () => ({
  browseQueryKeys: { noteTypes: ['note-types', 'browse', 'compact'] },
  browseApi: {
    fetchDecks: () => mocks.get('/browse/decks'),
    fetchDeckStructure: () => mocks.get('/browse/decks'),
    fetchDeckSummaries: () => Promise.resolve({ decks: [] }),
    fetchNoteTypes: () => mocks.get('/note-types', { compact: 1 }),
    fetchCards: (params: unknown) => mocks.get('/browse/cards', params),
    fetchCardDetail: (id: string) => mocks.get(`/browse/cards/${id}`),
    createNote: (body: unknown) => mocks.get('/notes', 'POST', body),
    updateCard: (id: string, body: unknown) => mocks.get(`/browse/cards/${id}`, 'PATCH', body),
    deleteNote: (id: string) => mocks.get(`/browse/notes/${id}`, 'DELETE'),
    deleteNotes: (ids: string[]) => mocks.get('/browse/notes/batch-delete', 'POST', { note_ids: ids }),
    generateVoiceVox: (body: unknown) => mocks.get('/browse/voicevox/generate', 'POST', body),
    fetchVoiceVoxProfile: () => mocks.get('/api/tts/providers/voicevox/profile'),
    saveVoiceVoxProfile: (body: unknown) => mocks.get('/api/tts/providers/voicevox/profile', 'PUT', body),
    fetchVoiceVoxVoices: (api_key: string) => mocks.get('/api/tts/providers/voicevox/voices', 'POST', { api_key }),
  },
}))
vi.mock('@/features/import/lib/ankiConnectClient', () => ({
  ankiConnectClient: { checkConnection: mocks.checkConnection },
}))

function payload(username: string) {
  return {
    user: { id: 7, username, is_admin: false }, csrf_token: 'fixture-csrf',
    links: { dashboard: '/dashboard', browse: '/browse', study: '/study' }, messages: [],
  }
}

function ShellAndConsumers() {
  const shell = useBootstrap()
  const browse = useBrowseState()
  const sync = useAnkiSyncPage()
  return (
    <div>
      <span data-shell>{shell.data?.user?.username}</span>
      <span data-browse-admin>{String(browse.isAdmin)}</span>
      <span data-sync>{sync.bootstrapQuery.data?.user?.username}</span>
    </div>
  )
}

describe('Shared session bootstrap', () => {
  let client: QueryClient
  let root: Root
  let container: HTMLDivElement

  beforeEach(() => {
    vi.resetAllMocks()
    mocks.get.mockImplementation((url: string) => Promise.resolve(
      url === '/browse/decks' ? { decks: [] } : { items: [] },
    ))
    mocks.checkConnection.mockResolvedValue({ status: 'Anki is not running' })
    client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    client.clear()
    container.remove()
    vi.restoreAllMocks()
  })

  async function render() {
    await act(async () => root.render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ShellAndConsumers />
        </MemoryRouter>
      </QueryClientProvider>,
    ))
  }

  it('deduplicates cold session requests across shell, Browse and Anki Sync', async () => {
    mocks.bootstrap.mockResolvedValue(payload('Learner'))
    await render()
    await act(async () => vi.waitFor(() => {
      expect(container.querySelector('[data-sync]')?.textContent).toBe('Learner')
    }))
    expect(mocks.bootstrap).toHaveBeenCalledTimes(1)
    expect(container.querySelector('[data-shell]')?.textContent).toBe('Learner')
    expect(mocks.get).toHaveBeenCalledWith('/flashcards/import/options')
  })

  it('reuses the shell cache on navigation and updates all consumers on invalidation', async () => {
    client.setQueryData(bootstrapQueryKey, payload('Cached learner'))
    await render()
    expect(mocks.bootstrap).not.toHaveBeenCalled()
    expect(container.querySelector('[data-sync]')?.textContent).toBe('Cached learner')
    expect(mocks.get).toHaveBeenCalledWith('/flashcards/import/options')

    mocks.bootstrap.mockResolvedValue(payload('Updated learner'))
    await act(async () => client.invalidateQueries({ queryKey: bootstrapQueryKey }))
    await act(async () => vi.waitFor(() => {
      expect(container.querySelector('[data-shell]')?.textContent).toBe('Updated learner')
      expect(container.querySelector('[data-sync]')?.textContent).toBe('Updated learner')
    }))
    expect(mocks.bootstrap).toHaveBeenCalledTimes(1)
    expect(client.getQueryData(['bootstrap'])).toBeUndefined()
  })

  it('refetches account data such as Anki import options after a sign-in change', async () => {
    const previousAccountOptions = { note_type_options: [{ id: 'note-type-of-a', name: '文法N1', fields: [] }] }
    client.setQueryData(bootstrapQueryKey, payload('Learner A'))
    client.setQueryData(['import-options'], previousAccountOptions)

    clearAccountQueries(client)
    client.setQueryData(bootstrapQueryKey, payload('Learner B'))
    await render()

    expect(mocks.bootstrap).not.toHaveBeenCalled()
    expect(container.querySelector('[data-sync]')?.textContent).toBe('Learner B')
    expect(mocks.get).toHaveBeenCalledWith('/flashcards/import/options')
    await act(async () => vi.waitFor(() => {
      expect(client.getQueryData(['import-options'])).toEqual({ items: [] })
    }))
  })
})
