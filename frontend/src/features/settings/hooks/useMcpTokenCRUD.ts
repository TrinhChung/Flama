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

export type McpScopeItem = {
  key: string
  label: string
  desc: string
  category: string
}

export type McpScopeCategory = {
  key: string
  name: string
  description: string
  scopes: string[]
}

export const SCOPE_CATEGORIES: McpScopeCategory[] = [
  {
    key: 'decks',
    name: 'Bộ thẻ & Chia sẻ',
    description: 'Xem, tạo mới cây thư mục deck và đăng tải chia sẻ Marketplace',
    scopes: ['deck:read', 'deck:write', 'deck-share:read', 'deck-share:write'],
  },
  {
    key: 'notes',
    name: 'Thẻ ghi nhớ & Đồng bộ',
    description: 'Tìm kiếm, tạo mới, chỉnh sửa, xóa và đồng bộ từ vựng',
    scopes: ['note:read', 'note:check', 'note:create', 'note:update', 'note:delete', 'note:sync'],
  },
  {
    key: 'note_types',
    name: 'Mẫu thẻ (Note Types)',
    description: 'Xem và quản lý schema trường dữ liệu cùng template hiển thị card',
    scopes: ['note-type:read', 'note-type:write'],
  },
  {
    key: 'study_stats',
    name: 'Học tập SRS & Thống kê',
    description: 'Lấy thẻ đến hạn ôn tập, ghi nhận kết quả Spaced Repetition và biểu đồ',
    scopes: ['study:read', 'study:write', 'stats:read'],
  },
  {
    key: 'media',
    name: 'Thư viện hình ảnh',
    description: 'Tìm kiếm, tải lên và quản lý ảnh minh họa cho thẻ',
    scopes: ['media:read', 'media:write'],
  },
]

export const ALL_MCP_SCOPES: McpScopeItem[] = [
  // Decks
  { key: 'deck:read', label: 'Xem danh sách Bộ thẻ', desc: 'Đọc thông tin các bộ thẻ và cây thư mục phân cấp', category: 'decks' },
  { key: 'deck:write', label: 'Quản lý & Tạo Bộ thẻ', desc: 'Tạo deck mới, đổi tên, cập nhật và tổ chức cây thư mục', category: 'decks' },
  { key: 'deck-share:read', label: 'Xem Bộ thẻ chia sẻ & Chợ', desc: 'Duyệt tìm shared decks trên Marketplace và xem chi tiết thẻ đã chia sẻ', category: 'decks' },
  { key: 'deck-share:write', label: 'Đăng tải & Xuất bản Release', desc: 'Chia sẻ deck lên Marketplace, cập nhật thông tin và phát hành release mới', category: 'decks' },

  // Notes
  { key: 'note:read', label: 'Xem chi tiết Thẻ ghi nhớ', desc: 'Đọc chi tiết các trường nội dung (từ vựng, kanji, nghĩa, ví dụ)', category: 'notes' },
  { key: 'note:check', label: 'Tìm kiếm & Kiểm tra trùng', desc: 'Tìm và kiểm tra xem từ vựng/thẻ đã tồn tại trong deck chưa', category: 'notes' },
  { key: 'note:create', label: 'Tạo Thẻ Flashcard mới', desc: 'Tự động tạo thẻ mới đơn lẻ hoặc tạo hàng loạt vào bộ thẻ', category: 'notes' },
  { key: 'note:update', label: 'Cập nhật Thẻ ghi nhớ & Tags', desc: 'Chỉnh sửa nội dung trường thẻ, gắn thẻ phân loại hoặc đổi deck', category: 'notes' },
  { key: 'note:delete', label: 'Xóa Thẻ ghi nhớ', desc: 'Xóa thẻ ghi nhớ và các flashcard liên quan khỏi bộ bài', category: 'notes' },
  { key: 'note:sync', label: 'Đồng bộ Thẻ từ bên ngoài', desc: 'Tự động đồng bộ tạo, sửa, xóa thẻ từ các nguồn kết nối', category: 'notes' },

  // Note Types
  { key: 'note-type:read', label: 'Xem Mẫu thẻ (Note Types)', desc: 'Đọc schema trường dữ liệu và mẫu định dạng thẻ flashcard', category: 'note_types' },
  { key: 'note-type:write', label: 'Quản lý Mẫu thẻ', desc: 'Tạo mới và chỉnh sửa cấu trúc trường hoặc mẫu card', category: 'note_types' },

  // Study & Stats
  { key: 'study:read', label: 'Xem Hàng đợi Học tập SRS', desc: 'Xem danh sách các thẻ đến hạn học hôm nay và khoảng cách ôn tập', category: 'study_stats' },
  { key: 'study:write', label: 'Ghi nhận Kết quả Ôn tập', desc: 'Gửi đánh giá kết quả học tập (Again, Hard, Good, Easy) vào thuật toán SRS', category: 'study_stats' },
  { key: 'stats:read', label: 'Xem Thống kê & Streak', desc: 'Theo dõi chuỗi ngày học liên tục, số thẻ đã học và tiến độ tổng quan', category: 'study_stats' },

  // Media
  { key: 'media:read', label: 'Xem & Tìm kiếm Hình ảnh', desc: 'Tìm kiếm hình ảnh trong thư viện ảnh dùng chung', category: 'media' },
  { key: 'media:write', label: 'Tải lên & Gắn thẻ Hình ảnh', desc: 'Upload, import ảnh từ URL và gắn thẻ hình ảnh minh họa', category: 'media' },
]

