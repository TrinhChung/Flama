import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { BarChart2 } from 'lucide-react'

interface StudyCompletionBreakdownProps {
  totalRatings: number
  againCount: number
  hardCount: number
  goodCount: number
  easyCount: number
}

export function StudyCompletionBreakdown({
  totalRatings,
  againCount,
  hardCount,
  goodCount,
  easyCount,
}: StudyCompletionBreakdownProps) {
  const { t } = useTranslation('study')

  if (totalRatings <= 0) return null

  return (
    <div className="space-y-1.5 sm:space-y-2 text-left">
      <div className="flex items-center justify-between text-xs font-medium text-muted-foreground px-0.5">
        <span className="flex items-center gap-1.5">
          <BarChart2 className="size-3.5 text-muted-foreground" />
          {t('completion.ratings_detail')}
        </span>
        <span>{t('completion.ratings_count', { count: totalRatings })}</span>
      </div>

      <div className="grid grid-cols-4 gap-1.5 sm:gap-2 text-center text-xs">
        <div className="p-1.5 sm:p-2 rounded-xl bg-rose-500/10 border border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300">
          <span className="block text-[10px] sm:text-[11px] font-medium opacity-80">
            {t('completion.ratings.again')}
          </span>
          <span className="text-xs sm:text-sm font-bold">{againCount}</span>
        </div>
        <div className="p-1.5 sm:p-2 rounded-xl bg-amber-500/10 border border-amber-200 dark:border-amber-900/40 text-amber-700 dark:text-amber-300">
          <span className="block text-[10px] sm:text-[11px] font-medium opacity-80">
            {t('completion.ratings.hard')}
          </span>
          <span className="text-xs sm:text-sm font-bold">{hardCount}</span>
        </div>
        <div className="p-1.5 sm:p-2 rounded-xl bg-blue-500/10 border border-blue-200 dark:border-blue-900/40 text-blue-700 dark:text-blue-300">
          <span className="block text-[10px] sm:text-[11px] font-medium opacity-80">
            {t('completion.ratings.good')}
          </span>
          <span className="text-xs sm:text-sm font-bold">{goodCount}</span>
        </div>
        <div className="p-1.5 sm:p-2 rounded-xl bg-emerald-500/10 border border-emerald-200 dark:border-emerald-900/40 text-emerald-700 dark:text-emerald-300">
          <span className="block text-[10px] sm:text-[11px] font-medium opacity-80">
            {t('completion.ratings.easy')}
          </span>
          <span className="text-xs sm:text-sm font-bold">{easyCount}</span>
        </div>
      </div>
    </div>
  )
}
