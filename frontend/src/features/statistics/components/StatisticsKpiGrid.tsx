import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import type { HeatmapOverviewData } from '@/shared/types/heatmap'
import type { TodayFutureStats } from '../types'

interface StatisticsKpiGridProps {
  stats: TodayFutureStats
  overview?: HeatmapOverviewData
  isFetching?: boolean
}

export function StatisticsKpiGrid({
  stats,
  overview,
  isFetching,
}: StatisticsKpiGridProps) {
  const { t } = useTranslation('statistics')

  const workloadLabel =
    stats.totals.daily_load < 15
      ? t('kpi.workload.level_light')
      : stats.totals.daily_load < 35
      ? t('kpi.workload.level_optimal')
      : t('kpi.workload.level_heavy')

  return (
    <div
      className={cn(
        'grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3.5 transition-opacity duration-200',
        isFetching && 'opacity-80',
      )}
    >
      {/* Card 1: Today */}
      <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border/70 bg-card p-3.5 sm:p-4 shadow-[0_1px_3px_rgba(0,0,0,0.03)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.2)] hover:border-primary/30 hover:shadow-md transition-all duration-200 active:scale-[0.99]">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[1.5px] bg-gradient-to-r from-transparent via-primary/25 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <div>
          <div className="flex items-center justify-between gap-1.5">
            <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 truncate">
              {t('kpi.today.title')}
            </span>
            <span className="inline-flex shrink-0 items-center rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary tabular-nums">
              {t('kpi.today.minutes', { minutes: stats.today.minutes.toFixed(1) })}
            </span>
          </div>
          <div className="mt-2 sm:mt-2.5">
            <div className="flex items-baseline gap-1">
              <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground tabular-nums">
                {stats.today.cards.toLocaleString()}
              </span>
              <span className="text-xs font-medium text-muted-foreground">
                {t('kpi.today.cards_unit')}
              </span>
            </div>
          </div>
        </div>
        <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
          <span>{t('kpi.today.speed_label')}</span>
          <span className="font-medium text-foreground/80">
            {t('kpi.today.speed_value', { speed: stats.today.sec_per_card.toFixed(1) })}
          </span>
        </div>
      </div>

      {/* Card 2: Streak */}
      <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border/70 bg-card p-3.5 sm:p-4 shadow-[0_1px_3px_rgba(0,0,0,0.03)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.2)] hover:border-amber-500/30 hover:shadow-md transition-all duration-200 active:scale-[0.99]">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[1.5px] bg-gradient-to-r from-transparent via-amber-500/25 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <div>
          <div className="flex items-center justify-between gap-1.5">
            <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 truncate">
              {t('kpi.streak.title')}
            </span>
            <span className="inline-flex shrink-0 items-center rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-400 tabular-nums">
              {t('kpi.streak.percent_days', { percent: overview?.metrics?.days_learned_percent ?? 0 })}
            </span>
          </div>
          <div className="mt-2 sm:mt-2.5">
            <div className="flex items-baseline gap-1">
              <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground tabular-nums">
                {(overview?.metrics?.current_streak_days ?? 0).toLocaleString()}
              </span>
              <span className="text-xs font-medium text-muted-foreground">
                {t('kpi.streak.days_unit')}
              </span>
            </div>
          </div>
        </div>
        <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
          <span>{t('kpi.streak.longest_label')}</span>
          <span className="font-medium text-foreground/80">
            {t('kpi.streak.longest_value', { days: overview?.metrics?.longest_streak_days ?? 0 })}
          </span>
        </div>
      </div>

      {/* Card 3: Forecast */}
      <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border/70 bg-card p-3.5 sm:p-4 shadow-[0_1px_3px_rgba(0,0,0,0.03)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.2)] hover:border-blue-500/30 hover:shadow-md transition-all duration-200 active:scale-[0.99]">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[1.5px] bg-gradient-to-r from-transparent via-blue-500/25 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <div>
          <div className="flex items-center justify-between gap-1.5">
            <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 truncate">
              {t('kpi.forecast.title')}
            </span>
            <span className="inline-flex shrink-0 items-center rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold text-blue-700 dark:bg-blue-500/15 dark:text-blue-300 tabular-nums">
              {t('kpi.forecast.tomorrow', { count: stats.totals.due_tomorrow })}
            </span>
          </div>
          <div className="mt-2 sm:mt-2.5">
            <div className="flex items-baseline gap-1">
              <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground tabular-nums">
                {stats.totals.total_reviews.toLocaleString()}
              </span>
              <span className="text-xs font-medium text-muted-foreground">
                {t('kpi.forecast.reviews_unit')}
              </span>
            </div>
          </div>
        </div>
        <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
          <span>{t('kpi.forecast.avg_label')}</span>
          <span className="font-medium text-foreground/80">
            {t('kpi.forecast.avg_value', { avg: stats.totals.avg_reviews_per_day.toFixed(1) })}
          </span>
        </div>
      </div>

      {/* Card 4: Daily Workload */}
      <div className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border/70 bg-card p-3.5 sm:p-4 shadow-[0_1px_3px_rgba(0,0,0,0.03)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.2)] hover:border-emerald-500/30 hover:shadow-md transition-all duration-200 active:scale-[0.99]">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[1.5px] bg-gradient-to-r from-transparent via-emerald-500/25 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        <div>
          <div className="flex items-center justify-between gap-1.5">
            <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 truncate">
              {t('kpi.workload.title')}
            </span>
            <span
              className={cn(
                'inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-semibold',
                stats.totals.daily_load < 15
                  ? 'text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 dark:bg-emerald-500/15'
                  : stats.totals.daily_load < 35
                  ? 'text-teal-700 dark:text-teal-400 bg-teal-500/10 dark:bg-teal-500/15'
                  : 'text-amber-700 dark:text-amber-400 bg-amber-500/10 dark:bg-amber-500/15',
              )}
            >
              {workloadLabel}
            </span>
          </div>
          <div className="mt-2 sm:mt-2.5">
            <div className="flex items-baseline gap-1">
              <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground tabular-nums">
                {stats.totals.daily_load.toFixed(1)}
              </span>
              <span className="text-xs font-medium text-muted-foreground">
                {t('kpi.workload.cards_per_day')}
              </span>
            </div>
          </div>
        </div>
        <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>{t('kpi.workload.target_label')}</span>
          <span className="font-medium text-foreground/80">
            {t('kpi.workload.target_value')}
          </span>
        </div>
      </div>
    </div>
  )
}
