import '@/shared/config/i18n'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { PageError } from '@/shared/components/PageState'
import { AmbientBackground } from '@/components/ambient-background'
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
    <div className="relative flex min-h-[100dvh] w-full items-center justify-center overflow-y-auto p-3.5 sm:p-6 text-foreground">
      <AmbientBackground />
      <main className="relative z-10 w-full max-w-2xl rounded-3xl border border-border/40 bg-card/90 backdrop-blur-md p-5 sm:p-8 shadow-2xl shadow-primary/5 dark:shadow-none">
        <div className="flex items-center justify-between pb-3.5 mb-5 border-b border-border/25">
          <Button asChild variant="ghost" size="sm" className="-ml-2 rounded-full text-xs sm:text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
            <Link to="/dashboard">
              <ArrowLeft className="mr-1.5 size-4" /> {t('page.back_to_dashboard')}
            </Link>
          </Button>
          <span className="text-[11px] sm:text-xs text-muted-foreground/80 font-medium px-2.5 py-1 rounded-full bg-muted/40">
            {t('page.prepare_session')}
          </span>
        </div>

        <div className="space-y-1.5 sm:space-y-2">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-orange-600 dark:text-orange-400">
            {t('page.prepare_session')}
          </p>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">{t('page.choose_card_type')}</h1>
          <p className="text-xs sm:text-sm leading-5 sm:leading-6 text-muted-foreground">
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
          className="mt-5 sm:mt-6"
        />
      </main>
    </div>
  )
}
