import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { StudyHeatmap } from '@/shared/components/StudyHeatmap'
import { Page, PageHeader, SectionCard } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useStatisticsConfig, useTodayFutureStats, useUserStudyTimeStats } from '../api'
import { FutureDueChart } from '../components/FutureDueChart'
import { UserStudyTimeChart } from '../components/UserStudyTimeChart'
import type { StatisticsFilters, UserStudyTimePreset } from '../types'

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
      <TabsList className="w-full h-9">
        {items.map((item) => (
          <TabsTrigger className="flex-1 text-xs font-medium min-h-[30px]" value={item.value} key={item.value}>
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}

export function StatisticsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const configQuery = useStatisticsConfig()
  const [currentYear, setCurrentYear] = useState<number>(new Date().getFullYear())

  const urlDeckIdParam = searchParams.get('deck_id')
  const urlScopeParam = searchParams.get('scope')

  const [filters, setFilters] = useState<StatisticsFilters>(() => ({
    scope: urlScopeParam === 'collection' ? 'collection' : 'deck',
    deckId: urlDeckIdParam ? Number(urlDeckIdParam) : null,
    historyRange: '12m',
    futureRange: '30',
    backlog: true,
  }))

  const [studyTimeRange, setStudyTimeRange] = useState<UserStudyTimePreset>('30d')

  useEffect(() => {
    if (configQuery.data && filters.deckId === null && filters.scope === 'deck') {
      const fallbackDeckId = urlDeckIdParam ? Number(urlDeckIdParam) : configQuery.data.initial_deck_id
      setFilters((current) => ({ ...current, deckId: fallbackDeckId }))
    }
  }, [configQuery.data, filters.deckId, filters.scope, urlDeckIdParam])

  const updateFiltersAndUrl = useCallback(
    (updater: (prev: StatisticsFilters) => StatisticsFilters) => {
      setFilters((prev) => {
        const next = updater(prev)
        const nextParams = new URLSearchParams(searchParams)
        if (next.scope === 'collection') {
          nextParams.set('scope', 'collection')
          nextParams.delete('deck_id')
        } else {
          nextParams.delete('scope')
          if (next.deckId) {
            nextParams.set('deck_id', String(next.deckId))
          } else {
            nextParams.delete('deck_id')
          }
        }
        setSearchParams(nextParams, { replace: true })
        return next
      })
    },
    [searchParams, setSearchParams],
  )

  const statsQuery = useTodayFutureStats(filters)
  const studyTimeQuery = useUserStudyTimeStats({
    scope: filters.scope,
    deckId: filters.deckId,
    range: studyTimeRange,
  })
  const overviewQuery = useQuery({
    queryKey: ['frontend', 'statistics', 'overview', currentYear],
    queryFn: () => appApi.getDashboardOverview(currentYear),
  })

  if (configQuery.isPending) return <PageLoading label="Đang tải cấu hình thống kê…" />
  if (configQuery.error) return <Page><PageError error={configQuery.error} /></Page>

  const stats = statsQuery.data
  const overview = overviewQuery.data

  return (
    <Page className="space-y-4 sm:space-y-6">
      <PageHeader
        title="Thống kê học tập"
        description="Theo dõi hiệu suất ghi nhớ, chuỗi ngày học và dự báo lịch ôn tập flashcard."
      />

      {/* Filter Toolbar Card */}
      <Card className="shadow-xs border-border/80 bg-card">
        <CardContent className="grid gap-3.5 p-3.5 sm:gap-4 sm:p-5 sm:grid-cols-2 md:grid-cols-3">
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-muted-foreground">
              Phạm vi
            </Label>
            <ChoiceTabs
              value={filters.scope}
              items={[{ label: 'Theo deck', value: 'deck' }, { label: 'Toàn bộ', value: 'collection' }]}
              onChange={(scope) => updateFiltersAndUrl((current) => ({ ...current, scope }))}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="statistics-deck" className="text-xs font-semibold text-muted-foreground">
              Bộ thẻ
            </Label>
            <div className="flex items-center gap-2">
              <NativeSelect
                id="statistics-deck"
                className={cn(
                  "flex-1 h-9 text-xs sm:text-sm",
                  filters.scope === 'collection' && "opacity-60 cursor-not-allowed"
                )}
                disabled={filters.scope === 'collection'}
                value={filters.scope === 'collection' ? '' : (filters.deckId === null ? '' : String(filters.deckId))}
                onChange={(event) => {
                  const nextId = event.currentTarget.value ? Number(event.currentTarget.value) : null
                  updateFiltersAndUrl((current) => ({ ...current, deckId: nextId }))
                }}
              >
                {filters.scope === 'collection' ? (
                  <NativeSelectOption value="">Toàn bộ collection</NativeSelectOption>
                ) : (
                  <>
                    <NativeSelectOption value="">Chọn deck</NativeSelectOption>
                    {configQuery.data.decks.map((deck) => (
                      <NativeSelectOption key={deck.id} value={String(deck.id)}>
                        {deck.name}
                      </NativeSelectOption>
                    ))}
                  </>
                )}
              </NativeSelect>

              {filters.scope === 'deck' && filters.deckId ? (
                <Button
                  asChild
                  size="sm"
                  className="h-9 shrink-0 px-3 text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground shadow-xs"
                >
                  <Link to={`/study?deck_id=${filters.deckId}`}>
                    Ôn tập →
                  </Link>
                </Button>
              ) : filters.scope === 'collection' ? (
                <Button
                  asChild
                  size="sm"
                  variant="outline"
                  className="h-9 shrink-0 px-3 text-xs font-semibold hover:border-primary/50 hover:text-primary"
                >
                  <Link to="/study">
                    Ôn tập →
                  </Link>
                </Button>
              ) : null}
            </div>
          </div>

          <div className="space-y-1.5 sm:col-span-2 md:col-span-1">
            <Label className="text-xs font-semibold text-muted-foreground">
              Lịch sử
            </Label>
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
          {/* KPI Stat Cards Grid - 2 columns on mobile, 4 columns on desktop */}
          <div className={cn(
            "grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3.5 transition-opacity duration-200",
            statsQuery.isFetching && "opacity-80"
          )}>
            {/* Card 1: Today */}
            <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border/70 bg-card p-3.5 sm:p-4 shadow-[0_1px_3px_rgba(0,0,0,0.03)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.2)] hover:border-primary/30 hover:shadow-md transition-all duration-200 active:scale-[0.99]">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-[1.5px] bg-gradient-to-r from-transparent via-primary/25 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div>
                <div className="flex items-center justify-between gap-1.5">
                  <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 truncate">
                    Hôm nay
                  </span>
                  <span className="inline-flex shrink-0 items-center rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary tabular-nums">
                    {stats.today.minutes.toFixed(1)} phút
                  </span>
                </div>
                <div className="mt-2 sm:mt-2.5">
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground tabular-nums">
                      {stats.today.cards.toLocaleString('vi-VN')}
                    </span>
                    <span className="text-xs font-medium text-muted-foreground">thẻ</span>
                  </div>
                </div>
              </div>
              <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
                <span>Tốc độ</span>
                <span className="font-medium text-foreground/80">{stats.today.sec_per_card.toFixed(1)}s / thẻ</span>
              </div>
            </div>

            {/* Card 2: Streak */}
            <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border/70 bg-card p-3.5 sm:p-4 shadow-[0_1px_3px_rgba(0,0,0,0.03)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.2)] hover:border-amber-500/30 hover:shadow-md transition-all duration-200 active:scale-[0.99]">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-[1.5px] bg-gradient-to-r from-transparent via-amber-500/25 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div>
                <div className="flex items-center justify-between gap-1.5">
                  <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 truncate">
                    Chuỗi Streak
                  </span>
                  <span className="inline-flex shrink-0 items-center rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-400 tabular-nums">
                    {overview?.metrics?.days_learned_percent ?? 0}% ngày
                  </span>
                </div>
                <div className="mt-2 sm:mt-2.5">
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground tabular-nums">
                      {(overview?.metrics?.current_streak_days ?? 0).toLocaleString('vi-VN')}
                    </span>
                    <span className="text-xs font-medium text-muted-foreground">ngày</span>
                  </div>
                </div>
              </div>
              <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
                <span>Kỷ lục dài nhất</span>
                <span className="font-medium text-foreground/80">{overview?.metrics?.longest_streak_days ?? 0} ngày</span>
              </div>
            </div>

            {/* Card 3: Forecast */}
            <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border/70 bg-card p-3.5 sm:p-4 shadow-[0_1px_3px_rgba(0,0,0,0.03)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.2)] hover:border-blue-500/30 hover:shadow-md transition-all duration-200 active:scale-[0.99]">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-[1.5px] bg-gradient-to-r from-transparent via-blue-500/25 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div>
                <div className="flex items-center justify-between gap-1.5">
                  <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 truncate">
                    Dự báo lượt ôn
                  </span>
                  <span className="inline-flex shrink-0 items-center rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold text-blue-700 dark:bg-blue-500/15 dark:text-blue-300 tabular-nums">
                    Mai: {stats.totals.due_tomorrow}
                  </span>
                </div>
                <div className="mt-2 sm:mt-2.5">
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground tabular-nums">
                      {stats.totals.total_reviews.toLocaleString('vi-VN')}
                    </span>
                    <span className="text-xs font-medium text-muted-foreground">lượt</span>
                  </div>
                </div>
              </div>
              <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
                <span>Trung bình</span>
                <span className="font-medium text-foreground/80">{stats.totals.avg_reviews_per_day.toFixed(1)} / ngày</span>
              </div>
            </div>

            {/* Card 4: Daily Workload */}
            <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border/70 bg-card p-3.5 sm:p-4 shadow-[0_1px_3px_rgba(0,0,0,0.03)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.2)] hover:border-emerald-500/30 hover:shadow-md transition-all duration-200 active:scale-[0.99]">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-[1.5px] bg-gradient-to-r from-transparent via-emerald-500/25 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div>
                <div className="flex items-center justify-between gap-1.5">
                  <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 truncate">
                    Tải lượng học
                  </span>
                  <span className={cn(
                    "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-semibold",
                    stats.totals.daily_load < 15
                      ? "text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 dark:bg-emerald-500/15"
                      : stats.totals.daily_load < 35
                      ? "text-teal-700 dark:text-teal-400 bg-teal-500/10 dark:bg-teal-500/15"
                      : "text-amber-700 dark:text-amber-400 bg-amber-500/10 dark:bg-amber-500/15"
                  )}>
                    {stats.totals.daily_load < 15 ? 'Nhẹ nhàng' : stats.totals.daily_load < 35 ? 'Tối ưu' : 'Cường độ cao'}
                  </span>
                </div>
                <div className="mt-2 sm:mt-2.5">
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground tabular-nums">
                      {stats.totals.daily_load.toFixed(1)}
                    </span>
                    <span className="text-xs font-medium text-muted-foreground">bài/ngày</span>
                  </div>
                </div>
              </div>
              <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>Mục tiêu</span>
                <span className="font-medium text-foreground/80">Duy trì trí nhớ</span>
              </div>
            </div>
          </div>

          {/* Average Study Time & Total Hours Chart */}
          {studyTimeQuery.data ? (
            <UserStudyTimeChart
              data={studyTimeQuery.data}
              range={studyTimeRange}
              onRangeChange={setStudyTimeRange}
              isLoading={studyTimeQuery.isFetching}
            />
          ) : null}

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
            <div className="space-y-4 sm:space-y-5">
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
              <p className="text-center sm:text-right text-[11px] sm:text-xs text-muted-foreground">
                Múi giờ hệ thống: {stats.timezone}
              </p>
            </div>
          </SectionCard>
        </>
      ) : null}
    </Page>
  )
}
