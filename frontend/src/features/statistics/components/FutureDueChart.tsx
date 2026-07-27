import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { EmptyState } from '@/shared/components/PageState'
import type { FutureDuePoint } from '../types'

const chartConfig = {
  due_count: {
    label: 'Thẻ đến hạn',
    color: 'var(--primary)',
  },
} satisfies ChartConfig

export function FutureDueChart({ series }: { series: FutureDuePoint[] }) {
  if (!series.length) {
    return <EmptyState title="Không có dữ liệu" description="Không có thẻ đến hạn trong khoảng đã chọn." />
  }

  const interval = series.length > 180 ? 29 : series.length > 60 ? 13 : 6

  return (
    <ChartContainer config={chartConfig} className="h-80 w-full">
      <BarChart accessibilityLayer data={series} margin={{ left: 0, right: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="day_offset"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          interval={interval}
          tickFormatter={(value) => `+${value}`}
        />
        <YAxis width={36} tickLine={false} axisLine={false} allowDecimals={false} />
        <ChartTooltip
          cursor={{ fill: 'var(--muted)' }}
          content={
            <ChartTooltipContent
              labelFormatter={(_, payload) => payload[0]?.payload?.date || ''}
            />
          }
        />
        <Bar dataKey="due_count" fill="var(--color-due_count)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartContainer>
  )
}
