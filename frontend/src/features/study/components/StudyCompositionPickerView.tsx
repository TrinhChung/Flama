import '@/shared/config/i18n'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { PageError } from '@/shared/components/PageState'
import { StudyModeSelector } from './StudyModeSelector'
import type { StudyCompositionGroup } from '../types'

export type StudyCompositionPickerViewProps = {
  deckName?: string | null
  error?: unknown
  compositionGroups: StudyCompositionGroup[]
  selectedCompositionId?: string | null
  onSelectComposition: (compositionId: string) => void
  disabled?: boolean
}

export function StudyCompositionPickerView({
  deckName,
  error,
  compositionGroups,
  selectedCompositionId,
  onSelectComposition,
  disabled = false,
}: StudyCompositionPickerViewProps) {
  const { t } = useTranslation('study')

  return (
    <div className="flex h-screen h-[100dvh] w-full items-center justify-center overflow-y-auto bg-background p-4 text-foreground sm:p-6">
      <main className="w-full max-w-2xl rounded-2xl border border-border/80 bg-card p-5 shadow-sm sm:p-7">
        <div className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-orange-600 dark:text-orange-400">
            {t('page.prepare_session')}
          </p>
          <h1 className="text-2xl font-bold tracking-tight">{t('page.choose_card_type')}</h1>
          <p className="text-sm leading-6 text-muted-foreground">
            {deckName
              ? t('page.deck_multiple_types', { deckName })
              : t('page.scope_multiple_types')}{' '}
            {t('page.choose_single_type_desc')}
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
  )
}
