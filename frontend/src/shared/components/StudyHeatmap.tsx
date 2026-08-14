import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { ChevronLeft, ChevronRight } from '@/shared/components/Icons'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { HeatmapDay, HeatmapOverviewData } from '@/shared/types/heatmap'

function getPercentile(arr: number[], p: number): number {
  if (arr.length === 0) return 0
  const index = (p / 100) * (arr.length - 1)
  const lower = Math.floor(index)
  const upper = Math.ceil(index)
  const weight = index - lower
  return Math.round(arr[lower] * (1 - weight) + arr[upper] * weight)
}

type HeatmapStats = {
  effectiveMax: number
  peakCards: number
}

function calculateMaxAndPeak(days: HeatmapDay[], isFuture: boolean): HeatmapStats {
  const values = days
    .filter((d) => (isFuture ? d.is_future : !d.is_future) && d.cards > 0)
    .map((d) => d.cards)
    .sort((a, b) => a - b)

  if (values.length === 0) return { effectiveMax: 20, peakCards: 0 }

  const peakCards = values[values.length - 1]
  let effectiveMax = peakCards

  // Outlier protection if user has >= 10 active days and a single massive peak
  if (values.length >= 10) {
    const p95 = getPercentile(values, 95)
    if (peakCards > p95 * 2.5) {
      effectiveMax = Math.max(20, Math.round(p95 * 1.6))
    }
  }

  return { effectiveMax: Math.max(20, effectiveMax), peakCards }
}

/**
 * Power/Root scale normalization (x^0.60).
 * Expands medium and high-volume days so every step is visually distinct up to the peak day.
 */
function getDayLevelPower(cards: number, effectiveMax: number): number {
  if (!cards || cards <= 0) return 0
  const score = Math.pow(Math.min(1.2, cards / effectiveMax), 0.6)

  if (score >= 0.95) return 7 // Đạt đỉnh / Kỷ lục
  if (score >= 0.76) return 6 // Rất cao
  if (score >= 0.58) return 5 // Khá cao
  if (score >= 0.42) return 4 // Trung bình
  if (score >= 0.28) return 3 // Trung bình thấp
  if (score >= 0.15) return 2 // Nhẹ nhàng
  return 1 // Khởi động
}

