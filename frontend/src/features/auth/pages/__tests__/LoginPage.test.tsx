// @vitest-environment jsdom

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import '@/shared/config/i18n'
import { LoginPage } from '../LoginPage'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const mockNavigateComponent = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    Navigate: ({ to, replace }: { to: string; replace?: boolean }) => {
      mockNavigateComponent(to, { replace })
      return createElement('div', { 'data-testid': 'mock-navigate', 'data-to': to })
    },
  }
})

let mockBootstrapData: any = null
let mockBootstrapLoading = false

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: mockBootstrapData,
    isPending: mockBootstrapLoading,
    isLoading: mockBootstrapLoading,
  }),
  bootstrapQueryKey: ['bootstrap'],
}))

vi.mock('../../api', () => ({
  login: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('LoginPage Component Redirection & Authentication States', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient
  const originalLocation = window.location

  beforeEach(() => {
    vi.clearAllMocks()
    mockBootstrapData = null
    mockBootstrapLoading = false

    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
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

  async function renderLoginPage(initialUrl: string) {
    await act(async () => {
      root.render(
        createElement(
          QueryClientProvider,
          { client: queryClient },
          createElement(
            MemoryRouter,
            { initialEntries: [initialUrl] },
            createElement(LoginPage),
          ),
        ),
      )
    })
  }

  it('renders loading spinner while bootstrap query is pending', async () => {
    mockBootstrapLoading = true
    await renderLoginPage('/login')

    const spinner = container.querySelector('.animate-spin')
    expect(spinner).not.toBeNull()
  })

  it('redirects authenticated user to backend endpoint via window.location.href and renders spinner, without Navigate component', async () => {
    mockBootstrapData = {
      user: { id: 1, email: 'user@flama.vn', username: 'flama_user', is_admin: false },
    }
    const backendTarget = '/oauth/authorize?client_id=chatgpt_flama&response_type=code'
    await renderLoginPage(`/login?next=${encodeURIComponent(backendTarget)}`)

    // window.location.href should be updated to backend target
    expect(window.location.href).toBe(backendTarget)
    // Never calls Navigate component for backend routes
    expect(mockNavigateComponent).not.toHaveBeenCalled()
    // Renders spinner while redirect occurs
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).not.toBeNull()
  })

  it('redirects authenticated user to SPA consent page via Navigate component', async () => {
    mockBootstrapData = {
      user: { id: 1, email: 'user@flama.vn', username: 'flama_user', is_admin: false },
    }
    const spaConsentTarget = '/oauth/consent?client_id=chatgpt_flama'
    await renderLoginPage(`/login?next=${encodeURIComponent(spaConsentTarget)}`)

    expect(mockNavigateComponent).toHaveBeenCalledWith(spaConsentTarget, { replace: true })
    expect(window.location.href).toBe('http://localhost:5173/login')
  })

  it('redirects authenticated user to standard SPA route via Navigate component', async () => {
    mockBootstrapData = {
      user: { id: 1, email: 'user@flama.vn', username: 'flama_user', is_admin: false },
    }
    await renderLoginPage('/login?next=/study')

    expect(mockNavigateComponent).toHaveBeenCalledWith('/study', { replace: true })
    expect(window.location.href).toBe('http://localhost:5173/login')
  })

  it('redirects authenticated user to /dashboard when no next param is provided', async () => {
    mockBootstrapData = {
      user: { id: 1, email: 'user@flama.vn', username: 'flama_user', is_admin: false },
    }
    await renderLoginPage('/login')

    expect(mockNavigateComponent).toHaveBeenCalledWith('/dashboard', { replace: true })
  })

  it('renders login form for unauthenticated user', async () => {
    mockBootstrapData = { user: null }
    await renderLoginPage('/login')

    const emailInput = container.querySelector('input[type="email"]')
    const passwordInput = container.querySelector('input[type="password"]')
    expect(emailInput).not.toBeNull()
    expect(passwordInput).not.toBeNull()
    expect(mockNavigateComponent).not.toHaveBeenCalled()
  })
})
