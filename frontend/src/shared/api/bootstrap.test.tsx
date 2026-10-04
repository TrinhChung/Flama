// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { bootstrapQueryKey, useBootstrap } from './bootstrap'
import { useBrowseState } from '@/features/browse/hooks/useBrowseState'
import { useAnkiSyncPage } from '@/features/import/hooks/useAnkiSyncPage'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({
  bootstrap: vi.fn(), get: vi.fn(), checkConnection: vi.fn(),
}))
vi.mock('@/app/api', () => ({ appApi: { getBootstrap: mocks.bootstrap, get: mocks.get } }))
vi.mock('@/lib/ankiConnectClient', () => ({
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
})
