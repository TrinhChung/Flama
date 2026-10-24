import { useCallback, useEffect, useLayoutEffect, useState, type RefObject } from 'react'

// Below this many visible rows the tree renders every row, exactly as before.
// Above it (e.g. a fully expanded 1,500-deck tree) only rows near the viewport mount.
export const VIRTUALIZE_MIN_ROWS = 150
export const OVERSCAN_ROWS = 12
export const ESTIMATED_ROW_HEIGHT = 36
const INITIAL_ROWS = 60

export type RowWindow = {
  enabled: boolean
  start: number
  end: number
  paddingTop: number
  paddingBottom: number
}

type WindowState = { start: number; end: number; rowHeight: number }

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

// Rows share one height per breakpoint; the median ignores the odd one out
// (drop-target border, last row without divider).
function medianRowHeight(list: HTMLElement | null): number {
  if (!list) return 0
  const heights = Array.from(list.querySelectorAll<HTMLElement>(':scope > [data-node-id]'))
    .map((row) => row.getBoundingClientRect().height)
    .filter((height) => height > 0)
    .sort((a, b) => a - b)
  return heights.length ? heights[Math.floor(heights.length / 2)] : 0
}

const scheduleFrame = (callback: () => void) =>
  typeof window.requestAnimationFrame === 'function'
    ? window.requestAnimationFrame(callback)
    : window.setTimeout(callback, 16)

const cancelFrame = (id: number) =>
  typeof window.cancelAnimationFrame === 'function'
    ? window.cancelAnimationFrame(id)
    : window.clearTimeout(id)

/**
 * Window-scrolled virtualization for an in-flow list. `anchorRef` is a spacer
 * rendered right before the first row, `listRef` the element whose direct
 * children are the rows. Rows stay in normal flow between two spacers, so the
 * page keeps its own scrollbar, dividers and tab order.
 */
export function useWindowedRows(
  count: number,
  anchorRef: RefObject<HTMLElement | null>,
  listRef: RefObject<HTMLElement | null>,
): RowWindow {
  const enabled = count >= VIRTUALIZE_MIN_ROWS
  const [state, setState] = useState<WindowState>(() => ({
    start: 0,
    end: INITIAL_ROWS,
    rowHeight: ESTIMATED_ROW_HEIGHT,
  }))

  const update = useCallback(() => {
    const anchor = anchorRef.current
    if (!enabled || !anchor) return
    const measured = medianRowHeight(listRef.current)
    const scrolledPast = -anchor.getBoundingClientRect().top
    const viewport = window.innerHeight || document.documentElement.clientHeight
    setState((prev) => {
      const rowHeight = measured > 0 ? measured : prev.rowHeight
      const start = clamp(Math.floor(scrolledPast / rowHeight) - OVERSCAN_ROWS, 0, count)
      const end = clamp(Math.ceil((scrolledPast + viewport) / rowHeight) + OVERSCAN_ROWS, start, count)
      return prev.start === start && prev.end === end && prev.rowHeight === rowHeight
        ? prev
        : { start, end, rowHeight }
    })
  }, [enabled, count, anchorRef, listRef])

  // Re-measure before paint whenever the rendered slice or row count changes.
  useLayoutEffect(() => {
    update()
  }, [update, state.start, state.end])

  useEffect(() => {
    if (!enabled) return
    let frame = 0
    const schedule = () => {
      if (frame) return
      frame = scheduleFrame(() => {
        frame = 0
        update()
      })
    }
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    return () => {
      if (frame) cancelFrame(frame)
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
    }
  }, [enabled, update])

  if (!enabled) {
    return { enabled, start: 0, end: count, paddingTop: 0, paddingBottom: 0 }
  }
  const start = Math.min(state.start, count)
  const end = clamp(state.end, start, count)
  return {
    enabled,
    start,
    end,
    paddingTop: start * state.rowHeight,
    paddingBottom: (count - end) * state.rowHeight,
  }
}
