import { useCallback, useEffect, useRef, useState } from 'react'
import type { DeckNode } from '../types'

export const TOUCH_LONG_PRESS_DELAY_MS = 450
export const TOUCH_SCROLL_SLOP_PX = 8
export const MOUSE_DRAG_THRESHOLD_PX = 6

function isTouchPointer(pointerType?: string): boolean {
  return pointerType === 'touch' || pointerType === 'pen'
}

export function isDescendant(parent: DeckNode, targetId: number): boolean {
  if (parent.id === targetId) return true
  for (const child of parent.children) {
    if (isDescendant(child, targetId)) return true
  }
  return false
}

export function useDeckTreeDragDrop(onMoveDeck?: (deckId: number, targetParentId: number | null) => Promise<void>) {
  const [draggedDeck, setDraggedDeck] = useState<DeckNode | null>(null)
  // Where the ghost badge first appears. Later pointer moves reposition it through
  // ghostRef directly, so dragging does not re-render the whole deck tree per move.
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null)
  const [dragOverId, setDragOverId] = useState<number | 'root' | null>(null)
  const [isInvalidDrop, setIsInvalidDrop] = useState(false)
  const ghostRef = useRef<HTMLDivElement | null>(null)

  const draggedDeckRef = useRef(draggedDeck)
  draggedDeckRef.current = draggedDeck
  const dragOverIdRef = useRef(dragOverId)
  dragOverIdRef.current = dragOverId
  const isInvalidDropRef = useRef(isInvalidDrop)
  isInvalidDropRef.current = isInvalidDrop
  const onMoveDeckRef = useRef(onMoveDeck)
  onMoveDeckRef.current = onMoveDeck

  const isJustDraggedRef = useRef(false)
  const justDraggedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const pendingRef = useRef<{
    deck: DeckNode
    startX: number
    startY: number
    currentX: number
    currentY: number
    pointerId?: number
    pointerType: string
    active: boolean
  } | null>(null)

  const clearLongPressTimer = () => {
    if (longPressTimerRef.current !== null) {
      clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }
  }

  const activateDrag = (pending: NonNullable<typeof pendingRef.current>) => {
    if (pending.active) return
    pending.active = true
    isJustDraggedRef.current = true
    if (justDraggedTimerRef.current) {
      clearTimeout(justDraggedTimerRef.current)
    }
    draggedDeckRef.current = pending.deck
    setDraggedDeck(pending.deck)
    setDragPos({ x: pending.currentX, y: pending.currentY })
  }

  // Stable identities let memoized DeckRows skip renders; both only touch refs and setters.
  const isDragJustEnded = useCallback(() => isJustDraggedRef.current, [])
  const isDragActive = useCallback(() => draggedDeckRef.current !== null, [])

  const handlePointerDownRow = useCallback((e: React.PointerEvent, node: DeckNode) => {
    if (e.button !== 0) return // Only primary click / primary touch
    clearLongPressTimer()

    const pointerType = e.pointerType || 'mouse'
    const pending = {
      deck: node,
      startX: e.clientX,
      startY: e.clientY,
      currentX: e.clientX,
      currentY: e.clientY,
      pointerId: e.pointerId,
      pointerType,
      active: false,
    }
    pendingRef.current = pending

    if (isTouchPointer(pointerType)) {
      longPressTimerRef.current = setTimeout(() => {
        longPressTimerRef.current = null
        if (pendingRef.current !== pending || pending.active) return
        activateDrag(pending)
        if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
          try {
            navigator.vibrate(25)
          } catch {
            // Ignore vibration errors on unsupported environments
          }
        }
      }, TOUCH_LONG_PRESS_DELAY_MS)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- helpers only use refs and state setters
  }, [])

  useEffect(() => {
    return () => {
      clearLongPressTimer()
      if (justDraggedTimerRef.current) {
        clearTimeout(justDraggedTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    const resetDragState = () => {
      clearLongPressTimer()
      pendingRef.current = null
      draggedDeckRef.current = null
      dragOverIdRef.current = null
      isInvalidDropRef.current = false
      setDraggedDeck(null)
      setDragPos(null)
      setDragOverId(null)
      setIsInvalidDrop(false)
    }

    const handlePointerMove = (e: PointerEvent) => {
      const pending = pendingRef.current
      if (!pending) return
      if (
        pending.pointerId !== undefined &&
        e.pointerId !== undefined &&
        pending.pointerId !== e.pointerId
      ) {
        return
      }

      pending.currentX = e.clientX
      pending.currentY = e.clientY

      const dx = Math.abs(e.clientX - pending.startX)
      const dy = Math.abs(e.clientY - pending.startY)

      if (!pending.active) {
        if (isTouchPointer(pending.pointerType)) {
          // On touch/pen, movement before long-press threshold means the user is scrolling/swiping
          if (dx > TOUCH_SCROLL_SLOP_PX || dy > TOUCH_SCROLL_SLOP_PX) {
            clearLongPressTimer()
            pendingRef.current = null
          }
          return
        }

        if (dx > MOUSE_DRAG_THRESHOLD_PX || dy > MOUSE_DRAG_THRESHOLD_PX) {
          activateDrag(pending)
        }
      }

      if (pending.active) {
        const ghost = ghostRef.current
        if (ghost) {
          ghost.style.left = `${e.clientX}px`
          ghost.style.top = `${e.clientY}px`
        }

        // Element collision detection under cursor
        const hit = document.elementFromPoint(e.clientX, e.clientY)
        const rowEl = hit?.closest('[data-node-id]') as HTMLElement | null
        const rootEl = hit?.closest('[data-root-drop="true"]') as HTMLElement | null

        if (rootEl) {
          isInvalidDropRef.current = false
          dragOverIdRef.current = 'root'
          setIsInvalidDrop(false)
          setDragOverId('root')
        } else if (rowEl) {
          const targetId = Number(rowEl.dataset.nodeId)
          if (!isNaN(targetId)) {
            const invalid = pending.deck.id === targetId || isDescendant(pending.deck, targetId)
            isInvalidDropRef.current = invalid
            dragOverIdRef.current = targetId
            setIsInvalidDrop(invalid)
            setDragOverId(targetId)
          }
        } else {
          dragOverIdRef.current = null
          isInvalidDropRef.current = false
          setDragOverId(null)
          setIsInvalidDrop(false)
        }
      }
    }

    const handlePointerUp = (e: PointerEvent) => {
      const pending = pendingRef.current
      if (
        pending?.pointerId !== undefined &&
        e.pointerId !== undefined &&
        pending.pointerId !== e.pointerId
      ) {
        return
      }
      clearLongPressTimer()
      if (pending?.active) {
        const deckBeingDragged = draggedDeckRef.current ?? pending.deck
        isJustDraggedRef.current = true
        if (justDraggedTimerRef.current) {
          clearTimeout(justDraggedTimerRef.current)
        }
        justDraggedTimerRef.current = setTimeout(() => {
          isJustDraggedRef.current = false
        }, 300)

        const currentDragOverId = dragOverIdRef.current
        const currentIsInvalidDrop = isInvalidDropRef.current
        const currentOnMoveDeck = onMoveDeckRef.current

        if (currentDragOverId === 'root' && deckBeingDragged.parent_id !== null) {
          void currentOnMoveDeck?.(deckBeingDragged.id, null)
        } else if (
          typeof currentDragOverId === 'number' &&
          !currentIsInvalidDrop &&
          deckBeingDragged.id !== currentDragOverId &&
          deckBeingDragged.parent_id !== currentDragOverId
        ) {
          void currentOnMoveDeck?.(deckBeingDragged.id, currentDragOverId)
        }
      }
      resetDragState()
    }

    const handlePointerCancel = () => {
      // Never commit a deck move when the browser cancels the pointer (e.g., native scroll takeover)
      if (pendingRef.current?.active) {
        isJustDraggedRef.current = true
        if (justDraggedTimerRef.current) {
          clearTimeout(justDraggedTimerRef.current)
        }
        justDraggedTimerRef.current = setTimeout(() => {
          isJustDraggedRef.current = false
        }, 300)
      }
      resetDragState()
    }

    const handleScroll = () => {
      if (pendingRef.current && !pendingRef.current.active) {
        clearLongPressTimer()
        pendingRef.current = null
      }
    }

    const handleTouchMove = (e: TouchEvent) => {
      if (pendingRef.current?.active && e.cancelable) {
        e.preventDefault()
      }
    }

    const handleTouchStart = (e: TouchEvent) => {
      if (e.touches.length > 1 && pendingRef.current && !pendingRef.current.active) {
        clearLongPressTimer()
        pendingRef.current = null
      }
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
    window.addEventListener('pointercancel', handlePointerCancel)
    window.addEventListener('scroll', handleScroll, true)
    window.addEventListener('touchmove', handleTouchMove, { passive: false })
    window.addEventListener('touchstart', handleTouchStart, { passive: true })

    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
      window.removeEventListener('pointercancel', handlePointerCancel)
      window.removeEventListener('scroll', handleScroll, true)
      window.removeEventListener('touchmove', handleTouchMove)
      window.removeEventListener('touchstart', handleTouchStart)
    }
  }, [])

  return {
    draggedDeck,
    dragPos,
    ghostRef,
    dragOverId,
    isInvalidDrop,
    isDragActive,
    isDragJustEnded,
    handlePointerDownRow,
  }
}
