import { useEffect, useState } from 'react'
import {
  Check,
  CheckCircle2,
  Copy,
  Eye,
  RotateCcw,
  Search,
  Shield,
  ShieldCheck,
  ShieldUser,
  Slash,
  Sparkles,
  Users,
  X,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
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
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Page, PageHeader, SectionCard, StatCard } from '@/shared/components/Page'
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
  timezone?: string
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

type PaymentCard = {
  label: string
  value: string
  tone: string
  hint: string
}

type PaymentDashboard = {
  cards: PaymentCard[]
  recent_orders: Array<{
    id: string
    merchant_order_code: string
    title: string
    status_label: string
    total_amount_display: string
  }>
}

type TtsProvider = {
  id: number
  provider_name: string
  provider_type: string
  base_url: string | null
  requires_api_key: boolean
  is_active: boolean
  shared_config: Record<string, unknown>
  provider_config: Record<string, unknown>
  default_settings: Record<string, unknown>
}

const AVATAR_GRADIENTS = [
  'from-amber-500 to-orange-600',
  'from-purple-500 to-indigo-600',
  'from-cyan-500 to-blue-600',
  'from-emerald-500 to-teal-600',
  'from-rose-500 to-pink-600',
  'from-yellow-500 to-amber-600',
]

function AdminHeader({
  title,
  description,
}: {
  title: string
  description?: string
}) {
  return (
    <div className="space-y-3">
      <Badge variant="destructive" className="gap-1 font-semibold">
        <ShieldCheck className="size-3.5" /> Admin
      </Badge>
      <PageHeader title={title} description={description} />
    </div>
  )
}

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
      <Badge className="bg-purple-500/15 text-purple-700 hover:bg-purple-500/25 dark:text-purple-300 gap-1 border-purple-500/30">
        <Sparkles className="size-3.5" />
        Creator
      </Badge>
    )
  }
  if (roleName?.toLowerCase() === 'enterprise') {
    return (
      <Badge className="bg-blue-500/15 text-blue-700 hover:bg-blue-500/25 dark:text-blue-300 gap-1 border-blue-500/30">
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

export function AdminUsersPage() {
  const queryClient = useQueryClient()
  const [searchText, setSearchText] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [detailUser, setDetailUser] = useState<AdminUser | null>(null)
  const [isBatchRoleModalOpen, setIsBatchRoleModalOpen] = useState(false)
  const [batchTargetRoleId, setBatchTargetRoleId] = useState<string>('')
  const [copiedEmail, setCopiedEmail] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchText.trim())
      setPage(1)
    }, 250)
    return () => window.clearTimeout(timer)
  }, [searchText])

  const queryKey = ['admin', 'users', debouncedSearch, status, page, perPage] as const
  const query = useQuery({
    queryKey,
    queryFn: () =>
      appApi.get<AdminUsersResponse>('/admin/users', {
        q: debouncedSearch,
        status,
        page,
        per_page: perPage,
      }),
  })

  // Single user mutation
  const mutation = useMutation({
    mutationFn: ({
      userId,
      payload,
    }: {
      userId: number
      payload: { role_id: number } | { is_disabled: boolean }
    }) => appApi.mutate(`/admin/users/${userId}`, 'PATCH', payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      toast.success('Đã cập nhật thông tin người dùng.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  // Batch status mutation
  const batchStatusMutation = useMutation({
    mutationFn: ({ ids, action }: { ids: number[]; action: 'activate' | 'disable' }) =>
      appApi.mutate<{ success_count?: number; fail_count?: number }>(
        '/admin/api/users/status/batch',
        'POST',
        { user_ids: ids, action },
      ),
    onSuccess: async (data, variables) => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      const actionText = variables.action === 'disable' ? 'vô hiệu hóa' : 'kích hoạt'
      toast.success(`Đã ${actionText} thành công ${data.success_count ?? variables.ids.length} người dùng.`)
      setSelectedIds([])
    },
    onError: (error: Error) => toast.error(error.message),
  })

  // Batch role mutation
  const batchRoleMutation = useMutation({
    mutationFn: ({ ids, targetRoleId }: { ids: number[]; targetRoleId: number }) =>
      appApi.mutate<{ success_count?: number; fail_count?: number }>(
        '/admin/api/users/roles/batch',
        'POST',
        { user_ids: ids, target_role_id: targetRoleId, mode: 'replace' },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      toast.success('Đã cập nhật vai trò hàng loạt thành công.')
      setIsBatchRoleModalOpen(false)
      setSelectedIds([])
    },
    onError: (error: Error) => toast.error(error.message),
  })

  if (query.isPending) return <PageLoading label="Đang tải danh sách người dùng…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  const users = query.data.items || []
  const summary = query.data.summary || {
    total_users: query.data.total || users.length,
    active_users: users.filter((u) => !u.is_disabled).length,
    disabled_users: users.filter((u) => u.is_disabled).length,
  }
  const roles = query.data.roles || []
  const totalPages = query.data.pages || Math.ceil((query.data.total || 1) / perPage) || 1

  const activePct =
    summary.total_users > 0
      ? Math.round((summary.active_users / summary.total_users) * 1000) / 10
      : 0

  const allPageIds = users.map((u) => u.id)
  const isAllPageSelected =
    allPageIds.length > 0 && allPageIds.every((id) => selectedIds.includes(id))

  const toggleSelectAll = () => {
    if (isAllPageSelected) {
      setSelectedIds((prev) => prev.filter((id) => !allPageIds.includes(id)))
    } else {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...allPageIds])))
    }
  }

  const toggleSelectRow = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    )
  }

  const handleCopyEmail = (email: string) => {
    if (!email) return
    navigator.clipboard.writeText(email).then(() => {
      setCopiedEmail(true)
      toast.success('Đã sao chép email!')
      setTimeout(() => setCopiedEmail(false), 1500)
    })
  }

  const handleResetFilters = () => {
    setSearchText('')
    setDebouncedSearch('')
    setStatus('')
    setPage(1)
  }

  return (
    <Page>
      <AdminHeader
        title="Quản lý Người dùng"
        description="Danh sách thành viên hệ thống, gán vai trò và quản trị trạng thái tài khoản."
      />

      {/* Metric Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Tổng số user"
          value={summary.total_users.toLocaleString('vi-VN')}
          hint="Thành viên hệ thống"
          tone="primary"
        />
        <StatCard
          label="Hoạt động (Active)"
          value={summary.active_users.toLocaleString('vi-VN')}
          hint={`${activePct}% trên tổng số`}
          tone="success"
        />
        <StatCard
          label="Vô hiệu hóa"
          value={summary.disabled_users.toLocaleString('vi-VN')}
          hint={summary.disabled_users > 0 ? 'Tài khoản bị khóa' : 'Không có tài khoản bị khóa'}
          tone={summary.disabled_users > 0 ? 'warning' : 'default'}
        />
        <StatCard
          label="Vai trò hệ thống"
          value={roles.length.toString()}
          hint="Cấp độ phân quyền"
          tone="default"
        />
      </div>

      {/* Toolbar & Filter */}
      <Card className="shadow-xs">
        <CardContent className="grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_180px_140px_auto]">
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
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPage(1)
            }}
          >
            <NativeSelectOption value="">Tất cả trạng thái</NativeSelectOption>
            <NativeSelectOption value="active">🟢 Active (Hoạt động)</NativeSelectOption>
            <NativeSelectOption value="disabled">🔴 Disabled (Vô hiệu hóa)</NativeSelectOption>
          </NativeSelect>

          <NativeSelect
            value={perPage.toString()}
            onChange={(e) => {
              setPerPage(Number(e.target.value))
              setPage(1)
            }}
          >
            <NativeSelectOption value="10">10 dòng/trang</NativeSelectOption>
            <NativeSelectOption value="20">20 dòng/trang</NativeSelectOption>
            <NativeSelectOption value="50">50 dòng/trang</NativeSelectOption>
          </NativeSelect>

          {(searchText || status !== '') && (
            <Button variant="ghost" size="icon" onClick={handleResetFilters} title="Đặt lại bộ lọc">
              <RotateCcw className="size-4" />
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Table State */}
      {!users.length ? (
        <EmptyState
          title="Không tìm thấy người dùng"
          description="Không có tài khoản nào phù hợp với bộ lọc hiện tại."
        />
      ) : (
        <Card className="overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/40">
                  <TableHead className="w-12 text-center">
                    <Checkbox
                      checked={isAllPageSelected}
                      onCheckedChange={toggleSelectAll}
                      aria-label="Chọn tất cả người dùng trang hiện tại"
                    />
                  </TableHead>
                  <TableHead>Người dùng</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Vai trò</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead className="text-right">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => {
                  const gradient = AVATAR_GRADIENTS[user.id % AVATAR_GRADIENTS.length]
                  const isSelected = selectedIds.includes(user.id)

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
                        <div className="flex items-center gap-3">
                          <div
                            className={`flex size-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br ${gradient} text-xs font-bold text-white shadow-xs`}
                          >
                            {(user.username[0] || '?').toUpperCase()}
                          </div>
                          <div>
                            <p className="font-semibold text-foreground">{user.username}</p>
                            {user.account_name && (
                              <p className="text-xs text-muted-foreground">@{user.account_name}</p>
                            )}
                          </div>
                        </div>
                      </TableCell>

                      <TableCell>
                        <span className="text-sm font-medium text-muted-foreground">{user.email}</span>
                      </TableCell>

                      <TableCell>
                        <div className="flex items-center gap-2">
                          <RoleBadge roleName={user.role_name} isAdmin={user.is_admin} />
                          {roles.length > 0 && (
                            <NativeSelect
                              value={user.role_id === null ? '' : String(user.role_id)}
                              className="h-7 w-32 text-xs"
                              disabled={mutation.isPending}
                              onChange={(e) =>
                                mutation.mutate({
                                  userId: user.id,
                                  payload: { role_id: Number(e.target.value) },
                                })
                              }
                            >
                              <NativeSelectOption value="" disabled>Đổi quyền…</NativeSelectOption>
                              {roles.map((r) => (
                                <NativeSelectOption key={r.id} value={String(r.id)}>
                                  {r.name}
                                </NativeSelectOption>
                              ))}
                            </NativeSelect>
                          )}
                        </div>
                      </TableCell>

                      <TableCell>
                        <StatusPill isDisabled={user.is_disabled} />
                      </TableCell>

                      <TableCell className="text-right">
                        <div className="inline-flex items-center gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-8 text-muted-foreground hover:text-foreground"
                            onClick={() => setDetailUser(user)}
                            title="Xem chi tiết"
                          >
                            <Eye className="size-4" />
                          </Button>

                          <Button
                            size="icon"
                            variant="ghost"
                            className={`size-8 ${
                              user.is_disabled
                                ? 'text-emerald-600 hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-950/50'
                                : 'text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-950/50'
                            }`}
                            disabled={mutation.isPending}
                            onClick={() =>
                              mutation.mutate({
                                userId: user.id,
                                payload: { is_disabled: !user.is_disabled },
                              })
                            }
                            title={user.is_disabled ? 'Kích hoạt tài khoản' : 'Vô hiệu hóa tài khoản'}
                          >
                            {user.is_disabled ? <CheckCircle2 className="size-4" /> : <Slash className="size-4" />}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>

          {/* Pagination Footer */}
          <div className="flex flex-col items-center justify-between gap-3 border-t p-4 sm:flex-row">
            <p className="text-xs text-muted-foreground">
              Hiển thị <strong className="text-foreground">{users.length}</strong> / {query.data.total || users.length} người dùng | Trang {page}/{totalPages}
            </p>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
              >
                Trước
              </Button>
              <span className="px-2 text-xs font-semibold">{page}</span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              >
                Sau
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Floating Selection Action Bar */}
      {selectedIds.length > 0 && (
        <div className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-full border border-white/20 bg-gray-900/95 px-4 py-2 text-white shadow-2xl backdrop-blur-md dark:border-white/10 dark:bg-gray-950/95 animate-in fade-in slide-in-from-bottom-5">
          <div className="flex items-center gap-2">
            <span className="flex size-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
              {selectedIds.length}
            </span>
            <span className="text-xs font-medium">đã chọn</span>
          </div>

          <div className="h-4 w-px bg-white/20" />

          <div className="flex items-center gap-1.5">
            {roles.length > 0 && (
              <Button
                size="sm"
                variant="secondary"
                className="h-8 text-xs font-medium"
                onClick={() => setIsBatchRoleModalOpen(true)}
              >
                <ShieldUser className="mr-1 size-3.5" /> Đổi vai trò
              </Button>
            )}

            <Button
              size="sm"
              className="h-8 bg-emerald-600 text-xs font-medium text-white hover:bg-emerald-500"
              disabled={batchStatusMutation.isPending}
              onClick={() => batchStatusMutation.mutate({ ids: selectedIds, action: 'activate' })}
            >
              <CheckCircle2 className="mr-1 size-3.5" /> Kích hoạt
            </Button>

            <Button
              size="sm"
              variant="destructive"
              className="h-8 text-xs font-medium"
              disabled={batchStatusMutation.isPending}
              onClick={() => batchStatusMutation.mutate({ ids: selectedIds, action: 'disable' })}
            >
              <Slash className="mr-1 size-3.5" /> Vô hiệu hóa
            </Button>

            <Button
              size="icon"
              variant="ghost"
              className="size-7 text-white/70 hover:bg-white/10 hover:text-white"
              onClick={() => setSelectedIds([])}
              title="Bỏ chọn tất cả"
            >
              <X className="size-4" />
            </Button>
          </div>
        </div>
      )}

      {/* User Detail Dialog */}
      <Dialog open={detailUser !== null} onOpenChange={(open) => !open && setDetailUser(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Users className="size-5 text-primary" />
              Chi tiết Người dùng
            </DialogTitle>
            <DialogDescription>
              Xem thông tin chi tiết tài khoản thành viên hệ thống.
            </DialogDescription>
          </DialogHeader>

          {detailUser && (
            <div className="space-y-4 py-2">
              <div className="flex items-center gap-3 border-b pb-3">
                <div
                  className={`flex size-12 items-center justify-center rounded-full bg-gradient-to-br ${
                    AVATAR_GRADIENTS[detailUser.id % AVATAR_GRADIENTS.length]
                  } text-lg font-bold text-white shadow-md`}
                >
                  {(detailUser.username[0] || '?').toUpperCase()}
                </div>
                <div>
                  <h4 className="font-bold text-foreground">{detailUser.username}</h4>
                  <div className="mt-1 flex items-center gap-2">
                    <RoleBadge roleName={detailUser.role_name} isAdmin={detailUser.is_admin} />
                    <StatusPill isDisabled={detailUser.is_disabled} />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase">ID Tài khoản</p>
                  <p className="font-medium">#{detailUser.id}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase">Múi giờ</p>
                  <p className="font-medium">{detailUser.timezone || 'UTC'}</p>
                </div>
                <div className="col-span-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase">Email liên hệ</p>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="font-medium text-foreground">{detailUser.email}</span>
                    <Button
                      size="icon"
                      variant="outline"
                      className="size-6"
                      onClick={() => handleCopyEmail(detailUser.email)}
                      title="Sao chép email"
                    >
                      {copiedEmail ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailUser(null)}>
              Đóng
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Batch Role Dialog */}
      <Dialog open={isBatchRoleModalOpen} onOpenChange={setIsBatchRoleModalOpen}>
        <DialogContent className="sm:max-w-xs">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldUser className="size-5 text-primary" />
              Đổi vai trò hàng loạt
            </DialogTitle>
            <DialogDescription>
              Chọn vai trò mới áp dụng cho {selectedIds.length} người dùng đã chọn.
            </DialogDescription>
          </DialogHeader>

          <div className="py-2">
            <Label htmlFor="batchRoleSelect" className="mb-2 block text-xs font-semibold">
              Vai trò mới
            </Label>
            <NativeSelect
              id="batchRoleSelect"
              value={batchTargetRoleId}
              onChange={(e) => setBatchTargetRoleId(e.target.value)}
            >
              <NativeSelectOption value="" disabled>Chọn vai trò…</NativeSelectOption>
              {roles.map((r) => (
                <NativeSelectOption key={r.id} value={String(r.id)}>
                  {r.name} {r.is_admin ? '(Admin)' : ''}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsBatchRoleModalOpen(false)}>
              Hủy
            </Button>
            <Button
              disabled={!batchTargetRoleId || batchRoleMutation.isPending}
              onClick={() =>
                batchRoleMutation.mutate({
                  ids: selectedIds,
                  targetRoleId: Number(batchTargetRoleId),
                })
              }
            >
              Cập nhật
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  )
}

export function AdminPaymentsPage() {
  const query = useQuery({
    queryKey: ['admin', 'payments'],
    queryFn: () => appApi.get<PaymentDashboard>('/admin/payments'),
  })

  if (query.isPending) return <PageLoading label="Đang tải thanh toán…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page>
      <AdminHeader
        title="Dashboard thanh toán"
        description="Tổng quan giao dịch và tình trạng payOS."
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {query.data.cards.map((item) => (
          <StatCard
            key={item.label}
            label={item.label}
            value={item.value}
            hint={item.hint}
            tone={
              item.tone === 'success'
                ? 'success'
                : item.tone === 'warning' || item.tone === 'danger'
                  ? 'warning'
                  : item.tone === 'primary'
                    ? 'primary'
                    : 'default'
            }
          />
        ))}
      </div>
      <SectionCard title="Đơn hàng gần đây">
        {!query.data.recent_orders.length ? (
          <p className="text-sm text-muted-foreground">Chưa có giao dịch trong kỳ.</p>
        ) : (
          <div className="space-y-3">
            {query.data.recent_orders.map((order) => (
              <div key={order.id} className="flex flex-wrap items-center justify-between gap-3 border-b pb-3 last:border-0 last:pb-0">
                <div>
                  <p className="font-medium">{order.title}</p>
                  <p className="font-mono text-xs text-muted-foreground">
                    {order.merchant_order_code}
                  </p>
                </div>
                <div className="text-right text-sm">
                  <p>{order.total_amount_display}</p>
                  <p className="text-muted-foreground">{order.status_label}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </Page>
  )
}

export function AdminTtsPage() {
  const queryClient = useQueryClient()
  const queryKey = ['admin', 'tts-providers'] as const
  const query = useQuery({
    queryKey,
    queryFn: () =>
      appApi.get<{ items: TtsProvider[] }>('/admin/tts-providers'),
  })
  const mutation = useMutation({
    mutationFn: ({
      provider,
      isActive,
    }: {
      provider: TtsProvider
      isActive: boolean
    }) =>
      appApi.mutate(`/admin/tts-providers/${provider.id}`, 'PUT', {
        ...provider,
        is_active: isActive,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey })
      toast.success('Đã cập nhật TTS provider.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  if (query.isPending) return <PageLoading label="Đang tải TTS provider…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page>
      <AdminHeader
        title="TTS Provider"
        description="Cấu hình provider dùng chung cho tài khoản người học."
      />
      {!query.data.items.length ? (
        <EmptyState title="Chưa có provider" description="Chưa có TTS provider nào trong hệ thống." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {query.data.items.map((provider) => (
            <Card key={provider.id}>
              <CardHeader>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <CardTitle>{provider.provider_name}</CardTitle>
                    <CardDescription>{provider.provider_type}</CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      id={`provider-${provider.id}`}
                      checked={provider.is_active}
                      disabled={mutation.isPending}
                      onCheckedChange={(isActive) =>
                        mutation.mutate({ provider, isActive })
                      }
                    />
                    <Label htmlFor={`provider-${provider.id}`}>
                      {provider.is_active ? 'Đang bật' : 'Đang tắt'}
                    </Label>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Base URL</p>
                  <p className="break-all font-mono text-xs">
                    {provider.base_url || 'Không cấu hình'}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Badge variant="outline">
                    {provider.requires_api_key ? 'Cần API key' : 'Không cần API key'}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </Page>
  )
}
