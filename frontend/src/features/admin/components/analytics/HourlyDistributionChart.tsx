import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Flame, Sun } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { HourlyDistributionItem } from '../../types/analytics'

type HourlyDistributionChartProps = {
  data: HourlyDistributionItem[]
}

export function HourlyDistributionChart({ data }: HourlyDistributionChartProps) {
  const maxReviews = Math.max(...data.map((d) => d.reviews_count), 0)
  const peakHour = data.find((d) => d.reviews_count === maxReviews && maxReviews > 0)

  return (
    <Card className="border-border/80 bg-card shadow-xs">
      <CardHeader className="flex flex-col gap-2 pb-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Flame className="size-4 text-orange-500" />
            Phân bố Khung giờ Học tập (24h Heatmap)
          </CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">
            Xác định các khung giờ cao điểm người dùng tập trung ôn bài trong ngày.
          </p>
        </div>

        {peakHour ? (
          <div className="flex items-center gap-1.5 rounded-lg bg-orange-500/10 px-2.5 py-1 text-xs font-medium text-orange-700 dark:text-orange-300">
            <Sun className="size-3.5" />
            <span>
              Cao điểm: <strong>{peakHour.hour_label}</strong> ({peakHour.reviews_count.toLocaleString()} lượt)
            </span>
          </div>
        ) : null}
      </CardHeader>

      <CardContent className="pt-2">
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border/50" />
              <XAxis
                dataKey="hour_label"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
                interval={1}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const item = payload[0].payload as HourlyDistributionItem
                    const isPeak = maxReviews > 0 && item.reviews_count === maxReviews
                    return (
                      <div className="rounded-lg border border-border bg-popover/95 p-2.5 text-xs shadow-md backdrop-blur-xs">
                        <div className="font-semibold text-foreground flex items-center justify-between gap-3 mb-1">
                          <span>Khung giờ: {item.hour_label} - {(item.hour + 1) % 24}:00</span>
                          {isPeak ? (
                            <span className="rounded bg-orange-500/15 px-1.5 py-0.5 text-[10px] font-bold text-orange-600 dark:text-orange-400">
                              🔥 Đỉnh cao điểm
                            </span>
                          ) : null}
                        </div>
                        <div className="space-y-1 text-muted-foreground">
                          <div className="flex items-center justify-between gap-4">
                            <span>Lượt lật thẻ:</span>
                            <span className="font-semibold text-foreground">{item.reviews_count.toLocaleString()}</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span>Học viên hoạt động:</span>
                            <span className="font-semibold text-foreground">{item.unique_users.toLocaleString()}</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span>Tổng thời gian học:</span>
                            <span className="font-semibold text-foreground">{item.duration_minutes} phút</span>
                          </div>
                        </div>
                      </div>
                    )
                  }
                  return null
                }}
              />
              <Bar dataKey="reviews_count" radius={[3, 3, 0, 0]}>
                {data.map((entry) => {
                  const isTop = maxReviews > 0 && entry.reviews_count >= maxReviews * 0.8
                  return (
                    <Cell
                      key={`cell-${entry.hour}`}
                      fill={isTop ? '#f97316' : '#64748b'}
                      opacity={isTop ? 0.95 : 0.45}
                    />
                  )
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
