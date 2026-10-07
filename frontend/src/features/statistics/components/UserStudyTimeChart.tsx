import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { UserStudyTimePreset, UserStudyTimeResponse } from '../types'

type UserStudyTimeChartProps = {
  data: UserStudyTimeResponse
  range: UserStudyTimePreset
  onRangeChange: (preset: UserStudyTimePreset) => void
  isLoading?: boolean
}

function formatDateLabel(dateStr: string): string {
  try {
    const parts = dateStr.split('-')
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}`
    }
  } catch {
    // fallback
  }
  return dateStr
}

export function UserStudyTimeChart({
  data,
  range,
  onRangeChange,
  isLoading,
}: UserStudyTimeChartProps) {
  const { t } = useTranslation('statistics')
  const { summary, daily_time_series } = data

  const chartData = daily_time_series.map((d) => ({
    date: d.date,
    dateLabel: formatDateLabel(d.date),
    minutes: d.total_duration_minutes,
    hours: d.total_duration_hours,
    reviewsCount: d.total_reviews,
    passRate: d.retention_pass_rate,
  }))

  const rangeOptions: Array<{ label: string; shortLabel: string; value: UserStudyTimePreset }> = [
    {
      label: t('study_time_chart.ranges.7d'),
      shortLabel: t('study_time_chart.ranges.7d_short'),
      value: '7d',
    },
    {
      label: t('study_time_chart.ranges.30d'),
      shortLabel: t('study_time_chart.ranges.30d_short'),
      value: '30d',
    },
    {
      label: t('study_time_chart.ranges.90d'),
      shortLabel: t('study_time_chart.ranges.90d_short'),
      value: '90d',
    },
    {
      label: t('study_time_chart.ranges.12m'),
      shortLabel: t('study_time_chart.ranges.12m_short'),
      value: '12m',
    },
    {
      label: t('study_time_chart.ranges.all'),
      shortLabel: t('study_time_chart.ranges.all_short'),
      value: 'all',
    },
  ]

  return (
    <Card className="border-border/80 bg-card shadow-xs">
      <CardHeader className="flex flex-col gap-3 pb-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="text-base font-semibold">
            {t('study_time_chart.title')}
          </CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">
            {t('study_time_chart.description')}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs sm:flex sm:flex-wrap sm:items-center sm:gap-2">
          <div className="flex items-center rounded-lg bg-amber-500/10 px-2.5 py-1.5 font-medium text-amber-700 dark:text-amber-300">
            <span className="truncate">
              <strong>{t('study_time_chart.avg_badge', { minutes: summary.avg_daily_minutes })}</strong>
            </span>
          </div>
          <div className="flex items-center rounded-lg bg-blue-500/10 px-2.5 py-1.5 font-medium text-blue-700 dark:text-blue-300">
            <span className="truncate">
              <strong>{t('study_time_chart.total_badge', { hours: summary.total_study_hours })}</strong>
            </span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-1">
        {/* Preset Range Selector & Date Range */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5">
          <Tabs
            value={range}
            onValueChange={(val) => onRangeChange(val as UserStudyTimePreset)}
            className="w-full sm:w-auto"
          >
            <TabsList className="grid w-full grid-cols-5 sm:w-auto">
              {rangeOptions.map((opt) => (
                <TabsTrigger
                  key={opt.value}
                  value={opt.value}
                  className="text-xs px-1 sm:px-3 font-medium min-h-[32px]"
                  disabled={isLoading}
                >
                  <span className="sm:hidden">{opt.shortLabel}</span>
                  <span className="hidden sm:inline">{opt.label}</span>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <span className="text-[11px] sm:text-xs text-muted-foreground text-right">
            {data.start_date} → {data.end_date}
          </span>
        </div>

        {/* Chart View */}
        {chartData.length === 0 ? (
          <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-border/80 p-6 text-center text-xs text-muted-foreground">
            <p className="font-semibold text-foreground text-sm">
              {t('study_time_chart.empty_title')}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {t('study_time_chart.empty_description')}
            </p>
          </div>
        ) : (
          <div className="h-60 sm:h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="userColorAvgMinutes" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border/50" />
                <XAxis
                  dataKey="dateLabel"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
                  minTickGap={16}
                />
                <YAxis
                  yAxisId="left"
                  width={35}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
                  unit="p"
                />
                <YAxis
                  yAxisId="right"
                  width={30}
                  orientation="right"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
                  unit="h"
                />
                <Tooltip
                  wrapperStyle={{ pointerEvents: 'none', zIndex: 50 }}
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0].payload
                      return (
                        <div className="rounded-lg border border-border bg-popover/95 p-2.5 sm:p-3 text-xs shadow-md backdrop-blur-xs max-w-[240px]">
                          <div className="font-semibold text-foreground mb-1">{item.date}</div>
                          <div className="space-y-1 text-muted-foreground">
                            <div className="flex items-center justify-between gap-3">
                              <span className="flex items-center gap-1.5">
                                <span className="size-2 rounded-full bg-amber-500" />
                                {t('study_time_chart.tooltip_time')}
                              </span>
                              <span className="font-semibold text-foreground">
                                {t('study_time_chart.tooltip_minutes', { minutes: item.minutes })}
                              </span>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <span className="flex items-center gap-1.5">
                                <span className="size-2 rounded-full bg-blue-500" />
                                {t('study_time_chart.tooltip_total_hours')}
                              </span>
                              <span className="font-semibold text-foreground">
                                {t('study_time_chart.tooltip_hours', { hours: item.hours })}
                              </span>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <span>{t('study_time_chart.tooltip_reviews')}</span>
                              <span className="font-semibold text-foreground">
                                {t('study_time_chart.tooltip_cards', { count: item.reviewsCount })}
                              </span>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <span>{t('study_time_chart.tooltip_retention')}</span>
                              <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                                {item.passRate}%
                              </span>
                            </div>
                          </div>
                        </div>
                      )
                    }
                    return null
                  }}
                />
                <Legend
                  verticalAlign="top"
                  align="right"
                  iconType="circle"
                  wrapperStyle={{ fontSize: '11px', paddingBottom: '8px' }}
                />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="minutes"
                  name={t('study_time_chart.series_time')}
                  stroke="#f59e0b"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#userColorAvgMinutes)"
                />
                <Bar
                  yAxisId="right"
                  dataKey="hours"
                  name={t('study_time_chart.series_hours')}
                  fill="#3b82f6"
                  opacity={0.65}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={16}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
