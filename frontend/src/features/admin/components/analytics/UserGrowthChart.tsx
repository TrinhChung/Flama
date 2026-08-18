import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { TrendingUp, UserCheck, Users } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { UserGrowthResponse } from '../../types/analytics'

type UserGrowthChartProps = {
  data: UserGrowthResponse
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

export function UserGrowthChart({ data }: UserGrowthChartProps) {
  const chartData = data.data.map((d) => ({
    date: d.date,
    dateLabel: formatDateLabel(d.date),
    newUsers: d.new_users,
    cumulativeUsers: d.cumulative_users,
    activeUsers: d.active_users,
    reviewsCount: d.reviews_count,
  }))

  const totalNewInPeriod = data.data.reduce((acc, curr) => acc + curr.new_users, 0)
  const latestCumulative = data.data[data.data.length - 1]?.cumulative_users || 0

  return (
    <Card className="border-border/80 bg-card shadow-xs">
      <CardHeader className="flex flex-col gap-2 pb-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <TrendingUp className="size-4 text-emerald-500" />
            Tăng trưởng Người dùng & Hoạt động (DAU)
          </CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">
            Theo dõi tốc độ đăng ký mới song song với lượng học viên hoạt động hằng ngày.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 rounded-lg bg-emerald-500/10 px-2.5 py-1 font-medium text-emerald-700 dark:text-emerald-300">
            <Users className="size-3.5" />
            <span>Mới: <strong>+{totalNewInPeriod.toLocaleString()} user</strong></span>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg bg-indigo-500/10 px-2.5 py-1 font-medium text-indigo-700 dark:text-indigo-300">
            <UserCheck className="size-3.5" />
            <span>Tích lũy: <strong>{latestCumulative.toLocaleString()} user</strong></span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-2">
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
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
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
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
                              <span className="size-2 rounded-full bg-emerald-500" />
                              Đăng ký mới:
                            </span>
                            <span className="font-semibold text-foreground">+{item.newUsers}</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span className="flex items-center gap-1.5">
                              <span className="size-2 rounded-full bg-orange-500" />
                              Học viên tích cực (DAU):
                            </span>
                            <span className="font-semibold text-foreground">{item.activeUsers}</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span className="flex items-center gap-1.5">
                              <span className="size-2 rounded-full bg-indigo-500" />
                              Tổng user tích lũy:
                            </span>
                            <span className="font-semibold text-foreground">{item.cumulativeUsers.toLocaleString()}</span>
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
              <Bar
                yAxisId="left"
                dataKey="newUsers"
                name="Đăng ký mới"
                fill="#10b981"
                opacity={0.8}
                radius={[4, 4, 0, 0]}
                barSize={12}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="activeUsers"
                name="DAU (Active User)"
                stroke="#f97316"
                strokeWidth={2}
                dot={{ r: 2 }}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="cumulativeUsers"
                name="Tổng User tích lũy"
                stroke="#6366f1"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
