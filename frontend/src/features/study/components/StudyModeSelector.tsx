import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Layers, SlidersHorizontal } from 'lucide-react'
import type { StudyCompositionGroup } from '../types'

export type StudyModeSelectorProps = {
  groups: StudyCompositionGroup[]
  selectedCompositionId?: string | null
  onSelectComposition: (compositionId: string) => void
  /** Cards per composition, shown next to the source label when present. */
  noteCounts?: Record<string, number> | null
  /** Adds a "field setup" action to each composition that has template inputs. */
  onConfigureComposition?: (compositionId: string) => void
  canConfigureComposition?: (compositionId: string) => boolean
  isCompositionCustomized?: (compositionId: string) => boolean
  disabled?: boolean
  className?: string
}

export function StudyModeSelector({
  groups,
  selectedCompositionId = null,
  onSelectComposition,
  noteCounts,
  onConfigureComposition,
  canConfigureComposition,
  isCompositionCustomized,
  disabled = false,
  className = '',
}: StudyModeSelectorProps) {
  const { t } = useTranslation('study')

  if (groups.length === 0) return null

  return (
    <div
      className={`study-mode-selector space-y-4 ${className}`}
      aria-label={t('mode_selector.aria_label')}
    >
      {groups.map((group) => (
        <section key={group.note_type_id} className="space-y-2" aria-labelledby={`note-type-${group.note_type_id}-label`}>
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <span className="flex size-7 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400">
              <Layers className="size-4" aria-hidden="true" />
            </span>
            <span id={`note-type-${group.note_type_id}-label`}>{group.note_type_name}</span>
          </div>
          {/* Rows with a setup action read better full width than in two columns. */}
          <div className={onConfigureComposition ? 'grid gap-2' : 'grid gap-2 sm:grid-cols-2'}>
            {group.compositions.map((composition) => {
              const id = composition.composition_id
              const isSelected = selectedCompositionId === id
              const count = noteCounts?.[id]
              const customized = Boolean(isCompositionCustomized?.(id))
              const configurable = Boolean(onConfigureComposition && (canConfigureComposition?.(id) ?? true))
              const stateClass = isSelected
                ? 'border-orange-500/80 bg-orange-500/10 text-orange-700 shadow-xs dark:text-orange-300'
                : 'border-border/40 bg-card/80 text-foreground hover:border-orange-400/60 hover:bg-orange-500/5 hover:shadow-xs dark:hover:border-orange-700/60'
              const content = (
                <>
                  <span className="block text-sm font-semibold">{composition.template_name}</span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {composition.context_kind === 'installed_source'
                      ? t('mode_selector.source_installed')
                      : composition.context_kind === 'installed_local'
                        ? t('mode_selector.custom_installed')
                        : t('mode_selector.user_deck')}
                    {typeof count === 'number' ? ` · ${t('mode_selector.card_count', { count })}` : ''}
                    {customized ? ` · ${t('mode_selector.custom_fields')}` : ''}
                  </span>
                </>
              )
              if (!configurable) {
                return (
                  <button
                    key={id}
                    type="button"
                    disabled={disabled}
                    onClick={() => onSelectComposition(id)}
                    className={`rounded-xl border px-4 py-3 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/60 disabled:cursor-not-allowed disabled:opacity-60 ${stateClass}`}
                    aria-pressed={isSelected}
                  >
                    {content}
                  </button>
                )
              }
              return (
                <div
                  key={id}
                  className={`flex items-stretch overflow-hidden rounded-xl border transition-colors has-[:disabled]:opacity-60 ${stateClass}`}
                >
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onSelectComposition(id)}
                    className="min-w-0 flex-1 px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-orange-500/60 disabled:cursor-not-allowed"
                    aria-pressed={isSelected}
                  >
                    {content}
                  </button>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onConfigureComposition?.(id)}
                    className="flex shrink-0 items-center gap-1.5 border-l border-border/70 px-3 text-xs font-semibold text-muted-foreground transition-colors hover:bg-orange-500/10 hover:text-orange-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-orange-500/60 disabled:cursor-not-allowed dark:hover:text-orange-300"
                    title={t('mode_selector.configure_fields_for', { name: composition.template_name })}
                    aria-label={t('mode_selector.configure_fields_for', { name: composition.template_name })}
                  >
                    <SlidersHorizontal className="size-3.5" aria-hidden="true" />
                    <span className="hidden sm:inline">{t('mode_selector.configure_fields')}</span>
                  </button>
                </div>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
