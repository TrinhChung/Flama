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
    if (!day.cards) return `${day.date}${todayLabel}: Chưa học`
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
  'stats-day--level-0 bg-[#EAE0D8] dark:bg-[#272320]',
  'stats-day--level-1 bg-[#FFE8D9] dark:bg-[#3D2517]',
  'stats-day--level-2 bg-[#FFD2B8] dark:bg-[#5C2E17]',
  'stats-day--level-3 bg-[#FFB488] dark:bg-[#7D3A16]',
  'stats-day--level-4 bg-[#FF9354] dark:bg-[#A34714]',
  'stats-day--level-5 bg-[#FF7020] dark:bg-[#CC5510]',
  'stats-day--level-6 bg-[#EE4D00] dark:bg-[#EE4D00]',
  'stats-day--level-7 bg-[#C93200] dark:bg-[#FF5D17]',
]

// Future days: 8 levels (0..7) soft, gentle slate-gray progression maintaining Flama's bright theme
const futureLevelClasses = [
  'stats-day--future-level-0 bg-[#F5EFEA] dark:bg-[#272320]',
  'stats-day--future-level-1 bg-[#E5E9EC] dark:bg-[#2F343B]',
  'stats-day--future-level-2 bg-[#D6DCDE] dark:bg-[#3D444E]',
  'stats-day--future-level-3 bg-[#C4CCD0] dark:bg-[#4C5562]',
  'stats-day--future-level-4 bg-[#B0BBC0] dark:bg-[#5C6675]',
  'stats-day--future-level-5 bg-[#9CA8AF] dark:bg-[#6D7888]',
  'stats-day--future-level-6 bg-[#88969F] dark:bg-[#7F8B9B]',
  'stats-day--future-level-7 bg-[#74838D] dark:bg-[#929EAE]',
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
  const [tooltipText, setTooltipText] = useState<string>('Rê chuột hoặc chạm vào các ô để xem chi tiết học tập.')
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const todayStr = overview?.today?.date || getTodayStr()

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
        container.scrollTo({ left: Math.max(0, targetScrollLeft), behavior: 'smooth' })
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
  const heatmap = overview?.heatmap
  const pastStats = useMemo(() => calculateMaxAndPeak(heatmap || [], false), [heatmap])
  const safeHeatmap = heatmap || []

  const firstDay = safeHeatmap[0]
  const leadingCount = firstDay
    ? (new Date(`${firstDay.date}T00:00:00Z`).getUTCDay() + 6) % 7
    : 0

  const allCells: Array<HeatmapDay | null> = [
    ...Array.from({ length: leadingCount }, () => null),
    ...safeHeatmap,
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
            <p className="stats-summary text-center text-sm sm:text-xl font-semibold text-primary tabular-nums mb-2 sm:mb-3 leading-tight">
              {summaryText}
            </p>
          )}

          {/* Year Navigation */}
          {showYearNav && (
            <div className="stats-nav flex items-center justify-center gap-2 mb-3 sm:mb-4">
              <button
                type="button"
                className="stats-year-btn size-7 sm:size-9 inline-flex items-center justify-center rounded-lg border border-border bg-card text-foreground shadow-xs hover:border-primary/50 hover:text-primary hover:bg-primary/10 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Previous year"
                disabled={year <= 1970}
                onClick={() => onYearChange(year - 1)}
              >
                <ChevronLeft className="size-3.5 sm:size-4" />
              </button>

              <div className="stats-year-label min-w-12 sm:min-w-16 text-center text-sm sm:text-base font-semibold text-foreground tabular-nums">
                {year}
              </div>

              <button
                type="button"
                className="stats-year-btn size-7 sm:size-9 inline-flex items-center justify-center rounded-lg border border-border bg-card text-foreground shadow-xs hover:border-primary/50 hover:text-primary hover:bg-primary/10 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Next year"
                disabled={year >= 2100}
                onClick={() => onYearChange(year + 1)}
              >
                <ChevronRight className="size-3.5 sm:size-4" />
              </button>
            </div>
          )}

          {/* Mobile swipe hint & today jump */}
          <div className="flex items-center justify-between text-[11px] text-muted-foreground sm:hidden mb-1.5 px-0.5 select-none">
            <span>← Vuốt ngang xem cả năm →</span>
            <button
              type="button"
              onClick={scrollToToday}
              className="font-medium text-primary active:opacity-70 transition-opacity underline underline-offset-2"
            >
              Về hôm nay
            </button>
          </div>

          {/* Heatmap Grid */}
          <div ref={scrollContainerRef} className="stats-heatmap-scroll overflow-x-auto pb-2 scroll-smooth">
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
                          className="stats-day aspect-square w-full rounded-[2px] bg-[#E9DDD4] dark:bg-[#272320] opacity-35"
                          aria-hidden="true"
                        />
                      )
                    }
                    const isFuture = Boolean(day.is_future)
                    const isToday = day.date === todayStr
                    const isSelected = selectedDate === day.date
                    const isPeak = !isFuture && day.cards > 0 && day.cards === pastStats.peakCards && pastStats.peakCards >= 10
                    // Unified intensity baseline: compare future cards against past historical study scale
                    const level = getDayLevelPower(day.cards, pastStats.effectiveMax)
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
                          isSelected && !isToday && 'ring-2 ring-primary ring-offset-1 ring-offset-card z-30 scale-125 shadow-md',
                        )}
                        title={title}
                        onClick={() => {
                          setSelectedDate(day.date)
                          setTooltipText(title)
                        }}
                        onMouseEnter={() => setTooltipText(title)}
                        onMouseLeave={() => {
                          if (!selectedDate) {
                            setTooltipText('Rê chuột hoặc chạm vào các ô để xem chi tiết học tập.')
                          }
                        }}
                      />
                    )
                  })}
                </div>
              ))}
            </div>
          </div>

          {/* Dynamic Hover / Tap Tooltip & Legend */}
          <div className="stats-footer-info min-h-[2rem] mt-2 flex flex-col sm:flex-row items-center justify-between gap-2 px-1 text-xs text-muted-foreground font-medium">
            <div className="stats-tooltip text-center sm:text-left text-foreground/90 font-medium px-2 py-1 rounded-md bg-muted/40 sm:bg-transparent w-full sm:w-auto">
              {tooltipText}
            </div>

            <div className="stats-legend flex flex-wrap items-center justify-center sm:justify-end gap-2 text-[11px] text-muted-foreground select-none shrink-0" aria-hidden="true">
              <div className="flex items-center gap-1">
                <span className="text-[10px] font-medium text-foreground/80">Đã học:</span>
                <span className="text-[10px] mr-0.5">Ít</span>
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#EAE0D8] dark:bg-[#272320]" title="0 thẻ" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#FFE8D9] dark:bg-[#3D2517]" title="Mức 1" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#FFD2B8] dark:bg-[#5C2E17]" title="Mức 2" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#FFB488] dark:bg-[#7D3A16]" title="Mức 3" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#FF9354] dark:bg-[#A34714]" title="Mức 4" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#FF7020] dark:bg-[#CC5510]" title="Mức 5" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#EE4D00] dark:bg-[#EE4D00]" title="Mức 6" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#C93200] dark:bg-[#FF5D17] ring-1 ring-[#EE4D00] shadow-[0_0_4px_rgba(238,77,0,0.5)]" title="Mức 7 (Đạt đỉnh)" />
                <span className="text-[10px] ml-0.5">Nhiều 🔥</span>
              </div>

              <span className="text-border mx-0.5 hidden sm:inline">•</span>

              <div className="flex items-center gap-1">
                <span className="text-[10px] font-medium text-foreground/80">Tới hạn:</span>
                <span className="text-[10px] mr-0.5">Ít</span>
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#F5EFEA] dark:bg-[#272320]" title="0 thẻ" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#E5E9EC] dark:bg-[#2F343B]" title="Tới hạn mức 1" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#C4CCD0] dark:bg-[#4C5562]" title="Tới hạn mức 3" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#9CA8AF] dark:bg-[#6D7888]" title="Tới hạn mức 5" />
                <span className="size-2.5 sm:size-3 rounded-[2px] bg-[#74838D] dark:bg-[#929EAE]" title="Tới hạn mức 7" />
                <span className="text-[10px] ml-0.5">Nhiều ⏳</span>
              </div>
            </div>
          </div>

          {/* Bottom Metrics Row */}
          {showMetrics && (
            <div className="stats-metrics mt-3 pt-3 border-t border-border/80 grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3 text-xs sm:text-sm">
              <div className="stats-metric rounded-lg border border-border/50 bg-muted/20 p-2 sm:border-0 sm:bg-transparent sm:p-0 flex flex-col sm:flex-row sm:items-baseline">
                <span className="text-muted-foreground">TB hàng ngày:</span>
                <strong className="text-primary font-bold sm:ml-1 text-sm sm:text-base tabular-nums">
                  {(overview?.metrics?.daily_average_cards ?? 0).toLocaleString('vi-VN')} thẻ
                </strong>
              </div>

              <div className="stats-metric rounded-lg border border-border/50 bg-muted/20 p-2 sm:border-0 sm:bg-transparent sm:p-0 flex flex-col sm:flex-row sm:items-baseline">
                <span className="text-muted-foreground">Tỷ lệ ngày học:</span>
                <strong className="text-primary font-bold sm:ml-1 text-sm sm:text-base tabular-nums">
                  {(overview?.metrics?.days_learned_percent ?? 0).toLocaleString('vi-VN')}%
                </strong>
              </div>

              <div className="stats-metric rounded-lg border border-border/50 bg-muted/20 p-2 sm:border-0 sm:bg-transparent sm:p-0 flex flex-col sm:flex-row sm:items-baseline">
                <span className="text-muted-foreground">Kỷ lục chuỗi:</span>
                <strong className="text-primary font-bold sm:ml-1 text-sm sm:text-base tabular-nums">
                  {(overview?.metrics?.longest_streak_days ?? 0).toLocaleString('vi-VN')} ngày
                </strong>
              </div>

              <div className="stats-metric rounded-lg border border-border/50 bg-muted/20 p-2 sm:border-0 sm:bg-transparent sm:p-0 flex flex-col sm:flex-row sm:items-baseline">
                <span className="text-muted-foreground">Chuỗi hiện tại:</span>
                <strong className="text-primary font-bold sm:ml-1 text-sm sm:text-base tabular-nums">
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