function getTodayStr(): string {
  const d = new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getDayTitle(day: HeatmapDay, isToday: boolean, isPeak: boolean): string {
  const todayLabel = isToday ? ' (Hôm nay)' : ''
  if (day.is_future) {
    return `${day.date}${todayLabel}: ${day.cards.toLocaleString('vi-VN')} thẻ đến hạn`
  }
  if (!day.cards) return `${day.date}${todayLabel}: Chưa học`
  if (isPeak) {
    return `🔥 ${day.date}${todayLabel} [KỶ LỤC NĂM]: ${day.cards.toLocaleString('vi-VN')} thẻ · ${day.minutes.toLocaleString('vi-VN')} phút`
  }
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

// Past days: 8 levels (0..7) pure vibrant Flama palette
const pastLevelClasses = [
  'stats-day--level-0 bg-[#EAE0D8]',
  'stats-day--level-1 bg-[#FFE8D9]',
  'stats-day--level-2 bg-[#FFD2B8]',
  'stats-day--level-3 bg-[#FFB488]',
  'stats-day--level-4 bg-[#FF9354]',
  'stats-day--level-5 bg-[#FF7020]',
  'stats-day--level-6 bg-[#EE4D00]',
  'stats-day--level-7 bg-[#C93200]',
]

// Future days: 8 levels (0..7) pastel orange progression
const futureLevelClasses = [
  'stats-day--future-level-0 bg-[#F5EFE9]/60',
  'stats-day--future-level-1 bg-[#FFF3EC]',
  'stats-day--future-level-2 bg-[#FFE5D6]',
  'stats-day--future-level-3 bg-[#FFCFB7]',
  'stats-day--future-level-4 bg-[#FFB594]',
  'stats-day--future-level-5 bg-[#FF956B]',
  'stats-day--future-level-6 bg-[#FF723F]',
  'stats-day--future-level-7 bg-[#E8551A]',
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

  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const todayRef = useRef<HTMLButtonElement>(null)

  const scrollToToday = useCallback(() => {
    if (scrollContainerRef.current && todayRef.current) {
      const container = scrollContainerRef.current
      const todayCell = todayRef.current
      const containerRect = container.getBoundingClientRect()
      const todayRect = todayCell.getBoundingClientRect()

      if (containerRect.width > 0) {
        const relativeLeft = todayRect.left - containerRect.left + container.scrollLeft
        const targetScrollLeft = relativeLeft - containerRect.width / 2 + todayRect.width / 2
        container.scrollLeft = Math.max(0, targetScrollLeft)
      }
    }
  }, [])

  useEffect(() => {
    if (loading) return

    const timer = setTimeout(scrollToToday, 50)
    window.addEventListener('resize', scrollToToday)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('resize', scrollToToday)
    }
  }, [overview, loading, year, scrollToToday])

  const todayData = overview?.today
  const summaryText = todayData
    ? `Hôm nay đã học ${todayData.cards.toLocaleString('vi-VN')} thẻ trong ${todayData.minutes.toFixed(
        2,
      )} phút (${todayData.cards > 0 ? (todayData.minutes * 60 / todayData.cards).toFixed(2) : '0.00'}s/thẻ)`
    : `Hôm nay đã học 0 thẻ trong 0.00 phút (0.00s/thẻ)`

  // Group heatmap into 53 weeks x 7 days
  const heatmap = overview?.heatmap || []
  const pastStats = useMemo(() => calculateMaxAndPeak(heatmap, false), [heatmap])
  const futureStats = useMemo(() => calculateMaxAndPeak(heatmap, true), [heatmap])

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
          <div ref={scrollContainerRef} className="stats-heatmap-scroll overflow-x-auto pb-2">
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
                    const stats = isFuture ? futureStats : pastStats
                    const isPeak = !isFuture && day.cards > 0 && day.cards === pastStats.peakCards && pastStats.peakCards >= 10
                    const level = getDayLevelPower(day.cards, stats.effectiveMax)
                    const title = getDayTitle(day, isToday, isPeak)
                    const bgClass = isFuture ? futureLevelClasses[level] : pastLevelClasses[level]

                    return (
                      <button
                        key={day.date}
                        ref={isToday ? todayRef : undefined}
                        type="button"
                        className={cn(
                          'stats-day relative aspect-square w-full rounded-[2px] border-0 p-0 transition-transform duration-150 hover:scale-125 focus-visible:outline-2 focus-visible:outline-orange-400 cursor-pointer',
                          bgClass,
                          isPeak && 'ring-1 ring-[#EE4D00] shadow-[0_0_8px_rgba(238,77,0,0.65)] z-20 scale-105 font-bold',
                          isToday && 'ring-2 ring-orange-600 ring-offset-1 ring-offset-card z-30 scale-110 shadow-sm font-bold',
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

          {/* Dynamic Hover Tooltip & 8-Level Legend */}
          <div className="stats-footer-info min-h-[1.5rem] mt-2 flex flex-col sm:flex-row items-center justify-between gap-1.5 px-1 text-xs text-muted-foreground font-medium">
            <div className="stats-tooltip text-center sm:text-left text-gray-500 font-medium">
              {tooltipText}
            </div>

            <div className="stats-legend flex items-center gap-1 text-[11px] text-muted-foreground select-none shrink-0" aria-hidden="true">
              <span className="text-[10px] mr-0.5">Ít</span>
              <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#EAE0D8]" title="0 thẻ" />
              <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#FFE8D9]" title="Mức 1" />
              <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#FFD2B8]" title="Mức 2" />
              <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#FFB488]" title="Mức 3" />
              <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#FF9354]" title="Mức 4" />
              <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#FF7020]" title="Mức 5" />
              <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#EE4D00]" title="Mức 6" />
              <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#C93200] ring-1 ring-[#EE4D00] shadow-[0_0_4px_rgba(238,77,0,0.5)]" title="Mức 7 (Đạt đỉnh)" />
              <span className="text-[10px] ml-0.5">Nhiều 🔥</span>
            </div>
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
