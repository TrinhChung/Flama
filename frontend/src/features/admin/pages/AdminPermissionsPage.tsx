import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  RotateCcw,
  Search,
  Shield,
  ShieldCheck,
  ShieldUser,
  Sparkles,
  Trash2,
  UserCheck,
  Users,
  X,
  XCircle,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
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
import { Page, PageHeader, StatCard } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

type AdminUser = {
  id: number
  username: string
  account_name?: string
  email: string
  status: 'active' | 'disabled'
  is_disabled: boolean
  is_admin: boolean
  role_id: number | null
  role_name: string | null
  created_at?: string
}

type AdminRole = {
  id: number
  code?: string
  name: string
  description?: string
  is_admin?: boolean
}

type AdminUserSummary = {
  total_users: number
  active_users: number
  disabled_users: number
}

type AdminUsersResponse = {
  items: AdminUser[]
  roles: AdminRole[]
  total: number
  page?: number
  per_page?: number
  pages?: number
  summary?: AdminUserSummary
}

type BatchResultItem = {
  user_id: number
  username?: string
  email?: string
  status: 'success' | 'fail'
  message?: string
}

type BatchResponse = {
  message?: string
  success_count: number
  fail_count: number
  results?: BatchResultItem[]
}

const AVATAR_GRADIENTS = [
  'from-amber-500 to-orange-600',
  'from-orange-500 to-rose-600',
  'from-sky-500 to-blue-600',
  'from-emerald-500 to-teal-600',
  'from-stone-500 to-zinc-600',
  'from-yellow-500 to-amber-600',
]

function RoleBadge({ roleName, isAdmin }: { roleName?: string | null; isAdmin?: boolean }) {
  if (isAdmin || roleName?.toLowerCase() === 'admin') {
    return (
      <Badge variant="destructive" className="gap-1 font-semibold">
        <ShieldCheck className="size-3.5" />
        Admin
      </Badge>
    )
  }
  if (roleName?.toLowerCase() === 'creator') {
    return (
      <Badge className="bg-amber-500/15 text-amber-800 dark:text-amber-300 hover:bg-amber-500/25 gap-1 border-amber-500/30">
        <Sparkles className="size-3.5" />
        Creator
      </Badge>
    )
  }
  if (roleName?.toLowerCase() === 'enterprise') {
    return (
      <Badge className="bg-sky-500/15 text-sky-800 dark:text-sky-300 hover:bg-sky-500/25 gap-1 border-sky-500/30">
        <Shield className="size-3.5" />
        Enterprise
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <Users className="size-3.5" />
      {roleName || 'User'}
    </Badge>
  )
}

function StatusPill({ isDisabled }: { isDisabled: boolean }) {
  if (isDisabled) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-xs font-medium text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-400">
        <span className="size-1.5 rounded-full bg-rose-600 dark:bg-rose-400" />
        Vô hiệu hóa
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-400">
      <span className="relative flex size-1.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
        <span className="relative inline-flex size-1.5 rounded-full bg-emerald-600 dark:bg-emerald-400" />
      </span>
      Hoạt động
    </span>
  )
}

