import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { FLAMA_MCP_URL } from '@/config/env'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader, StatCard } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'
import {
  ALL_MCP_SCOPES,
  SCOPE_CATEGORIES,
} from '@/features/settings/hooks/useMcpTokenCRUD'
import { McpOAuthTab } from '@/features/settings/components/McpOAuthTab'
import {
  AlertCircle,
  Bot,
  Check,
  Copy,
  Eraser,
  KeyRound,
  Link as LinkIcon,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  Users,
  Zap,
} from 'lucide-react'

type McpSummaryResponse = {
  total_tokens: number
  active_tokens: number
  revoked_tokens: number
  expired_tokens: number
  inactive_tokens: number
  total_requests: number
  total_users: number
  permitted_users: number
}

type AdminMcpUser = {
  id: number
  username: string
  email: string
  display_name: string
  avatar_url: string | null
  role_name: string
  is_admin: boolean
  is_disabled: boolean
  can_use_mcp: boolean
  raw_can_use_mcp: boolean
  can_manage_mcp_tokens?: boolean
  raw_can_manage_mcp_tokens?: boolean
  active_tokens_count: number
  total_tokens_count: number
}

type AdminMcpUsersResponse = {
  items: AdminMcpUser[]
  total: number
  page: number
  per_page: number
  pages: number
}

type AdminMcpToken = {
  id: number
  user_id: number
  username: string
  email: string
  client_id: number | null
  client_name: string | null
  name: string
  status: 'active' | 'expired' | 'exhausted' | 'revoked' | string
  scopes: string[]
  expires_at: string | null
  max_requests: number
  used_requests: number
  remaining_requests: number
  created_at: string | null
  last_used_at: string | null
  revoked: boolean
  token?: string
}

type AdminMcpTokensResponse = {
  items: AdminMcpToken[]
  total: number
  page: number
  per_page: number
  pages: number
}

function displayDate(value: string | null) {
  if (!value) return 'Vĩnh viễn'
  try {
    return new Date(value).toLocaleString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return value
  }
}

