import { memo } from 'react'

export interface KanjiGridBoxProps {
  char?: string
  gridStyle?: 'cross' | 'diagonal' | 'square'
  isTrace?: boolean
  isBlank?: boolean
  size?: number
  className?: string
}

export const KanjiGridBox = memo(function KanjiGridBox({
  char = '',
  gridStyle = 'cross',
  isTrace = false,
  isBlank = false,
  size = 52,
  className = '',
}: KanjiGridBoxProps) {
  const half = size / 2
  const fontSize = Math.round(size * 0.72)
  const yPos = Math.round(size * 0.76)

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={`shrink-0 rounded-[4px] bg-white select-none ${className}`}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Outer border */}
      <rect
        x="0.5"
        y="0.5"
        width={size - 1}
        height={size - 1}
        fill="#ffffff"
        stroke="#94a3b8"
        strokeWidth="1.2"
        rx="4"
      />

      {/* Cross guidelines */}
      {(gridStyle === 'cross' || gridStyle === 'diagonal') && (
        <>
          <line
            x1={half}
            y1={1}
            x2={half}
            y2={size - 1}
            stroke="#cbd5e1"
            strokeWidth="1"
            strokeDasharray="2 2"
          />
          <line
            x1={1}
            y1={half}
            x2={size - 1}
            y2={half}
            stroke="#cbd5e1"
            strokeWidth="1"
            strokeDasharray="2 2"
          />
        </>
      )}

      {/* Diagonal guidelines (米字格) */}
      {gridStyle === 'diagonal' && (
        <>
          <line
            x1={1}
            y1={1}
            x2={size - 1}
            y2={size - 1}
            stroke="#e2e8f0"
            strokeWidth="0.8"
            strokeDasharray="2 2"
          />
          <line
            x1={1}
            y1={size - 1}
            x2={size - 1}
            y2={1}
            stroke="#e2e8f0"
            strokeWidth="0.8"
            strokeDasharray="2 2"
          />
        </>
      )}

      {/* Character inside */}
      {isTrace && char && (
        <text
          x={half}
          y={yPos}
          fontFamily="'Hiragino Kaku Gothic ProN', 'Yu Gothic', 'Meiryo', 'Noto Sans JP', sans-serif"
          fontSize={fontSize}
          textAnchor="middle"
          fill="#cbd5e1"
          fontWeight="300"
        >
          {char}
        </text>
      )}

      {!isTrace && !isBlank && char && (
        <text
          x={half}
          y={yPos}
          fontFamily="'Hiragino Kaku Gothic ProN', 'Yu Gothic', 'Meiryo', 'Noto Sans JP', sans-serif"
          fontSize={fontSize}
          textAnchor="middle"
          fill="#0f172a"
          fontWeight="500"
        >
          {char}
        </text>
      )}
    </svg>
  )
})
