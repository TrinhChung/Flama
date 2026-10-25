import { useState } from 'react'
import { BarChart3, Gauge, Info, Plus, ShieldCheck, Users } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader, SectionCard, StatCard } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useQuotaOverview } from '../api/quotasApi'
import { QuotaOverridesTable } from '../components/quotas/QuotaOverridesTable'
import { QuotaPolicyCard } from '../components/quotas/QuotaPolicyCard'
import { QuotaUsagePanel } from '../components/quotas/QuotaUsagePanel'
import { QuotaUserDialog } from '../components/quotas/QuotaUserDialog'
import {
  QUOTA_KIND_META,
  QUOTA_PERIODS,
  QUOTA_STATS_PERIOD_LABELS,
  formatQuotaAmount,
} from '../components/quotas/quotaFormat'
import type { QuotaPeriod } from '../types/quotas'

export function AdminQuotasPage() {
  const [statsPeriod, setStatsPeriod] = useState<QuotaPeriod>('day')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogUserId, setDialogUserId] = useState<number | null>(null)
  const query = useQuotaOverview(statsPeriod)

  const openUser = (userId: number | null) => {
    setDialogUserId(userId)
    setDialogOpen(true)
  }

  if (query.isPending) return <PageLoading label="Đang tải cấu hình quota…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  const { settings, roles, policies, usage, overrides } = query.data
  const enforcedCount = policies.filter((policy) => policy.enforce).length
  const activeOverrides = overrides.filter((row) => row.is_active).length

  return (
    <Page size="wide">
      <div className="space-y-3">
        <Badge variant="destructive" className="gap-1 font-semibold">
          <ShieldCheck className="size-3.5" /> Admin
        </Badge>
        <PageHeader
          title="Quota sử dụng"
          description="Hạn mức API (Flama Connect), MCP và upload ảnh/audio theo vai trò hoặc riêng từng người dùng. Học thẻ và mọi thao tác trên web không bị tính quota."
          actions={
            <Button className="gap-1.5" onClick={() => openUser(null)}>
              <Plus className="size-4" /> Thêm quota riêng
            </Button>
          }
        />
      </div>

      {!settings.metering_enabled && (
        <Alert variant="destructive">
          <Info className="size-4" />
          <AlertTitle>Đang tắt đếm quota</AlertTitle>
          <AlertDescription>
            RATE_LIMIT_DAILY_ENABLED=false: không đếm và không chặn gì. Các thống kê bên dưới sẽ không thay đổi.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          tone={enforcedCount === 0 ? 'success' : 'warning'}
          label="Chế độ"
          value={enforcedCount === 0 ? 'Chỉ theo dõi' : `Chặn ${enforcedCount}/${policies.length} loại`}
          hint={enforcedCount === 0 ? 'Đang đếm để thu thập dữ liệu, chưa chặn ai' : 'Có loại quota đang chặn khi vượt'}
        />
        {policies.map((policy) => (
          <StatCard
            key={policy.kind}
            label={`${QUOTA_KIND_META[policy.kind].label} · ${QUOTA_STATS_PERIOD_LABELS[statsPeriod].toLowerCase()}`}
            value={formatQuotaAmount(usage[policy.kind].total, policy.unit)}
            hint={`${usage[policy.kind].over.length}${usage[policy.kind].over.length >= 10 ? '+' : ''} người vượt hạn mức`}
          />
        ))}
      </div>

      <Tabs defaultValue="policies" className="w-full space-y-6">
        <TabsList className="grid w-full grid-cols-3 md:inline-flex md:w-auto md:grid-cols-none">
          <TabsTrigger value="policies" className="gap-2">
            <Gauge className="size-4" />
            <span className="truncate">Chính sách</span>
          </TabsTrigger>
          <TabsTrigger value="usage" className="gap-2">
            <BarChart3 className="size-4" />
            <span className="truncate">Thống kê</span>
          </TabsTrigger>
          <TabsTrigger value="overrides" className="gap-2">
            <Users className="size-4" />
            <span className="truncate">Quota riêng ({activeOverrides})</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="policies" className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
            {policies.map((policy) => (
              <QuotaPolicyCard key={policy.kind} policy={policy} roles={roles} />
            ))}
          </div>
          <Alert className="border-sky-500/20 bg-sky-500/5 text-sky-900 dark:text-sky-200">
            <Info className="size-4 text-sky-600 dark:text-sky-400" />
            <AlertTitle className="font-semibold">Thứ tự áp dụng hạn mức</AlertTitle>
            <AlertDescription className="mt-1 text-xs leading-relaxed text-muted-foreground">
              <strong className="text-foreground">Quota riêng</strong> còn hạn &rarr;{' '}
              <strong className="text-foreground">Hạn mức của vai trò</strong>. Admin luôn không giới hạn. Thay đổi có
              hiệu lực trên mọi worker trong khoảng {settings.cache_ttl_seconds} giây. Mốc ngày/tháng/năm theo múi giờ{' '}
              {settings.timezone}.
            </AlertDescription>
          </Alert>
        </TabsContent>

        <TabsContent value="usage" className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              Bộ đếm: {settings.backend === 'redis' ? 'Redis (dùng chung mọi worker)' : 'bộ nhớ tiến trình (chỉ dev)'}.
              Lịch sử giữ khoảng 400 ngày.
            </p>
            <NativeSelect
              value={statsPeriod}
              onChange={(event) => setStatsPeriod(event.target.value as QuotaPeriod)}
              className="h-9 sm:w-40"
              aria-label="Kỳ thống kê"
            >
              {QUOTA_PERIODS.map((period) => (
                <NativeSelectOption key={period} value={period}>
                  {QUOTA_STATS_PERIOD_LABELS[period]}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <div className="grid grid-cols-1 gap-4 2xl:grid-cols-3">
            {policies.map((policy) => (
              <QuotaUsagePanel
                key={policy.kind}
                policy={policy}
                usage={usage[policy.kind]}
                onSelectUser={(userId) => openUser(userId)}
              />
            ))}
          </div>
        </TabsContent>

        <TabsContent value="overrides" className="space-y-4">
          <SectionCard
            title="Quota riêng theo người dùng"
            description="Hạn mức cấp riêng cho từng người, ưu tiên hơn mặc định của vai trò cho tới ngày hết hạn."
            actions={
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => openUser(null)}>
                <Plus className="size-3.5" /> Thêm quota riêng
              </Button>
            }
          >
            <QuotaOverridesTable overrides={overrides} onEditUser={(userId) => openUser(userId)} />
          </SectionCard>
        </TabsContent>
      </Tabs>

      <QuotaUserDialog
        open={dialogOpen}
        userId={dialogUserId}
        onOpenChange={setDialogOpen}
        onSelectUser={setDialogUserId}
      />
    </Page>
  )
}
