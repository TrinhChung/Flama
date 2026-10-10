import { useMemo, useState } from 'react'
import {
  Award,
  BadgePercent,
  Calculator,
  CheckCircle2,
  Coins,
  Edit3,
  Info,
  Layers,
  Plus,
  RotateCcw,
  Search,
  Shield,
  ShieldCheck,
  User,
  Users,
  X,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader, SectionCard, StatCard } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

type RoleFeeRow = {
  id: number
  code: string
  name: string
  description: string
  is_admin: boolean
  position: number
  default_platform_fee_percent: number
  user_count: number
}

type CreatorPolicy = {
  id: number
  feature_code: string
  is_monetized: boolean
  free_quota_per_creator: number
  price_per_key_minor: number
  price_per_key_display: string
  requires_pro_role: boolean
  updated_at: string | null
}

type CustomFeeUser = {
  id: number
  username: string
  account_name: string
  email: string
  is_admin: boolean
  is_disabled: boolean
  role_id: number | null
  role_name: string | null
  role_code: string | null
  role_default_fee_percent: number
  custom_platform_fee_percent: number | null
  effective_platform_fee_percent: number
  balance_amount_minor: number
  balance_amount_display: string
}

type FeeOverviewResponse = {
  summary: {
    global_default_fee_percent: number
    regular_fee_percent: number
    creator_fee_percent: number
    custom_fee_users_count: number
    total_roles_count: number
    total_sales_count: number
    total_gross_amount_minor: number
    total_gross_display: string
    total_platform_fee_amount_minor: number
    total_platform_fee_display: string
    total_creator_net_amount_minor: number
    total_creator_net_display: string
  }
  roles: RoleFeeRow[]
  creator_policy: CreatorPolicy
  custom_fee_users: CustomFeeUser[]
}

