import type { WorksheetEssayRowItem, WorksheetItem, WorksheetLayoutOptions } from '../../types'

/** Genkō yōshi grid: rows of square cells separated by optional spacer bands. */
export function EssayGridBody({
  items,
  options,
}: {
  items: WorksheetItem[]
  options: WorksheetLayoutOptions
}) {
  const gridColor = options.grid_color || '#475569'
  const boxStyle = options.box_style || 'square'
  const hasSpacer = options.has_spacer_band !== false
  const spacerHeight = Math.max(4, Math.min(24, Number(options.spacer_height || 10)))

  return (
    <div className="flex flex-col w-full my-auto">
      {items.map((rawItem, rIdx) => {
        const rowItem = rawItem as WorksheetEssayRowItem
        const cells = rowItem.cells || []

        return (
          <div key={rowItem.note_id || `essay-row-${rIdx}`} className="flex flex-col w-full">
            {/* Row of square cells */}
            <div className="flex w-full -space-x-px">
              {cells.map((cell, cIdx) => {
                const char = cell.char || ''
                const isBlank = cell.is_blank || !char
                const isTrace = Boolean(cell.is_trace)
                const isTitle = Boolean(cell.is_title)

                return (
                  <div
                    key={`cell-${rIdx}-${cIdx}`}
                    style={{
                      borderColor: gridColor,
                    }}
                    className="flex-1 aspect-square border relative flex items-center justify-center select-none overflow-hidden bg-white -mt-px first:-mt-0"
                  >
                    {/* Optional guideline lines */}
                    {boxStyle === 'cross' && (
                      <svg className="absolute inset-0 size-full pointer-events-none stroke-slate-300 stroke-dasharray-[2,2]">
                        <line x1="50%" y1="0" x2="50%" y2="100%" strokeWidth="0.75" />
                        <line x1="0" y1="50%" x2="100%" y2="50%" strokeWidth="0.75" />
                      </svg>
                    )}
                    {boxStyle === 'diagonal' && (
                      <svg className="absolute inset-0 size-full pointer-events-none stroke-slate-200 stroke-dasharray-[2,2]">
                        <line x1="50%" y1="0" x2="50%" y2="100%" strokeWidth="0.75" />
                        <line x1="0" y1="50%" x2="100%" y2="50%" strokeWidth="0.75" />
                        <line x1="0" y1="0" x2="100%" y2="100%" strokeWidth="0.5" stroke="#e2e8f0" />
                        <line x1="0" y1="100%" x2="100%" y2="0" strokeWidth="0.5" stroke="#e2e8f0" />
                      </svg>
                    )}
                    {/* Character content */}
                    {!isBlank && char && (
                      <span
                        className={`z-10 font-serif leading-none select-none ${
                          isTrace
                            ? 'text-slate-300 font-light'
                            : isTitle
                            ? 'text-slate-900 font-bold'
                            : 'text-slate-800 font-normal'
                        }`}
                        style={{
                          fontSize: 'clamp(10px, 1.4vw, 15px)',
                        }}
                      >
                        {char}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Spacer band between rows */}
            {hasSpacer && rIdx < items.length - 1 && (
              <div
                style={{
                  height: `${spacerHeight}px`,
                  borderColor: gridColor,
                }}
                className="w-full border-x border-b -mt-px bg-white"
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
