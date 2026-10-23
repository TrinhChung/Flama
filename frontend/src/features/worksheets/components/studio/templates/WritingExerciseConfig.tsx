import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { WritingExerciseCopy } from '../../../config/writingExercises'
import type { WorksheetLayoutOptions } from '../../../types'
import { LayoutOptionCheckbox, OptionPill, OptionTile } from '../controls/LayoutOptionControls'
import type { StudioLayoutTabProps } from '../StudioLayoutTab'

const LINE_COUNTS = [1, 2, 3, 4, 5, 6, 8]
const LINE_STYLES: { id: NonNullable<WorksheetLayoutOptions['writing_line_style']>; label: string }[] = [
  { id: 'dashed', label: '--- Nét đứt (Dashed)' },
  { id: 'solid', label: '─── Nét liền (Solid)' },
]

/** Prompt, answer-line count/style and visibility toggles shared by sentence and grammar sheets. */
export function WritingExerciseConfig({
  copy,
  layoutOptions,
  setLayoutOptions,
}: { copy: WritingExerciseCopy } & Pick<StudioLayoutTabProps, 'layoutOptions' | 'setLayoutOptions'>) {
  const linesCount = layoutOptions.writing_lines_count ?? 3
  return (
    <div className="space-y-3 pt-3 border-t border-border/60">
      <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
        {copy.title}
      </h4>
      <div className="space-y-2.5 bg-muted/20 p-3 rounded-xl border border-border/80">
        {/* Exercise prompt */}
        <div className="space-y-1.5">
          <Label className="text-xs font-semibold">{copy.promptLabel}</Label>
          <Input
            value={layoutOptions.exercise_prompt ?? copy.promptDefault}
            onChange={(e) =>
              setLayoutOptions((prev) => ({
                ...prev,
                exercise_prompt: e.target.value,
              }))
            }
            className="h-8 text-xs font-medium"
            placeholder={copy.promptPlaceholder}
          />
          <div className="flex items-center gap-1 flex-wrap pt-0.5">
            {copy.promptSuggestions.map((pText) => (
              <button
                key={pText}
                type="button"
                onClick={() =>
                  setLayoutOptions((prev) => ({
                    ...prev,
                    exercise_prompt: pText,
                  }))
                }
                className="text-[10px] px-2 py-0.5 rounded-md border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              >
                {pText}
              </button>
            ))}
          </div>
        </div>

        {/* Number of writing lines */}
        <div className="space-y-1 pt-1">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-semibold">{copy.linesLabel}</Label>
            <span className="text-xs font-bold text-primary">
              {linesCount} dòng
            </span>
          </div>
          <div className="flex items-center gap-1">
            {LINE_COUNTS.map((n) => (
              <OptionPill
                key={n}
                active={linesCount === n}
                onClick={() =>
                  setLayoutOptions((prev) => ({
                    ...prev,
                    writing_lines_count: n,
                  }))
                }
                className="flex-1 h-7.5 text-xs"
              >
                {n}
              </OptionPill>
            ))}
          </div>
          {copy.linesHint && (
            <p className="text-[10px] text-muted-foreground">
              {copy.linesHint}
            </p>
          )}
        </div>

        {/* Writing line style */}
        <div className="space-y-1 pt-1">
          <Label className="text-xs font-semibold">Kiểu đường kẻ:</Label>
          <div className="grid grid-cols-2 gap-1.5">
            {LINE_STYLES.map((st) => (
              <OptionTile
                key={st.id}
                active={(layoutOptions.writing_line_style || 'dashed') === st.id}
                onClick={() =>
                  setLayoutOptions((prev) => ({
                    ...prev,
                    writing_line_style: st.id,
                  }))
                }
                className="py-1.5 px-2 rounded-lg border text-xs font-medium transition-all"
              >
                {st.label}
              </OptionTile>
            ))}
          </div>
        </div>

        {/* Visibility toggles */}
        <div className="space-y-1.5 pt-1 text-xs">
          {copy.toggles.map((toggle) => (
            <LayoutOptionCheckbox
              key={toggle.field}
              field={toggle.field}
              label={toggle.label}
              defaultChecked={true}
              layoutOptions={layoutOptions}
              setLayoutOptions={setLayoutOptions}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
