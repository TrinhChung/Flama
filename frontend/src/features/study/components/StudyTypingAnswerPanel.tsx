import '@/shared/config/i18n'
import { useEffect, useId, useRef, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, Lightbulb, SkipForward } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import type { AnswerMaskCell } from '../typing/typingAnswer'
import { useTypingAnswer } from '../typing/useTypingAnswer'

export type StudyTypingAnswerPanelProps = {
  /** Accepted answers of this card; the first one drives the mask and hints. */
  answers: readonly string[]
  showLength: boolean
  hints: boolean
  revealed: boolean
  disabled?: boolean
  onReveal: () => void
}

function AnswerMask({ cells, concealLength }: { cells: AnswerMaskCell[]; concealLength: boolean }) {
  if (concealLength) {
    const shown = cells.filter((cell) => cell.kind === 'char' && cell.revealed)
    if (!shown.length) return null
    return (
      <p className="text-base font-semibold tracking-wide text-foreground" aria-hidden="true">
        {shown.map((cell) => (cell.kind === 'char' ? cell.char : '')).join('')}…
      </p>
    )
  }
  return (
    <div className="flex flex-wrap items-end gap-1" aria-hidden="true">
      {cells.map((cell, index) => (cell.kind === 'space' ? (
        <span key={index} className="w-2.5" />
      ) : (
        <span
          key={index}
          className={cn(
            'inline-flex h-8 min-w-6 items-center justify-center border-b-2 px-0.5 text-base font-semibold',
            cell.revealed ? 'border-orange-400 text-foreground' : 'border-border text-transparent',
          )}
        >
          {cell.revealed ? cell.char : '•'}
        </span>
      )))}
    </div>
  )
}

/**
 * Host-rendered typing input of a typing Study mode. The frontend alone
 * compares the answer: correct flips the card, incorrect asks to retype, and
 * the learner still chooses the rating with the normal buttons.
 */
export function StudyTypingAnswerPanel({
  answers,
  showLength,
  hints,
  revealed,
  disabled = false,
  onReveal,
}: StudyTypingAnswerPanelProps) {
  const { t } = useTranslation('study')
  const typing = useTypingAnswer({ answers, revealed, onCorrect: onReveal })
  const inputRef = useRef<HTMLInputElement>(null)
  const feedbackId = useId()
  const incorrect = typing.outcome === 'incorrect'
  const characterCount = typing.mask.filter((cell) => cell.kind === 'char').length

  useEffect(() => {
    if (incorrect) inputRef.current?.select()
  }, [incorrect, typing.attempts])

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      // Enter that confirms an IME conversion is not a submission.
      if (event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) return
      // The page shortcut handler skips prevented events, so this Enter never
      // also counts as "Good" once the card flips.
      event.preventDefault()
      if (!disabled) typing.submit()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      inputRef.current?.blur()
    }
  }

  if (revealed) {
    const details = typing.outcome === 'correct'
      ? [
          t('typing.correct'),
          typing.attempts > 1 ? t('typing.attempts', { count: typing.attempts }) : null,
          typing.hintsUsed > 0 ? t('typing.hints_used', { count: typing.hintsUsed }) : null,
        ]
      : typing.outcome === 'skipped'
        ? [
            t('typing.skipped'),
            typing.wrongAttempts > 0 ? t('typing.wrong_attempts', { count: typing.wrongAttempts }) : null,
            typing.hintsUsed > 0 ? t('typing.hints_used', { count: typing.hintsUsed }) : null,
          ]
        : []
    const typed = typing.outcome === 'correct' ? '' : typing.value.trim()
    return (
      <section
        aria-label={t('typing.aria_label')}
        className="study-typing-panel shrink-0 px-3 pt-2 sm:px-4"
      >
        <div className="mx-auto w-full max-w-2xl space-y-1 rounded-2xl border border-border/80 bg-card/90 px-3.5 py-2.5 shadow-xs">
          {details.length ? (
            <p
              role="status"
              className={cn(
                'flex items-center gap-1.5 text-sm font-semibold',
                typing.outcome === 'correct' ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400',
              )}
            >
              {typing.outcome === 'correct'
                ? <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
                : <SkipForward className="size-4 shrink-0" aria-hidden="true" />}
              {details.filter(Boolean).join(' · ')}
            </p>
          ) : null}
          {typed ? (
            <p className="text-xs text-muted-foreground">
              {t('typing.your_answer')}: <span className="font-medium text-foreground">{typed}</span>
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">
            {t('typing.answers')}: <span className="font-medium text-foreground">{answers.join(' · ')}</span>
          </p>
        </div>
      </section>
    )
  }

  return (
    <section aria-label={t('typing.aria_label')} className="study-typing-panel shrink-0 px-3 pt-2 sm:px-4">
      <div className="mx-auto w-full max-w-2xl space-y-2 rounded-2xl border border-border/80 bg-card/90 p-3 shadow-xs">
        {showLength || typing.hintsUsed > 0 ? (
          <div className="flex items-end justify-between gap-2">
            <AnswerMask cells={typing.mask} concealLength={!showLength} />
            {showLength ? (
              <span className="shrink-0 text-[11px] text-muted-foreground">{t('typing.length', { count: characterCount })}</span>
            ) : null}
          </div>
        ) : null}
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (!disabled) typing.submit()
          }}
        >
          <Input
            ref={inputRef}
            autoFocus
            value={typing.value}
            onChange={(event) => typing.setValue(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('typing.placeholder')}
            aria-label={t('typing.aria_label')}
            aria-invalid={incorrect || undefined}
            aria-describedby={feedbackId}
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            enterKeyHint="done"
            className="h-11 flex-1 rounded-xl bg-background text-base"
          />
          <Button type="submit" disabled={disabled || !typing.value.trim()} className="h-11 shrink-0 rounded-xl px-4 font-semibold">
            {t('typing.check')}
          </Button>
        </form>
        <div className="flex items-center justify-between gap-2">
          <p
            id={feedbackId}
            role="status"
            aria-live="polite"
            className={cn('min-w-0 text-xs', incorrect ? 'font-semibold text-rose-600 dark:text-rose-400' : 'text-muted-foreground')}
          >
            {incorrect ? t('typing.incorrect') : <span className="hidden sm:inline">{t('typing.keyboard_hint')}</span>}
          </p>
          <div className="flex shrink-0 items-center gap-1.5">
            {hints && typing.maxHints > 0 ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={typing.revealHint}
                disabled={typing.hintsUsed >= typing.maxHints}
                className="h-8 rounded-xl text-xs"
              >
                <Lightbulb className="size-3.5 text-amber-500" aria-hidden="true" />
                {t('typing.hint')}
                <span className="tabular-nums text-muted-foreground">
                  {t('typing.hint_progress', { used: typing.hintsUsed, max: typing.maxHints })}
                </span>
              </Button>
            ) : null}
            <Button type="button" variant="ghost" size="sm" onClick={onReveal} disabled={disabled} className="h-8 rounded-xl text-xs">
              <SkipForward className="size-3.5" aria-hidden="true" />
              {t('typing.skip')}
            </Button>
          </div>
        </div>
      </div>
    </section>
  )
}