export const SCOPE_PRESETS = [
  {
    key: 'all',
    label: 'Toàn quyền (Full Access)',
    badge: '17 Scopes',
    desc: 'Cấp tất cả 17 quyền (khuyên dùng cho Cursor / Claude Desktop / Antigravity)',
    scopes: ALL_MCP_SCOPES.map((s) => s.key),
  },
  {
    key: 'readonly',
    label: 'Chỉ đọc (Read-Only)',
    badge: '8 Scopes',
    desc: 'Chỉ xem và tra cứu dữ liệu, không sửa đổi cơ sở dữ liệu',
    scopes: ['deck:read', 'deck-share:read', 'note:read', 'note:check', 'note-type:read', 'study:read', 'stats:read', 'media:read'],
  },
  {
    key: 'manager',
    label: 'Quản lý Thẻ & Chia sẻ',
    badge: '12 Scopes',
    desc: 'Tạo/sửa thẻ, quản lý deck và phát hành release bộ thẻ',
    scopes: ['deck:read', 'deck:write', 'deck-share:read', 'deck-share:write', 'note:read', 'note:check', 'note:create', 'note:update', 'note:delete', 'note:sync', 'note-type:read', 'note-type:write'],
  },
  {
    key: 'study',
    label: 'Đồng hành Học tập',
    badge: '5 Scopes',
    desc: 'Tương tác học tập, ôn bài Spaced Repetition và xem streak',
    scopes: ['study:read', 'study:write', 'stats:read', 'deck:read', 'note:read'],
  },
]

export function useMcpTokenCRUD() {
  const queryClient = useQueryClient()
  const queryKey = ['mcp-tokens'] as const

  // Create state
  const [name, setName] = useState('Claude Desktop / Cursor IDE')
  const [expiry, setExpiry] = useState('180')
  const [selectedScopes, setSelectedScopes] = useState<string[]>(ALL_MCP_SCOPES.map((s) => s.key))
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)

  // Edit state (General + Scopes)
  const [editingToken, setEditingToken] = useState<McpTokenItem | null>(null)
  const [editName, setEditName] = useState('')
  const [editExpiry, setEditExpiry] = useState('keep')
  const [editScopes, setEditScopes] = useState<string[]>([])
  const [isPermissionsOnlyDialog, setIsPermissionsOnlyDialog] = useState(false)

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
      setIsPermissionsOnlyDialog(false)
      await refresh()
      toast.success('Đã cập nhật thông tin và quyền hạn MCP Token thành công.')
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

  // Toggling scopes for Create
  const toggleScope = (scopeKey: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scopeKey) ? prev.filter((s) => s !== scopeKey) : [...prev, scopeKey]
    )
  }

  const applyCreatePreset = (presetKey: string) => {
    const preset = SCOPE_PRESETS.find((p) => p.key === presetKey)
    if (preset) {
      setSelectedScopes([...preset.scopes])
    }
  }

  const toggleCreateCategory = (categoryKey: string) => {
    const cat = SCOPE_CATEGORIES.find((c) => c.key === categoryKey)
    if (!cat) return
    const allSelected = cat.scopes.every((s) => selectedScopes.includes(s))
    if (allSelected) {
      setSelectedScopes((prev) => prev.filter((s) => !cat.scopes.includes(s)))
    } else {
      setSelectedScopes((prev) => Array.from(new Set([...prev, ...cat.scopes])))
    }
  }

  // Toggling scopes for Edit
  const toggleEditScope = (scopeKey: string) => {
    setEditScopes((prev) =>
      prev.includes(scopeKey) ? prev.filter((s) => s !== scopeKey) : [...prev, scopeKey]
    )
  }

  const applyEditPreset = (presetKey: string) => {
    const preset = SCOPE_PRESETS.find((p) => p.key === presetKey)
    if (preset) {
      setEditScopes([...preset.scopes])
    }
  }

  const toggleEditCategory = (categoryKey: string) => {
    const cat = SCOPE_CATEGORIES.find((c) => c.key === categoryKey)
    if (!cat) return
    const allSelected = cat.scopes.every((s) => editScopes.includes(s))
    if (allSelected) {
      setEditScopes((prev) => prev.filter((s) => !cat.scopes.includes(s)))
    } else {
      setEditScopes((prev) => Array.from(new Set([...prev, ...cat.scopes])))
    }
  }

  const openEditDialog = (token: McpTokenItem) => {
    setEditingToken(token)
    setEditName(token.name || '')
    setEditExpiry('keep')
    setEditScopes(token.scopes || [])
    setIsPermissionsOnlyDialog(false)
  }

  const openPermissionsDialog = (token: McpTokenItem) => {
    setEditingToken(token)
    setEditName(token.name || '')
    setEditExpiry('keep')
    setEditScopes(token.scopes || [])
    setIsPermissionsOnlyDialog(true)
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
    applyCreatePreset,
    toggleCreateCategory,
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
    setEditScopes,
    toggleEditScope,
    applyEditPreset,
    toggleEditCategory,
    isPermissionsOnlyDialog,
    setIsPermissionsOnlyDialog,
    openEditDialog,
    openPermissionsDialog,
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


