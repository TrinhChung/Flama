import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Layers } from 'lucide-react'

interface StudyCompletionDeckStatusProps {
  counts: { new: number; learning: number; due: number }
}

export function StudyCompletionDeckStatus({ counts }: StudyCompletionDeckStatusProps) {
  const { t } = useTranslation('study')

  return (
    <div className="space-y-1.5 sm:space-y-2 text-left">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground px-0.5">
        <Layers className="size-3.5 text-muted-foreground" />
        <span>{t('completion.deck_status')}</span>
      </div>

      <div className="grid grid-cols-3 gap-1.5 sm:gap-2 text-center text-xs">
        <div className="p-2 sm:p-2.5 rounded-xl border border-border/60 bg-muted/20">
          <span className="block text-[10px] sm:text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
            {t('completion.status_new')}
          </span>
          <span className="text-xs sm:text-sm font-bold text-foreground">{counts.new}</span>
        </div>

        <div className="p-2 sm:p-2.5 rounded-xl border border-border/60 bg-muted/20">
          <span className="block text-[10px] sm:text-[11px] font-medium text-amber-600 dark:text-amber-400">
            {t('completion.status_learn')}
          </span>
          <span className="text-xs sm:text-sm font-bold text-foreground">{counts.learning}</span>
        </div>

        <div className="p-2 sm:p-2.5 rounded-xl border border-border/60 bg-muted/20">
          <span className="block text-[10px] sm:text-[11px] font-medium text-rose-600 dark:text-rose-400">
            {t('completion.status_due')}
          </span>
          <span className="text-xs sm:text-sm font-bold text-foreground">{counts.due}</span>
        </div>
      </div>
    </div>
  )
}
