// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ProfileEditDialog } from './ProfileEditDialog'

const mocks = vi.hoisted(() => ({ updateProfile: vi.fn() }))
vi.mock('../api/profileApi', () => ({ profileApi: { updateProfile: mocks.updateProfile } }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

const keys = [
  ['stats', 'today-future', { scope: 'collection' }],
  ['stats', 'study-time', { scope: 'collection' }],
  ['stats-overview', 2026],
  ['dashboard'],
  ['frontend', 'dashboard', 'overview', 2026],
  ['frontend', 'dashboard'],
  ['frontend', 'statistics', 'config'],
]

describe('ProfileEditDialog analytics policy freshness', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient

  beforeEach(async () => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
    mocks.updateProfile.mockReset().mockResolvedValue({})
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    keys.forEach((key) => client.setQueryData(key, { timezone: 'UTC' }))
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => root.render(
      <QueryClientProvider client={client}>
        <ProfileEditDialog
          open
          onOpenChange={vi.fn()}
          user={{ id: 1, username: 'reader', email: 'reader@example.com', timezone: 'UTC', created_at: null, role: null }}
        />
      </QueryClientProvider>,
    ))
  })

  afterEach(() => {
    act(() => root.unmount())
    client.clear()
    container.remove()
    vi.unstubAllGlobals()
  })

  async function submit(timezone: string) {
    const select = document.querySelector<HTMLSelectElement>('#profile-timezone')!
    act(() => {
      select.value = timezone
      select.dispatchEvent(new Event('change', { bubbles: true }))
    })
    await act(async () => {
      select.closest('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
  }

  it('invalidates cached analytics only after the server accepts a timezone change', async () => {
    let resolveUpdate!: (value: unknown) => void
    mocks.updateProfile.mockReturnValue(new Promise((resolve) => { resolveUpdate = resolve }))
    await submit('Asia/Tokyo')
    expect(mocks.updateProfile).toHaveBeenCalledWith(expect.objectContaining({ timezone: 'Asia/Tokyo' }))
    keys.forEach((key) => expect(client.getQueryState(key)?.isInvalidated).toBe(false))
    await act(async () => {
      resolveUpdate({})
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
    keys.forEach((key) => expect(client.getQueryState(key)?.isInvalidated).toBe(true))
  })

  it('preserves fresh analytics when an ordinary profile edit keeps the same timezone', async () => {
    await submit('UTC')
    expect(mocks.updateProfile).toHaveBeenCalled()
    keys.forEach((key) => expect(client.getQueryState(key)?.isInvalidated).toBe(false))
  })

  it('preserves existing cached analytics when the timezone update fails', async () => {
    mocks.updateProfile.mockRejectedValue(new Error('update rejected'))
    await submit('Asia/Tokyo')
    expect(mocks.updateProfile).toHaveBeenCalled()
    keys.forEach((key) => expect(client.getQueryState(key)?.isInvalidated).toBe(false))
  })
})
