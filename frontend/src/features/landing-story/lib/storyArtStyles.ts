import type { CSSProperties } from 'react'

// Shared palette and CSS-variable helpers for the story illustrations.

export const palette = {
  charcoal: '#211a17',
  paper: '#fff8ef',
  ground: '#32261f',
  hills: '#2a201c',
  red: '#ef3303',
  orange: '#fe6808',
  amber: '#fea00e',
  core: '#fff4ec',
  rim: '#f6a35c',
  personDark: '#6e4c3b',
  personDim: '#5b4033',
  personShadow: '#3f2e27',
  personWarm: '#a86d50',
  personLight: '#c98b67',
  personSoft: '#e2b08a',
  personDeep: '#8a5a44',
  wood: '#8a5a44',
  ink: '#3b2c25',
  leaf: '#a8a24e',
  sheet: '#efe2cc',
} as const

/** `0..1` progress of a beat inside the current scene, as a CSS expression. */
export function beat(start: number, duration = 0.2) {
  return `clamp(0, calc((var(--t) - ${start}) / ${duration}), 1)`
}

export function appear(start: number, duration = 0.2): CSSProperties {
  return { opacity: beat(start, duration) }
}

/** Reveals a stroke drawn with `pathLength={1}`. */
export function draw(start: number, duration = 0.25): CSSProperties {
  return { strokeDasharray: 1, strokeDashoffset: `calc(1 - ${beat(start, duration)})` }
}

export function rise(start: number, duration = 0.2, distance = 24): CSSProperties {
  return {
    opacity: beat(start, duration),
    transform: `translateY(calc((1 - ${beat(start, duration)}) * ${distance}px))`,
  }
}

export function grow(start: number, duration = 0.25, origin = 'center bottom'): CSSProperties {
  return {
    transform: `scale(${beat(start, duration)})`,
    transformBox: 'fill-box',
    transformOrigin: origin,
  }
}

export type Pose = 'offer' | 'reach' | 'rest' | 'up' | 'point'

export const HANDS: Record<Pose, [number, number]> = {
  offer: [62, -118],
  reach: [70, -134],
  rest: [24, -58],
  up: [44, -196],
  point: [80, -160],
}

/** Where a person's front hand ends up, in stage coordinates. */
export function handOf(x: number, y: number, pose: Pose, scale = 1, flip = false) {
  const [hx, hy] = HANDS[pose]
  return { x: x + hx * scale * (flip ? -1 : 1), y: y + hy * scale }
}

