// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Tabs } from '@/components/ui/tabs'
import { McpTokensTab } from '../McpTokensTab'
import {
  ALL_MCP_SCOPES,
  type McpTokenItem,
  useMcpTokenCRUD,
} from '../../hooks/useMcpTokenCRUD'

// Enable React 19 Act Environment to prevent repeated act(...) warnings
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

// Helper: Dispatches change on HTMLSelectElement
function setNativeSelectValue(element: HTMLSelectElement, value: string) {
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
  element.dispatchEvent(new Event('change', { bubbles: true }))
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

let mockBootstrapUser = {
  id: 1,
  email: 'admin@nihongo.flama',
  is_admin: true,
  can_manage_mcp_tokens: true,
}

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: {
      user: mockBootstrapUser,
    },
  }),
}))

// Async waitFor helper for polling DOM assertions in jsdom
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

// Wrapper component to host useMcpTokenCRUD and McpTokensTab inside Radix Tabs
function McpTokensTabContainer({ onSwitchToChatGPT }: { onSwitchToChatGPT?: () => void }) {
  const hookResult = useMcpTokenCRUD()
  return (
    <Tabs defaultValue="tokens">
      <McpTokensTab hookResult={hookResult} onSwitchToChatGPT={onSwitchToChatGPT} />
    </Tabs>
  )
}

