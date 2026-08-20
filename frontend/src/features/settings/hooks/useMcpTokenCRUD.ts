import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { FLAMA_MCP_URL } from '@/config/env'

export type McpTokenItem = {
  id: number
  name: string
  status: 'active' | 'expired' | 'exhausted' | 'revoked' | string
  expires_at: string | null
  max_requests: number
  remaining_requests: number
  used_requests: number
  scopes: string[]
  created_at: string | null
  last_used_at: string | null
  token?: string
}

export type McpPolicy = {
  default_expiry_days?: number
  allowed_expiry_days?: number[]
  allow_no_expiry?: boolean
  scopes: string[]
}

export type McpTokensResponse = {
  items: McpTokenItem[]
  policy: McpPolicy
}

export const ALL_MCP_SCOPES = [
  { key: 'deck:read', label: 'Xem danh sách Decks', desc: 'Đọc thông tin các bộ thẻ và cây thư mục' },
  { key: 'note-type:read', label: 'Xem Note Types', desc: 'Đọc schema trường dữ liệu và mẫu card' },
  { key: 'note:check', label: 'Tìm kiếm Thẻ', desc: 'Tìm và kiểm tra trùng lặp flashcard' },
  { key: 'note:create', label: 'Tạo Thẻ Flashcard', desc: 'Tự động tạo thẻ mới và thẻ hàng loạt' },
]

