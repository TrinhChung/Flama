import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
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
  email: string
  status: 'active' | 'disabled'
  is_disabled: boolean
  role_id: number | null
  role_name: string | null
}

type AdminRole = {
  id: number
  name: string
}

type AdminUsersResponse = {
  items: AdminUser[]
  roles: AdminRole[]
  total: number
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

function AdminHeader({
  title,
  description,
}: {
  title: string
  description?: string
}) {
  return (
    <div className="space-y-3">
      <Badge variant="destructive">Admin</Badge>
      <PageHeader title={title} description={description} />
    </div>
  )
}

export function AdminUsersPage() {
  const queryClient = useQueryClient()
  const [searchText, setSearchText] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [status, setStatus] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(searchText.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [searchText])

  const queryKey = ['admin', 'users', debouncedSearch, status] as const
  const query = useQuery({
    queryKey,
    queryFn: () =>
      appApi.get<AdminUsersResponse>('/admin/users', {
        q: debouncedSearch,
        status,
        per_page: 50,
      }),
  })
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
      toast.success('Đã cập nhật người dùng.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  if (query.isPending) return <PageLoading label="Đang tải người dùng…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page>
      <AdminHeader title="Người dùng & phân quyền" />
      <Card>
        <CardContent className="grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_220px]">
          <div className="relative">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-8"
              placeholder="Tìm email hoặc username…"
              value={searchText}
              onChange={(event) => setSearchText(event.currentTarget.value)}
            />
          </div>
          <NativeSelect
            className="w-full"
            value={status}
            onChange={(event) => setStatus(event.currentTarget.value)}
          >
            <NativeSelectOption value="">Tất cả trạng thái</NativeSelectOption>
            <NativeSelectOption value="active">Active</NativeSelectOption>
            <NativeSelectOption value="disabled">Disabled</NativeSelectOption>
          </NativeSelect>
        </CardContent>
      </Card>
      {!query.data.items.length ? (
        <EmptyState title="Không có người dùng" description="Không có kết quả phù hợp với bộ lọc." />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <Table className="min-w-180">
              <TableHeader>
                <TableRow>
                  <TableHead>Người dùng</TableHead>
                  <TableHead>Vai trò</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <p className="font-medium">{user.username}</p>
                      <p className="text-sm text-muted-foreground">{user.email}</p>
                    </TableCell>
                    <TableCell>
                      <NativeSelect
                        value={user.role_id === null ? '' : String(user.role_id)}
                        className="w-48"
                        disabled={mutation.isPending}
                        onChange={(event) =>
                          mutation.mutate({
                            userId: user.id,
                            payload: { role_id: Number(event.currentTarget.value) },
                          })
                        }
                      >
                        <NativeSelectOption value="" disabled>Chưa gán</NativeSelectOption>
                        {query.data.roles.map((role) => (
                          <NativeSelectOption key={role.id} value={String(role.id)}>
                            {role.name}
                          </NativeSelectOption>
                        ))}
                      </NativeSelect>
                    </TableCell>
                    <TableCell>
                      <Badge variant={user.is_disabled ? 'outline' : 'secondary'}>
                        {user.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant={user.is_disabled ? 'outline' : 'destructive'}
                        disabled={mutation.isPending}
                        onClick={() =>
                          mutation.mutate({
                            userId: user.id,
                            payload: { is_disabled: !user.is_disabled },
                          })
                        }
                      >
                        {user.is_disabled ? 'Kích hoạt' : 'Vô hiệu hóa'}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}
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
