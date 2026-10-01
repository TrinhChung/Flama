// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminMcpTokensPage } from '../AdminMcpTokensPage'

// Enable React 19 Act Environment
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

// Helper: Dispatches value changes on React-controlled HTMLInputElement in JSDOM
function setNativeInputValue(element: HTMLInputElement, value: string) {
  const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set
  const prototype = Object.getPrototypeOf(element)
  const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set

  if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {
    prototypeValueSetter.call(element, value)
  } else if (valueSetter) {
    valueSetter.call(element, value)
  } else {
    element.value = value
  }
  element.dispatchEvent(new Event('input', { bubbles: true }))
  element.dispatchEvent(new Event('change', { bubbles: true }))
}

// Helper: Click Radix Tabs Trigger
function clickRadixTab(trigger: HTMLElement) {
  trigger.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }))
  trigger.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
  trigger.dispatchEvent(new MouseEvent('pointerup', { bubbles: true }))
  trigger.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
  trigger.click()
}

// Hoisted Mocks
const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  mutate: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  writeText: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/app/api', () => ({
  appApi: {
    get: mocks.get,
    mutate: mocks.mutate,
  },
}))

vi.mock('sonner', () => ({
  toast: {
    success: (...args: unknown[]) => mocks.toastSuccess(...args),
    error: (...args: unknown[]) => mocks.toastError(...args),
  },
}))

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: {
      user: {
        id: 1,
        username: 'admin',
        email: 'admin@nihongo.flama',
        is_admin: true,
        can_manage_mcp_tokens: true,
      },
    },
  }),
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

