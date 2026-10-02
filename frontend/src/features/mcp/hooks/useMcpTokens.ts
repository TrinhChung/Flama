import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import type {
  CreateTokenPayload,
  IssuedTokenResult,
  McpToken,
  RotateTokenPayload,
  UpdateTokenPayload,
  UseMcpTokensOptions,
  UseMcpTokensReturn,
} from '../types'

interface AdminMcpTokensResponse {
  items: McpToken[]
  total: number
  page: number
  per_page: number
  pages: number
}

interface UserMcpTokensResponse {
  items: McpToken[]
  policy?: unknown
}

export function useMcpTokens(options: UseMcpTokensOptions): UseMcpTokensReturn {
  const { mode, userId, onSuccessMutation } = options
  const queryClient = useQueryClient()

  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'revoked' | 'expired'>('all')
  const [page, setPage] = useState(1)

  const { data: bootstrap } = useBootstrap()
  const canManageTokens = Boolean(bootstrap?.user?.is_admin || bootstrap?.user?.can_manage_mcp_tokens)

  const queryKey = useMemo(
    () =>
      mode === 'admin'
        ? (['mcp', 'tokens', mode, search, statusFilter, page, userId] as const)
        : (['mcp', 'tokens', mode] as const),
    [mode, search, statusFilter, page, userId]
  )

  const query = useQuery({
    queryKey,
    queryFn: async () => {
      if (mode === 'admin') {
        return appApi.get<AdminMcpTokensResponse>('/admin/mcp-tokens/tokens', {
          q: search.trim() || undefined,
          status: statusFilter === 'all' ? undefined : statusFilter,
          page,
          per_page: 50,
          user_id: userId,
        })
      }
      return appApi.get<UserMcpTokensResponse>('/mcp-tokens')
    },
    enabled: Boolean(bootstrap?.user),
  })

  const { tokens, totalItems, totalPages } = useMemo(() => {
    const rawItems: McpToken[] = query.data?.items ?? []
    if (mode === 'admin') {
      const adminData = query.data as AdminMcpTokensResponse | undefined
      return {
        tokens: rawItems,
        totalItems: adminData?.total ?? rawItems.length,
        totalPages: adminData?.pages ?? 1,
      }
    }
    let filtered = rawItems
    const term = search.trim().toLowerCase()
    if (term) {
      filtered = filtered.filter(
        (t) =>
          t.name.toLowerCase().includes(term) ||
          t.scopes?.some((s) => s.toLowerCase().includes(term)) ||
          t.status.toLowerCase().includes(term)
      )
    }
    if (statusFilter !== 'all') {
      filtered = filtered.filter((t) => t.status === statusFilter)
    }
    return {
      tokens: filtered,
      totalItems: filtered.length,
      totalPages: Math.max(1, Math.ceil(filtered.length / 50)),
    }
  }, [query.data, mode, search, statusFilter])

  const inactiveCount = useMemo(
    () => (query.data?.items ?? []).filter((t) => t.status !== 'active').length,
    [query.data?.items]
  )

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['mcp', 'tokens'] })
    if (mode === 'admin') {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['admin-mcp-summary'] }),
        queryClient.invalidateQueries({ queryKey: ['admin-mcp-tokens'] }),
      ])
    } else {
      await queryClient.invalidateQueries({ queryKey: ['mcp-tokens'] })
    }
    onSuccessMutation?.()
  }

  // 1. Create Token Mutation
  const createMutation = useMutation({
    mutationFn: async (payload: CreateTokenPayload): Promise<IssuedTokenResult> => {
      const path = mode === 'admin' ? '/admin/mcp-tokens/tokens' : '/mcp-tokens'
      const body: Record<string, unknown> = {
        name: payload.name.trim() || 'MCP Token',
        expires_in_days: payload.expires_in_days,
        scopes: payload.scopes,
      }
      if (mode === 'admin') {
        const targetUserId = payload.user_id ?? userId
        if (targetUserId !== undefined) body.user_id = targetUserId
        if (payload.custom_token?.trim()) body.custom_token = payload.custom_token.trim()
      }
      const res = await appApi.mutate<{ item: IssuedTokenResult & Partial<McpToken> }>(path, 'POST', body)
      return {
        token: res.item.token,
        name: res.item.name,
        username: res.item.username,
        expires_at: res.item.expires_at,
      }
    },
    onSuccess: async () => {
      await invalidate()
      toast.success('Đã tạo MCP Access Token mới thành công.')
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể tạo MCP token.'),
  })

  // 2. Update Token Mutation
  const updateMutation = useMutation({
    mutationFn: async (payload: UpdateTokenPayload): Promise<McpToken> => {
      const path = mode === 'admin' ? `/admin/mcp-tokens/tokens/${payload.id}` : `/mcp-tokens/${payload.id}`
      const body: Record<string, unknown> = {
        name: payload.name.trim() || 'MCP Token',
        scopes: payload.scopes,
      }
      if (payload.expires_in_days !== undefined && payload.expires_in_days !== 'keep') {
        body.expires_in_days = payload.expires_in_days === 'none' ? null : Number(payload.expires_in_days)
      }
      const res = await appApi.mutate<{ item: McpToken } | McpToken>(path, 'PATCH', body)
      return (res as { item?: McpToken }).item ?? (res as McpToken)
    },
    onSuccess: async () => {
      await invalidate()
      toast.success(
        mode === 'admin' ? 'Cập nhật token thành công.' : 'Đã cập nhật thông tin và quyền hạn MCP Token thành công.'
      )
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể cập nhật MCP token.'),
  })

  // 3. Rotate Token Secret Mutation
  const rotateMutation = useMutation({
    mutationFn: async (payload: RotateTokenPayload): Promise<IssuedTokenResult> => {
      const path = mode === 'admin' ? `/admin/mcp-tokens/tokens/${payload.id}/rotate` : `/mcp-tokens/${payload.id}/rotate`
      const body: Record<string, unknown> = {
        expires_in_days: payload.expires_in_days === 'none' ? null : payload.expires_in_days,
      }
      const res = await appApi.mutate<{ item: IssuedTokenResult & Partial<McpToken> }>(path, 'POST', body)
      return {
        token: res.item.token,
        name: res.item.name,
        username: res.item.username,
        expires_at: res.item.expires_at,
      }
    },
    onSuccess: async () => {
      await invalidate()
      toast.success(
        mode === 'admin'
          ? 'Đã xoay vòng Secret thành công! Secret mới đã được tạo.'
          : 'Đã xoay vòng Secret Token thành công! Secret mới đã được tạo.'
      )
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể xoay vòng secret token.'),
  })

  // 4. Revoke Token Mutation
  const revokeMutation = useMutation({
    mutationFn: async (id: number): Promise<void> => {
      const path = mode === 'admin' ? `/admin/mcp-tokens/tokens/${id}` : `/mcp-tokens/${id}`
      await appApi.mutate(path, 'DELETE')
    },
    onSuccess: async () => {
      await invalidate()
      toast.success(mode === 'admin' ? 'Đã thu hồi token thành công.' : 'MCP token đã được thu hồi.')
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể thu hồi token.'),
  })

  // 5. Purge Token Mutation
  const purgeMutation = useMutation({
    mutationFn: async (id: number): Promise<void> => {
      const path = mode === 'admin' ? `/admin/mcp-tokens/tokens/${id}/purge` : `/mcp-tokens/${id}/purge`
      await appApi.mutate(path, 'DELETE')
    },
    onSuccess: async () => {
      await invalidate()
      toast.success(mode === 'admin' ? 'Đã xóa vĩnh viễn token.' : 'Đã xóa vĩnh viễn token khỏi cơ sở dữ liệu.')
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể xóa vĩnh viễn token.'),
  })

  // 6. Cleanup Expired / Revoked Tokens Mutation
  const cleanupMutation = useMutation({
    mutationFn: async (): Promise<{ success: boolean; purged_count: number }> => {
      const path = mode === 'admin' ? '/admin/mcp-tokens/cleanup' : '/mcp-tokens/cleanup'
      const res = await appApi.mutate<{ success: boolean; purged_count?: number; deleted_count?: number }>(
        path,
        'POST'
      )
      return { success: res.success ?? true, purged_count: res.purged_count ?? res.deleted_count ?? 0 }
    },
    onSuccess: async ({ purged_count }) => {
      await invalidate()
      toast.success(
        mode === 'admin'
          ? `Đã dọn dẹp ${purged_count} token cũ thành công.`
          : `Đã dọn dẹp thành công ${purged_count} token cũ/hết hạn.`
      )
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể dọn dẹp token.'),
  })

  return {
    mode,
    tokens,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error as Error | null,
    refetch: query.refetch,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    page,
    setPage,
    totalPages,
    totalItems,
    inactiveCount,
    canManageTokens,
    createToken: createMutation.mutateAsync,
    updateToken: updateMutation.mutateAsync,
    rotateToken: rotateMutation.mutateAsync,
    revokeToken: revokeMutation.mutateAsync,
    purgeToken: purgeMutation.mutateAsync,
    cleanupExpired: cleanupMutation.mutateAsync,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isRotating: rotateMutation.isPending,
    isRevoking: revokeMutation.isPending,
    isPurging: purgeMutation.isPending,
    isCleaningUp: cleanupMutation.isPending,
  }
}
