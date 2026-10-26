import { useCallback, useEffect, useMemo, useState, type RefObject } from 'react'

export type VirtualRow = {
  index: number
  start: number
  size: number
}

export type VirtualDiffListOptions = {
  count: number
  containerRef: RefObject<HTMLElement | null>
  estimateHeight?: number
  overscan?: number
  getItemHeight?: (index: number) => number
}

export type VirtualDiffListResult = {
  virtualRows: VirtualRow[]
  totalHeight: number
  isVirtualized: boolean
  resetSearchBypass: () => void
  startIndex: number
  endIndex: number
  paddingTop: number
  paddingBottom: number
}

const scheduleFrame = (callback: () => void): number =>
  typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function'
    ? window.requestAnimationFrame(callback)
    : (window.setTimeout(callback, 16) as unknown as number)

const cancelFrame = (id: number): void => {
  if (typeof window !== 'undefined' && typeof window.cancelAnimationFrame === 'function') {
    window.cancelAnimationFrame(id)
  } else {
    window.clearTimeout(id)
  }
}


/**
 * In-house container-scrolled virtualization hook for high-volume diff lists.
 * Adapts the proven useWindowedRows pattern to container scrolling with <150 DOM nodes
 * and browser find bypass (Ctrl+F / Cmd+F / F3).
 */
export function useVirtualDiffList({
  count,
  containerRef,
  estimateHeight = 68,
  overscan = 10,
  getItemHeight,
}: VirtualDiffListOptions): VirtualDiffListResult {
  const [scrollTop, setScrollTop] = useState(0)
  const [viewportHeight, setViewportHeight] = useState(600)
  const [showAllForSearch, setShowAllForSearch] = useState(false)

  // Browser find bypass (Ctrl+F / Cmd+F / F3)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isFind = (e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'f'
      if (isFind || e.key === 'F3') {
        setShowAllForSearch(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Container scroll & size listener with RAF throttling
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const initialHeight = el.clientHeight || window.innerHeight || 600
    setViewportHeight(initialHeight)
    setScrollTop(el.scrollTop)

    let frame = 0
    const onScroll = () => {
      if (frame) return
      frame = scheduleFrame(() => {
        frame = 0
        if (!containerRef.current) return
        setScrollTop(containerRef.current.scrollTop)
        const currentHeight = containerRef.current.clientHeight || 600
        setViewportHeight(currentHeight)
      })
    }

    el.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)

    let resizeObserver: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        if (!containerRef.current) return
        const currentHeight = containerRef.current.clientHeight || 600
        setViewportHeight(currentHeight)
      })
      resizeObserver.observe(el)
    }

    return () => {
      if (frame) cancelFrame(frame)
      el.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (resizeObserver) resizeObserver.disconnect()
    }
  }, [containerRef])

  // Precalculate row offsets and heights if getItemHeight is provided
  const rowOffsets = useMemo(() => {
    if (!getItemHeight) return null
    const offsets: number[] = new Array(count)
    const sizes: number[] = new Array(count)
    let currentOffset = 0
    for (let i = 0; i < count; i++) {
      offsets[i] = currentOffset
      const size = getItemHeight(i)
      sizes[i] = size
      currentOffset += size
    }
    return { offsets, sizes, total: currentOffset }
  }, [count, getItemHeight])

  const totalHeight = rowOffsets ? rowOffsets.total : count * estimateHeight

  const { virtualRows, startIndex, endIndex, paddingTop, paddingBottom } = useMemo(() => {
    if (count === 0) {
      return {
        virtualRows: [],
        startIndex: 0,
        endIndex: 0,
        paddingTop: 0,
        paddingBottom: 0,
      }
    }

    if (showAllForSearch) {
      const rows: VirtualRow[] = []
      for (let i = 0; i < count; i++) {
        const start = rowOffsets ? rowOffsets.offsets[i] : i * estimateHeight
        const size = rowOffsets ? rowOffsets.sizes[i] : estimateHeight
        rows.push({ index: i, start, size })
      }
      return {
        virtualRows: rows,
        startIndex: 0,
        endIndex: count - 1,
        paddingTop: 0,
        paddingBottom: 0,
      }
    }

    let startIdx = 0
    let endIdx = count - 1

    if (rowOffsets) {
      const targetStart = Math.max(0, scrollTop - overscan * estimateHeight)
      const targetEnd = scrollTop + viewportHeight + overscan * estimateHeight

      // Find first row whose bottom edge >= targetStart
      let low = 0
      let high = count - 1
      while (low <= high) {
        const mid = Math.floor((low + high) / 2)
        const rowEnd = rowOffsets.offsets[mid] + rowOffsets.sizes[mid]
        if (rowEnd >= targetStart) {
          startIdx = mid
          high = mid - 1
        } else {
          low = mid + 1
        }
      }

      // Find last row whose top edge <= targetEnd
      low = startIdx
      high = count - 1
      while (low <= high) {
        const mid = Math.floor((low + high) / 2)
        if (rowOffsets.offsets[mid] <= targetEnd) {
          endIdx = mid
          low = mid + 1
        } else {
          high = mid - 1
        }
      }
    } else {
      startIdx = Math.max(0, Math.floor(scrollTop / estimateHeight) - overscan)
      endIdx = Math.min(
        count - 1,
        Math.ceil((scrollTop + viewportHeight) / estimateHeight) + overscan,
      )
    }

    const rows: VirtualRow[] = []
    for (let i = startIdx; i <= endIdx; i++) {
      const start = rowOffsets ? rowOffsets.offsets[i] : i * estimateHeight
      const size = rowOffsets ? rowOffsets.sizes[i] : estimateHeight
      rows.push({ index: i, start, size })
    }

    const firstRowStart = rows.length > 0 ? rows[0].start : 0
    const lastRow = rows.length > 0 ? rows[rows.length - 1] : null
    const lastRowEnd = lastRow ? lastRow.start + lastRow.size : 0
    const padTop = firstRowStart
    const padBottom = Math.max(0, totalHeight - lastRowEnd)

    return {
      virtualRows: rows,
      startIndex: startIdx,
      endIndex: endIdx,
      paddingTop: padTop,
      paddingBottom: padBottom,
    }
  }, [count, showAllForSearch, rowOffsets, scrollTop, estimateHeight, overscan, viewportHeight, totalHeight])

  const resetSearchBypass = useCallback(() => {
    setShowAllForSearch(false)
  }, [])

  return {
    virtualRows,
    totalHeight,
    isVirtualized: !showAllForSearch,
    resetSearchBypass,
    startIndex,
    endIndex,
    paddingTop,
    paddingBottom,
  }
}
