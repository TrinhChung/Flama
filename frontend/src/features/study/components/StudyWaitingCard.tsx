import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Clock3, Layers3, LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'

type StudyWaitingCardProps = {
  deckName?: string | null
  counts: { new: number; learning: number; due: number }
  nowMs: number
  pendingLearningCount: number
  nextEligibleAtMs: number | null
  nextDueAtMs: number | null
  isBusy: boolean
  onCommit: () => void
}

export function StudyWaitingCard({
  deckName,
  counts,
  nowMs,
  pendingLearningCount,
  nextEligibleAtMs,
  nextDueAtMs,
  isBusy,
  onCommit,
}: StudyWaitingCardProps) {
  const { t, i18n } = useTranslation('study')

  const remainingSeconds = nextEligibleAtMs === null
    ? 0
    : Math.max(0, Math.ceil((nextEligibleAtMs - nowMs) / 1000))

  const formatRemaining = (seconds: number) => {
    if (seconds <= 0) return t('waiting.reloading_cards')
    const minutes = Math.floor(seconds / 60)
    const remainingSec = seconds % 60
    if (minutes <= 0) {
      return t('waiting.remaining_seconds', { seconds: remainingSec })
    }
    return t('waiting.remaining_minutes_seconds', {
      minutes,
      seconds: remainingSec.toString().padStart(2, '0'),
    })
  }

  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <div className="w-full max-w-xl mx-auto py-6 px-4">
      <div className="rounded-2xl border border-amber-200/80 dark:border-amber-900/50 bg-card p-6 sm:p-8 space-y-6 text-center shadow-xs">
        <div className="inline-flex items-center justify-center size-12 rounded-xl bg-amber-500/10 border border-amber-200 dark:border-amber-900/50 text-amber-600 dark:text-amber-400 mx-auto">
          <Clock3 className="size-6" />
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium text-muted-foreground">
            {deckName || t('page.session_title')}
          </div>
          <h2 className="text-2xl font-bold text-foreground tracking-tight">
            {t('waiting.title')}
          </h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
            {t('waiting.desc')}
          </p>
        </div>

        <div
          className="rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-500/10 p-4"
          aria-live="polite"
        >
          <div className="text-sm font-semibold text-amber-700 dark:text-amber-300">
            {t('waiting.resume_in', { time: formatRemaining(remainingSeconds) })}
          </div>
          {nextDueAtMs !== null ? (
            <div className="mt-1 text-xs text-muted-foreground">
              {t('waiting.nominal_due', {
                time: new Date(nextDueAtMs).toLocaleTimeString(locale),
              })}
            </div>
          ) : null}
        </div>

        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div className="rounded-xl border border-border/60 bg-muted/20 p-3">
            <span className="block text-muted-foreground">{t('waiting.status_new')}</span>
            <strong className="text-base text-foreground">{counts.new}</strong>
          </div>
          <div className="rounded-xl border border-border/60 bg-muted/20 p-3">
            <span className="block text-amber-600 dark:text-amber-400">
              {t('waiting.status_learn')}
            </span>
            <strong className="text-base text-foreground">
              {Math.max(counts.learning, pendingLearningCount)}
            </strong>
          </div>
          <div className="rounded-xl border border-border/60 bg-muted/20 p-3">
            <span className="block text-muted-foreground">{t('waiting.status_due')}</span>
            <strong className="text-base text-foreground">{counts.due}</strong>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <Layers3 className="size-4" />
            <span>{t('waiting.pending_cards', { count: pendingLearningCount })}</span>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={isBusy}
            onClick={onCommit}
            className="w-full sm:w-auto"
          >
            <LogOut className="size-4 mr-2" />
            {t('waiting.end_now')}
          </Button>
        </div>
      </div>
    </div>
  )
}
