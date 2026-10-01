// @vitest-environment jsdom

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useMcpTokens } from './useMcpTokens'
import type { McpToken, UseMcpTokensOptions, UseMcpTokensReturn } from '../types'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  mutate: vi.fn(),
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
        username: 'admin',
        is_admin: true,
        can_manage_mcp_tokens: true,
      },
    },
  }),
}))

const mockTokens: McpToken[] = [
  {
    id: 101,
    name: 'Cursor IDE MacBook',
    status: 'active',
    scopes: ['deck:read', 'note:read', 'study:read'],
    expires_at: '2026-12-31T23:59:59Z',
    max_requests: 10000,
    used_requests: 50,
    remaining_requests: 9950,
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: '2026-09-30T10:00:00Z',
    user_id: 10,
    username: 'sensei_tanaka',
  },
  {
    id: 102,
    name: 'Old Claude Desktop',
    status: 'revoked',
    scopes: ['deck:read'],
    expires_at: '2026-05-01T00:00:00Z',
    max_requests: 1000,
    used_requests: 1000,
    remaining_requests: 0,
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: null,
    user_id: 10,
    username: 'sensei_tanaka',
    revoked: true,
  },
  {
    id: 103,
    name: 'Expired Agent Key',
    status: 'expired',
    scopes: ['note:create'],
    expires_at: '2026-02-01T00:00:00Z',
    max_requests: 500,
    used_requests: 100,
    remaining_requests: 400,
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: null,
    user_id: 20,
    username: 'student_ken',
  },
]

