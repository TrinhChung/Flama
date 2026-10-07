import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EmptyState } from '@/shared/components/PageState'
import type { FutureDuePoint } from '../types'

function CustomTooltip({ active, payload }: { active?: boolean; payload?: any[] }) {
  const { t } = useTranslation('statistics')
  if (!active || !payload || !payload.length) return null

  const data: FutureDuePoint = payload[0].payload
  const breakdown = data.breakdown || { new: 0, learn: 0, review: 0, relearn: 0 }

  return (
    <div className="rounded-xl border border-border/80 bg-gray-900/95 p-2.5 sm:p-3.5 text-xs text-white shadow-xl backdrop-blur-md min-w-[190px] max-w-[240px]">
      <div className="font-semibold text-gray-300 border-b border-gray-800 pb-1 mb-1.5 flex items-center justify-between">
        <span>{data.date}</span>
        <span className="text-gray-400 font-mono">+{data.day_offset}d</span>
      </div>
      <div className="space-y-1 sm:space-y-1.5">
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-blue-400 font-medium">
            <span className="size-2 rounded-full bg-blue-500" /> {t('future_due.card_types.new')}:
          </span>
          <span className="font-bold font-mono">{breakdown.new.toLocaleString()}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-orange-400 font-medium">
            <span className="size-2 rounded-full bg-orange-500" /> {t('future_due.card_types.learn')}:
          </span>
          <span className="font-bold font-mono">{breakdown.learn.toLocaleString()}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
            <span className="size-2 rounded-full bg-emerald-500" /> {t('future_due.card_types.review')}:
          </span>
          <span className="font-bold font-mono">{breakdown.review.toLocaleString()}</span>
        </div>
        <div className="pt-1 mt-1 border-t border-gray-800 flex items-center justify-between gap-3 text-gray-200">
          <span className="font-semibold">{t('future_due.total_due')}</span>
          <span className="font-bold font-mono text-orange-400">{data.due_count.toLocaleString()}</span>
        </div>
        <div className="flex items-center justify-between gap-3 text-amber-300">
          <span className="font-semibold flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-amber-500" /> {t('future_due.card_types.cumulative')}:
          </span>
          <span className="font-bold font-mono">{data.cumulative.toLocaleString()}</span>
        </div>
      </div>
    </div>
  )
}

function formatAxisNumber(val: number): string {
  if (val >= 1000) {
    const k = val / 1000
    return `${k.toFixed(k % 1 === 0 ? 0 : 1)}k`
  }
  return String(val)
}

export function FutureDueChart({ series }: { series: FutureDuePoint[] }) {
  const { t } = useTranslation('statistics')

  if (!series || !series.length) {
    return (
      <EmptyState
        title={t('future_due.empty_title')}
        description={t('future_due.empty_description')}
      />
    )
  }

  const interval = series.length > 180 ? 29 : series.length > 60 ? 13 : 6

  return (
    <div className="space-y-3">
      <div className="h-64 sm:h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={series} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.5} />
            <XAxis
              dataKey="day_offset"
              tickLine={false}
              axisLine={false}
              tickMargin={6}
              interval={interval}
              tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
              tickFormatter={(val) => (val === 0 ? t('future_due.today') : `+${val}d`)}
            />
            <YAxis
              yAxisId="due"
              width={35}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
              tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
              tickFormatter={formatAxisNumber}
            />
            <YAxis
              yAxisId="cumulative"
              width={35}
              orientation="right"
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
              tick={{ fontSize: 10, fill: '#f59e0b' }}
              tickFormatter={formatAxisNumber}
            />
            <Tooltip
              wrapperStyle={{ pointerEvents: 'none', zIndex: 50 }}
              content={<CustomTooltip />}
            />

            {/* Stacked Bars for Card Modes */}
            <Bar yAxisId="due" dataKey="breakdown.new" stackId="due" name={t('future_due.card_types.new')} fill="#3b82f6" radius={[0, 0, 0, 0]} />
            <Bar yAxisId="due" dataKey="breakdown.learn" stackId="due" name={t('future_due.card_types.learn')} fill="#f97316" radius={[0, 0, 0, 0]} />
            <Bar yAxisId="due" dataKey="breakdown.review" stackId="due" name={t('future_due.card_types.review')} fill="#10b981" radius={[3, 3, 0, 0]} />

            {/* Cumulative Line */}
            <Line
              yAxisId="cumulative"
              type="monotone"
              dataKey="cumulative"
              name={t('future_due.card_types.cumulative')}
              stroke="#f59e0b"
              strokeWidth={2.5}
              dot={series.length > 60 ? false : { r: 2, fill: '#f59e0b' }}
              activeDot={{ r: 5, fill: '#f59e0b' }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend Badge Row */}
      <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5 sm:gap-4 text-[11px] sm:text-xs font-medium text-muted-foreground pt-1">
        <div className="flex items-center gap-1.5">
          <span className="size-2.5 sm:size-3 rounded-sm bg-blue-500" />
          <span>{t('future_due.card_types.new')}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="size-2.5 sm:size-3 rounded-sm bg-orange-500" />
          <span>{t('future_due.card_types.learn')}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="size-2.5 sm:size-3 rounded-sm bg-emerald-500" />
          <span>{t('future_due.card_types.review')}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-0.5 w-3.5 sm:w-4 rounded-full bg-amber-500" />
          <span>{t('future_due.card_types.cumulative')}</span>
        </div>
      </div>
    </div>
  )
}
