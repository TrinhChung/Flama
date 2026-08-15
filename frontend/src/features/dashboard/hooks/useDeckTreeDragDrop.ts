import { useEffect, useRef, useState } from 'react'
import type { DeckNode } from '../types'

export function isDescendant(parent: DeckNode, targetId: number): boolean {
  if (parent.id === targetId) return true
  for (const child of parent.children) {
    if (isDescendant(child, targetId)) return true
  }
  return false
}

export function useDeckTreeDragDrop(onMoveDeck?: (deckId: number, targetParentId: number | null) => Promise<void>) {
  const [draggedDeck, setDraggedDeck] = useState<DeckNode | null>(null)
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null)
  const [dragOverId, setDragOverId] = useState<number | 'root' | null>(null)
  const [isInvalidDrop, setIsInvalidDrop] = useState(false)

  const isJustDraggedRef = useRef(false)
  const justDraggedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const pendingRef = useRef<{
    deck: DeckNode
    startX: number
    startY: number
    active: boolean
  } | null>(null)

  const isDragJustEnded = () => isJustDraggedRef.current

  const handlePointerDownRow = (e: React.PointerEvent, node: DeckNode) => {
    if (e.button !== 0) return // Only primary click
    pendingRef.current = {
      deck: node,
      startX: e.clientX,
      startY: e.clientY,
      active: false,
    }
  }

  useEffect(() => {
    const handlePointerMove = (e: PointerEvent) => {
      const pending = pendingRef.current
      if (!pending) return

      const dx = Math.abs(e.clientX - pending.startX)
      const dy = Math.abs(e.clientY - pending.startY)

      if (!pending.active && (dx > 6 || dy > 6)) {
        pending.active = true
        isJustDraggedRef.current = true
        if (justDraggedTimerRef.current) {
          clearTimeout(justDraggedTimerRef.current)
        }
        setDraggedDeck(pending.deck)
      }

      if (pending.active) {
        setDragPos({ x: e.clientX, y: e.clientY })

        // Element collision detection under cursor
        const hit = document.elementFromPoint(e.clientX, e.clientY)
        const rowEl = hit?.closest('[data-node-id]') as HTMLElement | null
        const rootEl = hit?.closest('[data-root-drop="true"]') as HTMLElement | null

        if (rootEl) {
          setIsInvalidDrop(false)
          setDragOverId('root')
        } else if (rowEl) {
          const targetId = Number(rowEl.dataset.nodeId)
          if (!isNaN(targetId)) {
            if (pending.deck.id === targetId || isDescendant(pending.deck, targetId)) {
              setIsInvalidDrop(true)
            } else {
              setIsInvalidDrop(false)
            }
            setDragOverId(targetId)
          }
        } else {
          setDragOverId(null)
          setIsInvalidDrop(false)
        }
      }
    }

    const handlePointerUp = () => {
      const pending = pendingRef.current
      if (pending?.active) {
        const deckBeingDragged = draggedDeck ?? pending.deck
        isJustDraggedRef.current = true
        if (justDraggedTimerRef.current) {
          clearTimeout(justDraggedTimerRef.current)
        }
        justDraggedTimerRef.current = setTimeout(() => {
          isJustDraggedRef.current = false
        }, 300)

        if (dragOverId === 'root' && deckBeingDragged.parent_id !== null) {
          void onMoveDeck?.(deckBeingDragged.id, null)
        } else if (
          typeof dragOverId === 'number' &&
          !isInvalidDrop &&
          deckBeingDragged.parent_id !== dragOverId
        ) {
          void onMoveDeck?.(deckBeingDragged.id, dragOverId)
        }
      }
      pendingRef.current = null
      setDraggedDeck(null)
      setDragPos(null)
      setDragOverId(null)
      setIsInvalidDrop(false)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
    window.addEventListener('pointercancel', handlePointerUp)

    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
      window.removeEventListener('pointercancel', handlePointerUp)
    }
  }, [draggedDeck, dragOverId, isInvalidDrop, onMoveDeck])

  // HTML5 Drag Fallbacks
  const handleDragStart = (e: React.DragEvent, node: DeckNode) => {
    e.stopPropagation()
    e.dataTransfer.setData('text/plain', String(node.id))
    e.dataTransfer.effectAllowed = 'move'
    setDraggedDeck(node)
    setDragPos({ x: e.clientX, y: e.clientY })
  }

  const handleDragEnd = () => {
    pendingRef.current = null
    setDraggedDeck(null)
    setDragPos(null)
    setDragOverId(null)
    setIsInvalidDrop(false)
  }

  const handleDragOverRow = (e: React.DragEvent, targetNode: DeckNode) => {
    e.preventDefault()
    e.stopPropagation()
    if (!draggedDeck) return

    setDragPos({ x: e.clientX, y: e.clientY })
    if (draggedDeck.id === targetNode.id || isDescendant(draggedDeck, targetNode.id)) {
      setIsInvalidDrop(true)
      e.dataTransfer.dropEffect = 'none'
    } else {
      setIsInvalidDrop(false)
      e.dataTransfer.dropEffect = 'move'
    }
    setDragOverId(targetNode.id)
  }

  const handleDragEnterRow = (e: React.DragEvent, targetNode: DeckNode) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOverId(targetNode.id)
  }

  const handleDropOnRow = (e: React.DragEvent, targetNode: DeckNode) => {
    e.preventDefault()
    e.stopPropagation()
    if (!draggedDeck) return

    if (draggedDeck.id === targetNode.id || isDescendant(draggedDeck, targetNode.id)) {
      handleDragEnd()
      return
    }

    const deckToMove = draggedDeck
    const targetParentId = targetNode.id
    handleDragEnd()

    if (deckToMove.parent_id !== targetParentId) {
      void onMoveDeck?.(deckToMove.id, targetParentId)
    }
  }

  const handleDragOverRoot = (e: React.DragEvent) => {
    e.preventDefault()
    if (!draggedDeck) return
    setDragPos({ x: e.clientX, y: e.clientY })
    setIsInvalidDrop(false)
    e.dataTransfer.dropEffect = 'move'
    setDragOverId('root')
  }

  const handleDropOnRoot = (e: React.DragEvent) => {
    e.preventDefault()
    if (!draggedDeck) return
    const deckToMove = draggedDeck
    handleDragEnd()

    if (deckToMove.parent_id !== null) {
      void onMoveDeck?.(deckToMove.id, null)
    }
  }

  return {
    draggedDeck,
    dragPos,
    dragOverId,
    isInvalidDrop,
    isDragJustEnded,
    handlePointerDownRow,
    handleDragStart,
    handleDragEnd,
    handleDragOverRow,
    handleDragEnterRow,
    handleDropOnRow,
    handleDragOverRoot,
    handleDropOnRoot,
  }
}