export function AdminPermissionsPage() {
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const initialSelectedCsv = searchParams.get('selected_ids') || ''
  const initialIds = useMemo(() => {
    return initialSelectedCsv
      ? initialSelectedCsv
          .split(',')
          .map((id) => Number(id.trim()))
          .filter((id) => Number.isInteger(id) && id > 0)
      : []
  }, [initialSelectedCsv])

  const [selectedUserIds, setSelectedUserIds] = useState<number[]>(initialIds)
  const [targetRoleId, setTargetRoleId] = useState<string>('')
  const [batchResponse, setBatchResponse] = useState<BatchResponse | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  // Filter & Search states
  const [searchText, setSearchText] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)
  const [viewMode, setViewMode] = useState<'all' | 'selected'>('all')

  // Cache user details so chips can display names even when browsing other pages
  const [userCache, setUserCache] = useState<Record<number, AdminUser>>({})

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchText.trim())
      setPage(1)
    }, 250)
    return () => window.clearTimeout(timer)
  }, [searchText])

  // Query users
  const isSelectedView = viewMode === 'selected'
  const queryKey = [
    'admin',
    'permissions-users',
    debouncedSearch,
    statusFilter,
    roleFilter,
    page,
    perPage,
    isSelectedView ? selectedUserIds.slice().sort().join(',') : 'all',
  ] as const

  const usersQuery = useQuery({
    queryKey,
    queryFn: () => {
      const params: Record<string, any> = {
        q: debouncedSearch,
        status: statusFilter,
        page,
        per_page: perPage,
      }
      if (roleFilter) {
        params.role_id = Number(roleFilter)
      }
      if (isSelectedView) {
        if (!selectedUserIds.length) {
          return Promise.resolve<AdminUsersResponse>({
            items: [],
            roles: [],
            total: 0,
            pages: 1,
          })
        }
        params.ids = selectedUserIds.join(',')
      }
      return appApi.get<AdminUsersResponse>('/admin/users', params)
    },
  })

  // Batch role mutation
  const batchMutation = useMutation({
    mutationFn: (payload: { user_ids: number[]; target_role_id: number; mode: 'replace' }) =>
      appApi.mutate<BatchResponse>('/admin/users/roles/batch', 'POST', payload),
    onSuccess: async (data) => {
      setBatchResponse(data)
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      await queryClient.invalidateQueries({ queryKey: ['admin', 'permissions-users'] })
      toast.success(`Đã áp dụng vai trò mới thành công cho ${data.success_count} người dùng.`)
    },
    onError: (error: Error) => {
      setValidationError(error.message)
      toast.error(error.message)
    },
  })

  // Update userCache with latest queried users
  useEffect(() => {
    if (usersQuery.data?.items) {
      setUserCache((prev) => {
        const next = { ...prev }
        for (const user of usersQuery.data.items) {
          next[user.id] = user
        }
        return next
      })
    }
  }, [usersQuery.data?.items])

  if (usersQuery.isPending && !usersQuery.data) {
    return <PageLoading label="Đang tải danh sách người dùng và cấu hình phân quyền…" />
  }

  if (usersQuery.error) {
    return (
      <Page>
        <PageError error={usersQuery.error} />
      </Page>
    )
  }

  const users = usersQuery.data?.items || []
  const roles = usersQuery.data?.roles || []
  const summary = usersQuery.data?.summary || {
    total_users: usersQuery.data?.total || users.length,
    active_users: users.filter((u) => !u.is_disabled).length,
    disabled_users: users.filter((u) => u.is_disabled).length,
  }
  const totalUsersCount = summary.total_users ?? usersQuery.data?.total ?? users.length
  const totalPages = usersQuery.data?.pages || Math.ceil((usersQuery.data?.total || 1) / perPage) || 1

  const currentPageIds = users.map((u) => u.id)
  const isAllCurrentPageSelected =
    currentPageIds.length > 0 && currentPageIds.every((id) => selectedUserIds.includes(id))

  const toggleSelectAllCurrentPage = () => {
    if (isAllCurrentPageSelected) {
      setSelectedUserIds((prev) => prev.filter((id) => !currentPageIds.includes(id)))
    } else {
      setSelectedUserIds((prev) => Array.from(new Set([...prev, ...currentPageIds])))
    }
  }

  const toggleSelectRow = (id: number) => {
    setSelectedUserIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    )
    setValidationError(null)
  }

  const handleRemoveUser = (id: number) => {
    setSelectedUserIds((prev) => prev.filter((item) => item !== id))
    setValidationError(null)
  }

  const handleClearAllSelected = () => {
    setSelectedUserIds([])
    setValidationError(null)
  }

  const handleResetFilters = () => {
    setSearchText('')
    setDebouncedSearch('')
    setStatusFilter('')
    setRoleFilter('')
    setPage(1)
  }

  const handleApply = () => {
    setValidationError(null)
    if (!targetRoleId) {
      setValidationError('Vui lòng chọn Vai trò mới trước khi áp dụng.')
      return
    }
    if (!selectedUserIds.length) {
      setValidationError('Danh sách người dùng được chọn hiện đang trống. Vui lòng chọn ít nhất 1 người dùng.')
      return
    }

    batchMutation.mutate({
      user_ids: selectedUserIds,
      target_role_id: Number(targetRoleId),
      mode: 'replace',
    })
  }

  return (
    <Page>
      {/* Header */}
      <div className="space-y-3">
        <Badge variant="outline" className="gap-1 font-bold border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400">
          <ShieldCheck className="size-3.5" /> Admin
        </Badge>
        <PageHeader
          title="Phân quyền Người dùng Hàng loạt"
          description="Tìm kiếm, chọn nhiều thành viên và thực hiện gán vai trò quyền hạn đồng thời."
          actions={
            <Button variant="outline" asChild>
              <Link to="/admin/users">
                <ArrowLeft className="mr-1.5 size-4" /> Quay lại Quản lý User
              </Link>
            </Button>
          }
        />
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Tổng số user hệ thống"
          value={totalUsersCount.toLocaleString('vi-VN')}
          hint="Thành viên đã đăng ký"
          tone="default"
        />
        <StatCard
          label="Đang chọn phân quyền"
          value={selectedUserIds.length.toLocaleString('vi-VN')}
          hint={selectedUserIds.length > 0 ? 'Sẵn sàng để áp dụng vai trò' : 'Chưa có user nào được chọn'}
          tone={selectedUserIds.length > 0 ? 'primary' : 'default'}
        />
        <StatCard
          label="Vai trò khả dụng"
          value={roles.length.toString()}
          hint="Cấp độ phân quyền hệ thống"
          tone="default"
        />
      </div>

      {/* Validation Error Alert */}
      {validationError && (
        <Alert variant="destructive">
          <AlertTriangle className="size-4" />
          <AlertTitle>Lỗi xác thực</AlertTitle>
          <AlertDescription>{validationError}</AlertDescription>
        </Alert>
      )}

      {/* Main Grid: User Selection on Left, Assignment Form on Right */}
      <div className="grid gap-6 lg:grid-cols-12 items-start">
        {/* Left Column: Users Browser and Selector */}
        <div className="space-y-4 lg:col-span-7 xl:col-span-8">
          {/* Toolbar & Filter Card */}
          <Card className="shadow-xs">
            <CardContent className="grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_160px_140px_auto]">
              <div className="relative">
                <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="pl-9 pr-9"
                  placeholder="Tìm kiếm username hoặc email…"
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                />
                {searchText && (
                  <button
                    type="button"
                    className="absolute top-1/2 right-2.5 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    onClick={() => setSearchText('')}
                    title="Xóa tìm kiếm"
                  >
                    <X className="size-4" />
                  </button>
                )}
              </div>

              <NativeSelect
                value={roleFilter}
                onChange={(e) => {
                  setRoleFilter(e.target.value)
                  setPage(1)
                }}
              >
                <NativeSelectOption value="">Tất cả vai trò</NativeSelectOption>
                {roles.map((r) => (
                  <NativeSelectOption key={r.id} value={String(r.id)}>
                    {r.name}
                  </NativeSelectOption>
                ))}
              </NativeSelect>

              <NativeSelect
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value)
                  setPage(1)
                }}
              >
                <NativeSelectOption value="">Tất cả trạng thái</NativeSelectOption>
                <NativeSelectOption value="active">🟢 Active</NativeSelectOption>
                <NativeSelectOption value="disabled">🔴 Disabled</NativeSelectOption>
              </NativeSelect>

              {(searchText || statusFilter || roleFilter) && (
                <Button variant="ghost" size="icon" onClick={handleResetFilters} title="Đặt lại bộ lọc">
                  <RotateCcw className="size-4" />
                </Button>
              )}
            </CardContent>
          </Card>

          {/* View Mode Tabs & Quick Actions */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="inline-flex rounded-lg border bg-muted/30 p-1 text-xs">
              <button
                type="button"
                className={`rounded-md px-3 py-1.5 font-medium transition-all ${
                  viewMode === 'all'
                    ? 'bg-background text-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                onClick={() => {
                  setViewMode('all')
                  setPage(1)
                }}
              >
                Tất cả người dùng ({totalUsersCount})
              </button>
              <button
                type="button"
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-all ${
                  viewMode === 'selected'
                    ? 'bg-background text-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                onClick={() => {
                  setViewMode('selected')
                  setPage(1)
                }}
              >
                <UserCheck className="size-3.5 text-primary" />
                Đã chọn ({selectedUserIds.length})
              </button>
            </div>

            <div className="flex items-center gap-2">
              {currentPageIds.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs"
                  onClick={toggleSelectAllCurrentPage}
                >
                  {isAllCurrentPageSelected ? 'Bỏ chọn trang này' : 'Chọn tất cả trang này'}
                </Button>
              )}
              {selectedUserIds.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 text-xs text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-950/40"
                  onClick={handleClearAllSelected}
                >
                  <Trash2 className="mr-1 size-3.5" /> Bỏ chọn tất cả ({selectedUserIds.length})
                </Button>
              )}
            </div>
          </div>

          {/* Users Table Card */}
          {users.length === 0 ? (
            <EmptyState
              title={viewMode === 'selected' ? 'Chưa chọn người dùng nào' : 'Không tìm thấy người dùng'}
              description={
                viewMode === 'selected'
                  ? 'Hãy chuyển sang tab "Tất cả người dùng" và tích chọn các thành viên cần phân quyền.'
                  : 'Không có tài khoản nào phù hợp với bộ lọc tìm kiếm hiện tại.'
              }
            />
          ) : (
            <Card className="overflow-hidden shadow-xs">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/40">
                      <TableHead className="w-12 text-center">
                        <Checkbox
                          checked={isAllCurrentPageSelected}
                          onCheckedChange={toggleSelectAllCurrentPage}
                          aria-label="Chọn tất cả người dùng trên trang"
                        />
                      </TableHead>
                      <TableHead>Người dùng</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Vai trò hiện tại</TableHead>
                      <TableHead>Trạng thái</TableHead>
                      <TableHead className="text-right">Chọn</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => {
                      const gradient = AVATAR_GRADIENTS[user.id % AVATAR_GRADIENTS.length]
                      const isSelected = selectedUserIds.includes(user.id)

                      return (
                        <TableRow
                          key={user.id}
                          className={isSelected ? 'bg-primary/5 hover:bg-primary/10' : undefined}
                        >
                          <TableCell className="text-center">
                            <Checkbox
                              checked={isSelected}
                              onCheckedChange={() => toggleSelectRow(user.id)}
                              aria-label={`Chọn ${user.username}`}
                            />
                          </TableCell>

                          <TableCell>
                            <div className="flex items-center gap-2.5">
                              <div
                                className={`flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br ${gradient} text-xs font-bold text-white shadow-xs`}
                              >
                                {(user.username[0] || '?').toUpperCase()}
                              </div>
                              <div>
                                <p className="text-sm font-semibold text-foreground">{user.username}</p>
                                {user.account_name && (
                                  <p className="text-xs text-muted-foreground">@{user.account_name}</p>
                                )}
                              </div>
                            </div>
                          </TableCell>

                          <TableCell>
                            <span className="text-xs text-muted-foreground">{user.email || '—'}</span>
                          </TableCell>

                          <TableCell>
                            <RoleBadge roleName={user.role_name} isAdmin={user.is_admin} />
                          </TableCell>

                          <TableCell>
                            <StatusPill isDisabled={user.is_disabled} />
                          </TableCell>

                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              variant={isSelected ? 'secondary' : 'outline'}
                              className="h-7 text-xs px-2.5"
                              onClick={() => toggleSelectRow(user.id)}
                            >
                              {isSelected ? (
                                <span className="inline-flex items-center gap-1 text-primary font-medium">
                                  <CheckCircle2 className="size-3.5" /> Đã chọn
                                </span>
                              ) : (
                                '+ Chọn'
                              )}
                            </Button>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination Controls */}
              <div className="flex flex-col items-center justify-between gap-3 border-t p-4 sm:flex-row">
                <p className="text-xs text-muted-foreground">
                  Hiển thị <strong className="text-foreground">{users.length}</strong> /{' '}
                  {usersQuery.data?.total || users.length} người dùng
                </p>

                <div className="flex items-center gap-3">
                  <NativeSelect
                    value={perPage.toString()}
                    className="h-8 w-28 text-xs"
                    onChange={(e) => {
                      setPerPage(Number(e.target.value))
                      setPage(1)
                    }}
                  >
                    <NativeSelectOption value="10">10 dòng</NativeSelectOption>
                    <NativeSelectOption value="20">20 dòng</NativeSelectOption>
                    <NativeSelectOption value="50">50 dòng</NativeSelectOption>
                  </NativeSelect>

                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs px-2.5"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(p - 1, 1))}
                    >
                      Trước
                    </Button>
                    <Badge
                      variant="outline"
                      className="h-8 px-3 text-xs font-mono font-bold bg-primary/10 text-primary border-primary/30"
                    >
                      {page} / {totalPages}
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs px-2.5"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                    >
                      Sau
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Role Assignment Form */}
        <div className="space-y-4 lg:col-span-5 xl:col-span-4 sticky top-6">
          <Card className="shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <ShieldUser className="size-4 text-primary" /> Form gán vai trò
                </CardTitle>
                <Badge variant={selectedUserIds.length > 0 ? 'default' : 'outline'} className="text-xs">
                  {selectedUserIds.length} user
                </Badge>
              </div>
              <CardDescription>Flama áp dụng mô hình 1 User = 1 Role chính.</CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Selected Users Preview */}
              <div className="space-y-2">
                <Label className="text-xs font-semibold text-muted-foreground uppercase flex items-center justify-between">
                  <span>User đã chọn ({selectedUserIds.length})</span>
                  {selectedUserIds.length > 0 && (
                    <button
                      type="button"
                      onClick={handleClearAllSelected}
                      className="text-xs font-normal text-rose-600 hover:underline"
                    >
                      Bỏ chọn tất cả
                    </button>
                  )}
                </Label>

                {selectedUserIds.length === 0 ? (
                  <div className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
                    Chưa có user nào được chọn. Hãy tích chọn từ danh sách bên trái.
                  </div>
                ) : (
                  <div className="max-h-48 overflow-y-auto rounded-lg border bg-muted/20 p-2 space-y-1.5">
                    {selectedUserIds.map((userId) => {
                      const user = userCache[userId]
                      return (
                        <div
                          key={userId}
                          className="flex items-center justify-between rounded-md bg-background px-2.5 py-1.5 text-xs shadow-2xs border"
                        >
                          <div className="flex items-center gap-2 overflow-hidden">
                            <span className="font-semibold text-foreground truncate">
                              {user ? user.username : `#${userId}`}
                            </span>
                            {user?.role_name && (
                              <span className="text-[10px] text-muted-foreground">
                                ({user.role_name})
                              </span>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => handleRemoveUser(userId)}
                            className="text-muted-foreground hover:text-rose-600 ml-1.5 p-0.5 rounded-xs"
                            title="Xóa khỏi danh sách chọn"
                          >
                            <X className="size-3.5" />
                          </button>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Target Role Selector */}
              <div className="space-y-2">
                <Label htmlFor="target-role-select">Vai trò mới (Target Role)</Label>
                <NativeSelect
                  id="target-role-select"
                  value={targetRoleId}
                  onChange={(e) => {
                    setTargetRoleId(e.target.value)
                    setValidationError(null)
                  }}
                >
                  <NativeSelectOption value="">-- Chọn Vai trò --</NativeSelectOption>
                  {roles.map((r) => (
                    <NativeSelectOption key={r.id} value={String(r.id)}>
                      {r.name} {r.is_admin ? '(Admin)' : ''}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>

              {/* Assignment Mode */}
              <div className="space-y-2">
                <Label>Chế độ gán quyền</Label>
                <Input value="Replace role (Thay thế vai trò)" disabled readOnly className="bg-muted/40" />
              </div>

              {/* Submit Button */}
              <Button
                className="w-full gap-2"
                disabled={!selectedUserIds.length || !targetRoleId || batchMutation.isPending}
                onClick={handleApply}
              >
                <ShieldUser className="size-4" />
                {batchMutation.isPending
                  ? 'Đang áp dụng vai trò…'
                  : `Áp dụng cho ${selectedUserIds.length} người dùng`}
              </Button>
            </CardContent>
          </Card>

          {/* Batch Application Results */}
          {batchResponse && (
            <Card className="shadow-xs border-emerald-500/30 bg-emerald-50/20 dark:bg-emerald-950/10">
              <CardHeader className="pb-3">
                <CardTitle className="text-base text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="size-4 text-emerald-600" /> Kết quả Áp dụng Vai trò
                </CardTitle>
                <CardDescription>
                  Thành công: <strong>{batchResponse.success_count}</strong> | Thất bại:{' '}
                  <strong>{batchResponse.fail_count}</strong>
                </CardDescription>
              </CardHeader>
              <CardContent>
                {batchResponse.results && (
                  <div className="max-h-56 overflow-y-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs">User</TableHead>
                          <TableHead className="text-xs">Trạng thái</TableHead>
                          <TableHead className="text-xs">Thông báo</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {batchResponse.results.map((res, idx) => (
                          <TableRow key={idx}>
                            <TableCell className="text-xs font-semibold">#{res.user_id}</TableCell>
                            <TableCell>
                              {res.status === 'success' ? (
                                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600">
                                  <CheckCircle2 className="size-3.5" /> Xong
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-600">
                                  <XCircle className="size-3.5" /> Lỗi
                                </span>
                              )}
                            </TableCell>
                            <TableCell className="text-[11px] text-muted-foreground">{res.message || '—'}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </Page>
  )
}
