import { useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ShieldCheck,
  ShieldUser,
  Users,
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
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

type AdminUser = {
  id: number
  username: string
  email: string
  is_disabled: boolean
  is_admin: boolean
  role_id: number | null
  role_name: string | null
}

type AdminRole = {
  id: number
  name: string
  is_admin?: boolean
}

type AdminUsersResponse = {
  items: AdminUser[]
  roles: AdminRole[]
}

type BatchResultItem = {
  user_id: number
  username?: string
  email?: string
  status: 'success' | 'fail'
  message?: string
}

type BatchResponse = {
  success_count: number
  fail_count: number
  results?: BatchResultItem[]
}

export function AdminPermissionsPage() {
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const initialSelectedCsv = searchParams.get('selected_ids') || ''
  const initialIds = initialSelectedCsv
    ? initialSelectedCsv
        .split(',')
        .map((id) => Number(id.trim()))
        .filter((id) => Number.isInteger(id) && id > 0)
    : []

  const [selectedUserIds, setSelectedUserIds] = useState<number[]>(initialIds)
  const [targetRoleId, setTargetRoleId] = useState<string>('')
  const [batchResponse, setBatchResponse] = useState<BatchResponse | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  const usersQuery = useQuery({
    queryKey: ['admin', 'users-all-for-permissions'],
    queryFn: () => appApi.get<AdminUsersResponse>('/admin/users', { per_page: 100 }),
  })

  const batchMutation = useMutation({
    mutationFn: (payload: { user_ids: number[]; target_role_id: number; mode: 'replace' }) =>
      appApi.mutate<BatchResponse>('/admin/users/roles/batch', 'POST', payload),
    onSuccess: async (data) => {
      setBatchResponse(data)
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      toast.success(`Đã áp dụng vai trò mới thành công cho ${data.success_count} người dùng.`)
    },
    onError: (error: Error) => {
      setValidationError(error.message)
      toast.error(error.message)
    },
  })

  if (usersQuery.isPending) return <PageLoading label="Đang tải danh sách người dùng và vai trò…" />
  if (usersQuery.error) return <Page><PageError error={usersQuery.error} /></Page>

  const allUsers = usersQuery.data.items || []
  const roles = usersQuery.data.roles || []
  const selectedUsers = allUsers.filter((u) => selectedUserIds.includes(u.id))

  const handleRemoveUser = (id: number) => {
    setSelectedUserIds((prev) => prev.filter((item) => item !== id))
    setValidationError(null)
  }

  const handleApply = () => {
    setValidationError(null)
    if (!targetRoleId) {
      setValidationError('Vui lòng chọn Vai trò mới trước khi áp dụng.')
      return
    }
    if (!selectedUserIds.length) {
      setValidationError('Danh sách người dùng được chọn hiện đang trống.')
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
      <div className="space-y-3">
        <Badge variant="outline" className="gap-1 font-bold border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400">
          <ShieldCheck className="size-3.5" /> Admin
        </Badge>
        <PageHeader
          title="Phân quyền Người dùng Hàng loạt"
          description="Thực hiện gán vai trò và cập nhật quyền hạn cho nhóm thành viên đã chọn."
          actions={
            <Button variant="outline" asChild>
              <Link to="/admin/users">
                <ArrowLeft className="mr-1.5 size-4" /> Quay lại Quản lý User
              </Link>
            </Button>
          }
        />
      </div>

      {validationError && (
        <Alert variant="destructive">
          <AlertTriangle className="size-4" />
          <AlertTitle>Lỗi xác thực</AlertTitle>
          <AlertDescription>{validationError}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Selected Users Table */}
        <Card className="lg:col-span-7 shadow-xs">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Users className="size-4 text-primary" /> Danh sách người dùng được chọn
                </CardTitle>
                <CardDescription>
                  Tổng số: <strong>{selectedUserIds.length}</strong> user
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {!selectedUserIds.length ? (
              <div className="p-6 text-center text-sm text-muted-foreground">
                Chưa chọn người dùng nào để gán quyền. Vui lòng quay lại danh sách User và tích chọn.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/40">
                      <TableHead>Username</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Trạng thái</TableHead>
                      <TableHead className="text-right">Thao tác</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {selectedUsers.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell className="font-semibold">{user.username}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">{user.email || '—'}</TableCell>
                        <TableCell>
                          <Badge variant={user.is_disabled ? 'destructive' : 'default'} className="text-[10px]">
                            {user.is_disabled ? 'Disabled' : 'Active'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                            onClick={() => handleRemoveUser(user.id)}
                          >
                            Xóa
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Assignment Form */}
        <Card className="lg:col-span-5 shadow-xs">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <ShieldUser className="size-4 text-primary" /> Form gán vai trò
            </CardTitle>
            <CardDescription>Flama áp dụng mô hình 1 User = 1 Role chính.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="target-role-select">Vai trò mới (Target Role)</Label>
              <NativeSelect
                id="target-role-select"
                value={targetRoleId}
                onChange={(e) => setTargetRoleId(e.target.value)}
              >
                <NativeSelectOption value="">-- Chọn Vai trò --</NativeSelectOption>
                {roles.map((r) => (
                  <NativeSelectOption key={r.id} value={String(r.id)}>
                    {r.name} {r.is_admin ? '(Admin)' : ''}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>

            <div className="space-y-2">
              <Label>Chế độ gán quyền (Mode)</Label>
              <Input value="Replace role (Thay thế vai trò)" disabled readOnly />
            </div>

            <Button
              className="w-full gap-2"
              disabled={!selectedUserIds.length || !targetRoleId || batchMutation.isPending}
              onClick={handleApply}
            >
              <ShieldUser className="size-4" /> Áp dụng quyền hàng loạt
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Batch Application Results */}
      {batchResponse && (
        <Card className="shadow-xs border-emerald-500/30 bg-emerald-50/20 dark:bg-emerald-950/10">
          <CardHeader>
            <CardTitle className="text-base text-emerald-800 dark:text-emerald-300">
              Kết quả Áp dụng Vai trò
            </CardTitle>
            <CardDescription>
              Thành công: <strong>{batchResponse.success_count}</strong> | Thất bại:{' '}
              <strong>{batchResponse.fail_count}</strong>
            </CardDescription>
          </CardHeader>
          <CardContent>
            {batchResponse.results && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User ID</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead>Thông báo</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {batchResponse.results.map((res, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="font-semibold">#{res.user_id}</TableCell>
                      <TableCell>
                        {res.status === 'success' ? (
                          <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600">
                            <CheckCircle2 className="size-4" /> Thành công
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600">
                            <XCircle className="size-4" /> Thất bại
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{res.message || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </Page>
  )
}
