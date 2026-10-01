import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader, StatCard } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'
import { McpOAuthTab } from '@/features/settings/components/McpOAuthTab'
import { McpTokensManager } from '@/features/mcp/components/McpTokensManager'
import { Bot, Check, KeyRound, Search, ShieldAlert, ShieldCheck, Users } from 'lucide-react'

type McpSummaryResponse = {
  total_tokens: number; active_tokens: number; revoked_tokens: number; expired_tokens: number
  inactive_tokens: number; total_requests: number; total_users: number; permitted_users: number
}

type AdminMcpUser = {
  id: number; username: string; email: string; display_name: string; avatar_url: string | null
  role_name: string; is_admin: boolean; is_disabled: boolean; can_use_mcp: boolean; raw_can_use_mcp: boolean
  can_manage_mcp_tokens?: boolean; raw_can_manage_mcp_tokens?: boolean
  active_tokens_count: number; total_tokens_count: number
}

type AdminMcpUsersResponse = { items: AdminMcpUser[]; total: number; page: number; per_page: number; pages: number }

const DEFAULT_SUMMARY: McpSummaryResponse = {
  total_tokens: 0, active_tokens: 0, revoked_tokens: 0, expired_tokens: 0,
  inactive_tokens: 0, total_requests: 0, total_users: 0, permitted_users: 0,
}

export function AdminMcpTokensPage() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'users' | 'tokens' | 'oauth'>('users')
  const [userSearch, setUserSearch] = useState('')
  const [userFilter, setUserFilter] = useState<'all' | 'permitted' | 'unpermitted'>('all')
  const [userPage, setUserPage] = useState(1)

  const summaryQuery = useQuery({
    queryKey: ['admin-mcp-summary'],
    queryFn: () => appApi.get<McpSummaryResponse>('/admin/mcp-tokens/summary'),
  })

  const usersQuery = useQuery({
    queryKey: ['admin-mcp-users', userSearch, userFilter, userPage],
    queryFn: () =>
      appApi.get<AdminMcpUsersResponse>('/admin/mcp-tokens/users', {
        q: userSearch, filter: userFilter, page: userPage, per_page: 20,
      }),
  })

  const refreshAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['admin-mcp-summary'] }),
      queryClient.invalidateQueries({ queryKey: ['admin-mcp-users'] }),
      queryClient.invalidateQueries({ queryKey: ['admin-mcp-tokens'] }),
      queryClient.invalidateQueries({ queryKey: ['mcp', 'tokens'] }),
    ])
  }

  const togglePermissionMutation = useMutation({
    mutationFn: ({ userId, canUseMcp }: { userId: number; canUseMcp: boolean }) =>
      appApi.mutate<{ success: boolean; message: string }>(
        `/admin/mcp-tokens/users/${userId}/permission`, 'POST', { can_use_mcp: canUseMcp }
      ),
    onSuccess: (data) => {
      toast.success(data.message || 'Cập nhật quyền thành công.')
      refreshAll()
    },
    onError: (err: Error) => toast.error(err.message || 'Không thể cập nhật quyền.'),
  })

  const summary = summaryQuery.data || DEFAULT_SUMMARY
  const users = usersQuery.data?.items || []

  if (summaryQuery.isPending && !summaryQuery.data) return <PageLoading label="Đang tải dữ liệu MCP..." />
  if (summaryQuery.error) return <Page><PageError error={summaryQuery.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-6 sm:space-y-8 pb-16 px-3 sm:px-6">
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
        <StatCard tone="primary" label="Token Hoạt động" value={`${summary.active_tokens} / ${summary.total_tokens}`} hint="Token đang hợp lệ trong hệ thống" />
        <StatCard tone="success" label="Tự Quản lý Token" value={`${summary.permitted_users} / ${summary.total_users}`} hint="Được tự tạo & xoay vòng secret" />
        <StatCard tone="default" label="Lượt gọi API" value={summary.total_requests.toLocaleString()} hint="Tổng requests qua MCP Tokens" />
        <StatCard tone="warning" label="Token Cũ / Thu hồi" value={summary.inactive_tokens} hint="Hết hạn hoặc đã thu hồi" />
      </div>

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full space-y-6">
        <div className="overflow-x-auto pb-1 -mx-1 px-1 no-scrollbar">
          <TabsList className="inline-flex w-full sm:w-auto p-1 bg-muted/60 backdrop-blur-md rounded-2xl gap-1">
            <TabsTrigger value="users" className="flex-1 sm:flex-none px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5">
              <Users className="size-4 shrink-0" />
              <span>Phân quyền Quản lý ({summary.permitted_users})</span>
            </TabsTrigger>
            <TabsTrigger value="tokens" className="flex-1 sm:flex-none px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5">
              <KeyRound className="size-4 shrink-0" />
              <span>Danh sách Token & Secrets ({summary.total_tokens})</span>
            </TabsTrigger>
            <TabsTrigger value="oauth" className="flex-1 sm:flex-none px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5">
              <Bot className="size-4 shrink-0" />
              <span>Tích hợp OAuth 2.1 & Clients</span>
            </TabsTrigger>
          </TabsList>
        </div>

        {/* TAB 1: PHÂN QUYỀN NGƯỜI DÙNG */}
        <TabsContent value="users" className="space-y-4 outline-hidden mt-0">
          <Card className="shadow-2xs">
            <CardHeader className="p-4 sm:p-6 pb-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base sm:text-lg font-bold">Phân Quyền Quản Lý Token MCP</CardTitle>
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
                    onChange={(e) => { setUserSearch(e.target.value); setUserPage(1) }}
                    className="pl-9 text-xs sm:text-sm h-9"
                  />
                </div>
                <div className="w-full sm:w-48">
                  <NativeSelect
                    value={userFilter}
                    onChange={(e) => { setUserFilter(e.target.value as any); setUserPage(1) }}
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
                        const isTogglePending = togglePermissionMutation.isPending && togglePermissionMutation.variables?.userId === u.id

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
                                <Badge variant="outline" className="text-[10px]">{u.role_name}</Badge>
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
                                <Badge className="bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/30 text-[11px]">Toàn quyền (Admin)</Badge>
                              ) : isGranted ? (
                                <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30 text-[11px] gap-1">
                                  <Check className="size-3" /> Tự quản lý Token
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-muted-foreground text-[11px]">Chỉ dùng cấu hình Admin</Badge>
                              )}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 text-xs gap-1 hover:border-primary hover:text-primary"
                                  onClick={() => setActiveTab('tokens')}
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
                                    onClick={() => togglePermissionMutation.mutate({ userId: u.id, canUseMcp: !rawGranted })}
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

        {/* TAB 2: DANH SÁCH TOKEN & SECRETS TOÀN HỆ THỐNG */}
        <TabsContent value="tokens" className="space-y-4 outline-hidden mt-0">
          <McpTokensManager
            mode="admin"
            users={users}
            onSuccessMutation={refreshAll}
          />
        </TabsContent>

        {/* TAB 3: OAUTH 2.1 & CLIENTS */}
        <TabsContent value="oauth" className="space-y-4 outline-hidden mt-0">
          <McpOAuthTab />
        </TabsContent>
      </Tabs>
    </Page>
  )
}
