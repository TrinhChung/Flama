import { memo } from 'react'

export interface KanjiGridBoxProps {
  char?: string
  gridStyle?: 'cross' | 'diagonal' | 'square'
  isTrace?: boolean
  isBlank?: boolean
  size?: number
  className?: string
  rounded?: boolean
  strokeColor?: string
  charColor?: string
}

export const KanjiGridBox = memo(function KanjiGridBox({
  char = '',
  gridStyle = 'cross',
  isTrace = false,
  isBlank = false,
  size = 36,
  className = '',
  rounded = false,
  strokeColor = '#64748b',
  charColor = '#0f172a',
}: KanjiGridBoxProps) {
  const half = size / 2
  const fontSize = Math.max(6, Math.round(size * 0.72))
  const yPos = Math.round(size * 0.76)
  const isSmall = size < 22
  const guideStroke = isSmall ? '0.6' : '1'
  const dashArray = isSmall ? '1 1' : '2 2'

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={`shrink-0 bg-white select-none ${rounded ? 'rounded-[3px]' : ''} ${className}`}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Outer border */}
      <rect
        x="0.5"
        y="0.5"
        width={size - 1}
        height={size - 1}
        fill="#ffffff"
        stroke={strokeColor}
        strokeWidth="1"
        rx={rounded ? 3 : 0}
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
            strokeWidth={guideStroke}
            strokeDasharray={dashArray}
          />
          <line
            x1={1}
            y1={half}
            x2={size - 1}
            y2={half}
            stroke="#cbd5e1"
            strokeWidth={guideStroke}
            strokeDasharray={dashArray}
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
            strokeWidth={isSmall ? '0.5' : '0.8'}
            strokeDasharray={dashArray}
          />
          <line
            x1={1}
            y1={size - 1}
            x2={size - 1}
            y2={1}
            stroke="#e2e8f0"
            strokeWidth={isSmall ? '0.5' : '0.8'}
            strokeDasharray={dashArray}
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
          fill={charColor}
          fontWeight="500"
        >
          {char}
        </text>
      )}
    </svg>
  )
})
