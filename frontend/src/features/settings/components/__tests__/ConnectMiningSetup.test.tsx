// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { appApi } from '@/app/api'
import { useYomitanTokenCRUD } from '../../hooks/useYomitanTokenCRUD'
import { YomitanTokensTab } from '../YomitanTokensTab'

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
  return <YomitanTokensTab hookResult={useYomitanTokenCRUD()} />
}

let root: Root
let host: HTMLDivElement
let client: QueryClient
const token = 'yomitan-secret-token-abcdef'

beforeEach(async () => {
  vi.clearAllMocks()
  await i18n.changeLanguage('en')
  vi.mocked(appApi.get).mockResolvedValue({
    items: [
      { id: 1, name: 'Existing Yomitan', status: 'active', scopes: [], preset: 'legacy', token_prefix: 'flama_yt_1', expires_at: null },
      { id: 2, name: 'asbplayer Token', status: 'active', scopes: ['note:create'], preset: 'mining-text', token_prefix: 'flama_yt_2', expires_at: null },
    ],
    policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true },
  })
  vi.mocked(appApi.mutate).mockResolvedValue({
    item: { id: 3, name: 'Yomitan - Personal PC', status: 'active', scopes: [], preset: 'legacy', token },
  })
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

it('exhibits pure Yomitan behavior without preset selector or asbplayer alerts', async () => {
  // 1. Verify absence of preset selector
  const presetSelector = host.querySelector('#connect-token-preset')
  expect(presetSelector).toBeNull()

  // 2. Verify absence of "Prepare deck and model" or asbplayer alerts
  const buttons = () => [...host.querySelectorAll('button')]
  const prepare = buttons().find((button) => button.textContent?.includes('Prepare deck and model'))
  expect(prepare).toBeUndefined()

  // Wait for query to resolve and verify pure Yomitan token filtering in table
  await waitFor(() => {
    expect(host.textContent).toContain('Existing Yomitan')
  })
  expect(host.textContent).not.toContain('asbplayer Token')

  // 3. Verify pure Yomitan config alert is present
  expect(host.textContent).toContain('Quick Yomitan Configuration')

  // 4. Create token
  const create = buttons().find((button) => button.textContent?.includes('Generate New Token'))!
  expect(create).toBeDefined()
  await act(async () => {
    create.click()
    await new Promise((resolve) => setTimeout(resolve, 20))
  })
  expect(appApi.mutate).toHaveBeenCalledWith(
    '/integration-tokens',
    'POST',
    expect.objectContaining({ preset: 'legacy' })
  )

  // 5. Verify single embedded Flama Connect URL is displayed and contains the token in the URL path
  await waitFor(() => {
    const displayed = [...host.querySelectorAll('code')].map((element) => element.textContent)
    expect(displayed).toContain(`https://connect.example/v1/flama-connect/${encodeURIComponent(token)}`)

    // Ensure no separate raw token code block is displayed
    const exactTokenCode = displayed.filter((text) => text === token)
    expect(exactTokenCode.length).toBe(0)
  })
})
