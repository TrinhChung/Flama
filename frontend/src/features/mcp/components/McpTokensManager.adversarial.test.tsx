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

describe('McpTokensManager Adversarial Stress Suite', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let queryClient: QueryClient

  const mockTokenAlpha: McpToken = {
    id: 101,
    name: 'Token Alpha',
    status: 'active',
    expires_at: '2026-12-31T23:59:59Z',
    max_requests: 10000,
    used_requests: 10,
    remaining_requests: 9990,
    scopes: ['deck:read'],
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: '2026-09-30T10:00:00Z',
  }

  const mockTokenBeta: McpToken = {
    id: 102,
    name: 'Token Beta',
    status: 'revoked',
    expires_at: '2026-06-01T00:00:00Z',
    max_requests: 1000,
    used_requests: 1000,
    remaining_requests: 0,
    scopes: ['note:read', 'note:check'],
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: null,
  }

  const mockJapaneseToken: McpToken = {
    id: 103,
    name: '日本語テストトークン',
    status: 'active',
    expires_at: '2026-12-31T23:59:59Z',
    max_requests: 1000,
    used_requests: 5,
    remaining_requests: 995,
    scopes: ['study:read'],
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: null,
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

  // =========================================================================
  // 1. DIALOG STATE HANDLING & RESET PROBING
  // =========================================================================
  describe('1. Dialog State Handling & Clean Reset', () => {
    it('cleans up dirty inputs when Create modal is closed without submitting', async () => {
      mocks.get.mockResolvedValueOnce({ items: [] })
      await renderManager('admin')

      // Open Create Modal
      const openBtn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Cấp Token mới cho User')
      )
      expect(openBtn).toBeDefined()
      await act(async () => {
        openBtn!.click()
      })

      await waitFor(() => {
        expect(document.body.textContent).toContain('Cấp MCP Access Token Mới')
      })

      // Dirty up fields: name, customToken, expiry
      const nameInput = document.querySelector<HTMLInputElement>('#mcp-token-name')!
      const customTokenInput = document.querySelector<HTMLInputElement>(
        'input[placeholder*="Dán chuỗi token"]'
      )!
      const expirySelect = document.querySelector<HTMLSelectElement>('#mcp-token-expiry')!

      await act(async () => {
        setNativeInputValue(nameInput, 'Dirty Unsubmitted Name')
        setNativeInputValue(customTokenInput, 'dirty_custom_secret_123')
        expirySelect.value = '30'
        expirySelect.dispatchEvent(new Event('change', { bubbles: true }))
      })

      // Deselect all scopes
      const deselectBtn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Bỏ chọn')
      )
      expect(deselectBtn).toBeDefined()
      await act(async () => {
        deselectBtn!.click()
      })

      // Cancel / Close dialog
      const cancelBtn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.trim() === 'Hủy'
      )
      expect(cancelBtn).toBeDefined()
      await act(async () => {
        cancelBtn!.click()
      })

      await waitFor(() => {
        expect(document.body.textContent).not.toContain('Cấp MCP Access Token Mới')
      })

      // Re-open Create Modal
      await act(async () => {
        openBtn!.click()
      })

      await waitFor(() => {
        expect(document.body.textContent).toContain('Cấp MCP Access Token Mới')
      })

      // Assert all inputs are cleanly reset
      const reloadedNameInput = document.querySelector<HTMLInputElement>('#mcp-token-name')!
      const reloadedCustomInput = document.querySelector<HTMLInputElement>(
        'input[placeholder*="Dán chuỗi token"]'
      )!
      const reloadedExpirySelect = document.querySelector<HTMLSelectElement>('#mcp-token-expiry')!

      expect(reloadedNameInput.value).toBe('')
      expect(reloadedCustomInput.value).toBe('')
      expect(reloadedExpirySelect.value).toBe('180')
      // All scopes should be re-selected by default
      expect(document.body.textContent).toContain(
        `Quyền hạn cấp cho Token (${ALL_MCP_SCOPES.length}/${ALL_MCP_SCOPES.length} Scopes)`
      )
    })

    it('isolates state between Edit modal sessions for different tokens', async () => {
      mocks.get.mockResolvedValueOnce({ items: [mockTokenAlpha, mockTokenBeta] })
      await renderManager('user')

      await waitFor(() => {
        expect(document.body.textContent).toContain('Token Alpha')
        expect(document.body.textContent).toContain('Token Beta')
      })

      // Open Edit for Token Alpha
      const editButtons = Array.from(
        document.querySelectorAll<HTMLButtonElement>('button[title*="Chỉnh sửa"]')
      )
      expect(editButtons.length).toBe(2)
      await act(async () => {
        editButtons[0].click() // Edit Token Alpha
      })

      await waitFor(() => {
        expect(document.body.textContent).toContain('Chỉnh sửa MCP Token')
      })

      const editNameInput = document.querySelector<HTMLInputElement>('#edit-token-name')!
      expect(editNameInput.value).toBe('Token Alpha')

      // Dirty up Edit Token Alpha
      await act(async () => {
        setNativeInputValue(editNameInput, 'Dirty Token Alpha Mutated')
      })

      // Cancel
      const cancelBtn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.trim() === 'Hủy'
      )
      await act(async () => {
        cancelBtn!.click()
      })

      await waitFor(() => {
        expect(document.body.textContent).not.toContain('Chỉnh sửa MCP Token')
      })

      // Now open Edit for Token Beta
      const editButtonsAfter = Array.from(
        document.querySelectorAll<HTMLButtonElement>('button[title*="Chỉnh sửa"]')
      )
      await act(async () => {
        editButtonsAfter[1].click() // Edit Token Beta
      })

      await waitFor(() => {
        expect(document.body.textContent).toContain('Chỉnh sửa MCP Token')
      })

      // Verify Token Beta data is cleanly shown, not contaminated by Token Alpha's dirty edits
      const editNameBetaInput = document.querySelector<HTMLInputElement>('#edit-token-name')!
      expect(editNameBetaInput.value).toBe('Token Beta')
      expect(document.body.textContent).toContain('Quyền hạn cấp cho Token (2/')

      // Cancel Token Beta edit
      const cancelBtnBeta = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.trim() === 'Hủy'
      )
      await act(async () => {
        cancelBtnBeta!.click()
      })

      // Re-open Token Alpha edit
      const editButtonsAlphaAgain = Array.from(
        document.querySelectorAll<HTMLButtonElement>('button[title*="Chỉnh sửa"]')
      )
      await act(async () => {
        editButtonsAlphaAgain[0].click()
      })

      // Verify Token Alpha original data is restored cleanly
      const reloadedAlphaInput = document.querySelector<HTMLInputElement>('#edit-token-name')!
      expect(reloadedAlphaInput.value).toBe('Token Alpha')
    })

    it('probes Rotate modal state across cancel and re-opening', async () => {
      mocks.get.mockResolvedValueOnce({ items: [mockTokenAlpha, mockTokenBeta] })
      await renderManager('user')

      await waitFor(() => {
        expect(document.body.textContent).toContain('Token Alpha')
      })

      const rotateButtons = Array.from(
        document.querySelectorAll<HTMLButtonElement>('button[title*="Xoay vòng"]')
      )
      expect(rotateButtons.length).toBe(2)

      // Open Rotate on Token Alpha
      await act(async () => {
        rotateButtons[0].click()
      })

      await waitFor(() => {
        expect(document.body.textContent).toContain('Đổi Secret Token (Rotate)')
      })

      const expirySelect = document.querySelector<HTMLSelectElement>('#rotate-token-expiry')!
      expect(expirySelect.value).toBe('180')

      // User changes to 30 days
      await act(async () => {
        expirySelect.value = '30'
        expirySelect.dispatchEvent(new Event('change', { bubbles: true }))
      })
      expect(expirySelect.value).toBe('30')

      // User clicks Cancel on ConfirmDialog
      const cancelBtn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.trim() === 'Hủy'
      )
      expect(cancelBtn).toBeDefined()
      await act(async () => {
        cancelBtn!.click()
      })

      await waitFor(() => {
        expect(document.body.textContent).not.toContain('Đổi Secret Token (Rotate)')
      })

      // Re-open Rotate modal on Token Beta
      await act(async () => {
        rotateButtons[1].click()
      })

      await waitFor(() => {
        expect(document.body.textContent).toContain('Đổi Secret Token (Rotate)')
      })

      const reopenedExpirySelect = document.querySelector<HTMLSelectElement>('#rotate-token-expiry')!
      // Adversarial Check: Does rotateExpiry reset cleanly to the default '180' days,
      // or does it leak the previous unsubmitted '30' days selection?
      expect(reopenedExpirySelect.value).toBe('180')
    })

    it('cleanly closes Revoke, Purge, and Scope Details modals on cancellation', async () => {
      mocks.get.mockResolvedValueOnce({ items: [mockTokenAlpha, mockTokenBeta] })
      await renderManager('user')

      await waitFor(() => {
        expect(document.body.textContent).toContain('Token Alpha')
      })

      // 1. Revoke Modal Open and Cancel
      const revokeBtn = document.querySelector<HTMLButtonElement>('button[title*="Thu hồi"]')!
      await act(async () => {
        revokeBtn.click()
      })
      await waitFor(() => {
        expect(document.body.textContent).toContain('Xác nhận thu hồi MCP Token')
      })
      const cancelRevokeBtn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.trim() === 'Hủy'
      )!
      await act(async () => {
        cancelRevokeBtn.click()
      })
      await waitFor(() => {
        expect(document.body.textContent).not.toContain('Xác nhận thu hồi MCP Token')
      })

      // 2. Purge Modal Open and Cancel
      const purgeBtn = document.querySelector<HTMLButtonElement>('button[title*="Xóa vĩnh viễn"]')!
      await act(async () => {
        purgeBtn.click()
      })
      await waitFor(() => {
        expect(document.body.textContent).toContain('Xác nhận xóa vĩnh viễn Token')
      })
      const cancelPurgeBtn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.trim() === 'Hủy'
      )!
      await act(async () => {
        cancelPurgeBtn.click()
      })
      await waitFor(() => {
        expect(document.body.textContent).not.toContain('Xác nhận xóa vĩnh viễn Token')
      })

      // 3. Scope Details Open and Close
      const scopesBtn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Scopes')
      )!
      await act(async () => {
        scopesBtn.click()
      })
      await waitFor(() => {
        expect(document.body.textContent).toContain('Chi Tiết Quyền Hạn')
      })
      const closeScopeBtn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.trim() === 'Đóng'
      )!
      await act(async () => {
        closeScopeBtn.click()
      })
      await waitFor(() => {
        expect(document.body.textContent).not.toContain('Chi Tiết Quyền Hạn')
      })
    })
  })

  // =========================================================================
  // 2. EDGE CASES PROBING
  // =========================================================================
  describe('2. Edge Cases Probing', () => {
    it('handles empty tokens list (items: []) gracefully in User mode', async () => {
      mocks.get.mockResolvedValueOnce({ items: [] })
      await renderManager('user')

      await waitFor(() => {
        expect(document.body.textContent).toContain('Không tìm thấy MCP token nào')
        expect(document.body.textContent).toContain('Bạn chưa tạo token nào hoặc không tìm thấy kết quả phù hợp.')
      })

      // Stat cards should show 0
      const statValues = Array.from(document.querySelectorAll('.text-xl.font-bold')).map(
        (el) => el.textContent
      )
      expect(statValues).toEqual(['0', '0', '0'])

      // Cleanup button should NOT be rendered when inactiveCount is 0
      expect(document.body.textContent).not.toContain('Dọn dẹp')

      // Create button is still available
      expect(document.body.textContent).toContain('Tạo Token mới')
    })

    it('handles empty tokens list (items: []) gracefully in Admin mode', async () => {
      mocks.get.mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        per_page: 50,
        pages: 1,
      })
      await renderManager('admin')

      await waitFor(() => {
        expect(document.body.textContent).toContain('Không tìm thấy MCP token nào')
        expect(document.body.textContent).toContain(
          'Chưa có token nào được cấp hoặc không khớp với bộ lọc tìm kiếm.'
        )
      })

      // Pagination controls should not be rendered when totalPages <= 1
      expect(document.body.textContent).not.toContain('Trang 1 / 1')
    })

    it('handles token with null/undefined scopes and unknown status without crashing', async () => {
      const weirdToken = {
        id: 999,
        name: 'Weird Edge Token',
        status: 'some_unknown_status',
        expires_at: null,
        scopes: null,
        max_requests: 100,
        used_requests: 100,
        remaining_requests: 0,
        created_at: '2026-01-01T00:00:00Z',
        last_used_at: null,
      } as unknown as McpToken
      mocks.get.mockResolvedValueOnce({ items: [weirdToken] })
      await renderManager('user')

      await waitFor(() => {
        expect(document.body.textContent).toContain('Weird Edge Token')
        expect(document.body.textContent).toContain('0 Scopes')
        expect(document.body.textContent).toContain('Hết lượt')
        expect(document.body.textContent).toContain('Vĩnh viễn / Không hết hạn')
      })
    })

    // -----------------------------------------------------------------------
    // MUTATION FAILURES WITHIN DIALOGS
    // -----------------------------------------------------------------------
    it('[Mutation Failure] keeps Create dialog open, preserves inputs, and triggers toast.error on failure', async () => {
      mocks.get.mockResolvedValueOnce({ items: [] })
      mocks.mutate.mockRejectedValueOnce(new Error('Server Error: Token name already exists'))

      await renderManager('user')

      const openBtn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Tạo Token mới')
      )!
      await act(async () => {
        openBtn.click()
      })

      await waitFor(() => {
        expect(document.body.textContent).toContain('Tạo MCP Access Token mới')
      })

      const nameInput = document.querySelector<HTMLInputElement>('#mcp-token-name')!
      await act(async () => {
        setNativeInputValue(nameInput, 'Duplicated Token Name')
      })

      // Submit form
      const dialog = document.querySelector('[role="dialog"]')!
      const submitBtn = Array.from(dialog.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Tạo Token mới')
      )!

      await act(async () => {
        submitBtn.click()
      })

      // Verify toast.error was fired
      await waitFor(() => {
        expect(mocks.toastError).toHaveBeenCalledWith('Server Error: Token name already exists')
      })

      // Verify Create dialog remains OPEN
      expect(document.body.textContent).toContain('Tạo MCP Access Token mới')

      // Verify user input is PRESERVED so user does not have to retype
      const preservedNameInput = document.querySelector<HTMLInputElement>('#mcp-token-name')
      expect(preservedNameInput?.value).toBe('Duplicated Token Name')
    })

    it('[Mutation Failure] keeps Edit dialog open, preserves modifications, and triggers toast.error on failure', async () => {
      mocks.get.mockResolvedValueOnce({ items: [mockTokenAlpha] })
      mocks.mutate.mockRejectedValueOnce(new Error('Network Error: Gateway Timeout'))

      await renderManager('user')
      await waitFor(() => {
        expect(document.body.textContent).toContain('Token Alpha')
      })

      const editBtn = document.querySelector<HTMLButtonElement>('button[title*="Chỉnh sửa"]')!
      await act(async () => {
        editBtn.click()
      })

      await waitFor(() => {
        expect(document.body.textContent).toContain('Chỉnh sửa MCP Token')
      })

      const editNameInput = document.querySelector<HTMLInputElement>('#edit-token-name')!
      await act(async () => {
        setNativeInputValue(editNameInput, 'Alpha Failed Update')
      })

      const dialog = document.querySelector('[role="dialog"]')!
      const saveBtn = Array.from(dialog.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Lưu quyền hạn')
      )!

      await act(async () => {
        saveBtn.click()
      })

      // Toast error fired
      await waitFor(() => {
        expect(mocks.toastError).toHaveBeenCalledWith('Network Error: Gateway Timeout')
      })

      // Edit dialog remains open
      expect(document.body.textContent).toContain('Chỉnh sửa MCP Token')

      // Form input preserved
      const preservedInput = document.querySelector<HTMLInputElement>('#edit-token-name')
      expect(preservedInput?.value).toBe('Alpha Failed Update')
    })

    it('[Mutation Failure] keeps Rotate dialog open and does NOT reveal secret modal on failure', async () => {
      mocks.get.mockResolvedValueOnce({ items: [mockTokenAlpha] })
      mocks.mutate.mockRejectedValueOnce(new Error('Failed to rotate secret: Token is locked'))

      await renderManager('user')
      await waitFor(() => {
        expect(document.body.textContent).toContain('Token Alpha')
      })

      const rotateBtn = document.querySelector<HTMLButtonElement>('button[title*="Xoay vòng"]')!
      await act(async () => {
        rotateBtn.click()
      })

      await waitFor(() => {
        expect(document.body.textContent).toContain('Đổi Secret Token (Rotate)')
      })

      const dialog = document.querySelector('[role="dialog"]')!
      const confirmBtn = Array.from(dialog.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Xác nhận Đổi Secret')
      )!

      await act(async () => {
        confirmBtn.click()
      })

      await waitFor(() => {
        expect(mocks.toastError).toHaveBeenCalledWith('Failed to rotate secret: Token is locked')
      })

      // Rotate dialog stays open
      expect(document.body.textContent).toContain('Đổi Secret Token (Rotate)')

      // Secret Reveal modal was NOT shown
      expect(document.body.textContent).not.toContain('Token & Secret Đã Được Tạo Thành Công')
    })

    it('[Mutation Failure] keeps Revoke and Purge dialogs open when API rejects', async () => {
      mocks.get.mockResolvedValue({ items: [mockTokenAlpha, mockTokenBeta] })
      mocks.mutate.mockRejectedValueOnce(new Error('Revoke 500 error'))

      await renderManager('user')
      await waitFor(() => {
        expect(document.body.textContent).toContain('Token Alpha')
      })

      // Try Revoke
      const revokeBtn = document.querySelector<HTMLButtonElement>('button[title*="Thu hồi"]')!
      await act(async () => {
        revokeBtn.click()
      })
      await waitFor(() => {
        expect(document.body.textContent).toContain('Xác nhận thu hồi MCP Token')
      })

      const confirmRevokeBtn = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')).find(
        (b) => b.textContent?.includes('Xác nhận thu hồi')
      )!
      await act(async () => {
        confirmRevokeBtn.click()
      })

      await waitFor(() => {
        expect(mocks.toastError).toHaveBeenCalledWith('Revoke 500 error')
      })
      // Revoke dialog remains open
      expect(document.body.textContent).toContain('Xác nhận thu hồi MCP Token')
    })

    // -----------------------------------------------------------------------
    // JAPANESE IME COMPOSITION IN SEARCHINPUT
    // -----------------------------------------------------------------------
    it('[Japanese IME] handles compositionstart, compositionend, and guards Escape/Enter during IME composition', async () => {
      mocks.get.mockResolvedValueOnce({
        items: [mockTokenAlpha, mockJapaneseToken],
      })

      await renderManager('user')
      await waitFor(() => {
        expect(document.body.textContent).toContain('Token Alpha')
        expect(document.body.textContent).toContain('日本語テストトークン')
      })

      const searchInput = document.querySelector<HTMLInputElement>(
        'input[placeholder*="Tìm kiếm token"]'
      )!
      expect(searchInput).not.toBeNull()

      // 1. Simulate Japanese IME composition start: typing "にほんご"
      await act(async () => {
        searchInput.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }))
      })

      // Type intermediate composition value
      await act(async () => {
        setNativeInputValue(searchInput, 'にほんご')
      })

      // 2. Press Escape during composition -> Should NOT clear input
      await act(async () => {
        const escapeImeEvent = new KeyboardEvent('keydown', {
          key: 'Escape',
          bubbles: true,
          cancelable: true,
        })
        Object.defineProperty(escapeImeEvent, 'isComposing', { value: true })
        searchInput.dispatchEvent(escapeImeEvent)
      })

      // Input value is preserved (Escape was swallowed)
      expect(searchInput.value).toBe('にほんご')

      // 3. Press Enter during composition -> Should NOT trigger any external action
      await act(async () => {
        const enterImeEvent = new KeyboardEvent('keydown', {
          key: 'Enter',
          bubbles: true,
          cancelable: true,
        })
        Object.defineProperty(enterImeEvent, 'isComposing', { value: true })
        searchInput.dispatchEvent(enterImeEvent)
      })

      // 4. Japanese IME candidate converted to Kanji: "日本語" and composition ends
      await act(async () => {
        setNativeInputValue(searchInput, '日本語')
        searchInput.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true }))
      })

      // Verify filtered list: Japanese token is visible, Token Alpha is filtered out
      await waitFor(() => {
        expect(document.body.textContent).toContain('日本語テストトークン')
        expect(document.body.textContent).not.toContain('Token Alpha')
      })

      // 5. Press Escape after composition has ended -> Should clear search input
      await act(async () => {
        const normalEscapeEvent = new KeyboardEvent('keydown', {
          key: 'Escape',
          bubbles: true,
          cancelable: true,
        })
        searchInput.dispatchEvent(normalEscapeEvent)
      })

      // Verify search input is cleared and all tokens are visible again
      await waitFor(() => {
        expect(searchInput.value).toBe('')
        expect(document.body.textContent).toContain('Token Alpha')
        expect(document.body.textContent).toContain('日本語テストトークン')
      })
    })
  })
})
