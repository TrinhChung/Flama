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
    <div className="relative flex flex-col items-center justify-start h-full h-[100dvh] max-h-[100dvh] w-full overflow-y-auto p-2.5 sm:p-4 md:p-6 text-foreground">
      <AmbientBackground />
      <main className="relative z-10 w-full max-w-2xl my-auto rounded-2xl sm:rounded-3xl border border-border/40 bg-card/90 backdrop-blur-md shadow-2xl shadow-primary/5 dark:shadow-none flex flex-col max-h-[calc(100dvh-1.25rem)] sm:max-h-[calc(100dvh-2rem)] md:max-h-[calc(100dvh-3rem)] overflow-hidden">
        {/* Header pinned top */}
        <div className="shrink-0 p-3.5 sm:p-5 md:p-6 pb-2.5 sm:pb-3 border-b border-border/25">
          <div className="flex items-center justify-between pb-2 mb-2 sm:pb-2.5 sm:mb-2.5 border-b border-border/15">
            <Button asChild variant="ghost" size="sm" className="-ml-1.5 sm:-ml-2 h-7 sm:h-8 rounded-full text-xs sm:text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
              <Link to="/dashboard">
                <ArrowLeft className="mr-1.5 size-3.5 sm:size-4 shrink-0" /> {t('page.back_to_dashboard')}
              </Link>
            </Button>
            <span className="text-[10px] sm:text-xs text-muted-foreground/80 font-medium px-2 py-0.5 rounded-full bg-muted/40">
              {t('page.prepare_session')}
            </span>
          </div>

          <div className="space-y-0.5 sm:space-y-1">
            <p className="text-[10px] sm:text-[11px] font-bold uppercase tracking-[0.18em] text-orange-600 dark:text-orange-400">
              {t('page.prepare_session')}
            </p>
            <h1 className="text-base sm:text-xl md:text-2xl font-bold tracking-tight">{t('page.choose_template')}</h1>
            <p className="text-xs sm:text-sm leading-4.5 sm:leading-5 text-muted-foreground">
              {compositionGroups.some((group) => group.compositions.length > 1) || compositionGroups.length > 1
                ? `${deckName ? t('page.deck_multiple_types', { deckName }) : t('page.scope_multiple_types')} `
                : ''}
              {t('page.choose_template_desc')}
            </p>
          </div>
        </div>

        {/* Scrollable selector body */}
        <div className="flex-1 min-h-0 overflow-y-auto p-3.5 sm:p-5 md:p-6">
          {error ? (
            <div className="mb-4">
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
            className="mt-1"
          />
        </div>
      </main>
    </div>
  )
}
