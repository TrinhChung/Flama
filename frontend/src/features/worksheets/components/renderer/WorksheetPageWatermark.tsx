import type { PageBranding } from './pageBranding'

/** Refined, non-distracting watermark overlays (mandatory protection). */
export function WorksheetPageWatermark({
  watermarkText,
  watermarkOpacity,
  watermarkLayout,
}: Pick<PageBranding, 'watermarkText' | 'watermarkOpacity' | 'watermarkLayout'>) {
  if (watermarkLayout === 'diagonal_grid') {
    return (
      <div
        aria-hidden="true"
        className="absolute -top-[25%] -left-[25%] w-[150%] h-[150%] pointer-events-none select-none z-30 flex flex-col justify-between overflow-hidden py-4"
        style={{ opacity: watermarkOpacity }}
      >
        {Array.from({ length: 8 }).map((_, rIdx) => (
          <div
            key={`wm-row-${rIdx}`}
            className="flex justify-around whitespace-nowrap font-medium text-[12px] sm:text-[13px] tracking-[6px] text-slate-700"
            style={{
              transform: `rotate(-28deg) translateX(${rIdx % 2 === 0 ? '0px' : '-70px'})`,
            }}
          >
            {Array.from({ length: 6 }).map((_, cIdx) => (
              <span key={`wm-token-${cIdx}`} className="px-8">
                {watermarkText} &bull;
              </span>
            ))}
          </div>
        ))}
      </div>
    )
  }

  if (watermarkLayout === 'margin_bounds') {
    return (
      <div
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none select-none z-30 flex justify-between overflow-hidden p-1"
        style={{ opacity: watermarkOpacity * 1.5 }}
      >
        {/* Left margin vertical stripe */}
        <div className="flex flex-col justify-around text-[10px] tracking-[3px] font-semibold text-slate-700 [writing-mode:vertical-rl] rotate-180 select-none">
          <span>{watermarkText} &bull; FLAMA WORKSHEET &bull; {watermarkText}</span>
          <span>{watermarkText} &bull; FLAMA WORKSHEET &bull; {watermarkText}</span>
        </div>

        {/* Right margin vertical stripe */}
        <div className="flex flex-col justify-around text-[10px] tracking-[3px] font-semibold text-slate-700 [writing-mode:vertical-rl] select-none">
          <span>{watermarkText} &bull; FLAMA WORKSHEET &bull; {watermarkText}</span>
          <span>{watermarkText} &bull; FLAMA WORKSHEET &bull; {watermarkText}</span>
        </div>
      </div>
    )
  }

  return null
}
