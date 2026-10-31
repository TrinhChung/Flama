// @vitest-environment jsdom

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import '@/shared/config/i18n'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import { login } from '../../api'
import { useLoginForm } from '../useLoginForm'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../../api', () => ({
  login: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('useLoginForm Redirection Logic', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient
  const originalLocation = window.location

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    delete (window as any).location
    window.location = {
      ...originalLocation,
      origin: 'http://localhost:5173',
      pathname: '/login',
      search: '',
      href: 'http://localhost:5173/login',
      assign: vi.fn(),
      replace: vi.fn(),
    } as any
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    ;(window as any).location = originalLocation
  })

  type HookReturn = ReturnType<typeof useLoginForm>

  function renderHookWithRoute(initialUrl: string): Promise<HookReturn> {
    let hookValues: HookReturn | null = null

    function Harness() {
      hookValues = useLoginForm()
      return createElement(
        'form',
        {
          id: 'test-form',
          onSubmit: hookValues.onSubmit,
        },
        createElement('input', {
          id: 'email',
          ...hookValues.form.register('email'),
        }),
        createElement('input', {
          id: 'password',
          ...hookValues.form.register('password'),
        }),
        createElement('button', { type: 'submit', id: 'submit-btn' }, 'Submit'),
      )
    }

    return new Promise((resolve) => {
      act(() => {
        root.render(
          createElement(
            QueryClientProvider,
            { client: queryClient },
            createElement(
              MemoryRouter,
              { initialEntries: [initialUrl] },
              createElement(Harness),
            ),
          ),
        )
      })
      resolve(hookValues!)
    })
  }

  async function submitForm(hookValues: HookReturn, email = 'user@flama.vn', pass = 'SecurePass123') {
    act(() => {
      hookValues.form.setValue('email', email)
      hookValues.form.setValue('password', pass)
    })

    const formEl = container.querySelector('#test-form') as HTMLFormElement
    await act(async () => {
      formEl.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }))
    })

    // Allow async mutation tick
    await act(async () => {
      await new Promise((r) => setTimeout(r, 20))
    })
  }

  it('redirects to backend via window.location.href when next is a backend OAuth authorize endpoint', async () => {
    vi.mocked(login).mockResolvedValueOnce({
      user: { id: 1, email: 'user@flama.vn', username: 'flama_user', is_admin: false },
      redirect_to: '/dashboard',
    } as any)

    const targetUrl = '/oauth/authorize?client_id=chatgpt_flama&scope=deck:read'
    const hook = await renderHookWithRoute(`/login?next=${encodeURIComponent(targetUrl)}`)
    await submitForm(hook)

    expect(window.location.href).toBe(targetUrl)
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('navigates via React Router when next is a standard SPA route', async () => {
    vi.mocked(login).mockResolvedValueOnce({
      user: { id: 1, email: 'user@flama.vn', username: 'flama_user', is_admin: false },
      redirect_to: '/dashboard',
    } as any)

    const hook = await renderHookWithRoute('/login?next=/study')
    await submitForm(hook)

    expect(mockNavigate).toHaveBeenCalledWith('/study', { replace: true })
    expect(window.location.href).toBe('http://localhost:5173/login')
  })

  it('navigates to /dashboard when next is a malicious protocol-relative URL', async () => {
    vi.mocked(login).mockResolvedValueOnce({
      user: { id: 1, email: 'user@flama.vn', username: 'flama_user', is_admin: false },
      redirect_to: undefined,
    } as any)

    const hook = await renderHookWithRoute('/login?next=//attacker.com/oauth/authorize')
    await submitForm(hook)

    expect(mockNavigate).toHaveBeenCalledWith('/dashboard', { replace: true })
    expect(window.location.href).toBe('http://localhost:5173/login')
  })

  it('navigates to sanitized redirect_to when next is not provided', async () => {
    vi.mocked(login).mockResolvedValueOnce({
      user: { id: 1, email: 'user@flama.vn', username: 'flama_user', is_admin: false },
      redirect_to: '/app/marketplace/decks',
    } as any)

    const hook = await renderHookWithRoute('/login')
    await submitForm(hook)

    expect(mockNavigate).toHaveBeenCalledWith('/marketplace/decks', { replace: true })
    expect(window.location.href).toBe('http://localhost:5173/login')
  })

  it('drops data cached for the previous account and keeps the bootstrap entry', async () => {
    const user = { id: 4, email: 'user@flama.vn', username: 'flama_user', is_admin: false }
    vi.mocked(login).mockResolvedValueOnce({ user, redirect_to: '/sync' } as any)
    queryClient.setQueryData(bootstrapQueryKey, { user: null, messages: [] })
    queryClient.setQueryData(['import-options'], { note_type_options: [{ id: 'note-type-of-previous-account' }] })

    const hook = await renderHookWithRoute('/login')
    await submitForm(hook)

    expect(queryClient.getQueryData(['import-options'])).toBeUndefined()
    expect(queryClient.getQueryData(bootstrapQueryKey)).toEqual({ user, messages: [] })
  })
})
