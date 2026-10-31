// @vitest-environment jsdom

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import '@/shared/config/i18n'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import { logout } from '../../api'
import { useLogout } from '../useLogout'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../api', () => ({
  logout: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

describe('useLogout', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient
  let mutation: ReturnType<typeof useLogout>

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    function Harness() {
      mutation = useLogout()
      return null
    }
    act(() => {
      root.render(
        createElement(
          QueryClientProvider,
          { client: queryClient },
          createElement(MemoryRouter, null, createElement(Harness)),
        ),
      )
    })
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('signs out without leaving the previous account data in the cache', async () => {
    vi.mocked(logout).mockResolvedValueOnce({ redirect_to: '/' })
    const user = { id: 36, email: 'previous@flama.vn', username: 'previous', is_admin: false }
    queryClient.setQueryData(bootstrapQueryKey, { user, messages: [{ category: 'info', message: 'hi' }] })
    queryClient.setQueryData(['import-options'], { note_type_options: [{ id: 'note-type-of-previous-account' }] })

    await act(async () => {
      await mutation.mutateAsync()
    })

    expect(queryClient.getQueryData(['import-options'])).toBeUndefined()
    expect(queryClient.getQueryData(bootstrapQueryKey)).toEqual({ user: null, messages: [] })
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
    expect(toast.success).toHaveBeenCalled()
  })

  it('keeps the session cache and reports the error when sign-out fails', async () => {
    vi.mocked(logout).mockRejectedValueOnce(new Error('offline'))
    queryClient.setQueryData(['import-options'], { note_type_options: [] })

    await act(async () => {
      await mutation.mutateAsync().catch(() => undefined)
    })

    expect(queryClient.getQueryData(['import-options'])).toEqual({ note_type_options: [] })
    expect(mockNavigate).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenCalledWith(expect.any(String), { description: 'offline' })
  })
})
