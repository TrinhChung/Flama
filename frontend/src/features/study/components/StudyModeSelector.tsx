import { Layers } from 'lucide-react'
import type { StudyCompositionGroup } from '../types'

export type StudyModeSelectorProps = {
  groups: StudyCompositionGroup[]
  selectedCompositionId?: string | null
  onSelectComposition: (compositionId: string) => void
  disabled?: boolean
  className?: string
}

export function StudyModeSelector({
  groups,
  selectedCompositionId = null,
  onSelectComposition,
  disabled = false,
  className = '',
}: StudyModeSelectorProps) {
  if (groups.length === 0) return null

  return (
    <div
      className={`study-mode-selector space-y-4 ${className}`}
      aria-label="Chọn kiểu thẻ để học"
    >
      {groups.map((group) => (
        <section key={group.note_type_id} className="space-y-2" aria-labelledby={`note-type-${group.note_type_id}-label`}>
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <span className="flex size-7 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400">
              <Layers className="size-4" aria-hidden="true" />
            </span>
            <span id={`note-type-${group.note_type_id}-label`}>{group.note_type_name}</span>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {group.compositions.map((composition) => {
              const isSelected = selectedCompositionId === composition.composition_id
              return (
                <button
                  key={composition.composition_id}
                  type="button"
                  disabled={disabled}
                  onClick={() => onSelectComposition(composition.composition_id)}
                  className={`rounded-xl border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/60 disabled:cursor-not-allowed disabled:opacity-60 ${
                    isSelected
                      ? 'border-orange-500 bg-orange-500/10 text-orange-700 dark:text-orange-300'
                      : 'border-border/80 bg-background text-foreground hover:border-orange-300 hover:bg-orange-500/5 dark:hover:border-orange-800'
                  }`}
                  aria-pressed={isSelected}
                >
                  <span className="block text-sm font-semibold">{composition.template_name}</span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {composition.context_kind === 'installed_source'
                      ? 'Thẻ gốc từ bộ đã cài'
                      : composition.context_kind === 'installed_local'
                        ? 'Thẻ riêng trong bộ đã cài'
                        : 'Thẻ trong bộ của bạn'}
                  </span>
                </button>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
