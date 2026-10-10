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

function Harness() {
  return <YomitanTokensTab hookResult={useYomitanTokenCRUD()} />
}

let root: Root
let host: HTMLDivElement
let client: QueryClient
const token = 'mining-secret-do-not-put-in-url'

beforeEach(async () => {
  vi.clearAllMocks()
  await i18n.changeLanguage('en')
  vi.mocked(appApi.get).mockResolvedValue({ items: [{ id: 1, name: 'Existing', status: 'active', scopes: [], expires_at: null }], policy: {} })
  vi.mocked(appApi.mutate).mockImplementation(async (path) => path.endsWith('sentence-mining-setup')
    ? { deckName: 'Sentences', modelName: 'Sentence Card' }
    : { item: { id: 2, name: 'asbplayer', status: 'active', scopes: ['note:create'], preset: 'mining-text', token } })
  host = document.createElement('div')
  document.body.append(host)
  root = createRoot(host)
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  await act(async () => {
    root.render(<QueryClientProvider client={client}><MemoryRouter><Harness /></MemoryRouter></QueryClientProvider>)
    await new Promise((resolve) => setTimeout(resolve, 20))
  })
})

afterEach(async () => {
  await act(async () => root.unmount())
  client.clear()
  host.remove()
})

it('creates a text mining token with separate endpoint/key and prepares its model explicitly', async () => {
  const selector = host.querySelector('#connect-token-preset') as HTMLSelectElement
  await act(async () => {
    selector.value = 'mining-text'
    selector.dispatchEvent(new Event('change', { bubbles: true }))
  })
  expect(vi.mocked(appApi.mutate)).not.toHaveBeenCalled()
  const buttons = () => [...host.querySelectorAll('button')]
  const prepare = buttons().find((button) => button.textContent?.includes('Prepare deck and model'))!
  await act(async () => { prepare.click(); await new Promise((resolve) => setTimeout(resolve, 20)) })
  expect(appApi.mutate).toHaveBeenCalledWith('/integration-tokens/sentence-mining-setup', 'POST', {})
  const create = buttons().find((button) => button.textContent?.includes('Generate New Token'))!
  await act(async () => { create.click(); await new Promise((resolve) => setTimeout(resolve, 20)) })
  expect(appApi.mutate).toHaveBeenCalledWith('/integration-tokens', 'POST', expect.objectContaining({ preset: 'mining-text' }))
  const displayed = [...host.querySelectorAll('code')].map((element) => element.textContent)
  expect(displayed).toContain('https://connect.example/v1/anki-connect')
  expect(displayed).toContain(token)
  expect(displayed.some((text) => text?.startsWith('https://') && text.includes(token))).toBe(false)
})
