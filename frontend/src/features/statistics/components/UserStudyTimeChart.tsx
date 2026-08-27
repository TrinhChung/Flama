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
import { Clock, Layers, Timer } from 'lucide-react'
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
  const { summary, daily_time_series } = data

  const chartData = daily_time_series.map((d) => ({
    date: d.date,
    dateLabel: formatDateLabel(d.date),
    minutes: d.total_duration_minutes,
    hours: d.total_duration_hours,
    reviewsCount: d.total_reviews,
    passRate: d.retention_pass_rate,
  }))

  const rangeOptions: Array<{ label: string; value: UserStudyTimePreset }> = [
    { label: '7 ngày', value: '7d' },
    { label: '30 ngày', value: '30d' },
    { label: '90 ngày', value: '90d' },
    { label: '1 năm', value: '12m' },
    { label: 'Tất cả', value: 'all' },
  ]

  return (
    <Card className="border-border/80 bg-card shadow-xs">
      <CardHeader className="flex flex-col gap-3 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Timer className="size-4 text-amber-500" />
            Thời gian học tập trung bình & Tổng giờ học
          </CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">
            Theo dõi số phút học trung bình mỗi ngày và tổng thời gian ôn tập flashcard của bạn.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-2.5 py-1 font-medium text-amber-700 dark:text-amber-300">
            <Clock className="size-3.5" />
            <span>
              TB: <strong>{summary.avg_daily_minutes} phút/ngày</strong>
              {summary.active_days_count > 0 && (
                <span className="opacity-80 text-[11px] ml-1">
                  ({summary.avg_study_minutes_active_day}p/ngày học)
                </span>
              )}
            </span>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg bg-blue-500/10 px-2.5 py-1 font-medium text-blue-700 dark:text-blue-300">
            <Layers className="size-3.5" />
            <span>
              Tổng: <strong>{summary.total_study_hours} giờ</strong> ({summary.total_reviews.toLocaleString('vi-VN')} lượt)
            </span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-1">
        {/* Preset Range Selector */}
        <div className="flex items-center justify-between">
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
                  className="text-xs px-3 font-medium"
                  disabled={isLoading}
                >
                  {opt.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <span className="hidden text-xs text-muted-foreground sm:inline-block">
            {data.start_date} → {data.end_date}
          </span>
        </div>

        {/* Chart View */}
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
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
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                minTickGap={20}
              />
              <YAxis
                yAxisId="left"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                unit=" p"
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                unit=" h"
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const item = payload[0].payload
                    return (
                      <div className="rounded-lg border border-border bg-popover/95 p-3 text-xs shadow-md backdrop-blur-xs">
                        <div className="font-semibold text-foreground mb-1.5">{item.date}</div>
                        <div className="space-y-1 text-muted-foreground">
                          <div className="flex items-center justify-between gap-4">
                            <span className="flex items-center gap-1.5">
                              <span className="size-2 rounded-full bg-amber-500" />
                              Thời gian học:
                            </span>
                            <span className="font-semibold text-foreground">{item.minutes} phút</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span className="flex items-center gap-1.5">
                              <span className="size-2 rounded-full bg-blue-500" />
                              Tổng giờ học:
                            </span>
                            <span className="font-semibold text-foreground">{item.hours} giờ</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span>Lượt lật thẻ:</span>
                            <span className="font-semibold text-foreground">{item.reviewsCount} thẻ</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span>Tỷ lệ nhớ đúng:</span>
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
                wrapperStyle={{ fontSize: '11px', paddingBottom: '10px' }}
              />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="minutes"
                name="Thời gian học (phút)"
                stroke="#f59e0b"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#userColorAvgMinutes)"
              />
              <Bar
                yAxisId="right"
                dataKey="hours"
                name="Tổng giờ học (h)"
                fill="#3b82f6"
                opacity={0.65}
                radius={[4, 4, 0, 0]}
                barSize={12}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
