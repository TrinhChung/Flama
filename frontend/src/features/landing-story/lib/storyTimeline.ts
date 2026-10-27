// Pure timeline math for the landing story. One scalar "story position" drives the
// whole journey: chapter index + local progress inside that chapter.

/** Local progress at which a chapter stops holding and starts handing off. */
export const HOLD_END = 0.8
/** The journey stops here inside the last chapter so the closing CTA stays put. */
export const LAST_CHAPTER_STOP = 0.6

const ENTER_START = -0.12
const ENTER_END = 0.04
const EXIT_START = 0.86
const EXIT_END = 1.02

export function clamp(value: number, min = 0, max = 1) {
  return Math.min(max, Math.max(min, value))
}

export function easeInOut(value: number) {
  const x = clamp(value)
  return x * x * (3 - 2 * x)
}

/**
 * Turns each chapter's raw local progress (0 when its top crosses the reading line,
 * 1 when its bottom does) into one story position.
 */
export function storyPosition(localProgress: number[]) {
  const count = localProgress.length
  if (count === 0) return 0
  const lastStop = count - 1 + LAST_CHAPTER_STOP
  for (let index = 0; index < count; index += 1) {
    const t = localProgress[index]
    if (t >= 0 && t < 1) return Math.min(lastStop, index + t)
  }
  if (localProgress[0] < 0) return 0
  return lastStop
}

/** Local progress (`t`) and visibility (`v`) of one scene at a story position. */
export function sceneState(position: number, index: number, count: number) {
  const local = position - index
  let visibility = 1
  if (index > 0 && local < ENTER_END) {
    visibility = clamp((local - ENTER_START) / (ENTER_END - ENTER_START))
  }
  if (index < count - 1 && local > EXIT_START) {
    visibility = Math.min(visibility, 1 - clamp((local - EXIT_START) / (EXIT_END - EXIT_START)))
  }
  return { t: clamp(local, -0.3, 1.3), v: visibility }
}

export type EmberAnchor = { x: number; y: number; size: number }

/** The guiding ember holds at each chapter's anchor, then travels to the next one. */
export function emberAt(position: number, anchors: EmberAnchor[]): EmberAnchor {
  const index = clamp(Math.floor(position), 0, anchors.length - 1)
  const from = anchors[index]
  const to = anchors[Math.min(index + 1, anchors.length - 1)]
  const travel = easeInOut((position - index - HOLD_END) / (1 - HOLD_END))
  // A small arc keeps the handoff from reading as a straight slide.
  const lift = Math.sin(travel * Math.PI) * 36
  return {
    x: from.x + (to.x - from.x) * travel,
    y: from.y + (to.y - from.y) * travel - lift,
    size: from.size + (to.size - from.size) * travel,
  }
}

/** 0 while the world is dark and warm, 1 once knowledge has spread into daylight. */
export function lightAt(position: number) {
  return easeInOut((position - 3.3) / (5.2 - 3.3))
}
