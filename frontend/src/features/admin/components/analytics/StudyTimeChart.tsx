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
import type { StudyTimeResponse } from '../../types/analytics'

type StudyTimeChartProps = {
  data: StudyTimeResponse
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

export function StudyTimeChart({ data }: StudyTimeChartProps) {
  const { summary, daily_time_series } = data

  const chartData = daily_time_series.map((d) => ({
    date: d.date,
    dateLabel: formatDateLabel(d.date),
    avgMinutes: d.avg_study_minutes_per_user,
    totalHours: d.total_duration_hours,
    activeUsers: d.active_users,
    reviewsCount: d.total_reviews,
    passRate: d.retention_pass_rate,
  }))

  return (
    <Card className="border-border/80 bg-card shadow-xs">
      <CardHeader className="flex flex-col gap-2 pb-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Timer className="size-4 text-amber-500" />
            Thời gian học tập trung bình & Tổng giờ học
          </CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">
            Theo dõi số phút học trung bình mỗi học viên và tổng tải học tập toàn hệ sinh thái.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-2.5 py-1 font-medium text-amber-700 dark:text-amber-300">
            <Clock className="size-3.5" />
            <span>TB: <strong>{summary.avg_daily_minutes_system} phút/ngày</strong></span>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg bg-blue-500/10 px-2.5 py-1 font-medium text-blue-700 dark:text-blue-300">
            <Layers className="size-3.5" />
            <span>Tổng: <strong>{summary.total_study_hours} giờ ({summary.total_reviews.toLocaleString()} lượt)</strong></span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-2">
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="colorAvgMinutes" x1="0" y1="0" x2="0" y2="1">
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
                              Thời gian học TB/user:
                            </span>
                            <span className="font-semibold text-foreground">{item.avgMinutes} phút</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span className="flex items-center gap-1.5">
                              <span className="size-2 rounded-full bg-blue-500" />
                              Tổng giờ học sàn:
                            </span>
                            <span className="font-semibold text-foreground">{item.totalHours} giờ</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span>Người học trong ngày:</span>
                            <span className="font-semibold text-foreground">{item.activeUsers} user</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span>Lượt lật thẻ:</span>
                            <span className="font-semibold text-foreground">{item.reviewsCount} thẻ</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span>Tỷ lệ nhớ đúng:</span>
                            <span className="font-semibold text-emerald-600 dark:text-emerald-400">{item.passRate}%</span>
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
                dataKey="avgMinutes"
                name="TB Phút / User / Ngày"
                stroke="#f59e0b"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorAvgMinutes)"
              />
              <Bar
                yAxisId="right"
                dataKey="totalHours"
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
