import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EmptyState } from '@/shared/components/PageState'
import type { FutureDuePoint } from '../types'

function CustomTooltip({ active, payload }: { active?: boolean; payload?: any[] }) {
  if (!active || !payload || !payload.length) return null

  const data: FutureDuePoint = payload[0].payload
  const breakdown = data.breakdown || { new: 0, learn: 0, review: 0, relearn: 0 }

  return (
    <div className="rounded-xl border border-border/80 bg-gray-900/95 p-3.5 text-xs text-white shadow-xl backdrop-blur-md min-w-[200px]">
      <div className="font-semibold text-gray-300 border-b border-gray-800 pb-1.5 mb-2 flex items-center justify-between">
        <span>Ngày: {data.date}</span>
        <span className="text-gray-400 font-mono">+{data.day_offset}d</span>
      </div>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-blue-400 font-medium">
            <span className="size-2 rounded-full bg-blue-500" /> Thẻ mới (New):
          </span>
          <span className="font-bold font-mono">{breakdown.new.toLocaleString('vi-VN')}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-orange-400 font-medium">
            <span className="size-2 rounded-full bg-orange-500" /> Đang học (Learn):
          </span>
          <span className="font-bold font-mono">{breakdown.learn.toLocaleString('vi-VN')}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
            <span className="size-2 rounded-full bg-emerald-500" /> Ôn tập (Review):
          </span>
          <span className="font-bold font-mono">{breakdown.review.toLocaleString('vi-VN')}</span>
        </div>
        <div className="pt-1.5 mt-1.5 border-t border-gray-800 flex items-center justify-between gap-3 text-gray-200">
          <span className="font-semibold">Tổng đến hạn:</span>
          <span className="font-bold font-mono text-orange-400">{data.due_count.toLocaleString('vi-VN')}</span>
        </div>
        <div className="flex items-center justify-between gap-3 text-amber-300">
          <span className="font-semibold flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-amber-500" /> Tích lũy:
          </span>
          <span className="font-bold font-mono">{data.cumulative.toLocaleString('vi-VN')}</span>
        </div>
      </div>
    </div>
  )
}

export function FutureDueChart({ series }: { series: FutureDuePoint[] }) {
  if (!series || !series.length) {
    return <EmptyState title="Không có dữ liệu" description="Không có thẻ đến hạn trong khoảng đã chọn." />
  }

  const interval = series.length > 180 ? 29 : series.length > 60 ? 13 : 6

  return (
    <div className="space-y-3">
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={series} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.5} />
            <XAxis
              dataKey="day_offset"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              interval={interval}
              tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              tickFormatter={(val) => (val === 0 ? 'Hôm nay' : `+${val}d`)}
            />
            <YAxis
              yAxisId="due"
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
              tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
            />
            <YAxis
              yAxisId="cumulative"
              orientation="right"
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
              tick={{ fontSize: 11, fill: '#f59e0b' }}
            />
            <Tooltip content={<CustomTooltip />} />

            {/* Stacked Bars for Card Modes */}
            <Bar yAxisId="due" dataKey="breakdown.new" stackId="due" name="Thẻ mới" fill="#3b82f6" radius={[0, 0, 0, 0]} />
            <Bar yAxisId="due" dataKey="breakdown.learn" stackId="due" name="Đang học" fill="#f97316" radius={[0, 0, 0, 0]} />
            <Bar yAxisId="due" dataKey="breakdown.review" stackId="due" name="Ôn tập" fill="#10b981" radius={[3, 3, 0, 0]} />

            {/* Cumulative Line */}
            <Line
              yAxisId="cumulative"
              type="monotone"
              dataKey="cumulative"
              name="Tích lũy"
              stroke="#f59e0b"
              strokeWidth={2.5}
              dot={series.length > 60 ? false : { r: 2, fill: '#f59e0b' }}
              activeDot={{ r: 5, fill: '#f59e0b' }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend Badge Row */}
      <div className="flex flex-wrap items-center justify-center gap-4 text-xs font-medium text-muted-foreground pt-1">
        <div className="flex items-center gap-1.5">
          <span className="size-3 rounded-sm bg-blue-500" />
          <span>Thẻ mới (New)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="size-3 rounded-sm bg-orange-500" />
          <span>Đang học (Learn)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="size-3 rounded-sm bg-emerald-500" />
          <span>Ôn tập (Review)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full bg-amber-500" />
          <span>Tích lũy (Cumulative)</span>
        </div>
      </div>
    </div>
  )
}
