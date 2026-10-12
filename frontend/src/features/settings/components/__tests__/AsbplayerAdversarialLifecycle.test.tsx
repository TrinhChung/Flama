// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { appApi } from '@/app/api'
import { toast } from 'sonner'
import { useAsbplayerTokenCRUD } from '../../hooks/useAsbplayerTokenCRUD'
import { AsbplayerTokensTab } from '../AsbplayerTokensTab'
import { YomitanTokensTab } from '../YomitanTokensTab'
import { useYomitanTokenCRUD } from '../../hooks/useYomitanTokenCRUD'

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

function AsbplayerHarness() {
  return <AsbplayerTokensTab hookResult={useAsbplayerTokenCRUD()} />
}

function YomitanHarness() {
  return <YomitanTokensTab hookResult={useYomitanTokenCRUD()} />
}

describe('Asbplayer Adversarial & Edge Case Lifecycle Tests', () => {
  let root: Root
  let host: HTMLDivElement
  let client: QueryClient

  beforeEach(async () => {
    vi.clearAllMocks()
    await i18n.changeLanguage('en')
    host = document.createElement('div')
    document.body.append(host)
    root = createRoot(host)
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })

    // Setup clipboard mock
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    client.clear()
    host.remove()
  })

  it('Edge Condition 1: Renders EmptyState when user has no asbplayer tokens', async () => {
    // Only return legacy Yomitan token, so asbplayer tokens list is empty
    vi.mocked(appApi.get).mockResolvedValue({
      items: [
        { id: 99, name: 'Yomitan Only', status: 'active', scopes: [], preset: 'legacy', token_prefix: 'flama_yt_99', expires_at: null },
      ],
      policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true },
    })

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <AsbplayerHarness />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    await waitFor(() => {
      expect(host.textContent).toContain('No asbplayer tokens yet')
    })
    expect(host.textContent).toContain('Create your first token to connect the asbplayer extension to Flama.')
    expect(host.textContent).not.toContain('Yomitan Only')
  })

  it('Edge Condition 2: Handles API error on token creation failure and displays toast error', async () => {
    vi.mocked(appApi.get).mockResolvedValue({ items: [], policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true } })
    vi.mocked(appApi.mutate).mockRejectedValue(new Error('Rate limit exceeded: maximum tokens reached'))

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <AsbplayerHarness />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    const buttons = () => [...host.querySelectorAll('button')]
    const createBtn = buttons().find((button) => button.textContent?.includes('Generate New Token'))!
    expect(createBtn).toBeDefined()

    await act(async () => {
      createBtn.click()
      await new Promise((r) => setTimeout(r, 20))
    })

    expect(toast.error).toHaveBeenCalledWith('Rate limit exceeded: maximum tokens reached')
  })

  it('Edge Condition 3: Handles API error on sentence-mining-setup failure and displays toast error', async () => {
    vi.mocked(appApi.get).mockResolvedValue({ items: [], policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true } })
    vi.mocked(appApi.mutate).mockRejectedValue(new Error('Existing Sentence Card fields differ; configure manually'))

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <AsbplayerHarness />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    const buttons = () => [...host.querySelectorAll('button')]
    const prepareBtn = buttons().find((button) => button.textContent?.includes('Prepare deck and model'))!
    expect(prepareBtn).toBeDefined()

    await act(async () => {
      prepareBtn.click()
      await new Promise((r) => setTimeout(r, 20))
    })

    expect(toast.error).toHaveBeenCalledWith('Existing Sentence Card fields differ; configure manually')
  })

  it('Lifecycle: Token Rotation and Revocation handlers with user confirmation', async () => {
    vi.mocked(appApi.get).mockResolvedValue({
      items: [
        { id: 42, name: 'asbplayer Chrome', status: 'active', scopes: ['note:create'], preset: 'mining-text', token_prefix: 'flama_yt_42', expires_at: null },
      ],
      policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true },
    })
    vi.mocked(appApi.mutate).mockResolvedValue({ item: { id: 43, name: 'asbplayer Chrome', status: 'active', scopes: ['note:create'], preset: 'mining-text', token: 'new-rotated-secret' } })

    // Mock confirm dialog
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <AsbplayerHarness />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    await waitFor(() => {
      expect(host.textContent).toContain('asbplayer Chrome')
    })

    // Find rotate/regenerate button
    const buttons = () => [...host.querySelectorAll('button')]
    const rotateBtn = buttons().find((b) => b.textContent?.includes('Regenerate'))!
    expect(rotateBtn).toBeDefined()

    await act(async () => {
      rotateBtn.click()
      await new Promise((r) => setTimeout(r, 20))
    })

    expect(confirmSpy).toHaveBeenCalled()
    expect(appApi.mutate).toHaveBeenCalledWith('/integration-tokens/42/rotate', 'POST', { expires_in_days: 180 })
    expect(toast.success).toHaveBeenCalledWith('Old token revoked and new token created successfully.')

    // Find revoke button
    const revokeBtn = buttons().find((b) => b.textContent?.includes('Revoke'))!
    expect(revokeBtn).toBeDefined()

    await act(async () => {
      revokeBtn.click()
      await new Promise((r) => setTimeout(r, 20))
    })

    expect(appApi.mutate).toHaveBeenCalledWith('/integration-tokens/42', 'DELETE')
    expect(toast.success).toHaveBeenCalledWith('Token was revoked immediately.')
  })

  it('Clipboard: Verifies copy interactions and clipboard failure fallback', async () => {
    vi.mocked(appApi.get).mockResolvedValue({
      items: [
        { id: 10, name: 'asbplayer Media', status: 'active', scopes: ['note:create', 'media:write'], preset: 'mining-media', token_prefix: 'flama_yt_10', expires_at: null },
      ],
      policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true },
    })

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <AsbplayerHarness />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    await waitFor(() => {
      expect(host.textContent).toContain('asbplayer Media')
    })

    // Click URL copy button in desktop table
    const buttons = () => [...host.querySelectorAll('button')]
    const copyUrlBtn = buttons().find((b) => b.textContent?.trim() === 'URL')!
    expect(copyUrlBtn).toBeDefined()

    await act(async () => {
      copyUrlBtn.click()
      await new Promise((r) => setTimeout(r, 20))
    })

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://connect.example/v1/anki-connect')
    expect(toast.success).toHaveBeenCalledWith('Copied to clipboard.')

    // Test clipboard failure
    vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(new Error('Permission denied'))
    await act(async () => {
      copyUrlBtn.click()
      await new Promise((r) => setTimeout(r, 20))
    })
    expect(toast.error).toHaveBeenCalledWith('Failed to copy to clipboard.')
  })

  it('Separation: Strict mutual exclusion between Yomitan and asbplayer tokens', async () => {
    const mixedTokens = {
      items: [
        { id: 1, name: 'Yomitan Token 1', status: 'active', scopes: [], preset: 'legacy', token_prefix: 'flama_yt_1', expires_at: null },
        { id: 2, name: 'Yomitan Token 2 (custom)', status: 'active', scopes: ['deck:read'], preset: 'custom', token_prefix: 'flama_yt_2', expires_at: null },
        { id: 3, name: 'asbplayer Text', status: 'active', scopes: ['note:create'], preset: 'mining-text', token_prefix: 'flama_yt_3', expires_at: null },
        { id: 4, name: 'asbplayer Media', status: 'active', scopes: ['note:create', 'media:write'], preset: 'mining-media', token_prefix: 'flama_yt_4', expires_at: null },
      ],
      policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true },
    }
    vi.mocked(appApi.get).mockResolvedValue(mixedTokens)

    // Render asbplayer harness
    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <AsbplayerHarness />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    await waitFor(() => {
      expect(host.textContent).toContain('asbplayer Text')
      expect(host.textContent).toContain('asbplayer Media')
    })
    // Yomitan tokens MUST NOT appear in asbplayer table
    expect(host.textContent).not.toContain('Yomitan Token 1')
    expect(host.textContent).not.toContain('Yomitan Token 2 (custom)')

    // Now render Yomitan harness with the SAME mixed token dataset
    await act(async () => root.unmount())
    host = document.createElement('div')
    document.body.append(host)
    root = createRoot(host)
    client.clear()

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <YomitanHarness />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    await waitFor(() => {
      expect(host.textContent).toContain('Yomitan Token 1')
      expect(host.textContent).toContain('Yomitan Token 2 (custom)')
    })
    // asbplayer tokens MUST NOT appear in Yomitan table
    expect(host.textContent).not.toContain('asbplayer Text')
    expect(host.textContent).not.toContain('asbplayer Media')
  })
})
