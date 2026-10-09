import '@/shared/config/i18n'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { PageError } from '@/shared/components/PageState'
import { StudyHeaderToolbar } from './StudyHeaderToolbar'
import { StudyModeSelector } from './StudyModeSelector'
import type { StudyCompositionGroup } from '../types'

export type StudyCompositionPickerViewProps = {
  deckName?: string | null
  deckId?: string | null
  error?: unknown
  compositionGroups: StudyCompositionGroup[]
  selectedCompositionId?: string | null
  onSelectComposition: (compositionId: string) => void
  noteCounts?: Record<string, number> | null
  onConfigureComposition?: (compositionId: string) => void
  canConfigureComposition?: (compositionId: string) => boolean
  isCompositionCustomized?: (compositionId: string) => boolean
  disabled?: boolean
}

export function StudyCompositionPickerView({
  deckName,
  deckId,
  error,
  compositionGroups,
  selectedCompositionId,
  onSelectComposition,
  noteCounts,
  onConfigureComposition,
  canConfigureComposition,
  isCompositionCustomized,
  disabled = false,
}: StudyCompositionPickerViewProps) {
  const { t } = useTranslation('study')

  return (
    <div className="flex h-screen h-[100dvh] w-full flex-col overflow-hidden bg-background text-foreground">
      <div className="shrink-0 px-3 pt-2">
        <StudyHeaderToolbar deckName={deckName} deckId={deckId} />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full w-full max-w-2xl items-start justify-center p-4 sm:items-center sm:p-6">
          <main className="w-full rounded-2xl border border-border/80 bg-card p-5 shadow-sm sm:p-7">
            <div className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-orange-600 dark:text-orange-400">
                {t('page.prepare_session')}
              </p>
              <h1 className="text-2xl font-bold tracking-tight">{t('page.choose_template')}</h1>
              <p className="text-sm leading-6 text-muted-foreground">
                {deckName
                  ? t('page.deck_multiple_types', { deckName })
                  : t('page.scope_multiple_types')}{' '}
                {t('page.choose_template_desc')}
              </p>
            </div>

            {error ? (
              <div className="mt-4">
                <PageError error={error} />
              </div>
            ) : null}

            <StudyModeSelector
              groups={compositionGroups}
              selectedCompositionId={selectedCompositionId}
              onSelectComposition={onSelectComposition}
              noteCounts={noteCounts}
              onConfigureComposition={onConfigureComposition}
              canConfigureComposition={canConfigureComposition}
              isCompositionCustomized={isCompositionCustomized}
              disabled={disabled}
              className="mt-6"
            />

            <div className="mt-6 border-t border-border/70 pt-4">
              <Button asChild variant="outline">
                <Link to="/dashboard">{t('page.back_to_dashboard')}</Link>
              </Button>
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}
