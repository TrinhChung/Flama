import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  CalendarCheck,
  Flame,
  Gauge,
  Layers,
} from 'lucide-react'
import { appApi } from '@/app/api'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { StudyHeatmap } from '@/shared/components/StudyHeatmap'
import { Page, PageHeader, SectionCard } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useStatisticsConfig, useTodayFutureStats } from '../api'
import { FutureDueChart } from '../components/FutureDueChart'
import type { StatisticsFilters } from '../types'

function ChoiceTabs<T extends string>({
  value,
  items,
  onChange,
}: {
  value: T
  items: Array<{ label: string; value: T }>
  onChange: (value: T) => void
}) {
  return (
    <Tabs value={value} onValueChange={(next) => onChange(next as T)}>
      <TabsList className="w-full">
        {items.map((item) => (
          <TabsTrigger className="flex-1 text-xs font-medium" value={item.value} key={item.value}>
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}

export function StatisticsPage() {
  const configQuery = useStatisticsConfig()
  const [currentYear, setCurrentYear] = useState<number>(new Date().getFullYear())
  const [filters, setFilters] = useState<StatisticsFilters>({
    scope: 'deck',
    deckId: null,
    historyRange: '12m',
    futureRange: '30',
    backlog: true,
  })

  useEffect(() => {
    if (configQuery.data && filters.deckId === null) {
      setFilters((current) => ({ ...current, deckId: configQuery.data.initial_deck_id }))
    }
  }, [configQuery.data, filters.deckId])

  const statsQuery = useTodayFutureStats(filters)
  const overviewQuery = useQuery({
    queryKey: ['frontend', 'statistics', 'overview', currentYear],
    queryFn: () => appApi.getDashboardOverview(currentYear),
  })

  if (configQuery.isPending) return <PageLoading label="Đang tải cấu hình thống kê…" />
  if (configQuery.error) return <Page><PageError error={configQuery.error} /></Page>

  const stats = statsQuery.data
  const overview = overviewQuery.data

  return (
    <Page>
      <PageHeader
        title="Thống kê học tập"
        description="Theo dõi hiệu suất ghi nhớ, chuỗi ngày học và dự báo lịch ôn tập flashcard."
      />

      {/* Filter Toolbar Card */}
      <Card className="shadow-xs border-border/80 bg-card">
        <CardContent className="grid gap-5 p-4 md:grid-cols-3 md:p-5">
          <div className="space-y-2">
            <Label className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
              <Layers className="size-3.5 text-orange-500" /> Phạm vi
            </Label>
            <ChoiceTabs
              value={filters.scope}
              items={[{ label: 'Theo deck', value: 'deck' }, { label: 'Toàn collection', value: 'collection' }]}
              onChange={(scope) => setFilters((current) => ({ ...current, scope }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="statistics-deck" className="text-xs font-semibold text-muted-foreground">
              Bộ thẻ (Deck)
            </Label>
            <NativeSelect
              id="statistics-deck"
              className="w-full h-9 text-sm"
              disabled={filters.scope === 'collection'}
              value={filters.deckId === null ? '' : String(filters.deckId)}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  deckId: event.currentTarget.value ? Number(event.currentTarget.value) : null,
                }))
              }
            >
              <NativeSelectOption value="">Chọn deck</NativeSelectOption>
              {configQuery.data.decks.map((deck) => (
                <NativeSelectOption key={deck.id} value={String(deck.id)}>
                  {deck.id}: {deck.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-semibold text-muted-foreground">Lịch sử thống kê</Label>
            <ChoiceTabs
              value={filters.historyRange}
              items={[{ label: '12 tháng', value: '12m' }, { label: 'Tất cả', value: 'all' }]}
              onChange={(historyRange) => setFilters((current) => ({ ...current, historyRange }))}
            />
          </div>
        </CardContent>
      </Card>

      {statsQuery.error ? <PageError error={statsQuery.error} /> : null}
      {statsQuery.isFetching && !stats ? <PageLoading label="Đang tính toán số liệu thống kê…" /> : null}

      {stats ? (
        <>
          {/* KPI Stat Cards Grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Card 1: Today */}
            <div className="relative overflow-hidden rounded-xl border border-border bg-card p-4 shadow-xs transition-all hover:shadow-md">
              <div className="absolute top-0 left-0 h-full w-1 bg-gradient-to-b from-orange-500 to-amber-500" />
              <div className="flex items-start gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 dark:bg-orange-500/20">
                  <Flame className="size-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Hôm nay</span>
                  <div className="mt-0.5 text-2xl font-bold tracking-tight text-foreground tabular-nums">
                    {stats.today.cards.toLocaleString('vi-VN')} <span className="text-xs font-medium text-muted-foreground">thẻ</span>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground tabular-nums">
                    {stats.today.minutes.toFixed(1)} phút ({stats.today.sec_per_card.toFixed(2)}s/thẻ)
                  </p>
                </div>
              </div>
            </div>

            {/* Card 2: Streak */}
            <div className="relative overflow-hidden rounded-xl border border-border bg-card p-4 shadow-xs transition-all hover:shadow-md">
              <div className="absolute top-0 left-0 h-full w-1 bg-gradient-to-b from-emerald-500 to-teal-500" />
              <div className="flex items-start gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20">
                  <CalendarCheck className="size-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Chuỗi Streak</span>
                  <div className="mt-0.5 text-2xl font-bold tracking-tight text-foreground tabular-nums">
                    {(overview?.metrics?.current_streak_days ?? 0).toLocaleString('vi-VN')}{' '}
                    <span className="text-xs font-medium text-muted-foreground">ngày</span>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground tabular-nums">
                    Kỷ lục: {overview?.metrics?.longest_streak_days ?? 0}d · Học {overview?.metrics?.days_learned_percent ?? 0}% ngày
                  </p>
                </div>
              </div>
            </div>

            {/* Card 3: Forecast */}
            <div className="relative overflow-hidden rounded-xl border border-border bg-card p-4 shadow-xs transition-all hover:shadow-md">
              <div className="absolute top-0 left-0 h-full w-1 bg-gradient-to-b from-sky-500 to-blue-500" />
              <div className="flex items-start gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-sky-500/10 text-sky-600 dark:bg-sky-500/20">
                  <BarChart3 className="size-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Dự báo lượt ôn</span>
                  <div className="mt-0.5 text-2xl font-bold tracking-tight text-foreground tabular-nums">
                    {stats.totals.total_reviews.toLocaleString('vi-VN')}{' '}
                    <span className="text-xs font-medium text-muted-foreground">lượt</span>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground tabular-nums">
                    Ngày mai: {stats.totals.due_tomorrow} · TB: {stats.totals.avg_reviews_per_day.toFixed(1)}/ngày
                  </p>
                </div>
              </div>
            </div>

            {/* Card 4: Daily Workload */}
            <div className="relative overflow-hidden rounded-xl border border-border bg-card p-4 shadow-xs transition-all hover:shadow-md">
              <div className="absolute top-0 left-0 h-full w-1 bg-gradient-to-b from-teal-500 to-emerald-600" />
              <div className="flex items-start gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-teal-600 dark:bg-teal-500/20">
                  <Gauge className="size-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Tải lượng học tập</span>
                  <div className="mt-0.5 text-2xl font-bold tracking-tight text-foreground tabular-nums">
                    {stats.totals.daily_load.toFixed(1)}{' '}
                    <span className="text-xs font-medium text-muted-foreground">bài/ngày</span>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">Mức tải ước tính duy trì ghi nhớ</p>
                </div>
              </div>
            </div>
          </div>

          {/* Yearly Heatmap Component */}
          <StudyHeatmap
            overview={overview}
            loading={overviewQuery.isPending}
            year={currentYear}
            onYearChange={(newYear) => setCurrentYear(newYear)}
          />

          {/* Future Due Chart Section */}
          <SectionCard
            title="Dự báo thẻ đến hạn trong tương lai"
            description="Phân bố số lượng bài ôn tập và tổng tích lũy theo từng ngày."
            actions={
              <div className="flex items-center gap-2">
                <Switch
                  id="backlog"
                  checked={filters.backlog}
                  onCheckedChange={(backlog) => setFilters((current) => ({ ...current, backlog }))}
                />
                <Label htmlFor="backlog" className="cursor-pointer text-xs font-medium whitespace-nowrap">
                  Thẻ quá hạn (Backlog)
                </Label>
              </div>
            }
          >
            <div className="space-y-5">
              <ChoiceTabs
                value={filters.futureRange}
                items={[
                  { label: '30 ngày', value: '30' },
                  { label: '90 ngày', value: '90' },
                  { label: '1 năm', value: '365' },
                  { label: 'Tất cả', value: 'all' },
                ]}
                onChange={(futureRange) => setFilters((current) => ({ ...current, futureRange }))}
              />
              <FutureDueChart series={stats.future_due.series} />
              <p className="text-right text-xs text-muted-foreground">Múi giờ hệ thống: {stats.timezone}</p>
            </div>
          </SectionCard>
        </>
      ) : null}
    </Page>
  )
}
