import { Layers } from 'lucide-react'
import type { AppliedComposition } from '../types'

export type StudyModeSelectorProps = {
  compositions?: AppliedComposition[]
  selectedCompositionId?: string | null
  onSelectComposition: (compositionId: string | null) => void
  disabled?: boolean
  className?: string
}

export function StudyModeSelector({
  compositions = [],
  selectedCompositionId = null,
  onSelectComposition,
  disabled = false,
  className = '',
}: StudyModeSelectorProps) {
  if (!compositions || compositions.length <= 1) {
    return null
  }

  return (
    <div
      className={`study-mode-selector flex items-center gap-1.5 p-1 bg-muted/60 dark:bg-zinc-900/60 backdrop-blur-sm rounded-lg border border-border/60 text-xs ${className}`}
      role="group"
      aria-label="Chế độ học và mẫu thẻ"
    >
      <div className="flex items-center gap-1 px-1.5 text-muted-foreground font-medium text-[11px] shrink-0">
        <Layers className="size-3.5 text-orange-500 shrink-0" />
        <span className="hidden sm:inline">Mẫu hiển thị:</span>
      </div>

      <button
        type="button"
        disabled={disabled}
        onClick={() => onSelectComposition(null)}
        className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all duration-150 ${
          selectedCompositionId === null
            ? 'bg-background text-foreground shadow-xs border border-border/80 font-bold'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted/80'
        }`}
      >
        Tất cả ({compositions.length})
      </button>

      {compositions.map((comp) => {
        const isSelected = selectedCompositionId === comp.composition_id
        return (
          <button
            key={comp.composition_id}
            type="button"
            disabled={disabled}
            onClick={() => onSelectComposition(comp.composition_id)}
            className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-150 truncate max-w-[140px] sm:max-w-[200px] ${
              isSelected
                ? 'bg-background text-orange-600 dark:text-orange-400 shadow-xs border border-orange-200 dark:border-orange-900/80 font-bold'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/80'
            }`}
            title={comp.template_name}
          >
            {comp.template_name}
          </button>
        )
      })}
    </div>
  )
}