describe('useMcpTokens Headless Hook Suite', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let queryClient: QueryClient
  let latest: UseMcpTokensReturn
  let invalidateSpy: ReturnType<typeof vi.spyOn>

  function Harness(props: UseMcpTokensOptions) {
    latest = useMcpTokens(props)
    return null
  }

  async function renderHarness(options: UseMcpTokensOptions) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(
        createElement(
          QueryClientProvider,
          { client: queryClient },
          createElement(Harness, options)
        )
      )
    })
  }

  async function waitFor(assertion: () => void, timeoutMs = 1500) {
    const start = Date.now()
    let lastError: unknown
    while (Date.now() - start < timeoutMs) {
      try {
        assertion()
        return
      } catch (err) {
        lastError = err
        await act(async () => {
          await new Promise((r) => setTimeout(r, 10))
        })
      }
    }
    if (lastError) throw lastError
  }

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    })
    invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    vi.clearAllMocks()
    mocks.mutate.mockReset()
    mocks.toastSuccess.mockReset()
    mocks.toastError.mockReset()
  })

  afterEach(async () => {
    queryClient.clear()
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

  describe('User Mode (`mode: "user"`)', () => {
    beforeEach(() => {
      mocks.get.mockImplementation((url: string) => {
        if (url === '/mcp-tokens') {
          return Promise.resolve({
            items: mockTokens,
            policy: { default_expiry_days: 180 },
          })
        }
        return Promise.resolve({})
      })
    })

    it('fetches tokens from /mcp-tokens and computes summary stats', async () => {
      await renderHarness({ mode: 'user' })

      await waitFor(() => {
        expect(latest.isLoading).toBe(false)
        expect(latest.tokens).toHaveLength(3)
        expect(latest.totalItems).toBe(3)
        expect(latest.totalPages).toBe(1)
        expect(latest.inactiveCount).toBe(2)
        expect(latest.canManageTokens).toBe(true)
      })

      expect(mocks.get).toHaveBeenCalledWith('/mcp-tokens')
    })

    it('performs instant client-side filtering by search term and statusFilter', async () => {
      await renderHarness({ mode: 'user' })

      await waitFor(() => {
        expect(latest.tokens).toHaveLength(3)
      })

      // Search by name
      await act(async () => {
        latest.setSearch('MacBook')
      })
      expect(latest.tokens).toHaveLength(1)
      expect(latest.tokens[0].name).toBe('Cursor IDE MacBook')

      // Search by scope
      await act(async () => {
        latest.setSearch('note:create')
      })
      expect(latest.tokens).toHaveLength(1)
      expect(latest.tokens[0].name).toBe('Expired Agent Key')

      // Reset search, filter by status
      await act(async () => {
        latest.setSearch('')
        latest.setStatusFilter('revoked')
      })
      expect(latest.tokens).toHaveLength(1)
      expect(latest.tokens[0].id).toBe(102)

      // Filter by active
      await act(async () => {
        latest.setStatusFilter('active')
      })
      expect(latest.tokens).toHaveLength(1)
      expect(latest.tokens[0].id).toBe(101)
    })

    it('executes createToken mutation, invalidates query, and returns token result', async () => {
      mocks.mutate.mockResolvedValueOnce({
        item: {
          id: 104,
          name: 'New User Token',
          token: 'flama_mcp_sec_user_123',
          expires_at: '2026-10-20T00:00:00Z',
        },
      })

      await renderHarness({ mode: 'user' })
      await waitFor(() => expect(latest.isLoading).toBe(false))

      let result: unknown
      await act(async () => {
        result = await latest.createToken({
          name: 'New User Token',
          expires_in_days: 180,
          scopes: ['deck:read', 'note:read'],
        })
      })

      expect(mocks.mutate).toHaveBeenCalledWith('/mcp-tokens', 'POST', {
        name: 'New User Token',
        expires_in_days: 180,
        scopes: ['deck:read', 'note:read'],
      })
      expect(result).toEqual({
        token: 'flama_mcp_sec_user_123',
        name: 'New User Token',
        username: undefined,
        expires_at: '2026-10-20T00:00:00Z',
      })
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['mcp', 'tokens'] })
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['mcp-tokens'] })
      expect(mocks.toastSuccess).toHaveBeenCalledWith('Đã tạo MCP Access Token mới thành công.')
    })

    it('executes updateToken, rotateToken, revokeToken, purgeToken, and cleanupExpired mutations', async () => {
      await renderHarness({ mode: 'user' })
      await waitFor(() => expect(latest.isLoading).toBe(false))

      // 1. Update Token
      mocks.mutate.mockResolvedValueOnce({
        item: { ...mockTokens[0], name: 'Updated Name', scopes: ['deck:read'] },
      })
      await act(async () => {
        await latest.updateToken({
          id: 101,
          name: 'Updated Name',
          scopes: ['deck:read'],
          expires_in_days: 'none',
        })
      })
      expect(mocks.mutate).toHaveBeenCalledWith('/mcp-tokens/101', 'PATCH', {
        name: 'Updated Name',
        scopes: ['deck:read'],
        expires_in_days: null,
      })
      expect(mocks.toastSuccess).toHaveBeenCalledWith(
        'Đã cập nhật thông tin và quyền hạn MCP Token thành công.'
      )

      // 2. Rotate Token
      mocks.mutate.mockResolvedValueOnce({
        item: { token: 'flama_rotated_sec_789', name: 'Cursor IDE MacBook' },
      })
      let rotateResult: unknown
      await act(async () => {
        rotateResult = await latest.rotateToken({ id: 101, expires_in_days: 90 })
      })
      expect(mocks.mutate).toHaveBeenCalledWith('/mcp-tokens/101/rotate', 'POST', {
        expires_in_days: 90,
      })
      expect(rotateResult).toMatchObject({
        token: 'flama_rotated_sec_789',
        name: 'Cursor IDE MacBook',
      })

      // 3. Revoke Token
      mocks.mutate.mockResolvedValueOnce({})
      await act(async () => {
        await latest.revokeToken(101)
      })
      expect(mocks.mutate).toHaveBeenCalledWith('/mcp-tokens/101', 'DELETE')
      expect(mocks.toastSuccess).toHaveBeenCalledWith('MCP token đã được thu hồi.')

      // 4. Purge Token
      mocks.mutate.mockResolvedValueOnce({})
      await act(async () => {
        await latest.purgeToken(102)
      })
      expect(mocks.mutate).toHaveBeenCalledWith('/mcp-tokens/102/purge', 'DELETE')
      expect(mocks.toastSuccess).toHaveBeenCalledWith(
        'Đã xóa vĩnh viễn token khỏi cơ sở dữ liệu.'
      )

      // 5. Cleanup Expired
      mocks.mutate.mockResolvedValueOnce({ success: true, purged_count: 2 })
      let cleanupResult: unknown
      await act(async () => {
        cleanupResult = await latest.cleanupExpired()
      })
      expect(mocks.mutate).toHaveBeenCalledWith('/mcp-tokens/cleanup', 'POST')
      expect(cleanupResult).toEqual({ success: true, purged_count: 2 })
      expect(mocks.toastSuccess).toHaveBeenCalledWith(
        'Đã dọn dẹp thành công 2 token cũ/hết hạn.'
      )
    })
  })

  describe('Admin Mode (`mode: "admin"`)', () => {
    beforeEach(() => {
      mocks.get.mockImplementation((url: string) => {
        if (url === '/admin/mcp-tokens/tokens') {
          return Promise.resolve({
            items: mockTokens,
            total: 3,
            page: 1,
            per_page: 50,
            pages: 1,
          })
        }
        return Promise.resolve({})
      })
    })

    it('fetches tokens with query params and extracts pagination', async () => {
      await renderHarness({ mode: 'admin', userId: 10 })

      await waitFor(() => {
        expect(latest.isLoading).toBe(false)
        expect(latest.tokens).toHaveLength(3)
        expect(latest.totalItems).toBe(3)
        expect(latest.totalPages).toBe(1)
        expect(latest.inactiveCount).toBe(2)
      })

      expect(mocks.get).toHaveBeenCalledWith('/admin/mcp-tokens/tokens', {
        q: undefined,
        status: undefined,
        page: 1,
        per_page: 50,
        user_id: 10,
      })
    })

    it('dispatches admin createToken with user_id & custom_token, invalidating admin summary', async () => {
      mocks.mutate.mockResolvedValueOnce({
        item: {
          token: 'flama_custom_admin_token_001',
          name: 'Tanaka Assigned Key',
          username: 'sensei_tanaka',
        },
      })

      await renderHarness({ mode: 'admin', userId: 10 })
      await waitFor(() => expect(latest.isLoading).toBe(false))

      let result: unknown
      await act(async () => {
        result = await latest.createToken({
          name: 'Tanaka Assigned Key',
          expires_in_days: null,
          scopes: ['deck:read', 'deck:write'],
          custom_token: 'flama_custom_admin_token_001',
        })
      })

      expect(mocks.mutate).toHaveBeenCalledWith('/admin/mcp-tokens/tokens', 'POST', {
        name: 'Tanaka Assigned Key',
        expires_in_days: null,
        scopes: ['deck:read', 'deck:write'],
        user_id: 10,
        custom_token: 'flama_custom_admin_token_001',
      })
      expect(result).toEqual({
        token: 'flama_custom_admin_token_001',
        name: 'Tanaka Assigned Key',
        username: 'sensei_tanaka',
        expires_at: undefined,
      })
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['admin-mcp-summary'] })
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['admin-mcp-tokens'] })
    })

    it('dispatches admin rotate, revoke, purge, and cleanup endpoints', async () => {
      await renderHarness({ mode: 'admin' })
      await waitFor(() => expect(latest.isLoading).toBe(false))

      // Rotate
      mocks.mutate.mockResolvedValueOnce({
        item: { token: 'admin_rotated_token', name: 'Tanaka Key' },
      })
      await act(async () => {
        await latest.rotateToken({ id: 101, expires_in_days: null })
      })
      expect(mocks.mutate).toHaveBeenCalledWith('/admin/mcp-tokens/tokens/101/rotate', 'POST', {
        expires_in_days: null,
      })

      // Revoke
      mocks.mutate.mockResolvedValueOnce({})
      await act(async () => {
        await latest.revokeToken(101)
      })
      expect(mocks.mutate).toHaveBeenCalledWith('/admin/mcp-tokens/tokens/101', 'DELETE')
      expect(mocks.toastSuccess).toHaveBeenCalledWith('Đã thu hồi token thành công.')

      // Purge
      mocks.mutate.mockResolvedValueOnce({})
      await act(async () => {
        await latest.purgeToken(102)
      })
      expect(mocks.mutate).toHaveBeenCalledWith('/admin/mcp-tokens/tokens/102/purge', 'DELETE')
      expect(mocks.toastSuccess).toHaveBeenCalledWith('Đã xóa vĩnh viễn token.')

      // Cleanup
      mocks.mutate.mockResolvedValueOnce({ success: true, purged_count: 5 })
      await act(async () => {
        await latest.cleanupExpired()
      })
      expect(mocks.mutate).toHaveBeenCalledWith('/admin/mcp-tokens/cleanup', 'POST')
      expect(mocks.toastSuccess).toHaveBeenCalledWith('Đã dọn dẹp 5 token cũ thành công.')
    })
  })

  describe('Error Handling and Callbacks', () => {
    it('fires toast.error and rejects mutation promise on failure', async () => {
      mocks.mutate.mockRejectedValueOnce(new Error('Database lock error'))

      await renderHarness({ mode: 'user' })
      await waitFor(() => expect(latest.isLoading).toBe(false))

      await expect(
        act(async () => {
          await latest.revokeToken(101)
        })
      ).rejects.toThrow('Database lock error')

      expect(mocks.toastError).toHaveBeenCalledWith('Database lock error')
    })

    it('calls onSuccessMutation callback when mutation succeeds', async () => {
      const onSuccessMutation = vi.fn()
      mocks.mutate.mockResolvedValueOnce({})

      await renderHarness({ mode: 'user', onSuccessMutation })
      await waitFor(() => expect(latest.isLoading).toBe(false))

      await act(async () => {
        await latest.revokeToken(101)
      })

      expect(onSuccessMutation).toHaveBeenCalledTimes(1)
    })
  })
})
