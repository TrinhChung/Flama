// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { McpTokensManager } from './McpTokensManager'
import type { McpToken } from '../types'
import { ALL_MCP_SCOPES } from '../types'

// Enable React 19 Act Environment
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

// Mock ResizeObserver for JSDOM
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver

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

// Hoisted Mocks
const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  mutate: vi.fn(),
  writeText: vi.fn().mockResolvedValue(undefined),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
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
        email: 'test@nihongo.flama',
        is_admin: true,
        can_manage_mcp_tokens: true,
      },
    },
  }),
}))

async function waitFor(assertion: () => void, timeoutMs = 2000) {
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

describe('McpTokensManager Component Suite', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let queryClient: QueryClient

  const mockActiveToken: McpToken = {
    id: 101,
    name: 'Cursor IDE MacBook',
    status: 'active',
    expires_at: '2026-12-31T23:59:59Z',
    max_requests: 10000,
    used_requests: 42,
    remaining_requests: 9958,
    scopes: ['deck:read', 'note:read', 'note:check', 'study:read'],
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: '2026-09-30T10:00:00Z',
  }

  const mockRevokedToken: McpToken = {
    id: 102,
    name: 'Old Claude Desktop',
    status: 'revoked',
    expires_at: '2026-05-01T00:00:00Z',
    max_requests: 1000,
    used_requests: 1000,
    remaining_requests: 0,
    scopes: ['deck:read'],
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: null,
  }

  const mockAdminToken: McpToken = {
    ...mockActiveToken,
    id: 201,
    name: 'Tanaka Workstation',
    username: 'sensei_tanaka',
    email: 'tanaka@nihongo.flama',
    client_name: 'Antigravity AI',
  }

  const mockUsers = [
    { id: 10, username: 'user10', email: 'user10@nihongo.flama', display_name: 'User Ten' },
    { id: 20, username: 'user20', email: 'user20@nihongo.flama', display_name: 'User Twenty' },
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
    mocks.writeText.mockReset().mockResolvedValue(undefined)
    mocks.mutate.mockReset()
    mocks.toastSuccess.mockReset()
    mocks.toastError.mockReset()
    mocks.get.mockReset().mockResolvedValue({ items: [] })
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

  const renderManager = async (mode: 'user' | 'admin' = 'user', extraProps = {}) => {
    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <McpTokensManager mode={mode} users={mockUsers} {...extraProps} />
        </QueryClientProvider>
      )
    })
  }

  // --- TEST 1: USER MODE RENDERING ---
  it('renders tokens list and stat cards in user mode', async () => {
    mocks.get.mockResolvedValueOnce({
      items: [mockActiveToken, mockRevokedToken],
    })

    await renderManager('user')

    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
      expect(document.body.textContent).toContain('Old Claude Desktop')
      expect(document.body.textContent).toContain('Quản lý MCP Access Tokens')
      expect(document.body.textContent).toContain('Hoạt động')
      expect(document.body.textContent).toContain('Đã thu hồi')
    })

    // Assert that User mode does NOT render owner column header
    expect(document.body.textContent).not.toContain('Chủ sở hữu')
  })

  // --- TEST 2: ADMIN MODE RENDERING ---
  it('renders Owner column and targets admin endpoint in admin mode', async () => {
    mocks.get.mockResolvedValueOnce({
      items: [mockAdminToken],
      total: 1,
      page: 1,
      per_page: 50,
      pages: 1,
    })

    await renderManager('admin')

    await waitFor(() => {
      expect(document.body.textContent).toContain('Chủ sở hữu')
      expect(document.body.textContent).toContain('sensei_tanaka')
      expect(document.body.textContent).toContain('tanaka@nihongo.flama')
      expect(document.body.textContent).toContain('Tanaka Workstation')
      expect(document.body.textContent).toContain('OAuth: Antigravity AI')
    })

    expect(mocks.get).toHaveBeenCalledWith(
      '/admin/mcp-tokens/tokens',
      expect.objectContaining({ page: 1, per_page: 50 })
    )
  })

  // --- TEST 3: SEARCH INPUT FILTERING ---
  it('filters tokens using SearchInput with IME and clear capability', async () => {
    mocks.get.mockResolvedValueOnce({
      items: [mockActiveToken, mockRevokedToken],
    })

    await renderManager('user')

    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
      expect(document.body.textContent).toContain('Old Claude Desktop')
    })

    const searchInput = document.querySelector<HTMLInputElement>(
      'input[placeholder*="Tìm kiếm token"]'
    )
    expect(searchInput).not.toBeNull()

    // Filter for "Claude"
    await act(async () => {
      setNativeInputValue(searchInput!, 'Claude')
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Old Claude Desktop')
      expect(document.body.textContent).not.toContain('Cursor IDE MacBook')
    })

    // Clear search
    await act(async () => {
      setNativeInputValue(searchInput!, '')
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
      expect(document.body.textContent).toContain('Old Claude Desktop')
    })
  })

  // --- TEST 4: CREATE TOKEN & SECRET MODAL WITH CODE SNIPPET BOX ---
  it('creates token and reveals secret key with CodeSnippetBox', async () => {
    mocks.get.mockResolvedValueOnce({ items: [] })
    mocks.mutate.mockResolvedValueOnce({
      item: {
        id: 105,
        name: 'New Agent Key',
        token: 'flama_sec_agent_live_999',
        status: 'active',
        scopes: ALL_MCP_SCOPES.map((s) => s.key),
      },
    })

    await renderManager('user')

    const createBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tạo Token mới')
    )
    expect(createBtn).toBeDefined()
    await act(async () => {
      createBtn!.click()
    })

    // Modal opens
    await waitFor(() => {
      expect(document.body.textContent).toContain('Tạo MCP Access Token mới')
    })

    const nameInput = document.querySelector<HTMLInputElement>('#mcp-token-name')
    expect(nameInput).not.toBeNull()
    await act(async () => {
      setNativeInputValue(nameInput!, 'New Agent Key')
    })

    // Click submit in modal
    const dialog = document.querySelector('[role="dialog"]')!
    const submitBtn = Array.from(dialog.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tạo Token mới')
    )
    expect(submitBtn).toBeDefined()
    await act(async () => {
      submitBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith(
      '/mcp-tokens',
      'POST',
      expect.objectContaining({
        name: 'New Agent Key',
        scopes: expect.any(Array),
      })
    )

    // Secret Reveal Modal appears with CodeSnippetBox
    await waitFor(() => {
      expect(document.body.textContent).toContain('Token & Secret Đã Được Tạo Thành Công')
      expect(document.body.textContent).toContain('flama_sec_agent_live_999')
      expect(document.body.textContent).toContain('Secret Access Token (Bearer Key)')
    })

    // Test copy via CodeSnippetBox button
    const copySecretBtn = Array.from(
      document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')
    ).find((b) => b.textContent?.includes('Sao chép') && !b.textContent?.includes('URL'))
    expect(copySecretBtn).toBeDefined()
    await act(async () => {
      copySecretBtn!.click()
    })
    expect(mocks.writeText).toHaveBeenCalledWith('flama_sec_agent_live_999')

    // Close secret modal
    const closeBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đã lưu Secret & Đóng')
    )
    expect(closeBtn).toBeDefined()
    await act(async () => {
      closeBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).not.toContain('Token & Secret Đã Được Tạo Thành Công')
    })
  })

  // --- TEST 5: EDIT TOKEN MODAL ---
  it('opens edit modal and saves modified token properties', async () => {
    mocks.get.mockResolvedValueOnce({ items: [mockActiveToken] })
    mocks.mutate.mockResolvedValueOnce({
      item: { ...mockActiveToken, name: 'Updated IDE Name' },
    })

    await renderManager('user')
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
    })

    const editBtn = document.querySelector<HTMLButtonElement>('button[title*="Chỉnh sửa"]')
    expect(editBtn).not.toBeNull()
    await act(async () => {
      editBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Chỉnh sửa MCP Token')
    })

    const editNameInput = document.querySelector<HTMLInputElement>('#edit-token-name')
    expect(editNameInput?.value).toBe('Cursor IDE MacBook')
    await act(async () => {
      setNativeInputValue(editNameInput!, 'Updated IDE Name')
    })

    const dialog = document.querySelector('[role="dialog"]')!
    const saveBtn = Array.from(dialog.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Lưu quyền hạn')
    )
    expect(saveBtn).toBeDefined()
    await act(async () => {
      saveBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith(
      `/mcp-tokens/${mockActiveToken.id}`,
      'PATCH',
      expect.objectContaining({ name: 'Updated IDE Name' })
    )
  })

  // --- TEST 6: ROTATE SECRET CONFIRM DIALOG ---
  it('opens rotate ConfirmDialog, executes rotation, and reveals new secret', async () => {
    mocks.get.mockResolvedValueOnce({ items: [mockActiveToken] })
    mocks.mutate.mockResolvedValueOnce({
      item: {
        id: mockActiveToken.id,
        name: mockActiveToken.name,
        token: 'flama_sec_rotated_new_key_777',
      },
    })

    await renderManager('user')
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
    })

    const rotateBtn = document.querySelector<HTMLButtonElement>('button[title*="Xoay vòng"]')
    expect(rotateBtn).not.toBeNull()
    await act(async () => {
      rotateBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Đổi Secret Token (Rotate)')
    })

    const dialog = document.querySelector('[role="dialog"]')!
    const confirmRotateBtn = Array.from(dialog.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xác nhận Đổi Secret')
    )
    expect(confirmRotateBtn).toBeDefined()
    await act(async () => {
      confirmRotateBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith(
      `/mcp-tokens/${mockActiveToken.id}/rotate`,
      'POST',
      expect.objectContaining({ expires_in_days: 180 })
    )

    await waitFor(() => {
      expect(document.body.textContent).toContain('flama_sec_rotated_new_key_777')
    })
  })

  // --- TEST 7: REVOKE & PURGE CONFIRM DIALOGS ---
  it('handles revoke for active token and purge for inactive token', async () => {
    mocks.get.mockResolvedValue({ items: [mockActiveToken, mockRevokedToken] })
    mocks.mutate.mockResolvedValueOnce({}) // For Revoke
    mocks.mutate.mockResolvedValueOnce({}) // For Purge

    await renderManager('user')
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
      expect(document.body.textContent).toContain('Old Claude Desktop')
    })

    // 1. Revoke active token
    const revokeBtn = document.querySelector<HTMLButtonElement>('button[title*="Thu hồi"]')
    expect(revokeBtn).not.toBeNull()
    await act(async () => {
      revokeBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Xác nhận thu hồi MCP Token')
    })

    const revokeDialog = document.querySelector('[role="dialog"]')!
    const confirmRevokeBtn = Array.from(revokeDialog.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xác nhận thu hồi')
    )
    expect(confirmRevokeBtn).toBeDefined()
    await act(async () => {
      confirmRevokeBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith(`/mcp-tokens/${mockActiveToken.id}`, 'DELETE')

    // 2. Purge revoked token
    const purgeBtn = document.querySelector<HTMLButtonElement>('button[title*="Xóa vĩnh viễn"]')
    expect(purgeBtn).not.toBeNull()
    await act(async () => {
      purgeBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Xác nhận xóa vĩnh viễn Token')
    })

    const purgeDialog = document.querySelector('[role="dialog"]')!
    const confirmPurgeBtn = Array.from(purgeDialog.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xóa vĩnh viễn')
    )
    expect(confirmPurgeBtn).toBeDefined()
    await act(async () => {
      confirmPurgeBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith(`/mcp-tokens/${mockRevokedToken.id}/purge`, 'DELETE')
  })

  // --- TEST 8: CLEANUP EXPIRED TOKENS CONFIRM DIALOG ---
  it('triggers cleanup for inactive tokens from header button', async () => {
    mocks.get.mockResolvedValue({ items: [mockActiveToken, mockRevokedToken] })
    mocks.mutate.mockResolvedValueOnce({ success: true, purged_count: 1 })

    await renderManager('user')
    await waitFor(() => {
      expect(document.body.textContent).toContain('Dọn dẹp 1 token cũ')
    })

    const cleanupBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Dọn dẹp 1 token cũ')
    )
    expect(cleanupBtn).toBeDefined()
    await act(async () => {
      cleanupBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Dọn dẹp Token cũ & Hết hạn')
    })

    const dialog = document.querySelector('[role="dialog"]')!
    const confirmCleanupBtn = Array.from(dialog.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Dọn dẹp 1 token')
    )
    expect(confirmCleanupBtn).toBeDefined()
    await act(async () => {
      confirmCleanupBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith('/mcp-tokens/cleanup', 'POST')
  })

  // --- TEST 9: VIEW SCOPE DETAILS DIALOG ---
  it('opens scope details dialog showing descriptions', async () => {
    mocks.get.mockResolvedValueOnce({ items: [mockActiveToken] })

    await renderManager('user')
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
    })

    const scopesBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Scopes')
    )
    expect(scopesBtn).toBeDefined()
    await act(async () => {
      scopesBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Chi Tiết Quyền Hạn (Cursor IDE MacBook)')
      expect(document.body.textContent).toContain('Xem danh sách Bộ thẻ')
    })
  })
})
