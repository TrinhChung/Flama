import type { CSSProperties } from 'react'

/**
 * Reading / meaning / source-word pill next to a reference character. Font
 * sizes scale with the box size; pass only the values that should be shown.
 */
export function KanjiItemMeta({
  className,
  style,
  boxSize,
  reading,
  meaning,
  sourceWord,
}: {
  className: string
  style: CSSProperties
  boxSize: number
  reading?: string | false
  meaning?: string | false
  sourceWord?: string | false
}) {
  return (
    <div className={className} style={style}>
      {reading && (
        <span
          className="font-semibold text-slate-900 truncate"
          style={{ fontSize: `${Math.max(6, Math.min(11, Math.round(boxSize * 0.3)))}px`, lineHeight: 1.15 }}
          title={reading}
        >
          {reading}
        </span>
      )}
      {meaning && (
        <span
          className="text-slate-500 truncate"
          style={{ fontSize: `${Math.max(5.5, Math.min(10, Math.round(boxSize * 0.25)))}px`, lineHeight: 1.15 }}
          title={meaning}
        >
          {meaning}
        </span>
      )}
      {sourceWord && (
        <span
          className="text-slate-400 italic truncate"
          style={{
            fontSize: `${Math.max(5, Math.min(9, Math.round(boxSize * 0.23)))}px`,
            lineHeight: 1.1,
          }}
        >
          ({sourceWord})
        </span>
      )}
    </div>
  )
}
