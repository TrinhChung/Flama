import type { ReactNode } from 'react'

const INK_COLOR_SWATCHES = [
  { label: 'Đỏ', color: '#e11d48' },
  { label: 'Xanh dương', color: '#2563eb' },
  { label: 'Xanh lá', color: '#16a34a' },
  { label: 'Cam', color: '#ea580c' },
  { label: 'Tím', color: '#9333ea' },
  { label: 'Đen', color: '#0f172a' },
]

/** Row of round ink swatches; `children` renders after them (e.g. a custom color input). */
export function ColorSwatchPicker({
  value,
  onChange,
  children,
}: {
  value: string
  onChange: (color: string) => void
  children?: ReactNode
}) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {INK_COLOR_SWATCHES.map((p) => {
        const isSelected = value === p.color
        return (
          <button
            key={p.color}
            type="button"
            onClick={() => onChange(p.color)}
            className={`size-5 rounded-full transition-all flex items-center justify-center ${
              isSelected
                ? 'ring-2 ring-primary ring-offset-1 scale-110 shadow-xs'
                : 'opacity-70 hover:opacity-100 hover:scale-105'
            }`}
            style={{ backgroundColor: p.color }}
            title={p.label}
          >
            {isSelected && <span className="text-[9px] text-white font-bold leading-none">✓</span>}
          </button>
        )
      })}
      {children}
    </div>
  )
}
