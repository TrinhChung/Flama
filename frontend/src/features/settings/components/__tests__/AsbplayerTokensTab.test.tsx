// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { appApi } from '@/app/api'
import { useAsbplayerTokenCRUD } from '../../hooks/useAsbplayerTokenCRUD'
import { AsbplayerTokensTab } from '../AsbplayerTokensTab'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('@/app/api', () => ({ appApi: { get: vi.fn(), mutate: vi.fn() } }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))
vi.mock('@/config/env', () => ({
  FLAMA_CONNECT_URL: 'https://connect.example/v1/flama-connect',
  FLAMA_ANKI_CONNECT_URL: 'https://connect.example/v1/anki-connect',
}))

async function waitFor(assertion: () => void, timeoutMs = 2500) {
  const start = Date.now()
  let lastError: unknown
  while (Date.now() - start < timeoutMs) {
    try {
      assertion()
      return
    } catch (err) {
      lastError = err
      await act(async () => {
        await new Promise((r) => setTimeout(r, 15))
      })
    }
  }
  if (lastError) throw lastError
}

function Harness() {
  return <AsbplayerTokensTab hookResult={useAsbplayerTokenCRUD()} />
}

let root: Root
let host: HTMLDivElement
let client: QueryClient
const token = 'asbplayer-secret-key-12345'

beforeEach(async () => {
  vi.clearAllMocks()
  await i18n.changeLanguage('en')
  vi.mocked(appApi.get).mockResolvedValue({
    items: [
      { id: 1, name: 'asbplayer Desktop', status: 'active', scopes: ['note:create'], preset: 'mining-text', token_prefix: 'flama_yt_abc', expires_at: null },
      { id: 2, name: 'Yomitan Token', status: 'active', scopes: [], preset: 'legacy', token_prefix: 'flama_yt_legacy', expires_at: null },
    ],
    policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true },
  })
  vi.mocked(appApi.mutate).mockImplementation(async (path) =>
    path.endsWith('sentence-mining-setup')
      ? { deckName: 'Sentences', modelName: 'Sentence Card' }
      : { item: { id: 3, name: 'asbplayer - Media', status: 'active', scopes: ['note:create', 'media:write'], preset: 'mining-media', token } }
  )
  host = document.createElement('div')
  document.body.append(host)
  root = createRoot(host)
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  await act(async () => {
    root.render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Harness />
        </MemoryRouter>
      </QueryClientProvider>
    )
  })
})

afterEach(async () => {
  await act(async () => root.unmount())
  client.clear()
  host.remove()
})

it('selects preset, calls sentence-mining-setup, and creates token with separate AnkiConnect URL and Key', async () => {
  // Wait for query to resolve and verify token filtering: Yomitan token is filtered out, only asbplayer token shown
  await waitFor(() => {
    expect(host.textContent).toContain('asbplayer Desktop')
  })
  expect(host.textContent).not.toContain('Yomitan Token')

  // Select mining-media preset
  const selector = host.querySelector('#asbplayer-token-preset') as HTMLSelectElement
  expect(selector).not.toBeNull()
  await act(async () => {
    selector.value = 'mining-media'
    selector.dispatchEvent(new Event('change', { bubbles: true }))
  })

  // Click Prepare deck and model button
  const buttons = () => [...host.querySelectorAll('button')]
  const prepare = buttons().find((button) => button.textContent?.includes('Prepare deck and model'))!
  expect(prepare).toBeDefined()
  await act(async () => {
    prepare.click()
    await new Promise((resolve) => setTimeout(resolve, 20))
  })
  expect(appApi.mutate).toHaveBeenCalledWith('/integration-tokens/sentence-mining-setup', 'POST', {})

  // Create token
  const create = buttons().find((button) => button.textContent?.includes('Generate New Token'))!
  expect(create).toBeDefined()
  await act(async () => {
    create.click()
    await new Promise((resolve) => setTimeout(resolve, 20))
  })
  expect(appApi.mutate).toHaveBeenCalledWith(
    '/integration-tokens',
    'POST',
    expect.objectContaining({ preset: 'mining-media' })
  )

  // Verify AnkiConnect URL and API key displayed separately
  await waitFor(() => {
    const displayed = [...host.querySelectorAll('code')].map((element) => element.textContent)
    expect(displayed).toContain('https://connect.example/v1/anki-connect')
    expect(displayed).toContain(token)
    expect(displayed.some((text) => text?.startsWith('https://') && text.includes(token))).toBe(false)
  })
})
