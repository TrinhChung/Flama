import '@/shared/config/i18n'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowRightLeft, LoaderCircle, LogOut, MonitorSmartphone, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type StudySessionTakeoverState =
  | 'idle'
  | 'requesting'
  | 'waiting'
  | 'yielding'
  | 'unavailable'

type StudySessionConflictProps = {
  deckName?: string | null
  takeoverState: StudySessionTakeoverState
  onTakeover: () => void
  onForceTakeover?: () => void
  onLeave: () => void
}

export function StudySessionConflict({
  deckName,
  takeoverState,
  onTakeover,
  onForceTakeover,
  onLeave,
}: StudySessionConflictProps) {
  const { t } = useTranslation('study')
  const titleRef = useRef<HTMLHeadingElement>(null)
  const unavailable = takeoverState === 'unavailable'
  const pending = takeoverState === 'requesting'
    || takeoverState === 'waiting'
    || takeoverState === 'yielding'

  useEffect(() => {
    titleRef.current?.focus()
  }, [])

  const statusMessage = takeoverState === 'waiting'
    ? t('conflict.request_received')
    : takeoverState === 'requesting'
      ? t('conflict.requesting_handover')
      : takeoverState === 'yielding'
        ? t('conflict.saving_handover')
        : unavailable
          ? t('conflict.no_response')
          : t('conflict.default_instruction')

  return (
    <section
      className="w-full max-w-xl mx-auto py-6 px-4"
      aria-labelledby="study-session-conflict-title"
      aria-describedby="study-session-conflict-description study-session-conflict-status"
    >
      <div className="rounded-2xl border border-amber-200/80 bg-card p-6 text-center shadow-xs space-y-6 dark:border-amber-900/50 sm:p-8">
        <div className="mx-auto inline-flex size-12 items-center justify-center rounded-xl border border-amber-200 bg-amber-500/10 text-amber-600 dark:border-amber-900/50 dark:text-amber-400">
          <MonitorSmartphone className="size-6" aria-hidden="true" />
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium text-muted-foreground">
            {deckName || t('page.session_title')}
          </div>
          <h1
            ref={titleRef}
            id="study-session-conflict-title"
            tabIndex={-1}
            className="text-2xl font-bold tracking-tight text-foreground outline-none"
          >
            {t('conflict.title')}
          </h1>
          <p
            id="study-session-conflict-description"
            className="mx-auto max-w-md text-sm leading-relaxed text-muted-foreground"
          >
            {t('conflict.desc_1')} {t('conflict.desc_2')}
          </p>
        </div>

        <div
          id="study-session-conflict-status"
          className="rounded-xl border border-amber-200 bg-amber-500/10 p-4 text-sm text-amber-800 dark:border-amber-900/50 dark:text-amber-200"
          role={unavailable ? 'alert' : 'status'}
          aria-live={unavailable ? 'assertive' : 'polite'}
          aria-atomic="true"
        >
          {statusMessage}
        </div>

        <div className="flex flex-col-reverse justify-center gap-3 sm:flex-row flex-wrap">
          <Button
            type="button"
            variant="outline"
            disabled={takeoverState === 'yielding'}
            onClick={onLeave}
            className="w-full sm:w-auto"
          >
            <LogOut className="mr-2 size-4" aria-hidden="true" />
            {t('conflict.leave_tab')}
          </Button>
          <Button
            type="button"
            variant={unavailable ? 'outline' : 'default'}
            disabled={pending}
            onClick={onTakeover}
            className="w-full sm:w-auto"
            aria-busy={pending}
          >
            {pending ? (
              <LoaderCircle className="mr-2 size-4 animate-spin" aria-hidden="true" />
            ) : (
              <ArrowRightLeft className="mr-2 size-4" aria-hidden="true" />
            )}
            {pending
              ? t('conflict.switching')
              : unavailable
                ? t('conflict.resend_request')
                : t('conflict.switch_to_tab')}
          </Button>
          {onForceTakeover && (unavailable || takeoverState === 'idle') ? (
            <Button
              type="button"
              variant={unavailable ? 'default' : 'ghost'}
              onClick={onForceTakeover}
              className={cn(
                'w-full sm:w-auto text-xs sm:text-sm font-semibold',
                unavailable
                  ? 'bg-amber-600 hover:bg-amber-700 text-white dark:bg-amber-600 dark:hover:bg-amber-700 shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
              title={t('conflict.force_open_tooltip')}
            >
              <Zap className="mr-2 size-4 text-amber-300" aria-hidden="true" />
              {t('conflict.force_open')}
            </Button>
          ) : null}
        </div>
      </div>
    </section>
  )
}
