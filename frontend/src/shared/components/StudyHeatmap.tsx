import { useState } from 'react'
import { ChevronLeft, ChevronRight } from '@/shared/components/Icons'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { HeatmapDay, HeatmapOverviewData } from '@/shared/types/heatmap'

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

function getTodayStr(): string {
  const d = new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getDayTitle(day: HeatmapDay, isToday: boolean): string {
  const todayLabel = isToday ? ' (Hôm nay)' : ''
  if (day.is_future) {
    return `${day.date}${todayLabel}: ${day.cards.toLocaleString('vi-VN')} thẻ đến hạn`
  }
  if (!day.cards) return `${day.date}${todayLabel}: Chưa học`
  return `${day.date}${todayLabel}: ${day.cards.toLocaleString('vi-VN')} thẻ · ${day.minutes.toLocaleString('vi-VN')} phút`
}

export type StudyHeatmapProps = {
  overview?: HeatmapOverviewData
  loading?: boolean
  year: number
  onYearChange: (year: number) => void
  showSummary?: boolean
  showMetrics?: boolean
  showYearNav?: boolean
  className?: string
}

// Past days (darker, vibrant)
const pastLevelClasses = [
  'stats-day--level-0 bg-[#E2D6CC]',
  'stats-day--level-1 bg-[#FFBA93]',
  'stats-day--level-2 bg-[#FF9456]',
  'stats-day--level-3 bg-[#FA6C1B]',
  'stats-day--level-4 bg-[#D94E02]',
  'stats-day--level-5 bg-[#AC3800]',
]

// Future days (lighter, pastel)
const futureLevelClasses = [
  'stats-day--future-level-0 bg-[#F5EFE9]/60',
  'stats-day--future-level-1 bg-[#FFEBE0]',
  'stats-day--future-level-2 bg-[#FFD9C6]',
  'stats-day--future-level-3 bg-[#FFC2A4]',
  'stats-day--future-level-4 bg-[#FFA87D]',
  'stats-day--future-level-5 bg-[#FF8D57]',
]

export function StudyHeatmap({
  overview,
  loading = false,
  year,
  onYearChange,
  showSummary = true,
  showMetrics = true,
  showYearNav = true,
  className,
}: StudyHeatmapProps) {
  const [tooltipText, setTooltipText] = useState<string>('Rê chuột lên các ô để xem chi tiết học tập.')
  const todayStr = getTodayStr()

  const todayData = overview?.today
  const summaryText = todayData
    ? `Hôm nay đã học ${todayData.cards.toLocaleString('vi-VN')} thẻ trong ${todayData.minutes.toFixed(
        2,
      )} phút (${todayData.cards > 0 ? (todayData.minutes * 60 / todayData.cards).toFixed(2) : '0.00'}s/thẻ)`
    : `Hôm nay đã học 0 thẻ trong 0.00 phút (0.00s/thẻ)`

  // Group heatmap into 53 weeks x 7 days
  const heatmap = overview?.heatmap || []
  const firstDay = heatmap[0]
  const leadingCount = firstDay
    ? (new Date(`${firstDay.date}T00:00:00Z`).getUTCDay() + 6) % 7
    : 0

  const allCells: Array<HeatmapDay | null> = [
    ...Array.from({ length: leadingCount }, () => null),
    ...heatmap,
  ]

  const weeks: Array<Array<HeatmapDay | null>> = []
  for (let i = 0; i < allCells.length; i += 7) {
    weeks.push(allCells.slice(i, i + 7))
  }

  return (
    <section className={cn("stats-board w-full rounded-xl sm:rounded-2xl border-0 sm:border border-border bg-card p-2.5 sm:p-6 shadow-none sm:shadow-sm", className)}>
      {loading && !overview ? (
        <div className="space-y-4">
          <Skeleton className="h-6 w-64 mx-auto bg-muted" />
          <Skeleton className="h-28 w-full bg-muted" />
        </div>
      ) : (
        <>
          {/* Summary Text */}
          {showSummary && (
            <p className="stats-summary text-center text-sm sm:text-xl font-semibold text-[#E05C07] tabular-nums mb-2 sm:mb-3 leading-tight">
              {summaryText}
            </p>
          )}

          {/* Year Navigation */}
          {showYearNav && (
            <div className="stats-nav flex items-center justify-center gap-2 mb-3 sm:mb-4">
              <button
                type="button"
                className="stats-year-btn size-7 sm:size-9 inline-flex items-center justify-center rounded-lg border border-border bg-white text-gray-600 shadow-xs hover:border-orange-300 hover:text-orange-700 hover:bg-orange-50 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Previous year"
                disabled={year <= 1970}
                onClick={() => onYearChange(year - 1)}
              >
                <ChevronLeft className="size-3.5 sm:size-4" />
              </button>

              <div className="stats-year-label min-w-12 sm:min-w-16 text-center text-sm sm:text-base font-semibold text-gray-600 tabular-nums">
                {year}
              </div>

              <button
                type="button"
                className="stats-year-btn size-7 sm:size-9 inline-flex items-center justify-center rounded-lg border border-border bg-white text-gray-600 shadow-xs hover:border-orange-300 hover:text-orange-700 hover:bg-orange-50 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Next year"
                disabled={year >= 2100}
                onClick={() => onYearChange(year + 1)}
              >
                <ChevronRight className="size-3.5 sm:size-4" />
              </button>
            </div>
          )}

          {/* Heatmap Grid */}
          <div className="stats-heatmap-scroll overflow-x-auto pb-2">
            <div
              className="stats-heatmap grid gap-[3px] min-w-[720px] p-1"
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
                    const isFuture = Boolean(day.is_future)
                    const isToday = day.date === todayStr
                    const level = getDayLevel(day.cards, isFuture)
                    const title = getDayTitle(day, isToday)
                    const bgClass = isFuture ? futureLevelClasses[level] : pastLevelClasses[level]

                    return (
                      <button
                        key={day.date}
                        type="button"
                        className={cn(
                          'stats-day relative aspect-square w-full rounded-[2px] border-0 p-0 transition-transform duration-150 hover:scale-125 focus-visible:outline-2 focus-visible:outline-orange-400 cursor-pointer',
                          bgClass,
                          isToday && 'ring-2 ring-orange-600 ring-offset-1 ring-offset-card z-10 scale-110 shadow-sm font-bold',
                        )}
                        title={title}
                        onMouseEnter={() => setTooltipText(title)}
                        onMouseLeave={() => setTooltipText('Rê chuột lên các ô để xem chi tiết học tập.')}
                      />
                    )
                  })}
                </div>
              ))}
            </div>
          </div>

          {/* Dynamic Hover Tooltip */}
          <div className="stats-tooltip min-h-[1.25rem] mt-2 text-center text-xs sm:text-[0.86rem] text-gray-500 font-medium">
            {tooltipText}
          </div>

          {/* Bottom Metrics Row */}
          {showMetrics && (
            <div className="stats-metrics mt-3 pt-2.5 border-t border-border/80 grid grid-cols-2 sm:flex sm:flex-wrap sm:items-center sm:justify-between gap-2 sm:gap-3 text-xs sm:text-[0.95rem] text-gray-700">
              <div className="stats-metric flex flex-col sm:flex-row sm:items-center whitespace-nowrap">
                <span className="text-muted-foreground sm:text-gray-700">Trung bình hàng ngày:</span>
                <strong className="text-[#E05C07] font-bold sm:ml-1 text-sm sm:text-base">
                  {(overview?.metrics?.daily_average_cards ?? 0).toLocaleString('vi-VN')} thẻ
                </strong>
              </div>

              <div className="stats-metric flex flex-col sm:flex-row sm:items-center whitespace-nowrap">
                <span className="text-muted-foreground sm:text-gray-700">Tỷ lệ ngày học:</span>
                <strong className="text-[#E05C07] font-bold sm:ml-1 text-sm sm:text-base">
                  {(overview?.metrics?.days_learned_percent ?? 0).toLocaleString('vi-VN')}%
                </strong>
              </div>

              <div className="stats-metric flex flex-col sm:flex-row sm:items-center whitespace-nowrap">
                <span className="text-muted-foreground sm:text-gray-700">Chuỗi học dài nhất:</span>
                <strong className="text-[#E05C07] font-bold sm:ml-1 text-base">
                  {(overview?.metrics?.longest_streak_days ?? 0).toLocaleString('vi-VN')} ngày
                </strong>
              </div>

              <div className="stats-metric flex flex-col sm:flex-row sm:items-center whitespace-nowrap">
                <span className="text-muted-foreground sm:text-gray-700">Chuỗi học hiện tại:</span>
                <strong className="text-[#E05C07] font-bold sm:ml-1 text-base">
                  {(overview?.metrics?.current_streak_days ?? 0).toLocaleString('vi-VN')} ngày
                </strong>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  )
}