export function AdminMcpTokensPage() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'users' | 'tokens' | 'oauth'>('users')

  // --- Users Tab State ---
  const [userSearch, setUserSearch] = useState('')
  const [userFilter, setUserFilter] = useState<'all' | 'permitted' | 'unpermitted'>('all')
  const [userPage, setUserPage] = useState(1)

  // --- Tokens Tab State ---
  const [tokenSearch, setTokenSearch] = useState('')
  const [tokenStatusFilter, setTokenStatusFilter] = useState<'all' | 'active' | 'revoked' | 'expired'>('all')
  const [tokenPage, setTokenPage] = useState(1)

  // --- Create Token Dialog (Admin on behalf of user) ---
  const [isCreateTokenOpen, setIsCreateTokenOpen] = useState(false)
  const [createUserId, setCreateUserId] = useState<number | ''>('')
  const [createTokenName, setCreateTokenName] = useState('MCP Token')
  const [createCustomToken, setCreateCustomToken] = useState('')
  const [createExpiry, setCreateExpiry] = useState('180')
  const [createScopes, setCreateScopes] = useState<string[]>(ALL_MCP_SCOPES.map((s) => s.key))

  // --- Newly Issued Token Display Dialog ---
  const [issuedResult, setIssuedResult] = useState<{ token: string; name: string; username?: string } | null>(null)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)

  // --- Edit Token Dialog ---
  const [editingToken, setEditingToken] = useState<AdminMcpToken | null>(null)
  const [editName, setEditName] = useState('')
  const [editExpiry, setEditExpiry] = useState('keep')
  const [editScopes, setEditScopes] = useState<string[]>([])
  const [isScopeDetailsOpen, setIsScopeDetailsOpen] = useState(false)
  const [viewingScopeToken, setViewingScopeToken] = useState<AdminMcpToken | null>(null)

  // --- Rotate Token Dialog ---
  const [rotatingToken, setRotatingToken] = useState<AdminMcpToken | null>(null)
  const [rotateExpiry, setRotateExpiry] = useState('180')

  // --- Revoke / Purge / Cleanup State ---
  const [revokingTokenId, setRevokingTokenId] = useState<number | null>(null)
  const [purgingToken, setPurgingToken] = useState<AdminMcpToken | null>(null)
  const [isCleanupOpen, setIsCleanupOpen] = useState(false)

  // 1. Summary Query
  const summaryQuery = useQuery({
    queryKey: ['admin-mcp-summary'],
    queryFn: () => appApi.get<McpSummaryResponse>('/admin/mcp-tokens/summary'),
  })

  // 2. Users Query
  const usersQuery = useQuery({
    queryKey: ['admin-mcp-users', userSearch, userFilter, userPage],
    queryFn: () =>
      appApi.get<AdminMcpUsersResponse>('/admin/mcp-tokens/users', {
        q: userSearch,
        filter: userFilter,
        page: userPage,
        per_page: 20,
      }),
  })

  // 3. Tokens Query
  const tokensQuery = useQuery({
    queryKey: ['admin-mcp-tokens', tokenSearch, tokenStatusFilter, tokenPage],
    queryFn: () =>
      appApi.get<AdminMcpTokensResponse>('/admin/mcp-tokens/tokens', {
        q: tokenSearch,
        status: tokenStatusFilter,
        page: tokenPage,
        per_page: 50,
      }),
  })

  const refreshAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['admin-mcp-summary'] }),
      queryClient.invalidateQueries({ queryKey: ['admin-mcp-users'] }),
      queryClient.invalidateQueries({ queryKey: ['admin-mcp-tokens'] }),
    ])
  }

  // --- Mutations ---
  const togglePermissionMutation = useMutation({
    mutationFn: ({ userId, canUseMcp }: { userId: number; canUseMcp: boolean }) =>
      appApi.mutate<{ success: boolean; message: string }>(
        `/admin/mcp-tokens/users/${userId}/permission`,
        'POST',
        { can_use_mcp: canUseMcp }
      ),
    onSuccess: (data) => {
      toast.success(data.message || 'Cập nhật quyền thành công.')
      refreshAll()
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể cập nhật quyền.'),
  })

  const createTokenMutation = useMutation({
    mutationFn: () => {
      if (!createUserId) throw new Error('Vui lòng chọn người dùng.')
      const payload: Record<string, any> = {
        user_id: Number(createUserId),
        name: createTokenName.trim() || 'MCP Token',
        expires_in_days: createExpiry === 'none' ? null : Number(createExpiry),
        scopes: createScopes,
      }
      if (createCustomToken.trim()) {
        payload.custom_token = createCustomToken.trim()
      }
      return appApi.mutate<{ item: { token: string; name: string } }>(
        '/admin/mcp-tokens/tokens',
        'POST',
        payload
      )
    },
    onSuccess: ({ item }) => {
      const targetUser = usersQuery.data?.items.find((u) => u.id === Number(createUserId))
      setIssuedResult({
        token: item.token,
        name: item.name,
        username: targetUser?.username,
      })
      setIsCreateTokenOpen(false)
      refreshAll()
      toast.success('Đã tạo MCP Access Token mới thành công.')
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể tạo token.'),
  })

  const updateTokenMutation = useMutation({
    mutationFn: () => {
      if (!editingToken) throw new Error('Không tìm thấy token.')
      const payload: Record<string, any> = {
        name: editName.trim() || 'MCP Token',
        scopes: editScopes,
      }
      if (editExpiry !== 'keep') {
        payload.expires_in_days = editExpiry === 'none' ? null : Number(editExpiry)
      }
      return appApi.mutate(`/admin/mcp-tokens/tokens/${editingToken.id}`, 'PATCH', payload)
    },
    onSuccess: () => {
      setEditingToken(null)
      refreshAll()
      toast.success('Cập nhật token thành công.')
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể cập nhật token.'),
  })

  const rotateTokenMutation = useMutation({
    mutationFn: (tokenId: number) =>
      appApi.mutate<{ item: { token: string; name: string } }>(
        `/admin/mcp-tokens/tokens/${tokenId}/rotate`,
        'POST',
        {
          expires_in_days: rotateExpiry === 'none' ? null : Number(rotateExpiry),
        }
      ),
    onSuccess: ({ item }) => {
      setIssuedResult({
        token: item.token,
        name: item.name,
        username: rotatingToken?.username,
      })
      setRotatingToken(null)
      refreshAll()
      toast.success('Đã xoay vòng Secret thành công! Secret mới đã được tạo.')
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể xoay vòng secret token.'),
  })

  const revokeTokenMutation = useMutation({
    mutationFn: (tokenId: number) =>
      appApi.mutate(`/admin/mcp-tokens/tokens/${tokenId}`, 'DELETE'),
    onSuccess: () => {
      setRevokingTokenId(null)
      refreshAll()
      toast.success('Đã thu hồi token thành công.')
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể thu hồi token.'),
  })

  const purgeTokenMutation = useMutation({
    mutationFn: (tokenId: number) =>
      appApi.mutate(`/admin/mcp-tokens/tokens/${tokenId}/purge`, 'DELETE'),
    onSuccess: () => {
      setPurgingToken(null)
      refreshAll()
      toast.success('Đã xóa vĩnh viễn token.')
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể xóa token.'),
  })

  const cleanupMutation = useMutation({
    mutationFn: () => appApi.mutate<{ success: boolean; purged_count: number }>('/admin/mcp-tokens/cleanup', 'POST'),
    onSuccess: (data) => {
      setIsCleanupOpen(false)
      refreshAll()
      toast.success(`Đã dọn dẹp ${data.purged_count} token cũ thành công.`)
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể dọn dẹp token.'),
  })

  const copy = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedKey(label)
      toast.success(`Đã sao chép ${label}`)
      setTimeout(() => setCopiedKey(null), 2500)
    } catch {
      toast.error('Không thể sao chép vào bộ nhớ tạm')
    }
  }

  const summary = summaryQuery.data || {
    total_tokens: 0,
    active_tokens: 0,
    revoked_tokens: 0,
    expired_tokens: 0,
    inactive_tokens: 0,
    total_requests: 0,
    total_users: 0,
    permitted_users: 0,
  }

  const users = usersQuery.data?.items || []
  const tokens = tokensQuery.data?.items || []

  if (summaryQuery.isPending && !summaryQuery.data) return <PageLoading label="Đang tải dữ liệu MCP..." />
  if (summaryQuery.error) return <Page><PageError error={summaryQuery.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-6 sm:space-y-8 pb-16 px-3 sm:px-6">
      {/* Header */}
      <div className="space-y-3">
        <Badge variant="destructive" className="gap-1 font-semibold">
          <ShieldCheck className="size-3.5" /> Admin
        </Badge>
        <PageHeader
          title="Quản trị Token & Kết nối AI (MCP)"
          description="Cấp quyền sử dụng cho người dùng, giám sát và quản trị tất cả Token & Secrets toàn hệ thống."
        />
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <StatCard
          tone="primary"
          label="Token Hoạt động"
          value={`${summary.active_tokens} / ${summary.total_tokens}`}
          hint="Token đang hợp lệ trong hệ thống"
        />
        <StatCard
          tone="success"
          label="Tự Quản lý Token"
          value={`${summary.permitted_users} / ${summary.total_users}`}
          hint="Được tự tạo & xoay vòng secret"
        />
        <StatCard
          tone="default"
          label="Lượt gọi API"
          value={summary.total_requests.toLocaleString()}
          hint="Tổng requests qua MCP Tokens"
        />
        <StatCard
          tone="warning"
          label="Token Cũ / Thu hồi"
          value={summary.inactive_tokens}
          hint="Hết hạn hoặc đã thu hồi"
        />
      </div>

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full space-y-6">
        <div className="overflow-x-auto pb-1 -mx-1 px-1 no-scrollbar">
          <TabsList className="inline-flex w-full sm:w-auto p-1 bg-muted/60 backdrop-blur-md rounded-2xl gap-1">
            <TabsTrigger
              value="users"
              className="flex-1 sm:flex-none px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5"
            >
              <Users className="size-4 shrink-0" />
              <span>Phân quyền Quản lý ({summary.permitted_users})</span>
            </TabsTrigger>
            <TabsTrigger
              value="tokens"
              className="flex-1 sm:flex-none px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5"
            >
              <KeyRound className="size-4 shrink-0" />
              <span>Danh sách Token & Secrets ({summary.total_tokens})</span>
            </TabsTrigger>
            <TabsTrigger
              value="oauth"
              className="flex-1 sm:flex-none px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5"
            >
              <Bot className="size-4 shrink-0" />
              <span>Tích hợp OAuth 2.1 & Clients</span>
            </TabsTrigger>
          </TabsList>
        </div>

        {/* ================= TAB 1: PHÂN QUYỀN NGƯỜI DÙNG ================= */}
        <TabsContent value="users" className="space-y-4 outline-hidden mt-0">
          <Card className="shadow-2xs">
            <CardHeader className="p-4 sm:p-6 pb-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base sm:text-lg font-bold">
                    Phân Quyền Quản Lý Token MCP
                  </CardTitle>
                  <CardDescription className="text-xs sm:text-sm">
                    Mặc định tất cả người dùng đều có thể sử dụng MCP theo các thông số cấu hình do Quản trị viên thiết lập. Cấp quyền tại đây cho phép người dùng tự tạo token riêng, tùy biến scopes và xoay vòng secret cá nhân.
                  </CardDescription>
                </div>
              </div>

              {/* Filters */}
              <div className="flex flex-col sm:flex-row gap-2.5 pt-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                  <Input
                    placeholder="Tìm theo username, email hoặc tên..."
                    value={userSearch}
                    onChange={(e) => {
                      setUserSearch(e.target.value)
                      setUserPage(1)
                    }}
                    className="pl-9 text-xs sm:text-sm h-9"
                  />
                </div>
                <div className="w-full sm:w-48">
                  <NativeSelect
                    value={userFilter}
                    onChange={(e) => {
                      setUserFilter(e.target.value as any)
                      setUserPage(1)
                    }}
                    className="text-xs sm:text-sm h-9"
                  >
                    <NativeSelectOption value="all">Tất cả người dùng</NativeSelectOption>
                    <NativeSelectOption value="permitted">Được tự quản lý ({summary.permitted_users})</NativeSelectOption>
                    <NativeSelectOption value="unpermitted">Chỉ dùng cấu hình Admin ({summary.total_users - summary.permitted_users})</NativeSelectOption>
                  </NativeSelect>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-4 sm:p-6 pt-0">
              {usersQuery.isPending ? (
                <PageLoading label="Đang tải danh sách người dùng…" />
              ) : !users.length ? (
                <EmptyState
                  title="Không tìm thấy người dùng"
                  description="Thử thay đổi từ khóa tìm kiếm hoặc bộ lọc trạng thái quyền."
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/40">
                        <TableHead className="font-semibold">Người dùng</TableHead>
                        <TableHead className="font-semibold">Vai trò</TableHead>
                        <TableHead className="font-semibold">Tài khoản</TableHead>
                        <TableHead className="font-semibold">Token Active</TableHead>
                        <TableHead className="font-semibold">Quyền Quản lý Token</TableHead>
                        <TableHead className="text-right font-semibold">Thao tác</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map((u) => {
                        const isGranted = Boolean(u.can_manage_mcp_tokens ?? u.can_use_mcp)
                        const rawGranted = Boolean(u.raw_can_manage_mcp_tokens ?? u.raw_can_use_mcp)
                        const isTogglePending =
                          togglePermissionMutation.isPending &&
                          togglePermissionMutation.variables?.userId === u.id

                        return (
                          <TableRow key={u.id}>
                            <TableCell>
                              <div className="flex flex-col">
                                <span className="font-semibold text-xs sm:text-sm">{u.display_name}</span>
                                <span className="text-[11px] text-muted-foreground">{u.email}</span>
                              </div>
                            </TableCell>

                            <TableCell>
                              {u.is_admin ? (
                                <Badge variant="destructive" className="gap-1 font-semibold text-[10px]">
                                  <ShieldCheck className="size-3" /> Admin
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-[10px]">
                                  {u.role_name}
                                </Badge>
                              )}
                            </TableCell>

                            <TableCell>
                              {u.is_disabled ? (
                                <Badge variant="destructive" className="text-[10px]">Bị khóa</Badge>
                              ) : (
                                <Badge variant="outline" className="text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px]">
                                  Hoạt động
                                </Badge>
                              )}
                            </TableCell>

                            <TableCell>
                              <div className="flex items-center gap-1.5">
                                <KeyRound className="size-3 text-muted-foreground" />
                                <span className="text-xs font-semibold">{u.active_tokens_count}</span>
                                <span className="text-[10px] text-muted-foreground">/ {u.total_tokens_count}</span>
                              </div>
                            </TableCell>

                            <TableCell>
                              {u.is_admin ? (
                                <Badge className="bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/30 text-[11px]">
                                  Toàn quyền (Admin)
                                </Badge>
                              ) : isGranted ? (
                                <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30 text-[11px] gap-1">
                                  <Check className="size-3" /> Tự quản lý Token
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-muted-foreground text-[11px]">
                                  Chỉ dùng cấu hình Admin
                                </Badge>
                              )}
                            </TableCell>

                            <TableCell className="text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 text-xs gap-1 hover:border-primary hover:text-primary"
                                  onClick={() => {
                                    setCreateUserId(u.id)
                                    setCreateCustomToken('')
                                    setIsCreateTokenOpen(true)
                                  }}
                                  title={`Cấp hoặc gán thêm MCP Access Token cho ${u.username}`}
                                >
                                  <KeyRound className="size-3 text-primary" />
                                  <span>Cấp Token</span>
                                </Button>

                                {!u.is_admin && (
                                  <Button
                                    size="sm"
                                    variant={isGranted ? 'secondary' : 'default'}
                                    disabled={isTogglePending}
                                    onClick={() =>
                                      togglePermissionMutation.mutate({
                                        userId: u.id,
                                        canUseMcp: !rawGranted,
                                      })
                                    }
                                    className="h-8 text-xs gap-1.5"
                                  >
                                    {isGranted ? (
                                      <>
                                        <ShieldAlert className="size-3 text-amber-600 dark:text-amber-400" />
                                        <span>Thu hồi quyền quản lý</span>
                                      </>
                                    ) : (
                                      <>
                                        <ShieldCheck className="size-3" />
                                        <span>Cấp quyền quản lý</span>
                                      </>
                                    )}
                                  </Button>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Pagination */}
              {usersQuery.data && usersQuery.data.pages > 1 && (
                <div className="flex items-center justify-between pt-4 border-t mt-4 text-xs text-muted-foreground">
                  <span>Trang {usersQuery.data.page} / {usersQuery.data.pages} (Tổng {usersQuery.data.total} người dùng)</span>
                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={userPage <= 1}
                      onClick={() => setUserPage((p) => Math.max(1, p - 1))}
                    >
                      Trước
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={userPage >= usersQuery.data.pages}
                      onClick={() => setUserPage((p) => p + 1)}
                    >
                      Sau
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ================= TAB 2: DANH SÁCH TOKEN & SECRETS TOÀN HỆ THỐNG ================= */}
        <TabsContent value="tokens" className="space-y-4 outline-hidden mt-0">
          <Card className="shadow-2xs">
            <CardHeader className="p-4 sm:p-6 pb-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base sm:text-lg font-bold">
                    Danh sách Token & Secrets Toàn Hệ Thống ({summary.total_tokens})
                  </CardTitle>
                  <CardDescription className="text-xs sm:text-sm">
                    Theo dõi trạng thái, chỉnh sửa quyền hạn trực tiếp hoặc xoay vòng secret mà không làm gián đoạn kết nối.
                  </CardDescription>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {summary.inactive_tokens > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5 text-xs text-amber-700 dark:text-amber-400 border-amber-500/40 hover:bg-amber-50 dark:hover:bg-amber-950/30"
                      onClick={() => setIsCleanupOpen(true)}
                    >
                      <Eraser className="size-3.5" />
                      Dọn dẹp {summary.inactive_tokens} token cũ
                    </Button>
                  )}
                  <Button
                    size="sm"
                    className="gap-1.5 text-xs"
                    onClick={() => {
                      setCreateUserId(users[0]?.id || '')
                      setIsCreateTokenOpen(true)
                    }}
                  >
                    <Plus className="size-3.5" />
                    Cấp Token mới cho User
                  </Button>
                </div>
              </div>

              {/* Filters */}
              <div className="flex flex-col sm:flex-row gap-2.5 pt-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                  <Input
                    placeholder="Tìm theo tên token, username hoặc email chủ sở hữu..."
                    value={tokenSearch}
                    onChange={(e) => {
                      setTokenSearch(e.target.value)
                      setTokenPage(1)
                    }}
                    className="pl-9 text-xs sm:text-sm h-9"
                  />
                </div>
                <div className="w-full sm:w-44">
                  <NativeSelect
                    value={tokenStatusFilter}
                    onChange={(e) => {
                      setTokenStatusFilter(e.target.value as any)
                      setTokenPage(1)
                    }}
                    className="text-xs sm:text-sm h-9"
                  >
                    <NativeSelectOption value="all">Tất cả trạng thái</NativeSelectOption>
                    <NativeSelectOption value="active">Hoạt động ({summary.active_tokens})</NativeSelectOption>
                    <NativeSelectOption value="revoked">Đã thu hồi ({summary.revoked_tokens})</NativeSelectOption>
                    <NativeSelectOption value="expired">Đã hết hạn ({summary.expired_tokens})</NativeSelectOption>
                  </NativeSelect>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-4 sm:p-6 pt-0">
              {tokensQuery.isPending ? (
                <PageLoading label="Đang tải danh sách token…" />
              ) : !tokens.length ? (
                <EmptyState
                  title="Chưa có token nào"
                  description="Bấm 'Cấp Token mới cho User' ở trên để tạo token cho người dùng."
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/40">
                        <TableHead className="font-semibold">Chủ sở hữu</TableHead>
                        <TableHead className="font-semibold">Tên gợi nhớ</TableHead>
                        <TableHead className="font-semibold">Trạng thái</TableHead>
                        <TableHead className="font-semibold">Thời hạn</TableHead>
                        <TableHead className="font-semibold">Quyền hạn (Scopes)</TableHead>
                        <TableHead className="font-semibold">Lần dùng cuối</TableHead>
                        <TableHead className="text-right font-semibold">Thao tác</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tokens.map((token) => {
                        const tokenScopes = token.scopes || []
                        const isFullAccess = tokenScopes.length === ALL_MCP_SCOPES.length
                        const isReadOnly =
                          tokenScopes.length > 0 &&
                          tokenScopes.every((s) => s.includes(':read') || s === 'note:check')

                        return (
                          <TableRow key={token.id}>
                            <TableCell>
                              <div className="flex flex-col">
                                <span className="font-semibold text-xs">{token.username}</span>
                                <span className="text-[10px] text-muted-foreground">{token.email}</span>
                              </div>
                            </TableCell>

                            <TableCell className="font-medium text-xs sm:text-sm">
                              <div className="flex items-center gap-2">
                                <Zap className="size-3.5 text-primary shrink-0" />
                                <span className="font-semibold">{token.name || 'MCP Token'}</span>
                                {token.client_name && (
                                  <Badge variant="outline" className="text-[10px] py-0 px-1 text-muted-foreground">
                                    OAuth: {token.client_name}
                                  </Badge>
                                )}
                              </div>
                            </TableCell>

                            <TableCell>
                              <Badge
                                variant={
                                  token.status === 'active'
                                    ? 'outline'
                                    : token.status === 'expired'
                                    ? 'secondary'
                                    : 'destructive'
                                }
                                className={
                                  token.status === 'active'
                                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30'
                                    : ''
                                }
                              >
                                {token.status === 'active'
                                  ? 'Hoạt động'
                                  : token.status === 'expired'
                                  ? 'Hết hạn'
                                  : 'Đã thu hồi'}
                              </Badge>
                            </TableCell>

                            <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                              {displayDate(token.expires_at)}
                            </TableCell>

                            <TableCell>
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 px-1.5 text-[11px] font-semibold gap-1 text-primary hover:text-primary"
                                  onClick={() => {
                                    setViewingScopeToken(token)
                                    setIsScopeDetailsOpen(true)
                                  }}
                                >
                                  <Shield className="size-3" />
                                  <span>{tokenScopes.length} Scopes</span>
                                </Button>
                                {isFullAccess && (
                                  <Badge variant="outline" className="text-[10px] text-purple-600 dark:text-purple-400 border-purple-500/30 py-0">
                                    Full Access
                                  </Badge>
                                )}
                                {isReadOnly && (
                                  <Badge variant="outline" className="text-[10px] text-sky-600 dark:text-sky-400 border-sky-500/30 py-0">
                                    Read-only
                                  </Badge>
                                )}
                              </div>
                            </TableCell>

                            <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                              {token.last_used_at ? displayDate(token.last_used_at) : 'Chưa dùng'}
                            </TableCell>

                            <TableCell className="text-right whitespace-nowrap">
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  title="Chỉnh sửa quyền hạn & thông tin"
                                  className="h-8 w-8 p-0"
                                  onClick={() => {
                                    setEditingToken(token)
                                    setEditName(token.name)
                                    setEditExpiry('keep')
                                    setEditScopes([...token.scopes])
                                  }}
                                >
                                  <Pencil className="size-3.5" />
                                </Button>

                                <Button
                                  variant="ghost"
                                  size="sm"
                                  title="Xoay vòng Secret (Tạo key mới mà giữ nguyên scopes)"
                                  className="h-8 w-8 p-0 text-amber-600 dark:text-amber-400 hover:text-amber-700"
                                  onClick={() => {
                                    setRotatingToken(token)
                                    setRotateExpiry('180')
                                  }}
                                >
                                  <RefreshCw className="size-3.5" />
                                </Button>

                                {token.status === 'active' ? (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    title="Thu hồi token"
                                    className="h-8 w-8 p-0 text-rose-600 hover:text-rose-700"
                                    onClick={() => setRevokingTokenId(token.id)}
                                  >
                                    <Trash2 className="size-3.5" />
                                  </Button>
                                ) : (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    title="Xóa vĩnh viễn"
                                    className="h-8 w-8 p-0 text-rose-700 hover:text-rose-800"
                                    onClick={() => setPurgingToken(token)}
                                  >
                                    <Trash2 className="size-3.5 text-rose-700" />
                                  </Button>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Pagination */}
              {tokensQuery.data && tokensQuery.data.pages > 1 && (
                <div className="flex items-center justify-between pt-4 border-t mt-4 text-xs text-muted-foreground">
                  <span>Trang {tokensQuery.data.page} / {tokensQuery.data.pages} (Tổng {tokensQuery.data.total} token)</span>
                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={tokenPage <= 1}
                      onClick={() => setTokenPage((p) => Math.max(1, p - 1))}
                    >
                      Trước
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={tokenPage >= tokensQuery.data.pages}
                      onClick={() => setTokenPage((p) => p + 1)}
                    >
                      Sau
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ================= TAB 3: OAUTH 2.1 & CLIENTS ================= */}
        <TabsContent value="oauth" className="space-y-4 outline-hidden mt-0">
          <McpOAuthTab />
        </TabsContent>
      </Tabs>

      {/* ================= DIALOGS ================= */}

      {/* 1. Newly Issued Token Dialog */}
      <Dialog open={Boolean(issuedResult)} onOpenChange={(open) => !open && setIssuedResult(null)}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
              <KeyRound className="size-5" />
              Token & Secret Đã Được Tạo Thành Công
            </DialogTitle>
            <DialogDescription>
              Hãy sao chép ngay chuỗi Secret token bên dưới. Vì lý do an toàn, chuỗi secret đầy đủ sẽ không được hiển thị lại sau khi bạn đóng hộp thoại này.
            </DialogDescription>
          </DialogHeader>

          {issuedResult && (
            <div className="space-y-4 py-2">
              <div className="p-3 rounded-lg border bg-muted/40 text-xs space-y-1">
                <div><strong>Tên gợi nhớ:</strong> {issuedResult.name}</div>
                {issuedResult.username && <div><strong>Chủ sở hữu:</strong> {issuedResult.username}</div>}
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Secret Access Token (Bearer Key)</Label>
                <div className="flex items-center gap-2">
                  <Input
                    readOnly
                    value={issuedResult.token}
                    className="font-mono text-xs bg-muted/60 select-all"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copy(issuedResult.token, 'Secret Token')}
                    className="gap-1.5 shrink-0"
                  >
                    {copiedKey === 'Secret Token' ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
                    <span>{copiedKey === 'Secret Token' ? 'Đã chép' : 'Sao chép'}</span>
                  </Button>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Endpoint URL dành cho AI Assistant</Label>
                <div className="flex items-center gap-2">
                  <Input
                    readOnly
                    value={`${FLAMA_MCP_URL.replace(/\/+$/, '')}/${encodeURIComponent(issuedResult.token)}`}
                    className="font-mono text-xs bg-muted/60 select-all"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      copy(
                        `${FLAMA_MCP_URL.replace(/\/+$/, '')}/${encodeURIComponent(issuedResult.token)}`,
                        'Server URL'
                      )
                    }
                    className="gap-1.5 shrink-0"
                  >
                    {copiedKey === 'Server URL' ? <Check className="size-3.5 text-emerald-600" /> : <LinkIcon className="size-3.5" />}
                    <span>{copiedKey === 'Server URL' ? 'Đã chép' : 'Sao chép URL'}</span>
                  </Button>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button onClick={() => setIssuedResult(null)}>Đã lưu Secret & Đóng</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 2. Create Token Dialog */}
      <Dialog open={isCreateTokenOpen} onOpenChange={setIsCreateTokenOpen}>
        <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Cấp MCP Access Token Mới</DialogTitle>
            <DialogDescription>
              Tạo token ủy quyền kết nối API cho một tài khoản người dùng trong hệ thống.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Chọn người dùng nhận token *</Label>
              <NativeSelect
                value={String(createUserId)}
                onChange={(e) => setCreateUserId(Number(e.target.value))}
                className="text-xs"
              >
                {!createUserId && (
                  <NativeSelectOption value="">-- Chọn người dùng --</NativeSelectOption>
                )}
                {users.map((u) => (
                  <NativeSelectOption key={u.id} value={String(u.id)}>
                    {u.display_name} ({u.username} - {u.email})
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Tên gợi nhớ *</Label>
              <Input
                placeholder="VD: Claude Desktop PC, ChatGPT Connector..."
                value={createTokenName}
                onChange={(e) => setCreateTokenName(e.target.value)}
                className="text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold">Chuỗi Secret Token (Tùy chọn)</Label>
                <span className="text-[10px] text-muted-foreground font-medium">Để trống để tự động sinh</span>
              </div>
              <Input
                placeholder="Dán chuỗi token đã có hoặc để trống (VD: flama_mcp_...)"
                value={createCustomToken}
                onChange={(e) => setCreateCustomToken(e.target.value)}
                className="text-xs font-mono"
              />
              <p className="text-[11px] text-muted-foreground">
                Nếu bạn đã tạo sẵn chuỗi token bên ngoài và muốn nhập trực tiếp cho người dùng, hãy dán vào đây (tối thiểu 16 ký tự). Nếu để trống, hệ thống sẽ tự sinh ngẫu nhiên chuỗi token bảo mật mới.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Thời hạn hiệu lực</Label>
              <NativeSelect
                value={createExpiry}
                onChange={(e) => setCreateExpiry(e.target.value)}
                className="text-xs"
              >
                <NativeSelectOption value="30">30 ngày</NativeSelectOption>
                <NativeSelectOption value="90">90 ngày</NativeSelectOption>
                <NativeSelectOption value="180">180 ngày (Khuyên dùng)</NativeSelectOption>
                <NativeSelectOption value="365">1 năm</NativeSelectOption>
                <NativeSelectOption value="none">Vĩnh viễn (Không hết hạn)</NativeSelectOption>
              </NativeSelect>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold">Phân quyền Scopes ({createScopes.length} đã chọn)</Label>
                <div className="flex items-center gap-1.5">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[11px] px-1.5"
                    onClick={() => setCreateScopes(ALL_MCP_SCOPES.map((s) => s.key))}
                  >
                    Chọn tất cả
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[11px] px-1.5"
                    onClick={() => setCreateScopes([])}
                  >
                    Bỏ chọn
                  </Button>
                </div>
              </div>

              <div className="space-y-2 max-h-56 overflow-y-auto border rounded-lg p-2.5 bg-muted/20">
                {SCOPE_CATEGORIES.map((cat) => (
                  <div key={cat.key} className="space-y-1 pb-2 border-b last:border-b-0">
                    <div className="text-xs font-semibold text-primary">{cat.name}</div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                      {ALL_MCP_SCOPES.filter((s) => s.category === cat.key).map((sc) => (
                        <label
                          key={sc.key}
                          className="flex items-center gap-2 p-1 rounded-md hover:bg-muted/50 cursor-pointer text-xs"
                        >
                          <Checkbox
                            checked={createScopes.includes(sc.key)}
                            onCheckedChange={(checked) => {
                              setCreateScopes((prev) =>
                                checked ? [...prev, sc.key] : prev.filter((k) => k !== sc.key)
                              )
                            }}
                          />
                          <span className="truncate">{sc.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateTokenOpen(false)}>Hủy</Button>
            <Button
              disabled={createTokenMutation.isPending || !createUserId}
              onClick={() => createTokenMutation.mutate()}
            >
              {createTokenMutation.isPending ? 'Đang tạo…' : 'Cấp Token Mới'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 3. Edit Token Dialog */}
      <Dialog open={Boolean(editingToken)} onOpenChange={(open) => !open && setEditingToken(null)}>
        <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Chỉnh Sửa Token & Scopes</DialogTitle>
            <DialogDescription>
              Cập nhật tên gợi nhớ, thời hạn hoặc thay đổi trực tiếp quyền hạn (scopes).
            </DialogDescription>
          </DialogHeader>

          {editingToken && (
            <div className="space-y-4 py-2">
              <div className="p-3 rounded-lg border bg-muted/40 text-xs space-y-1">
                <div><strong>Chủ sở hữu:</strong> {editingToken.username} ({editingToken.email})</div>
                <div><strong>Trạng thái:</strong> {editingToken.status}</div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Tên gợi nhớ</Label>
                <Input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Thời hạn</Label>
                <NativeSelect
                  value={editExpiry}
                  onChange={(e) => setEditExpiry(e.target.value)}
                  className="text-xs"
                >
                  <NativeSelectOption value="keep">Giữ nguyên thời hạn hiện tại</NativeSelectOption>
                  <NativeSelectOption value="30">Gia hạn 30 ngày</NativeSelectOption>
                  <NativeSelectOption value="90">Gia hạn 90 ngày</NativeSelectOption>
                  <NativeSelectOption value="180">Gia hạn 180 ngày</NativeSelectOption>
                  <NativeSelectOption value="none">Chuyển sang Vĩnh viễn</NativeSelectOption>
                </NativeSelect>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-semibold">Quyền hạn ({editScopes.length} Scopes)</Label>
                  <div className="flex items-center gap-1.5">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 text-[11px] px-1.5"
                      onClick={() => setEditScopes(ALL_MCP_SCOPES.map((s) => s.key))}
                    >
                      Chọn tất cả
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 text-[11px] px-1.5"
                      onClick={() => setEditScopes([])}
                    >
                      Bỏ chọn
                    </Button>
                  </div>
                </div>

                <div className="space-y-2 max-h-56 overflow-y-auto border rounded-lg p-2.5 bg-muted/20">
                  {SCOPE_CATEGORIES.map((cat) => (
                    <div key={cat.key} className="space-y-1 pb-2 border-b last:border-b-0">
                      <div className="text-xs font-semibold text-primary">{cat.name}</div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                        {ALL_MCP_SCOPES.filter((s) => s.category === cat.key).map((sc) => (
                          <label
                            key={sc.key}
                            className="flex items-center gap-2 p-1 rounded-md hover:bg-muted/50 cursor-pointer text-xs"
                          >
                            <Checkbox
                              checked={editScopes.includes(sc.key)}
                              onCheckedChange={(checked) => {
                                setEditScopes((prev) =>
                                  checked ? [...prev, sc.key] : prev.filter((k) => k !== sc.key)
                                )
                              }}
                            />
                            <span className="truncate">{sc.label}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingToken(null)}>Hủy</Button>
            <Button
              disabled={updateTokenMutation.isPending}
              onClick={() => updateTokenMutation.mutate()}
            >
              {updateTokenMutation.isPending ? 'Đang lưu…' : 'Lưu Thay Đổi'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 4. Rotate Secret Dialog */}
      <Dialog open={Boolean(rotatingToken)} onOpenChange={(open) => !open && setRotatingToken(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <RefreshCw className="size-5" />
              Xoay Vòng Secret Cho Token
            </DialogTitle>
            <DialogDescription>
              Xoay vòng secret sẽ sinh một Secret Key mới cho token <strong>{rotatingToken?.name}</strong>. Secret cũ sẽ ngay lập tức bị vô hiệu hóa mà không làm mất phân quyền Scopes đã cấu hình.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Thời hạn hiệu lực của Secret mới</Label>
              <NativeSelect
                value={rotateExpiry}
                onChange={(e) => setRotateExpiry(e.target.value)}
                className="text-xs"
              >
                <NativeSelectOption value="30">30 ngày</NativeSelectOption>
                <NativeSelectOption value="90">90 ngày</NativeSelectOption>
                <NativeSelectOption value="180">180 ngày</NativeSelectOption>
                <NativeSelectOption value="365">1 năm</NativeSelectOption>
                <NativeSelectOption value="none">Vĩnh viễn (Không hết hạn)</NativeSelectOption>
              </NativeSelect>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setRotatingToken(null)}>Hủy</Button>
            <Button
              disabled={rotateTokenMutation.isPending}
              onClick={() => rotatingToken && rotateTokenMutation.mutate(rotatingToken.id)}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              {rotateTokenMutation.isPending ? 'Đang xoay vòng…' : 'Xác Nhận Xoay Vòng Secret'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 5. View Scope Details Dialog */}
      <Dialog open={isScopeDetailsOpen} onOpenChange={setIsScopeDetailsOpen}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Shield className="size-5 text-primary" />
              Chi Tiết Quyền Hạn ({viewingScopeToken?.name})
            </DialogTitle>
            <DialogDescription>
              Chủ sở hữu: <strong>{viewingScopeToken?.username}</strong> ({viewingScopeToken?.email})
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            {viewingScopeToken?.scopes?.length ? (
              <div className="grid grid-cols-1 gap-2">
                {viewingScopeToken.scopes.map((scopeKey) => {
                  const scopeMeta = ALL_MCP_SCOPES.find((s) => s.key === scopeKey)
                  return (
                    <div key={scopeKey} className="p-2 rounded-lg border bg-muted/30 flex items-start gap-2.5">
                      <Check className="size-4 text-emerald-600 shrink-0 mt-0.5" />
                      <div>
                        <div className="text-xs font-semibold">{scopeMeta?.label || scopeKey}</div>
                        <div className="text-[11px] text-muted-foreground">{scopeMeta?.desc || scopeKey}</div>
                        <div className="text-[10px] font-mono text-muted-foreground/80 mt-0.5">{scopeKey}</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <EmptyState title="Không có scope nào" description="Token này không có quyền hạn nào." />
            )}
          </div>

          <DialogFooter>
            <Button onClick={() => setIsScopeDetailsOpen(false)}>Đóng</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 6. Revoke Token Confirmation Dialog */}
      <Dialog open={Boolean(revokingTokenId)} onOpenChange={(open) => !open && setRevokingTokenId(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-rose-600 dark:text-rose-400 flex items-center gap-2">
              <AlertCircle className="size-5" />
              Thu Hồi Token Này?
            </DialogTitle>
            <DialogDescription>
              Token sẽ chuyển sang trạng thái <strong>Đã thu hồi (Revoked)</strong>. Các ứng dụng AI đang sử dụng token này sẽ không thể gọi API được nữa.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRevokingTokenId(null)}>Hủy</Button>
            <Button
              variant="destructive"
              disabled={revokeTokenMutation.isPending}
              onClick={() => revokingTokenId && revokeTokenMutation.mutate(revokingTokenId)}
            >
              {revokeTokenMutation.isPending ? 'Đang thu hồi…' : 'Xác Nhận Thu Hồi'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 7. Purge Token Confirmation Dialog */}
      <Dialog open={Boolean(purgingToken)} onOpenChange={(open) => !open && setPurgingToken(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-rose-700 dark:text-rose-400 flex items-center gap-2">
              <Trash2 className="size-5" />
              Xóa Vĩnh Viễn Token?
            </DialogTitle>
            <DialogDescription>
              Hành động này sẽ xóa hoàn toàn bản ghi token <strong>{purgingToken?.name}</strong> khỏi cơ sở dữ liệu. Thao tác này không thể hoàn tác.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPurgingToken(null)}>Hủy</Button>
            <Button
              variant="destructive"
              disabled={purgeTokenMutation.isPending}
              onClick={() => purgingToken && purgeTokenMutation.mutate(purgingToken.id)}
            >
              {purgeTokenMutation.isPending ? 'Đang xóa…' : 'Xóa Vĩnh Viễn'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 8. Cleanup Dialog */}
      <Dialog open={isCleanupOpen} onOpenChange={setIsCleanupOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Eraser className="size-5 text-amber-600" />
              Dọn Dẹp Token Hết Hạn & Đã Thu Hồi
            </DialogTitle>
            <DialogDescription>
              Hệ thống sẽ xóa vĩnh viễn tất cả <strong>{summary.inactive_tokens}</strong> token đã hết hạn hoặc đã thu hồi trên toàn hệ thống để tối ưu cơ sở dữ liệu.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCleanupOpen(false)}>Hủy</Button>
            <Button
              disabled={cleanupMutation.isPending}
              onClick={() => cleanupMutation.mutate()}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              {cleanupMutation.isPending ? 'Đang dọn dẹp…' : 'Xác Nhận Dọn Dẹp'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  )
}
