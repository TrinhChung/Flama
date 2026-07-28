import { useState } from 'react'
import { ChevronLeft, ChevronRight } from '@/shared/components/Icons'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { DashboardHeatmapDay, DashboardOverview } from '../types'

function getDayLevel(cards: number, isFuture: boolean): number {
  if (!cards || cards <= 0) return 0
  if (isFuture) {
    if (cards >= 30) return 5
    if (cards >= 15) return 4
    if (cards >= 5) return 3
    return 2
  }
  if (cards >= 30) return 5
  if (cards >= 15) return 4
  if (cards >= 5) return 3
  return 1
}

function getDayTitle(day: DashboardHeatmapDay): string {
  if (day.is_future) {
    return `${day.date}: ${day.cards.toLocaleString('vi-VN')} thẻ đến hạn`
  }
  if (!day.cards) return `${day.date}: Chưa học`
  return `${day.date}: ${day.cards.toLocaleString('vi-VN')} thẻ · ${day.minutes.toLocaleString('vi-VN')} phút`
}

export function DashboardHeatmap({
  overview,
  loading,
  year,
  onYearChange,
}: {
  overview?: DashboardOverview
  loading: boolean
  year: number
  onYearChange: (year: number) => void
}) {
  const [tooltipText, setTooltipText] = useState<string>('Hover a day to view details.')

  const todayData = overview?.today
  const summaryText = todayData
    ? `Studied ${todayData.cards.toLocaleString('vi-VN')} cards in ${todayData.minutes.toFixed(
        2,
      )} minutes today (${todayData.cards > 0 ? (todayData.minutes * 60 / todayData.cards).toFixed(2) : '0.00'}s/card)`
    : `Studied 0 cards in 0.00 minutes today (0.00s/card)`

  // Group heatmap into 53 weeks x 7 days
  const heatmap = overview?.heatmap || []
  const firstDay = heatmap[0]
  const leadingCount = firstDay
    ? (new Date(`${firstDay.date}T00:00:00Z`).getUTCDay() + 6) % 7
    : 0

  const allCells: Array<DashboardHeatmapDay | null> = [
    ...Array.from({ length: leadingCount }, () => null),
    ...heatmap,
  ]

  const weeks: Array<Array<DashboardHeatmapDay | null>> = []
  for (let i = 0; i < allCells.length; i += 7) {
    weeks.push(allCells.slice(i, i + 7))
  }

  const levelBgClasses = [
    'stats-day--level-0 bg-[#E9DDD4]', // Level 0
    'stats-day--level-1 bg-[#FFE1CE]', // Level 1
    'stats-day--level-2 bg-[#FFC39C]', // Level 2
    'stats-day--level-3 bg-[#FEA46B]', // Level 3
    'stats-day--level-4 bg-[#FE8639]', // Level 4
    'stats-day--level-5 bg-[#E05C07]', // Level 5
  ]

  return (
    <section className="stats-board w-full max-w-[1100px] mx-auto mt-5 p-5 rounded-xl border border-border bg-[#f7f7f7]">
      {loading && !overview ? (
        <div className="space-y-4">
          <Skeleton className="h-6 w-64 mx-auto bg-muted" />
          <Skeleton className="h-28 w-full bg-muted" />
        </div>
      ) : (
        <>
          {/* Summary Text */}
          <p className="stats-summary text-center text-xl font-semibold text-[#E05C07] tabular-nums mb-3 leading-tight">
            {summaryText}
          </p>

          {/* Year Navigation */}
          <div className="stats-nav flex items-center justify-center gap-2 mb-4">
            <button
              type="button"
              className="stats-year-btn size-9 inline-flex items-center justify-center rounded-lg border border-border bg-white text-gray-600 shadow-xs hover:border-orange-300 hover:text-orange-700 hover:bg-orange-50 transition-all cursor-pointer"
              aria-label="Previous year"
              disabled={year <= 1970}
              onClick={() => onYearChange(year - 1)}
            >
              <ChevronLeft className="size-4" />
            </button>

            <div className="stats-year-label min-w-16 text-center text-base font-semibold text-gray-600 tabular-nums">
              {year}
            </div>

            <button
              type="button"
              className="stats-year-btn size-9 inline-flex items-center justify-center rounded-lg border border-border bg-white text-gray-600 shadow-xs hover:border-orange-300 hover:text-orange-700 hover:bg-orange-50 transition-all cursor-pointer"
              aria-label="Next year"
              disabled={year >= 2100}
              onClick={() => onYearChange(year + 1)}
            >
              <ChevronRight className="size-4" />
            </button>
          </div>

          {/* Heatmap Grid */}
          <div className="stats-heatmap-scroll overflow-x-auto pb-2">
            <div
              className="stats-heatmap grid gap-[3px] min-w-[720px]"
              style={{
                gridTemplateColumns: `repeat(${Math.max(weeks.length, 53)}, minmax(0, 1fr))`,
              }}
              role="grid"
              aria-label="Study heatmap"
            >
              {weeks.map((week, weekIndex) => (
                <div key={weekIndex} className="stats-week grid grid-rows-7 gap-[3px]">
                  {week.map((day, dayIndex) => {
                    if (!day) {
                      return (
                        <span
                          key={`empty-${weekIndex}-${dayIndex}`}
                          className="stats-day aspect-square w-full rounded-[2px] bg-[#E9DDD4] opacity-35"
                          aria-hidden="true"
                        />
                      )
                    }
                    const level = getDayLevel(day.cards, Boolean(day.is_future))
                    const title = getDayTitle(day)

                    return (
                      <button
                        key={day.date}
                        type="button"
                        className={cn(
                          'stats-day aspect-square w-full rounded-[2px] border-0 p-0 transition-transform duration-150 hover:scale-125 focus-visible:outline-2 focus-visible:outline-orange-400 cursor-pointer',
                          levelBgClasses[level],
                        )}
                        title={title}
                        onMouseEnter={() => setTooltipText(title)}
                        onMouseLeave={() => setTooltipText('Hover a day to view details.')}
                      />
                    )
                  })}
                </div>
              ))}
            </div>
          </div>

          {/* Dynamic Hover Tooltip */}
          <div className="stats-tooltip min-h-[1.25rem] mt-2 text-center text-[0.86rem] text-gray-500">
            {tooltipText}
          </div>

          {/* Bottom Metrics Inline Row */}
          <div className="stats-metrics mt-3.5 pt-3 border-t border-border flex flex-wrap items-center justify-between gap-3 text-[0.95rem] text-gray-700">
            <div className="stats-metric whitespace-nowrap">
              Daily average:
              <strong className="text-[#E05C07] font-bold ml-1 text-base">
                {(overview?.metrics.daily_average_cards ?? 0).toLocaleString('vi-VN')} cards
              </strong>
            </div>

            <div className="stats-metric whitespace-nowrap">
              Days learned:
              <strong className="text-[#E05C07] font-bold ml-1 text-base">
                {(overview?.metrics.days_learned_percent ?? 0).toLocaleString('vi-VN')}%
              </strong>
            </div>

            <div className="stats-metric whitespace-nowrap">
              Longest streak:
              <strong className="text-[#E05C07] font-bold ml-1 text-base">
                {(overview?.metrics.longest_streak_days ?? 0).toLocaleString('vi-VN')} days
              </strong>
            </div>

            <div className="stats-metric whitespace-nowrap">
              Current streak:
              <strong className="text-[#E05C07] font-bold ml-1 text-base">
                {(overview?.metrics.current_streak_days ?? 0).toLocaleString('vi-VN')} days
              </strong>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
