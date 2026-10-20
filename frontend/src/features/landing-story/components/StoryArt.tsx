import type { CSSProperties, ReactNode, Ref } from 'react'
import { HANDS, palette, type Pose } from '../lib/storyArtStyles'

// Shared illustration kit for the landing story. Every scene uses these pieces so
// people, hands, flames and machines keep one scale, one rounding and one light.

export function StoryDefs() {
  return (
    <svg width="0" height="0" aria-hidden="true" focusable="false" className="absolute">
      <defs>
        <linearGradient id="story-flame" x1="10" y1="54" x2="51" y2="6" gradientUnits="userSpaceOnUse">
          <stop stopColor={palette.red} />
          <stop offset=".58" stopColor={palette.orange} />
          <stop offset="1" stopColor={palette.amber} />
        </linearGradient>
        <radialGradient id="story-glow">
          <stop offset="0" stopColor={palette.amber} stopOpacity=".5" />
          <stop offset=".45" stopColor={palette.orange} stopOpacity=".16" />
          <stop offset="1" stopColor={palette.orange} stopOpacity="0" />
        </radialGradient>
        <linearGradient id="story-wordmark" x1="0" x2="1" y1="0" y2="0">
          <stop stopColor="#e8501c" />
          <stop offset=".5" stopColor="#f97316" />
          <stop offset="1" stopColor="#f59e0b" />
        </linearGradient>
        <linearGradient id="story-skin" x1="0" x2="0" y1="520" y2="600" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor={palette.personSoft} />
          <stop offset="1" stopColor={palette.personSoft} stopOpacity="0" />
        </linearGradient>
        {Object.entries(groundTones).flatMap(([tone, colors]) =>
          (['hills', 'ground'] as const).map((layer) => (
            <linearGradient
              key={`${layer}-${tone}`}
              id={`story-${layer}-${tone}`}
              x1="0"
              x2="0"
              y1="420"
              y2="600"
              gradientUnits="userSpaceOnUse"
            >
              <stop offset="0" stopColor={colors[layer]} />
              <stop offset=".62" stopColor={colors[layer]} />
              <stop offset="1" stopColor={colors[layer]} stopOpacity="0" />
            </linearGradient>
          )),
        )}
      </defs>
    </svg>
  )
}

const FLAME_BODY =
  'M35 3c3 12-8 15-5 26 1-7-5-10-5-16C14 23 8 32 10 43c2 12 12 18 23 18 13 0 23-9 23-22 0-9-5-18-14-25 1 9-3 13-6 17 2-11 1-18-1-28Z'
const FLAME_CORE =
  'M33 57c-7 0-12-5-12-12 0-6 4-10 9-15-1 7 5 9 4 15 3-4 5-8 4-14 5 4 8 9 8 15 0 7-6 11-13 11Z'

type FlameProps = {
  x: number
  y: number
  size?: number
  glow?: boolean
  style?: CSSProperties
}

/** The Flama flame silhouette, anchored at its base. */
export function Flame({ x, y, size = 1, glow = false, style }: FlameProps) {
  return (
    <g style={style}>
      <g transform={`translate(${x} ${y})`}>
        {glow ? <circle cy={-22 * size} r={70 * size} fill="url(#story-glow)" /> : null}
        <g transform={`scale(${size * 0.62})`}>
          <g className="story-loop story-flicker">
            <g transform="translate(-33 -61)">
              <path fill="url(#story-flame)" d={FLAME_BODY} />
              <path fill={palette.core} d={FLAME_CORE} opacity=".94" />
            </g>
          </g>
        </g>
      </g>
    </g>
  )
}

type EmberProps = {
  x: number
  y: number
  size: number
  emberRef?: Ref<SVGGElement>
}

/** The guiding ember. In pinned mode its position comes from CSS variables. */
export function Ember({ x, y, size, emberRef }: EmberProps) {
  const style = {
    '--ex': x,
    '--ey': y,
    '--es': size,
    transform: 'translate(calc(var(--ex) * 1px), calc(var(--ey) * 1px)) scale(var(--es))',
  } as CSSProperties
  return (
    <g ref={emberRef} style={style} className="story-ember">
      <circle cy={-22} r={96} fill="url(#story-glow)" />
      <Flame x={0} y={0} size={1} />
    </g>
  )
}

type PersonProps = {
  x: number
  y: number
  fill: string
  rim?: string
  scale?: number
  flip?: boolean
  pose?: Pose
  style?: CSSProperties
  children?: ReactNode
}

/** A stylised person standing at (x, y). Unflipped people face right. */
export function Person({
  x,
  y,
  fill,
  rim,
  scale = 1,
  flip = false,
  pose = 'rest',
  style,
  children,
}: PersonProps) {
  const [hx, hy] = HANDS[pose]
  const elbowX = (14 + hx) / 2 + 6
  const elbowY = (-126 + hy) / 2 + 20
  return (
    <g style={style}>
      <g transform={`translate(${x} ${y}) scale(${flip ? -scale : scale} ${scale})`}>
        <path d="M-34 0C-38-60-36-112-22-136Q0-150 22-136C36-112 38-60 34 0Z" fill={fill} />
        <circle cy={-170} r={24} fill={fill} />
        {rim ? (
          <g stroke={rim} strokeLinecap="round" fill="none" opacity=".7">
            <path d="M10-191A24 24 0 0 1 12-149" strokeWidth={4} />
            <path d="M24-128C33-104 35-60 33-8" strokeWidth={3} />
          </g>
        ) : null}
        <path
          d={`M14-126Q${elbowX} ${elbowY} ${hx} ${hy}`}
          stroke={fill}
          strokeWidth={13}
          strokeLinecap="round"
          fill="none"
        />
        <circle cx={hx} cy={hy} r={9} fill={fill} />
        {children}
      </g>
    </g>
  )
}

const groundTones = {
  dark: { hills: palette.hills, ground: palette.ground },
  light: { hills: '#f6e6d2', ground: '#efd9bf' },
} as const

/** Rolling ground shared by every scene; it fades out at the bottom of the frame. */
export function Ground({ tone = 'dark' }: { tone?: 'dark' | 'light' }) {
  return (
    <g>
      <path d="M0 455Q200 400 400 440T800 430V600H0Z" fill={`url(#story-hills-${tone})`} />
      <path d="M0 505Q400 475 800 505V600H0Z" fill={`url(#story-ground-${tone})`} />
    </g>
  )
}

export function Wheel({
  cx,
  cy,
  r,
  stroke,
  spokes = 8,
  width = 6,
  style,
}: {
  cx: number
  cy: number
  r: number
  stroke: string
  spokes?: number
  width?: number
  style?: CSSProperties
}) {
  return (
    <g style={{ transformBox: 'fill-box', transformOrigin: 'center', ...style }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={stroke} strokeWidth={width} />
      <circle cx={cx} cy={cy} r={width * 1.4} fill={stroke} />
      {Array.from({ length: spokes }, (_, index) => {
        const angle = (index / spokes) * Math.PI * 2
        return (
          <line
            key={index}
            x1={cx}
            y1={cy}
            x2={cx + Math.cos(angle) * r}
            y2={cy + Math.sin(angle) * r}
            stroke={stroke}
            strokeWidth={width * 0.6}
            strokeLinecap="round"
          />
        )
      })}
    </g>
  )
}
