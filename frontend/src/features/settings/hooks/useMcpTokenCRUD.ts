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

  const [name, setName] = useState('Claude Desktop / Cursor IDE')
  const [expiry, setExpiry] = useState('180')
  const [selectedScopes, setSelectedScopes] = useState<string[]>([
    'deck:read',
    'note-type:read',
    'note:check',
    'note:create',
  ])
  const [issued, setIssued] = useState<McpTokenItem | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const [revokeTargetId, setRevokeTargetId] = useState<number | null>(null)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)

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
    onError: (error: Error) => toast.error(error.message),
  })

  const revokeMutation = useMutation({
    mutationFn: (id: number) => appApi.mutate(`/mcp-tokens/${id}`, 'DELETE'),
    onSuccess: async () => {
      setRevokeTargetId(null)
      await refresh()
      toast.success('MCP token đã được thu hồi ngay lập tức.')
    },
    onError: (error: Error) => toast.error(error.message),
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
    isCreateDialogOpen,
    setIsCreateDialogOpen,
    refresh,
    createMutation,
    revokeMutation,
  }
}