const AVATAR_GRADIENTS = [
  'from-amber-500 to-orange-600',
  'from-orange-500 to-rose-600',
  'from-sky-500 to-blue-600',
  'from-emerald-500 to-teal-600',
  'from-stone-500 to-zinc-600',
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
  if (roleName?.toLowerCase().includes('sáng tạo') || roleName?.toLowerCase() === 'creator') {
    return (
      <Badge variant="outline" className="bg-muted text-foreground border-border/80 gap-1 font-medium">
        <Award className="size-3.5" />
        Creator
      </Badge>
    )
  }
  if (roleName?.toLowerCase().includes('nghiệp') || roleName?.toLowerCase() === 'enterprise') {
    return (
      <Badge className="bg-sky-500/15 text-sky-800 dark:text-sky-300 hover:bg-sky-500/25 gap-1 border-sky-500/30">
        <Shield className="size-3.5" />
        Enterprise
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <User className="size-3.5" />
      {roleName || 'User'}
    </Badge>
  )
}

function FeePercentBadge({ percent }: { percent: number }) {
  if (percent === 0) {
    return (
      <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 font-semibold">
        0% (Miễn phí)
      </Badge>
    )
  }
  if (percent <= 5) {
    return (
      <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300 font-semibold">
        {percent}%
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300 font-semibold">
      {percent}%
    </Badge>
  )
}

export function AdminFeesPage() {
  const queryClient = useQueryClient()
  const queryKey = ['admin', 'fees-overview'] as const

  const query = useQuery({
    queryKey,
    queryFn: () => appApi.get<FeeOverviewResponse>('/admin/fees'),
  })

  // Role fee edit dialog state
  const [editingRole, setEditingRole] = useState<RoleFeeRow | null>(null)
  const [roleFeeInput, setRoleFeeInput] = useState<string>('')

  // Creator policy form state
  const [creatorPolicyForm, setCreatorPolicyForm] = useState<{
    is_monetized: boolean
    free_quota_per_creator: number
    price_per_key_minor: number
    requires_pro_role: boolean
  } | null>(null)

  // Custom user fee dialog state
  const [userFeeDialogOpen, setUserFeeDialogOpen] = useState(false)
  const [selectedUserForOverride, setSelectedUserForOverride] = useState<CustomFeeUser | null>(null)
  const [customFeeInput, setCustomFeeInput] = useState<string>('')
  const [userSearchTerm, setUserSearchTerm] = useState<string>('')
  const [userSearchResults, setUserSearchResults] = useState<CustomFeeUser[]>([])
  const [isSearchingUsers, setIsSearchingUsers] = useState(false)

  // Filter custom users in table
  const [customUserFilterText, setCustomUserFilterText] = useState('')

  // Simulator state
  const [simPrice, setSimPrice] = useState<number>(100000)
  const [simFeePercent, setSimFeePercent] = useState<number>(10)

  // Initialize creator policy form once query loads
  if (query.data && creatorPolicyForm === null) {
    const p = query.data.creator_policy
    setCreatorPolicyForm({
      is_monetized: p.is_monetized,
      free_quota_per_creator: p.free_quota_per_creator,
      price_per_key_minor: p.price_per_key_minor,
      requires_pro_role: p.requires_pro_role,
    })
  }

  // Mutations
  const updateRoleMutation = useMutation({
    mutationFn: async ({ roleId, feePercent }: { roleId: number; feePercent: number }) => {
      return appApi.mutate<{ role: RoleFeeRow; message: string }>(`/admin/fees/roles/${roleId}`, 'PATCH', {
        default_platform_fee_percent: feePercent,
      })
    },
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey })
      setEditingRole(null)
      toast.success(data.message || 'Đã cập nhật mức phí vai trò thành công.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const updateCreatorPolicyMutation = useMutation({
    mutationFn: async (payload: {
      is_monetized: boolean
      free_quota_per_creator: number
      price_per_key_minor: number
      requires_pro_role: boolean
    }) => {
      return appApi.mutate<{ creator_policy: CreatorPolicy; message: string }>('/admin/fees/creator-policy', 'PUT', payload)
    },
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey })
      toast.success(data.message || 'Đã lưu cấu hình chính sách Creator thành công.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const updateUserCustomFeeMutation = useMutation({
    mutationFn: async ({ userId, customFeePercent }: { userId: number; customFeePercent: number | null }) => {
      return appApi.mutate<{ user: CustomFeeUser; message: string }>(`/admin/fees/users/${userId}`, 'PATCH', {
        custom_platform_fee_percent: customFeePercent,
      })
    },
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey })
      setUserFeeDialogOpen(false)
      setSelectedUserForOverride(null)
      setCustomFeeInput('')
      toast.success(data.message || 'Đã cập nhật ngoại lệ phí người dùng thành công.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  // User search helper
  const handleSearchUsers = async (q: string) => {
    setUserSearchTerm(q)
    if (!q.trim()) {
      setUserSearchResults([])
      return
    }
    setIsSearchingUsers(true)
    try {
      const resp = await appApi.get<{ items: CustomFeeUser[] }>(`/admin/fees/search-users?q=${encodeURIComponent(q)}`)
      setUserSearchResults(resp.items || [])
    } catch {
      setUserSearchResults([])
    } finally {
      setIsSearchingUsers(false)
    }
  }

  // Filtered custom fee users
  const filteredCustomUsers = useMemo(() => {
    if (!query.data?.custom_fee_users) return []
    const term = customUserFilterText.trim().toLowerCase()
    if (!term) return query.data.custom_fee_users
    return query.data.custom_fee_users.filter(
      (u) =>
        u.username.toLowerCase().includes(term) ||
        u.email.toLowerCase().includes(term) ||
        (u.role_name && u.role_name.toLowerCase().includes(term))
    )
  }, [query.data?.custom_fee_users, customUserFilterText])

  if (query.isPending) return <PageLoading label="Đang tải thông tin cấu hình phí…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  const { summary, roles, custom_fee_users } = query.data

  // Simulator calculations
  const simFeeAmount = Math.round(simPrice * (simFeePercent / 100))
  const simCreatorNet = Math.max(0, simPrice - simFeeAmount)

  return (
    <Page size="wide">
      <AdminHeader
        title="Thiết lập Phí & Chiết khấu Nền tảng"
        description="Quản lý biểu phí sàn Marketplace theo vai trò, chính sách thu phí tính năng Creator, và danh sách ngoại lệ phí của người dùng."
      />

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Phí sàn chuẩn (Mặc định)"
          value={`${summary.regular_fee_percent}%`}
          hint="Áp dụng cho học viên & mặc định toàn hệ thống"
        />
        <StatCard
          label="Phí ưu đãi Nhà sáng tạo"
          value={`${summary.creator_fee_percent}%`}
          hint="Tỷ lệ chiết khấu cho vai trò Creator"
        />
        <StatCard
          label="Ngoại lệ người dùng"
          value={String(summary.custom_fee_users_count)}
          hint="Tài khoản có tỷ lệ phí tùy chỉnh riêng"
        />
        <StatCard
          label="Tổng phí sàn đã thu"
          value={summary.total_platform_fee_display}
          hint={`Thu từ ${summary.total_sales_count} giao dịch bán Deck (${summary.total_gross_display})`}
        />
      </div>

      {/* Main Tabs Container */}
      <Tabs defaultValue="roles" className="w-full space-y-6">
        <TabsList className="grid w-full grid-cols-2 md:w-auto md:inline-flex md:grid-cols-none">
          <TabsTrigger value="roles" className="gap-2">
            <Layers className="size-4" />
            Biểu phí vai trò
          </TabsTrigger>
          <TabsTrigger value="creator-policy" className="gap-2">
            <Award className="size-4" />
            Tính năng Creator
          </TabsTrigger>
          <TabsTrigger value="user-overrides" className="gap-2">
            <Users className="size-4" />
            Ngoại lệ người dùng ({custom_fee_users.length})
          </TabsTrigger>
          <TabsTrigger value="simulator" className="gap-2">
            <Calculator className="size-4" />
            Mô phỏng doanh thu
          </TabsTrigger>
        </TabsList>

        {/* TAB 1: ROLE FEE TIERS */}
        <TabsContent value="roles" className="space-y-4">
          <SectionCard
            title="Biểu phí chiết khấu theo vai trò"
            description="Tỷ lệ % phí nền tảng Flama giữ lại khi tác giả bán bộ thẻ hoặc loại thẻ trên Marketplace."
          >
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[200px]">Vai trò</TableHead>
                    <TableHead>Mã định danh</TableHead>
                    <TableHead>Số tài khoản</TableHead>
                    <TableHead>Mức phí mặc định</TableHead>
                    <TableHead className="text-right">Hành động</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {roles.map((role) => (
                    <TableRow key={role.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <RoleBadge roleName={role.name} isAdmin={role.is_admin} />
                          <span className="font-medium">{role.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                          {role.code}
                        </code>
                      </TableCell>
                      <TableCell>
                        <span className="inline-flex items-center gap-1 text-sm font-medium">
                          <User className="size-3.5 text-muted-foreground" />
                          {role.user_count.toLocaleString('vi-VN')}
                        </span>
                      </TableCell>
                      <TableCell>
                        <FeePercentBadge percent={role.default_platform_fee_percent} />
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-1.5"
                          onClick={() => {
                            setEditingRole(role)
                            setRoleFeeInput(String(role.default_platform_fee_percent))
                          }}
                        >
                          <Edit3 className="size-3.5" />
                          Sửa mức phí
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <Alert className="mt-4 border-sky-500/20 bg-sky-500/5 text-sky-900 dark:text-sky-200">
              <Info className="size-4 text-sky-600 dark:text-sky-400" />
              <AlertTitle className="font-semibold">Nguyên tắc tính phí nền tảng</AlertTitle>
              <AlertDescription className="text-xs leading-relaxed text-muted-foreground mt-1">
                Khi đơn hàng thành công, hệ thống xác định tỷ lệ phí theo thứ tự ưu tiên:
                <strong className="text-foreground"> Ngoại lệ người dùng</strong> (nếu có) &rarr;
                <strong className="text-foreground"> Mức phí của Vai trò</strong> &rarr;
                <strong className="text-foreground"> Mặc định toàn sàn (10%)</strong>.
              </AlertDescription>
            </Alert>
          </SectionCard>
        </TabsContent>

        {/* TAB 2: CREATOR MONETIZATION POLICIES */}
        <TabsContent value="creator-policy" className="space-y-4">
          <SectionCard
            title="Chính sách thu phí tính năng Creator"
            description="Cấu hình hạn mức miễn phí và phí phát hành mã kích hoạt Deck (Deck Access Keys) dành cho các tác giả."
          >
            {creatorPolicyForm && (
              <div className="space-y-6 max-w-2xl">
                <div className="flex items-center justify-between rounded-lg border p-4 shadow-sm">
                  <div className="space-y-0.5">
                    <Label htmlFor="monetize-switch" className="text-base font-semibold cursor-pointer">
                      Bật thu phí phát hành mã kích hoạt
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Nếu tắt, mọi creator đều có thể phát hành mã kích hoạt không giới hạn và hoàn toàn miễn phí.
                    </p>
                  </div>
                  <Switch
                    id="monetize-switch"
                    checked={creatorPolicyForm.is_monetized}
                    onCheckedChange={(checked) =>
                      setCreatorPolicyForm({ ...creatorPolicyForm, is_monetized: checked })
                    }
                  />
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="freeQuotaInput" className="font-semibold text-sm">
                      Hạn mức mã miễn phí mỗi Creator
                    </Label>
                    <Input
                      id="freeQuotaInput"
                      type="number"
                      min="-1"
                      value={creatorPolicyForm.free_quota_per_creator}
                      onChange={(e) =>
                        setCreatorPolicyForm({
                          ...creatorPolicyForm,
                          free_quota_per_creator: parseInt(e.target.value) || 0,
                        })
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Nhập <code>-1</code> nếu không giới hạn số lượng mã miễn phí.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="pricePerKeyInput" className="font-semibold text-sm">
                      Đơn giá mỗi mã vượt hạn mức (VNĐ)
                    </Label>
                    <Input
                      id="pricePerKeyInput"
                      type="number"
                      min="0"
                      step="1000"
                      value={creatorPolicyForm.price_per_key_minor}
                      onChange={(e) =>
                        setCreatorPolicyForm({
                          ...creatorPolicyForm,
                          price_per_key_minor: Math.max(0, parseInt(e.target.value) || 0),
                        })
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Được trừ trực tiếp vào số dư ví của Creator khi phát hành mã vượt hạn mức.
                    </p>
                  </div>
                </div>

                <div className="flex items-center justify-between rounded-lg border p-4 shadow-sm">
                  <div className="space-y-0.5">
                    <Label htmlFor="proRoleSwitch" className="text-base font-semibold cursor-pointer">
                      Yêu cầu tài khoản Creator / Enterprise
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Chỉ người dùng có vai trò Nhà sáng tạo hoặc Doanh nghiệp mới được phép tạo mã kích hoạt.
                    </p>
                  </div>
                  <Switch
                    id="proRoleSwitch"
                    checked={creatorPolicyForm.requires_pro_role}
                    onCheckedChange={(checked) =>
                      setCreatorPolicyForm({ ...creatorPolicyForm, requires_pro_role: checked })
                    }
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <Button
                    onClick={() => updateCreatorPolicyMutation.mutate(creatorPolicyForm)}
                    disabled={updateCreatorPolicyMutation.isPending}
                    className="gap-2"
                  >
                    <CheckCircle2 className="size-4" />
                    {updateCreatorPolicyMutation.isPending ? 'Đang lưu…' : 'Lưu cấu hình Creator'}
                  </Button>
                </div>
              </div>
            )}
          </SectionCard>
        </TabsContent>

        {/* TAB 3: USER CUSTOM OVERRIDES */}
        <TabsContent value="user-overrides" className="space-y-4">
          <SectionCard
            title="Danh sách người dùng có mức phí riêng"
            description="Các tài khoản đối tác hoặc tác giả đặc biệt được áp dụng tỷ lệ chiết khấu sàn tùy chỉnh."
            actions={
              <Button
                onClick={() => {
                  setSelectedUserForOverride(null)
                  setCustomFeeInput('')
                  setUserSearchTerm('')
                  setUserSearchResults([])
                  setUserFeeDialogOpen(true)
                }}
                className="gap-1.5"
                size="sm"
              >
                <Plus className="size-4" />
                Thêm ngoại lệ người dùng
              </Button>
            }
          >
            {/* Filter Bar */}
            <div className="mb-4 flex items-center gap-2 max-w-sm">
              <div className="relative w-full">
                <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
                <Input
                  placeholder="Tìm theo tên, email, vai trò…"
                  value={customUserFilterText}
                  onChange={(e) => setCustomUserFilterText(e.target.value)}
                  className="pl-8"
                />
              </div>
              {customUserFilterText && (
                <Button variant="ghost" size="sm" onClick={() => setCustomUserFilterText('')}>
                  <X className="size-4" />
                </Button>
              )}
            </div>

            {filteredCustomUsers.length === 0 ? (
              <EmptyState
                title="Không có ngoại lệ phí nào"
                description={
                  customUserFilterText
                    ? 'Không tìm thấy người dùng phù hợp với từ khóa tìm kiếm.'
                    : 'Chưa có tài khoản nào được đặt mức phí tùy chỉnh. Tất cả người dùng đều áp dụng theo mức phí mặc định của vai trò.'
                }
              />
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Người dùng</TableHead>
                      <TableHead>Vai trò</TableHead>
                      <TableHead>Phí vai trò</TableHead>
                      <TableHead>Phí tùy chỉnh</TableHead>
                      <TableHead>Số dư ví</TableHead>
                      <TableHead className="text-right">Hành động</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredCustomUsers.map((user, idx) => {
                      const grad = AVATAR_GRADIENTS[idx % AVATAR_GRADIENTS.length]
                      return (
                        <TableRow key={user.id}>
                          <TableCell>
                            <div className="flex items-center gap-3">
                              <div
                                className={`size-8 rounded-full bg-gradient-to-br ${grad} flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-sm`}
                              >
                                {user.username.slice(0, 2).toUpperCase()}
                              </div>
                              <div>
                                <p className="font-semibold text-foreground leading-snug">
                                  {user.username}
                                </p>
                                <p className="text-xs text-muted-foreground">{user.email}</p>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <RoleBadge roleName={user.role_name} isAdmin={user.is_admin} />
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {user.role_default_fee_percent}%
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className="border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300 font-bold"
                            >
                              {user.custom_platform_fee_percent}%
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            {user.balance_amount_display}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <Button
                                variant="outline"
                                size="sm"
                                className="gap-1"
                                onClick={() => {
                                  setSelectedUserForOverride(user)
                                  setCustomFeeInput(String(user.custom_platform_fee_percent ?? ''))
                                  setUserFeeDialogOpen(true)
                                }}
                              >
                                <Edit3 className="size-3.5" />
                                Sửa
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:bg-destructive/10 gap-1"
                                onClick={() => {
                                  if (
                                    window.confirm(
                                      `Xóa ngoại lệ phí của người dùng "${user.username}" và đưa về mức phí vai trò mặc định (${user.role_default_fee_percent}%)?`
                                    )
                                  ) {
                                    updateUserCustomFeeMutation.mutate({
                                      userId: user.id,
                                      customFeePercent: null,
                                    })
                                  }
                                }}
                              >
                                <RotateCcw className="size-3.5" />
                                Xóa ngoại lệ
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </SectionCard>
        </TabsContent>

        {/* TAB 4: REVENUE & COMMISSION SIMULATOR */}
        <TabsContent value="simulator" className="space-y-4">
          <SectionCard
            title="Công cụ mô phỏng phân chia doanh thu & phí sàn"
            description="Xem trước số tiền thực nhận của tác giả và phí sàn Flama giữ lại khi giao dịch phát sinh."
          >
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Input controls */}
              <div className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="simPriceInput" className="font-semibold text-sm">
                    Giá bán học liệu (VNĐ)
                  </Label>
                  <Input
                    id="simPriceInput"
                    type="number"
                    min="0"
                    step="10000"
                    value={simPrice}
                    onChange={(e) => setSimPrice(Math.max(0, parseInt(e.target.value) || 0))}
                  />
                  <div className="flex flex-wrap gap-2 pt-1">
                    {[20000, 50000, 100000, 200000, 500000].map((amount) => (
                      <Button
                        key={amount}
                        type="button"
                        variant={simPrice === amount ? 'default' : 'outline'}
                        size="xs"
                        onClick={() => setSimPrice(amount)}
                      >
                        {amount.toLocaleString('vi-VN')} ₫
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="simFeeInput" className="font-semibold text-sm">
                    Tỷ lệ phí sàn áp dụng (%)
                  </Label>
                  <Input
                    id="simFeeInput"
                    type="number"
                    min="0"
                    max="100"
                    step="0.5"
                    value={simFeePercent}
                    onChange={(e) =>
                      setSimFeePercent(Math.min(100, Math.max(0, parseFloat(e.target.value) || 0)))
                    }
                  />
                  <div className="flex flex-wrap gap-2 pt-1">
                    {[
                      { label: '0% (Admin / Miễn phí)', val: 0 },
                      { label: '5% (Nhà sáng tạo)', val: 5 },
                      { label: '10% (Học viên thường)', val: 10 },
                      { label: '15%', val: 15 },
                    ].map((preset) => (
                      <Button
                        key={preset.val}
                        type="button"
                        variant={simFeePercent === preset.val ? 'default' : 'outline'}
                        size="xs"
                        onClick={() => setSimFeePercent(preset.val)}
                      >
                        {preset.label}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Visual Breakdown Card */}
              <Card className="border-border/60 bg-muted/30">
                <CardHeader>
                  <CardTitle className="text-base font-bold flex items-center gap-2">
                    <Coins className="size-4 text-amber-500" />
                    Kết quả phân chia doanh thu
                  </CardTitle>
                  <CardDescription>
                    Chi tiết phân tách cho 1 giao dịch bán bộ thẻ trị giá {simPrice.toLocaleString('vi-VN')} ₫
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Giá người mua thanh toán (Gross):</span>
                      <span className="font-bold text-foreground">
                        {simPrice.toLocaleString('vi-VN')} ₫
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground flex items-center gap-1.5">
                        <span className="size-2.5 rounded-full bg-rose-500 inline-block" />
                        Phí nền tảng Flama ({simFeePercent}%):
                      </span>
                      <span className="font-bold text-rose-600 dark:text-rose-400">
                        -{simFeeAmount.toLocaleString('vi-VN')} ₫
                      </span>
                    </div>
                    <div className="border-t pt-3 flex items-center justify-between text-base font-bold">
                      <span className="text-foreground flex items-center gap-1.5">
                        <span className="size-2.5 rounded-full bg-emerald-500 inline-block" />
                        Tác giả thực nhận vào ví (Net):
                      </span>
                      <span className="text-emerald-600 dark:text-emerald-400 text-lg">
                        +{simCreatorNet.toLocaleString('vi-VN')} ₫
                      </span>
                    </div>
                  </div>

                  {/* Ratio bar */}
                  <div className="space-y-1.5 pt-2">
                    <div className="h-3 w-full rounded-full overflow-hidden flex bg-muted">
                      <div
                        className="bg-emerald-500 transition-all duration-300"
                        style={{ width: `${100 - simFeePercent}%` }}
                        title={`Tác giả nhận: ${100 - simFeePercent}%`}
                      />
                      <div
                        className="bg-rose-500 transition-all duration-300"
                        style={{ width: `${simFeePercent}%` }}
                        title={`Phí sàn: ${simFeePercent}%`}
                      />
                    </div>
                    <div className="flex justify-between text-[11px] text-muted-foreground px-0.5">
                      <span>Tác giả: {100 - simFeePercent}%</span>
                      <span>Sàn Flama: {simFeePercent}%</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </SectionCard>
        </TabsContent>
      </Tabs>

      {/* DIALOG: EDIT ROLE DEFAULT FEE */}
      <Dialog open={editingRole !== null} onOpenChange={(open) => !open && setEditingRole(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BadgePercent className="size-5 text-amber-500" />
              Thiết lập phí cho vai trò: {editingRole?.name}
            </DialogTitle>
            <DialogDescription>
              Mức phí chiết khấu mặc định áp dụng cho tất cả tài khoản thuộc vai trò{' '}
              <strong className="text-foreground">{editingRole?.name}</strong>.
            </DialogDescription>
          </DialogHeader>

          {editingRole && (
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="roleFeeInput" className="text-xs font-semibold">
                  Tỷ lệ phí nền tảng (%)
                </Label>
                <div className="relative">
                  <Input
                    id="roleFeeInput"
                    type="number"
                    min="0"
                    max="100"
                    step="0.5"
                    value={roleFeeInput}
                    onChange={(e) => setRoleFeeInput(e.target.value)}
                    placeholder="VD: 5"
                    className="pr-8"
                  />
                  <span className="absolute right-3 top-2.5 text-xs text-muted-foreground font-semibold">
                    %
                  </span>
                </div>
              </div>

              {/* Quick Presets */}
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Chọn nhanh mức phí:</Label>
                <div className="flex flex-wrap gap-1.5">
                  {[0, 3, 5, 8, 10, 15, 20].map((preset) => (
                    <Button
                      key={preset}
                      type="button"
                      variant={roleFeeInput === String(preset) ? 'default' : 'outline'}
                      size="xs"
                      onClick={() => setRoleFeeInput(String(preset))}
                    >
                      {preset}%
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setEditingRole(null)}>
              Hủy
            </Button>
            <Button
              onClick={() => {
                if (!editingRole) return
                const val = parseFloat(roleFeeInput)
                if (isNaN(val) || val < 0 || val > 100) {
                  toast.error('Vui lòng nhập tỷ lệ phí hợp lệ từ 0 đến 100%.')
                  return
                }
                updateRoleMutation.mutate({
                  roleId: editingRole.id,
                  feePercent: val,
                })
              }}
              disabled={updateRoleMutation.isPending}
            >
              {updateRoleMutation.isPending ? 'Đang lưu…' : 'Cập nhật mức phí'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* DIALOG: USER CUSTOM FEE OVERRIDE (CREATE OR EDIT) */}
      <Dialog
        open={userFeeDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            setUserFeeDialogOpen(false)
            setSelectedUserForOverride(null)
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BadgePercent className="size-5 text-primary" />
              {selectedUserForOverride
                ? `Cập nhật mức phí cho ${selectedUserForOverride.username}`
                : 'Thiết lập mức phí riêng cho người dùng'}
            </DialogTitle>
            <DialogDescription>
              Gán tỷ lệ phí ưu đãi hoặc mức phí sàn riêng cho từng tác giả cụ thể.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {!selectedUserForOverride ? (
              <div className="space-y-3">
                <Label htmlFor="searchUserField" className="text-xs font-semibold">
                  Tìm kiếm người dùng (theo tên hoặc email)
                </Label>
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
                  <Input
                    id="searchUserField"
                    placeholder="Nhập tên đăng nhập hoặc email…"
                    value={userSearchTerm}
                    onChange={(e) => handleSearchUsers(e.target.value)}
                    className="pl-8"
                  />
                </div>

                {isSearchingUsers && (
                  <p className="text-xs text-muted-foreground">Đang tìm kiếm người dùng…</p>
                )}

                {userSearchResults.length > 0 && (
                  <div className="max-h-48 overflow-y-auto rounded-md border divide-y">
                    {userSearchResults.map((user) => (
                      <button
                        key={user.id}
                        type="button"
                        className="w-full px-3 py-2 text-left hover:bg-muted/50 flex items-center justify-between text-xs transition-colors"
                        onClick={() => {
                          setSelectedUserForOverride(user)
                          setCustomFeeInput(
                            user.custom_platform_fee_percent !== null && user.custom_platform_fee_percent !== undefined
                              ? String(user.custom_platform_fee_percent)
                              : ''
                          )
                        }}
                      >
                        <div>
                          <p className="font-semibold text-foreground">{user.username}</p>
                          <p className="text-muted-foreground">{user.email}</p>
                        </div>
                        <div className="text-right">
                          <RoleBadge roleName={user.role_name} isAdmin={user.is_admin} />
                          <p className="text-muted-foreground mt-0.5">
                            Phí vai trò: {user.role_default_fee_percent}%
                          </p>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="rounded-lg border bg-muted/20 p-3 flex items-center justify-between">
                  <div>
                    <p className="font-bold text-foreground">{selectedUserForOverride.username}</p>
                    <p className="text-xs text-muted-foreground">{selectedUserForOverride.email}</p>
                  </div>
                  <div className="text-right">
                    <RoleBadge
                      roleName={selectedUserForOverride.role_name}
                      isAdmin={selectedUserForOverride.is_admin}
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Mặc định vai trò: {selectedUserForOverride.role_default_fee_percent}%
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="customFeeInput" className="text-xs font-semibold">
                    Mức phí tùy chỉnh (%)
                  </Label>
                  <div className="relative">
                    <Input
                      id="customFeeInput"
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      placeholder="VD: 5"
                      value={customFeeInput}
                      onChange={(e) => setCustomFeeInput(e.target.value)}
                      className="pr-8"
                    />
                    <span className="absolute right-3 top-2.5 text-xs text-muted-foreground font-semibold">
                      %
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Để trống hoặc bấm &quot;Dùng mặc định vai trò&quot; để xóa ngoại lệ.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">Mức phí gợi ý:</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {[0, 2, 5, 7, 10].map((val) => (
                      <Button
                        key={val}
                        type="button"
                        variant={customFeeInput === String(val) ? 'default' : 'outline'}
                        size="xs"
                        onClick={() => setCustomFeeInput(String(val))}
                      >
                        {val}%
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="flex-col sm:flex-row gap-2 sm:justify-between">
            {selectedUserForOverride && (
              <Button
                type="button"
                variant="ghost"
                className="text-muted-foreground hover:text-foreground"
                onClick={() => {
                  setSelectedUserForOverride(null)
                  setCustomFeeInput('')
                }}
              >
                Chọn user khác
              </Button>
            )}
            <div className="flex gap-2 justify-end w-full sm:w-auto">
              <Button variant="outline" onClick={() => setUserFeeDialogOpen(false)}>
                Hủy
              </Button>
              {selectedUserForOverride && (
                <Button
                  onClick={() => {
                    const raw = customFeeInput.trim()
                    const val = raw ? parseFloat(raw) : null
                    if (val !== null && (isNaN(val) || val < 0 || val > 100)) {
                      toast.error('Vui lòng nhập tỷ lệ phí từ 0 đến 100% hoặc để trống.')
                      return
                    }
                    updateUserCustomFeeMutation.mutate({
                      userId: selectedUserForOverride.id,
                      customFeePercent: val,
                    })
                  }}
                  disabled={updateUserCustomFeeMutation.isPending}
                >
                  {updateUserCustomFeeMutation.isPending ? 'Đang lưu…' : 'Lưu mức phí'}
                </Button>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  )
}