describe('McpTokensTab Baseline Characterization Suite', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let queryClient: QueryClient

  const mockActiveToken: McpTokenItem = {
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

  const mockRevokedToken: McpTokenItem = {
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

  beforeEach(() => {
    mockBootstrapUser = {
      id: 1,
      email: 'admin@nihongo.flama',
      is_admin: true,
      can_manage_mcp_tokens: true,
    }

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

    // Default GET response for /mcp-tokens
    mocks.get.mockImplementation((url: string) => {
      if (url === '/mcp-tokens') {
        return Promise.resolve({
          items: [mockActiveToken, mockRevokedToken],
          policy: {
            default_expiry_days: 180,
            allowed_expiry_days: [30, 90, 180, 365],
            allow_no_expiry: true,
            scopes: ALL_MCP_SCOPES.map((s) => s.key),
          },
        })
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

  const renderTab = async () => {
    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <McpTokensTabContainer />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })
  }

  // =========================================================================
  // FLOW 1: CREATE TOKEN WITH SCOPES (F1)
  // =========================================================================
  it('[Flow 1] creates a new token with specific scopes and expiry', async () => {
    mocks.mutate.mockResolvedValueOnce({
      item: {
        id: 103,
        name: 'Antigravity Agent',
        token: 'flama_mcp_sec_live_test_123',
        status: 'active',
        scopes: ['deck:read', 'deck-share:read', 'note:read', 'note:check', 'note-type:read', 'study:read', 'stats:read', 'media:read'],
        expires_at: '2026-12-31T23:59:59Z',
      },
    })

    await renderTab()

    // Wait for initial render of token list
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
    })

    // 1. Enter custom token name
    const nameInput = document.querySelector<HTMLInputElement>('#mcp-token-name')
    expect(nameInput).not.toBeNull()
    await act(async () => {
      setNativeInputValue(nameInput!, 'Antigravity Agent')
    })

    // 2. Select expiry: 6 months (180 days)
    const expirySelect = document.querySelector<HTMLSelectElement>('#mcp-token-expiry')
    expect(expirySelect).not.toBeNull()
    await act(async () => {
      setNativeSelectValue(expirySelect!, '180')
    })

    // 3. Click 1-Click Preset "Chỉ đọc (Read-Only)"
    const readOnlyBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Chỉ đọc')
    )
    expect(readOnlyBtn).toBeDefined()
    await act(async () => {
      readOnlyBtn!.click()
    })

    // Verify scope counter reflects read-only preset (8 Scopes)
    expect(document.body.textContent).toContain('8/17 Scopes')

    // 4. Click Submit "Tạo Token mới"
    const submitBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tạo Token mới')
    )
    expect(submitBtn).toBeDefined()
    expect(submitBtn!.disabled).toBe(false)
    await act(async () => {
      submitBtn!.click()
    })

    // 5. Assert mutate call with expected payload
    expect(mocks.mutate).toHaveBeenCalledWith(
      '/mcp-tokens',
      'POST',
      expect.objectContaining({
        name: 'Antigravity Agent',
        expires_in_days: 180,
        scopes: expect.arrayContaining(['deck:read', 'note:read', 'note:check']),
      })
    )

    // 6. Assert Secret Modal/Alert appears with newly issued secret
    await waitFor(() => {
      expect(document.body.textContent).toContain('Secret Token của bạn đã sẵn sàng!')
      expect(document.body.textContent).toContain('flama_mcp_sec_live_test_123')
    })

    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      expect.stringContaining('Đã tạo MCP Access Token mới thành công')
    )
  })

  it('[Flow 1 Validation] validates empty name and shows duplicate name warning', async () => {
    await renderTab()

    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
    })

    const nameInput = document.querySelector<HTMLInputElement>('#mcp-token-name')!
    const submitBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tạo Token mới')
    )!

    // Clear name -> Submit must be disabled
    await act(async () => {
      setNativeInputValue(nameInput, '   ')
    })
    expect(submitBtn.disabled).toBe(true)

    // Type duplicate active token name -> Warning banner must appear
    await act(async () => {
      setNativeInputValue(nameInput, 'Cursor IDE MacBook')
    })

    await waitFor(() => {
      expect(document.body.textContent).toContain('Bạn đã có một token đang hoạt động mang tên này')
    })
  })

  // =========================================================================
  // FLOW 2: REVEAL SECRET & CLIPBOARD COPY (F2)
  // =========================================================================
  it('[Flow 2] reveals plaintext secret, server URL, and copies to clipboard', async () => {
    mocks.mutate.mockResolvedValueOnce({
      item: {
        id: 104,
        name: 'Clipboard Token',
        token: 'flama_sec_copy_987654321',
        status: 'active',
        scopes: ['deck:read'],
        expires_at: '2026-12-31T23:59:59Z',
      },
    })

    await renderTab()
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
    })

    const nameInput = document.querySelector<HTMLInputElement>('#mcp-token-name')!
    await act(async () => {
      setNativeInputValue(nameInput, 'Clipboard Token')
    })

    const submitBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tạo Token mới')
    )!
    await act(async () => {
      submitBtn.click()
    })

    // Secret alert revealed
    await waitFor(() => {
      expect(document.body.textContent).toContain('Secret Token của bạn đã sẵn sàng!')
      expect(document.body.textContent).toContain('flama_sec_copy_987654321')
    })

    // 1. Copy secret plaintext
    const copyTokenBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Sao chép') && !b.textContent?.includes('URL')
    )
    expect(copyTokenBtn).toBeDefined()
    await act(async () => {
      copyTokenBtn!.click()
    })

    expect(mocks.writeText).toHaveBeenCalledWith('flama_sec_copy_987654321')
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      expect.stringContaining('Đã sao chép Token vào bộ nhớ tạm')
    )

    // Button label transitions to "Đã chép"
    await waitFor(() => {
      expect(copyTokenBtn!.textContent).toContain('Đã chép')
    })

    // 2. Copy Server URL endpoint
    const copyUrlBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Sao chép URL')
    )
    expect(copyUrlBtn).toBeDefined()
    await act(async () => {
      copyUrlBtn!.click()
    })

    expect(mocks.writeText).toHaveBeenCalledWith(
      expect.stringContaining('flama_sec_copy_987654321')
    )

    // 3. Dismiss / Close the secret alert
    const closeAlertBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Đóng'
    )
    expect(closeAlertBtn).toBeDefined()
    await act(async () => {
      closeAlertBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).not.toContain('Secret Token của bạn đã sẵn sàng!')
    })
  })

  // =========================================================================
  // FLOW 3: EDIT INFO & UPDATE SCOPES (F3)
  // =========================================================================
  it('[Flow 3] opens edit dialog and updates token name, expiry, and scopes', async () => {
    mocks.mutate.mockResolvedValueOnce({
      item: {
        ...mockActiveToken,
        name: 'Cursor Pro Workstation',
        scopes: ['deck:read', 'note:read', 'study:read'],
      },
    })

    await renderTab()
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
    })

    // 1. Click edit button on active token row
    const editBtn = document.querySelector<HTMLButtonElement>(
      'button[title="Chỉnh sửa tên & thời hạn"]'
    )
    expect(editBtn).not.toBeNull()
    await act(async () => {
      editBtn!.click()
    })

    // 2. Edit dialog opens with pre-filled values
    await waitFor(() => {
      expect(document.body.textContent).toContain('Chỉnh sửa MCP Token')
    })

    const editNameInput = document.querySelector<HTMLInputElement>('#edit-token-name')
    expect(editNameInput?.value).toBe('Cursor IDE MacBook')

    // 3. Modify name and expiry
    await act(async () => {
      setNativeInputValue(editNameInput!, 'Cursor Pro Workstation')
    })

    const editExpirySelect = document.querySelector<HTMLSelectElement>('#edit-token-expiry')
    expect(editExpirySelect).not.toBeNull()
    await act(async () => {
      setNativeSelectValue(editExpirySelect!, '365')
    })

    // 4. Click Save
    const saveBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Lưu quyền hạn')
    )
    expect(saveBtn).toBeDefined()
    await act(async () => {
      saveBtn!.click()
    })

    // 5. Assert PATCH mutate call
    expect(mocks.mutate).toHaveBeenCalledWith(
      `/mcp-tokens/${mockActiveToken.id}`,
      'PATCH',
      expect.objectContaining({
        name: 'Cursor Pro Workstation',
        expires_in_days: 365,
        scopes: expect.any(Array),
      })
    )

    // Dialog closes
    await waitFor(() => {
      expect(document.body.textContent).not.toContain('Chỉnh sửa MCP Token')
    })
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      expect.stringContaining('Đã cập nhật thông tin và quyền hạn')
    )
  })

  it('[Flow 3 Scopes View] opens permissions-only dialog from scope badge trigger', async () => {
    await renderTab()
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
    })

    // Click permission shield button
    const permBtn = document.querySelector<HTMLButtonElement>(
      'button[title="Phân quyền & Cấp quyền hạn (Scopes)"]'
    )
    expect(permBtn).not.toBeNull()
    await act(async () => {
      permBtn!.click()
    })

    // Dialog opens with permissions-specific title
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cấp & Chỉnh sửa Quyền hạn MCP Token')
    })

    // In permissions-only mode, the name input is hidden
    expect(document.querySelector('#edit-token-name')).toBeNull()

    // Click Cancel
    const cancelBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Hủy'
    )
    expect(cancelBtn).toBeDefined()
    await act(async () => {
      cancelBtn!.click()
    })

    await waitFor(() => {
      expect(document.body.textContent).not.toContain('Cấp & Chỉnh sửa Quyền hạn MCP Token')
    })
  })

  // =========================================================================
  // FLOW 4: ROTATE SECRET (F4)
  // =========================================================================
  it('[Flow 4] rotates token secret and reveals newly generated key in alert', async () => {
    mocks.mutate.mockResolvedValueOnce({
      item: {
        id: mockActiveToken.id,
        name: mockActiveToken.name,
        token: 'flama_sec_rotated_999888',
        status: 'active',
        expires_at: '2027-01-01T00:00:00Z',
      },
    })

    await renderTab()
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
    })

    // Click rotate button on active token row
    const rotateBtn = document.querySelector<HTMLButtonElement>(
      'button[title="Xoay vòng / Đổi Secret Key"]'
    )
    expect(rotateBtn).not.toBeNull()
    await act(async () => {
      rotateBtn!.click()
    })

    // Rotate modal opens
    await waitFor(() => {
      expect(document.body.textContent).toContain('Đổi Secret Token (Rotate)')
      expect(document.body.textContent).toContain('tạo mới chuỗi bí mật (Secret Key)')
    })

    // Select new expiry
    const rotateExpirySelect = document.querySelector<HTMLSelectElement>('#rotate-token-expiry')
    expect(rotateExpirySelect).not.toBeNull()
    await act(async () => {
      setNativeSelectValue(rotateExpirySelect!, '180')
    })

    // Confirm rotate
    const confirmRotateBtn = Array.from(document.querySelectorAll('button')).find((b) =>
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

    // Secret alert opens with new rotated key
    await waitFor(() => {
      expect(document.body.textContent).toContain('flama_sec_rotated_999888')
    })
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      expect.stringContaining('Đã xoay vòng Secret Token thành công')
    )
  })

  // =========================================================================
  // FLOW 5: REVOKE & PURGE TOKENS (F5)
  // =========================================================================
  it('[Flow 5 Revoke] soft-revokes an active token with confirmation dialog', async () => {
    mocks.mutate.mockResolvedValueOnce({})

    await renderTab()
    await waitFor(() => {
      expect(document.body.textContent).toContain('Cursor IDE MacBook')
    })

    // Click revoke button (ShieldAlert)
    const revokeBtn = document.querySelector<HTMLButtonElement>(
      'button[title="Thu hồi Token"]'
    )
    expect(revokeBtn).not.toBeNull()
    await act(async () => {
      revokeBtn!.click()
    })

    // Revoke dialog appears
    await waitFor(() => {
      expect(document.body.textContent).toContain('Xác nhận thu hồi MCP Token')
      expect(document.body.textContent).toContain('Token này sẽ bị hủy kích hoạt ngay lập tức')
    })

    // Confirm revoke
    const confirmRevokeBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xác nhận thu hồi')
    )
    expect(confirmRevokeBtn).toBeDefined()
    await act(async () => {
      confirmRevokeBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith(
      `/mcp-tokens/${mockActiveToken.id}`,
      'DELETE'
    )

    await waitFor(() => {
      expect(document.body.textContent).not.toContain('Xác nhận thu hồi MCP Token')
    })
    expect(mocks.toastSuccess).toHaveBeenCalledWith('MCP token đã được thu hồi.')
  })

  it('[Flow 5 Purge] permanently deletes a revoked token from database', async () => {
    mocks.mutate.mockResolvedValueOnce({})

    await renderTab()
    await waitFor(() => {
      expect(document.body.textContent).toContain('Old Claude Desktop')
    })

    // Click purge button (Trash2) on the revoked token
    const purgeBtn = document.querySelector<HTMLButtonElement>(
      'button[title="Xóa vĩnh viễn khỏi database"]'
    )
    expect(purgeBtn).not.toBeNull()
    await act(async () => {
      purgeBtn!.click()
    })

    // Purge confirmation dialog appears
    await waitFor(() => {
      expect(document.body.textContent).toContain('Xác nhận xóa vĩnh viễn Token')
      expect(document.body.textContent).toContain('Hành động này không thể hoàn tác')
    })

    // Confirm purge
    const confirmPurgeBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xóa vĩnh viễn')
    )
    expect(confirmPurgeBtn).toBeDefined()
    await act(async () => {
      confirmPurgeBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith(
      `/mcp-tokens/${mockRevokedToken.id}/purge`,
      'DELETE'
    )

    await waitFor(() => {
      expect(document.body.textContent).not.toContain('Xác nhận xóa vĩnh viễn Token')
    })
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      'Đã xóa vĩnh viễn token khỏi cơ sở dữ liệu.'
    )
  })

  // =========================================================================
  // FLOW 6: CLEANUP EXPIRED / INACTIVE TOKENS (F6)
  // =========================================================================
  it('[Flow 6] bulk cleans up inactive and expired tokens', async () => {
    mocks.mutate.mockResolvedValueOnce({ success: true, purged_count: 1 })

    await renderTab()
    await waitFor(() => {
      expect(document.body.textContent).toContain('Dọn dẹp 1 token cũ')
    })

    // Click header cleanup button
    const cleanupHeaderBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Dọn dẹp 1 token cũ')
    )
    expect(cleanupHeaderBtn).toBeDefined()
    await act(async () => {
      cleanupHeaderBtn!.click()
    })

    // Cleanup confirmation dialog appears
    await waitFor(() => {
      expect(document.body.textContent).toContain('Dọn dẹp Token cũ & Hết hạn')
      expect(document.body.textContent).toContain('Xóa sạch tất cả 1 token đã thu hồi hoặc đã hết hạn')
    })

    // Confirm cleanup: select the button inside the dialog footer (not the header button)
    const dialogElement = document.querySelector('[role="dialog"]')
    expect(dialogElement).not.toBeNull()
    const confirmCleanupBtn = Array.from(dialogElement!.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Dọn dẹp')
    )
    expect(confirmCleanupBtn).toBeDefined()
    await act(async () => {
      confirmCleanupBtn!.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith('/mcp-tokens/cleanup', 'POST')

    await waitFor(() => {
      expect(document.body.textContent).not.toContain('Dọn dẹp Token cũ & Hết hạn')
    })
    expect(mocks.toastSuccess).toHaveBeenCalledWith('Đã dọn dẹp thành công 1 token cũ/hết hạn.')
  })

  // =========================================================================
  // PERMISSION BOUNDARY: NON-MANAGER USER
  // =========================================================================
  it('hides create card and write action buttons for standard non-manager user', async () => {
    mockBootstrapUser = {
      id: 2,
      email: 'student@nihongo.flama',
      is_admin: false,
      can_manage_mcp_tokens: false,
    }

    await renderTab()
    await waitFor(() => {
      expect(document.body.textContent).toContain('Thông số Máy chủ MCP')
    })

    // Create token card should NOT be rendered
    expect(document.querySelector('#mcp-token-name')).toBeNull()
    expect(document.body.textContent).not.toContain('Tạo MCP Access Token mới')

    // Token management table and action buttons should NOT be rendered for non-managers
    expect(document.querySelector('button[title="Chỉnh sửa tên & thời hạn"]')).toBeNull()
    expect(document.querySelector('button[title="Xoay vòng / Đổi Secret Key"]')).toBeNull()
    expect(document.querySelector('button[title="Thu hồi Token"]')).toBeNull()
    expect(document.querySelector('button[title="Xóa vĩnh viễn khỏi database"]')).toBeNull()
    expect(document.body.textContent).not.toContain('Danh sách Token & Secrets')

    // Read-only explanatory banner is displayed
    expect(document.body.textContent).toContain('Thông số Kết nối AI do Quản trị viên Quản lý')
  })
})