export function useMcpTokenCRUD() {
  const queryClient = useQueryClient()
  const queryKey = ['mcp-tokens'] as const

  // Create state
  const [name, setName] = useState('Claude Desktop / Cursor IDE')
  const [expiry, setExpiry] = useState('180')
  const [selectedScopes, setSelectedScopes] = useState<string[]>([
    'deck:read',
    'note-type:read',
    'note:check',
    'note:create',
  ])
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)

  // Edit state
  const [editingToken, setEditingToken] = useState<McpTokenItem | null>(null)
  const [editName, setEditName] = useState('')
  const [editExpiry, setEditExpiry] = useState('keep')
  const [editScopes, setEditScopes] = useState<string[]>([])

  // Rotate state
  const [rotateTargetToken, setRotateTargetToken] = useState<McpTokenItem | null>(null)
  const [rotateExpiry, setRotateExpiry] = useState('180')

  // Revoke & Purge & Cleanup states
  const [revokeTargetId, setRevokeTargetId] = useState<number | null>(null)
  const [purgeTargetToken, setPurgeTargetToken] = useState<McpTokenItem | null>(null)
  const [isCleanupDialogOpen, setIsCleanupDialogOpen] = useState(false)

  // Newly issued / rotated token display
  const [issued, setIssued] = useState<McpTokenItem | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  const issuedMcpUrl = issued?.token
    ? `${FLAMA_MCP_URL.replace(/\/+$/, '')}/${encodeURIComponent(issued.token)}`
    : null

  const query = useQuery({
    queryKey,
    queryFn: () => appApi.get<McpTokensResponse>('/mcp-tokens'),
  })

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey })
  }

  // 1. Create Token Mutation
  const createMutation = useMutation({
    mutationFn: () =>
      appApi.mutate<{ item: McpTokenItem }>('/mcp-tokens', 'POST', {
        name: name.trim() || 'MCP Token',
        expires_in_days: expiry === 'none' ? null : Number(expiry),
        scopes: selectedScopes,
      }),
    onSuccess: async ({ item }) => {
      setIssued(item)
      setIsCreateDialogOpen(false)
      await refresh()
      toast.success('Đã tạo MCP Access Token mới thành công.')
    },
    onError: (error: Error) => toast.error(error.message || 'Không thể tạo MCP token.'),
  })

  // 2. Update Token Mutation
  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editingToken) throw new Error('Không tìm thấy token để sửa')
      const payload: Record<string, any> = {
        name: editName.trim() || 'MCP Token',
        scopes: editScopes,
      }
      if (editExpiry !== 'keep') {
        payload.expires_in_days = editExpiry === 'none' ? null : Number(editExpiry)
      }
      return appApi.mutate<{ item: McpTokenItem }>(`/mcp-tokens/${editingToken.id}`, 'PATCH', payload)
    },
    onSuccess: async () => {
      setEditingToken(null)
      await refresh()
      toast.success('Đã cập nhật thông tin MCP Token.')
    },
    onError: (error: Error) => toast.error(error.message || 'Không thể cập nhật MCP token.'),
  })

  // 3. Rotate Secret Mutation
  const rotateMutation = useMutation({
    mutationFn: (tokenId: number) =>
      appApi.mutate<{ item: McpTokenItem }>(`/mcp-tokens/${tokenId}/rotate`, 'POST', {
        expires_in_days: rotateExpiry === 'none' ? null : Number(rotateExpiry),
      }),
    onSuccess: async ({ item }) => {
      setIssued(item)
      setRotateTargetToken(null)
      await refresh()
      toast.success('Đã xoay vòng Secret Token thành công! Secret mới đã được tạo.')
    },
    onError: (error: Error) => toast.error(error.message || 'Không thể đổi Secret token.'),
  })

  // 4. Revoke Token Mutation (Soft delete)
  const revokeMutation = useMutation({
    mutationFn: (id: number) => appApi.mutate(`/mcp-tokens/${id}`, 'DELETE'),
    onSuccess: async () => {
      setRevokeTargetId(null)
      await refresh()
      toast.success('MCP token đã được thu hồi.')
    },
    onError: (error: Error) => toast.error(error.message || 'Không thể thu hồi token.'),
  })

  // 5. Purge Token Mutation (Hard delete)
  const purgeMutation = useMutation({
    mutationFn: (id: number) => appApi.mutate(`/mcp-tokens/${id}/purge`, 'DELETE'),
    onSuccess: async () => {
      setPurgeTargetToken(null)
      await refresh()
      toast.success('Đã xóa vĩnh viễn token khỏi cơ sở dữ liệu.')
    },
    onError: (error: Error) => toast.error(error.message || 'Không thể xóa vĩnh viễn token.'),
  })

  // 6. Cleanup All Revoked & Expired Tokens
  const cleanupMutation = useMutation({
    mutationFn: () => appApi.mutate<{ success: boolean; purged_count: number }>('/mcp-tokens/cleanup', 'POST'),
    onSuccess: async ({ purged_count }) => {
      setIsCleanupDialogOpen(false)
      await refresh()
      toast.success(`Đã dọn dẹp thành công ${purged_count} token cũ/hết hạn.`)
    },
    onError: (error: Error) => toast.error(error.message || 'Không thể dọn dẹp token.'),
  })

  const copy = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(label)
      window.setTimeout(() => setCopied(null), 2000)
      toast.success(`Đã sao chép ${label} vào bộ nhớ tạm.`)
    } catch {
      toast.error('Không thể sao chép vào bộ nhớ tạm.')
    }
  }

  const toggleScope = (scopeKey: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scopeKey) ? prev.filter((s) => s !== scopeKey) : [...prev, scopeKey]
    )
  }

  const toggleEditScope = (scopeKey: string) => {
    setEditScopes((prev) =>
      prev.includes(scopeKey) ? prev.filter((s) => s !== scopeKey) : [...prev, scopeKey]
    )
  }

  const openEditDialog = (token: McpTokenItem) => {
    setEditingToken(token)
    setEditName(token.name || '')
    setEditExpiry('keep')
    setEditScopes(token.scopes || [])
  }

  const openRotateDialog = (token: McpTokenItem) => {
    setRotateTargetToken(token)
    setRotateExpiry('180')
  }

  return {
    query,
    name,
    setName,
    expiry,
    setExpiry,
    selectedScopes,
    setSelectedScopes,
    toggleScope,
    issued,
    setIssued,
    copied,
    copy,
    issuedMcpUrl,
    revokeTargetId,
    setRevokeTargetId,
    purgeTargetToken,
    setPurgeTargetToken,
    isCleanupDialogOpen,
    setIsCleanupDialogOpen,
    isCreateDialogOpen,
    setIsCreateDialogOpen,
    editingToken,
    setEditingToken,
    editName,
    setEditName,
    editExpiry,
    setEditExpiry,
    editScopes,
    toggleEditScope,
    openEditDialog,
    rotateTargetToken,
    setRotateTargetToken,
    rotateExpiry,
    setRotateExpiry,
    openRotateDialog,
    refresh,
    createMutation,
    updateMutation,
    rotateMutation,
    revokeMutation,
    purgeMutation,
    cleanupMutation,
  }
}

