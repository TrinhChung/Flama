import '@/shared/config/i18n'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { StudyHeatmap } from '@/shared/components/StudyHeatmap'
import { Page, PageHeader, SectionCard } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useStatisticsConfig, useTodayFutureStats, useUserStudyTimeStats } from '../api'
import { FutureDueChart } from '../components/FutureDueChart'
import { StatisticsFilterCard } from '../components/StatisticsFilterCard'
import { StatisticsKpiGrid } from '../components/StatisticsKpiGrid'
import { UserStudyTimeChart } from '../components/UserStudyTimeChart'
import { useStatisticsFilters } from '../hooks/useStatisticsFilters'
import type { UserStudyTimePreset } from '../types'

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
  const { t } = useTranslation('statistics')
  const configQuery = useStatisticsConfig()
  const [currentYear, setCurrentYear] = useState<number>(new Date().getFullYear())
  const [studyTimeRange, setStudyTimeRange] = useState<UserStudyTimePreset>('30d')

  const { filters, setFilters, updateFiltersAndUrl } = useStatisticsFilters(configQuery.data)

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

  if (configQuery.isPending) return <PageLoading label={t('loading.config')} />
  if (configQuery.error) return <Page><PageError error={configQuery.error} /></Page>

  const stats = statsQuery.data
  const overview = overviewQuery.data

  return (
    <Page size="wide" className="space-y-4 sm:space-y-6">
      <PageHeader
        title={t('header.title')}
        description={t('header.description')}
      />

      {/* Filter Toolbar Card */}
      <StatisticsFilterCard
        filters={filters}
        decks={configQuery.data.decks}
        onUpdateFiltersAndUrl={updateFiltersAndUrl}
        onSetFilters={setFilters}
      />

      {statsQuery.error ? <PageError error={statsQuery.error} /> : null}
      {statsQuery.isFetching && !stats ? <PageLoading label={t('loading.stats')} /> : null}

      {stats ? (
        <>
          {/* KPI Stat Cards Grid */}
          <StatisticsKpiGrid
            stats={stats}
            overview={overview}
            isFetching={statsQuery.isFetching}
          />

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
            title={t('future_due.section_title')}
            description={t('future_due.section_description')}
            actions={
              <div className="flex items-center gap-2">
                <Switch
                  id="backlog"
                  checked={filters.backlog}
                  onCheckedChange={(backlog) => setFilters((current) => ({ ...current, backlog }))}
                />
                <Label htmlFor="backlog" className="cursor-pointer text-xs font-medium whitespace-nowrap">
                  {t('future_due.backlog_label')}
                </Label>
              </div>
            }
          >
            <div className="space-y-4 sm:space-y-5">
              <ChoiceTabs
                value={filters.futureRange}
                items={[
                  { label: t('future_due.ranges.30d'), value: '30' },
                  { label: t('future_due.ranges.90d'), value: '90' },
                  { label: t('future_due.ranges.1y'), value: '365' },
                  { label: t('future_due.ranges.all'), value: 'all' },
                ]}
                onChange={(futureRange) => setFilters((current) => ({ ...current, futureRange }))}
              />
              <FutureDueChart series={stats.future_due.series} />
              <p className="text-center sm:text-right text-[11px] sm:text-xs text-muted-foreground">
                {t('future_due.timezone_notice', { tz: stats.timezone })}
              </p>
            </div>
          </SectionCard>
        </>
      ) : null}
    </Page>
  )
}
