import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'

interface StudyCompletionStatsGridProps {
  totalRatings: number
  timeFormatted: string
  retentionRate: number
}

export function StudyCompletionStatsGrid({
  totalRatings,
  timeFormatted,
  retentionRate,
}: StudyCompletionStatsGridProps) {
  const { t } = useTranslation('study')

  return (
    <div className="grid grid-cols-3 gap-2 sm:gap-3">
      <div className="rounded-xl border border-border/60 bg-muted/20 p-2.5 sm:p-3.5 space-y-0.5">
        <span className="block text-[11px] sm:text-xs font-medium text-muted-foreground">
          {t('completion.reviewed_cards')}
        </span>
        <span className="text-base sm:text-lg font-bold text-foreground">
          {t('completion.cards_count', { count: totalRatings })}
        </span>
      </div>

      <div className="rounded-xl border border-border/60 bg-muted/20 p-2.5 sm:p-3.5 space-y-0.5">
        <span className="block text-[11px] sm:text-xs font-medium text-muted-foreground">
          {t('completion.time')}
        </span>
        <span
          className="text-base sm:text-lg font-bold text-foreground whitespace-nowrap block"
          title={timeFormatted}
        >
          {timeFormatted}
        </span>
      </div>

      <div className="rounded-xl border border-border/60 bg-muted/20 p-2.5 sm:p-3.5 space-y-0.5">
        <span className="block text-[11px] sm:text-xs font-medium text-muted-foreground">
          {t('completion.accuracy')}
        </span>
        <span className="text-base sm:text-lg font-bold text-emerald-600 dark:text-emerald-400">
          {retentionRate}%
        </span>
      </div>
    </div>
  )
}