describe('AdminMcpTokensPage Baseline Characterization Suite', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let queryClient: QueryClient

  const mockAdminSummary = {
    total_tokens: 3,
    active_tokens: 2,
    revoked_tokens: 1,
    expired_tokens: 0,
    inactive_tokens: 1,
    total_requests: 1250,
    total_users: 5,
    permitted_users: 4,
  }

  const mockAdminUsers = [
    {
      id: 10,
      username: 'sensei_tanaka',
      email: 'tanaka@nihongo.flama',
      display_name: 'Tanaka Sensei',
      avatar_url: null,
      role_name: 'Instructor',
      is_admin: false,
      is_disabled: false,
      can_use_mcp: true,
      raw_can_use_mcp: true,
      can_manage_mcp_tokens: true,
      active_tokens_count: 1,
      total_tokens_count: 2,
    },
  ]

  const mockAdminTokens = [
    {
      id: 501,
      user_id: 10,
      username: 'sensei_tanaka',
      email: 'tanaka@nihongo.flama',
      client_id: null,
      client_name: null,
      name: 'Tanaka Cursor Agent',
      status: 'active',
      scopes: ['deck:read', 'note:create'],
      expires_at: '2026-12-31T23:59:59Z',
      max_requests: 10000,
      used_requests: 120,
      remaining_requests: 9880,
      created_at: '2026-01-01T00:00:00Z',
      last_used_at: '2026-09-30T10:00:00Z',
      revoked: false,
    },
    {
      id: 502,
      user_id: 10,
      username: 'sensei_tanaka',
      email: 'tanaka@nihongo.flama',
      client_id: null,
      client_name: null,
      name: 'Tanaka Old Key',
      status: 'revoked',
      scopes: ['deck:read'],
      expires_at: '2026-05-01T00:00:00Z',
      max_requests: 1000,
      used_requests: 1000,
      remaining_requests: 0,
      created_at: '2026-01-01T00:00:00Z',
      last_used_at: null,
      revoked: true,
    },
  ]

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    })

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    Object.assign(navigator, {
      clipboard: {
        writeText: mocks.writeText,
      },
    })

    vi.clearAllMocks()

    mocks.get.mockImplementation((url: string) => {
      if (url === '/admin/mcp-tokens/summary') {
        return Promise.resolve(mockAdminSummary)
      }
      if (url === '/admin/mcp-tokens/users') {
        return Promise.resolve({
          items: mockAdminUsers,
          total: 1,
          page: 1,
          per_page: 50,
          pages: 1,
        })
      }
      if (url === '/admin/mcp-tokens/tokens') {
        return Promise.resolve({
          items: mockAdminTokens,
          total: 2,
          page: 1,
          per_page: 50,
          pages: 1,
        })
      }
      if (url.startsWith('/api/oauth')) {
        return Promise.resolve({ items: [] })
      }
      return Promise.resolve({})
    })
  })

  afterEach(async () => {
    if (root && container) {
      const activeRoot = root
      await act(async () => {
        activeRoot.unmount()
      })
      container.remove()
    }
    document.body.replaceChildren()
    container = null
    root = null
    vi.clearAllMocks()
  })

  const renderPage = async () => {
    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <AdminMcpTokensPage />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })
  }

  // --- ADMIN TOKENS TAB & OWNER COLUMN ---
  it('renders admin token table with Owner column and targets admin tokens endpoint', async () => {
    await renderPage()

    // Wait for admin header & summary stat cards
    await waitFor(() => {
      expect(document.body.textContent).toContain('Quản trị Token & Kết nối AI')
      expect(document.body.textContent).toContain('Token Hoạt động')
    })

    // Click tab 2: Danh sách Token & Secrets
    const tokensTabTrigger = Array.from(document.querySelectorAll('button[role="tab"]')).find((t) =>
      t.textContent?.includes('Danh sách Token & Secrets')
    )
    expect(tokensTabTrigger).toBeDefined()
    await act(async () => {
      clickRadixTab(tokensTabTrigger as HTMLElement)
    })

    // Tokens table should render Owner (Chủ sở hữu) column
    await waitFor(() => {
      expect(document.body.textContent).toContain('Chủ sở hữu')
      expect(document.body.textContent).toContain('sensei_tanaka')
      expect(document.body.textContent).toContain('tanaka@nihongo.flama')
      expect(document.body.textContent).toContain('Tanaka Cursor Agent')
    })

    // Confirm that admin query endpoint was called
    expect(mocks.get).toHaveBeenCalledWith(
      '/admin/mcp-tokens/tokens',
      expect.objectContaining({ page: 1, per_page: 50 })
    )
  })

  // --- ADMIN CREATE TOKEN WITH SECRET REVEAL ---
  it('creates token on behalf of a user, targets admin endpoint, and reveals secret', async () => {
    mocks.mutate.mockResolvedValueOnce({
      item: {
        token: 'flama_sec_admin_issued_xyz987',
        name: 'Assigned Claude Key',
      },
    })

    await renderPage()
    await waitFor(() => {
      expect(document.body.textContent).toContain('Quản trị Token & Kết nối AI')
    })

    const tokensTabTrigger = Array.from(document.querySelectorAll('button[role="tab"]')).find((t) =>
      t.textContent?.includes('Danh sách Token & Secrets')
    )
    expect(tokensTabTrigger).toBeDefined()
    await act(async () => {
      clickRadixTab(tokensTabTrigger as HTMLElement)
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Cấp Token mới cho User')
    })

    // Click "Cấp Token mới cho User" button
    const openCreateBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Cấp Token mới cho User')
    )
    expect(openCreateBtn).toBeDefined()
    await act(async () => {
      openCreateBtn!.click()
    })

    // Wait for create dialog
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cấp MCP Access Token Mới')
    })

    // Fill token name
    const createDialog = document.querySelector('[role="dialog"]')!
    const nameInput = createDialog.querySelector<HTMLInputElement>(
      'input[placeholder*="Claude Desktop PC"]'
    )
    expect(nameInput).not.toBeNull()
    await act(async () => {
      setNativeInputValue(nameInput!, 'Assigned Claude Key')
    })

    // Submit form
    const submitBtn = Array.from(createDialog.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Cấp Token Mới')
    )
    expect(submitBtn).toBeDefined()
    await act(async () => {
      submitBtn!.click()
    })

    // Assert admin POST mutate call
    expect(mocks.mutate).toHaveBeenCalledWith(
      '/admin/mcp-tokens/tokens',
      'POST',
      expect.objectContaining({
        user_id: 10,
        name: 'Assigned Claude Key',
        scopes: expect.any(Array),
      })
    )

    // Admin secret reveal modal appears
    await waitFor(() => {
      expect(document.body.textContent).toContain('Token & Secret Đã Được Tạo Thành Công')
      const secretInput = document.querySelector<HTMLInputElement>('input.font-mono')
      expect(secretInput?.value).toBe('flama_sec_admin_issued_xyz987')
    })

    // Copy secret token
    const copyBtn = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')).find(
      (b) => b.textContent?.includes('Sao chép') && !b.textContent?.includes('URL')
    )
    expect(copyBtn).toBeDefined()
    await act(async () => {
      copyBtn!.click()
    })

    expect(mocks.writeText).toHaveBeenCalledWith('flama_sec_admin_issued_xyz987')
  })

  // --- ADMIN ROTATE, REVOKE, PURGE & CLEANUP ---
  it('dispatches admin rotate, revoke, purge, and cleanup endpoints', async () => {
    mocks.mutate.mockResolvedValueOnce({
      item: {
        token: 'flama_sec_admin_rotated_456',
        name: 'Tanaka Cursor Agent',
      },
    }) // for rotate
    mocks.mutate.mockResolvedValueOnce({}) // for revoke
    mocks.mutate.mockResolvedValueOnce({}) // for purge
    mocks.mutate.mockResolvedValueOnce({ success: true, purged_count: 1 }) // for cleanup

    await renderPage()
    await waitFor(() => {
      expect(document.body.textContent).toContain('Quản trị Token & Kết nối AI')
    })

    const tokensTabTrigger = Array.from(document.querySelectorAll('button[role="tab"]')).find((t) =>
      t.textContent?.includes('Danh sách Token & Secrets')
    )
    expect(tokensTabTrigger).toBeDefined()
    await act(async () => {
      clickRadixTab(tokensTabTrigger as HTMLElement)
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Tanaka Cursor Agent')
    })

    // 1. Rotate Token
    const rotateBtn = document.querySelector<HTMLButtonElement>(
      'button[title*="Xoay vòng Secret"]'
    )
    expect(rotateBtn).not.toBeNull()
    await act(async () => {
      rotateBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Xoay Vòng Secret Cho Token')
    })

    const confirmRotateBtn = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')).find(
      (b) => b.textContent?.includes('Xác Nhận Xoay Vòng Secret')
    )
    expect(confirmRotateBtn).toBeDefined()
    await act(async () => {
      confirmRotateBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith(
      '/admin/mcp-tokens/tokens/501/rotate',
      'POST',
      expect.anything()
    )

    // Close secret modal
    await waitFor(() => {
      expect(document.body.textContent).toContain('Token & Secret Đã Được Tạo Thành Công')
      const secretInput = document.querySelector<HTMLInputElement>('input.font-mono')
      expect(secretInput?.value).toBe('flama_sec_admin_rotated_456')
    })
    const closeSecretBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đã lưu Secret & Đóng')
    )
    await act(async () => {
      closeSecretBtn?.click()
    })

    // 2. Revoke Token (501)
    const revokeBtn = document.querySelector<HTMLButtonElement>('button[title*="Thu hồi"]')
    expect(revokeBtn).not.toBeNull()
    await act(async () => {
      revokeBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Thu Hồi Token Này?')
    })
    const confirmRevokeBtn = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')).find(
      (b) => b.textContent?.includes('Xác Nhận Thu Hồi')
    )
    await act(async () => {
      confirmRevokeBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith('/admin/mcp-tokens/tokens/501', 'DELETE')

    // 3. Purge Token (502)
    const purgeBtn = document.querySelector<HTMLButtonElement>(
      'button[title*="Xóa vĩnh viễn"]'
    )
    expect(purgeBtn).not.toBeNull()
    await act(async () => {
      purgeBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Xóa Vĩnh Viễn Token?')
    })
    const confirmPurgeBtn = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')).find(
      (b) => b.textContent?.includes('Xóa Vĩnh Viễn')
    )
    await act(async () => {
      confirmPurgeBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith('/admin/mcp-tokens/tokens/502/purge', 'DELETE')

    // 4. Cleanup Expired / Inactive Tokens
    const cleanupBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Dọn dẹp 1 token cũ')
    )
    expect(cleanupBtn).toBeDefined()
    await act(async () => {
      cleanupBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Dọn Dẹp Token Hết Hạn & Đã Thu Hồi')
    })
    const confirmCleanupBtn = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')).find(
      (b) => b.textContent?.includes('Xác Nhận Dọn Dẹp')
    )
    await act(async () => {
      confirmCleanupBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith('/admin/mcp-tokens/cleanup', 'POST')
  })
})
