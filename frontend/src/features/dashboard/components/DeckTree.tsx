import { useEffect, useRef, useState } from 'react'
import {
  ArrowLeftRight,
  ArrowCounterclockwise,
  ChevronRight,
  Copy,
  GearFill,
  PencilSquare,
  Share,
  TrashFill,
} from '@/shared/components/Icons'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import type { DeckNode, SelectedDeckAction } from '../types'

type DeckTreeProps = {
  nodes: DeckNode[]
  adminMode: boolean
  selectedDeckId?: number | null
  onSelect?: (deck: DeckNode) => void
  onActivate?: (deck: DeckNode) => void
  onAction: (action: SelectedDeckAction) => void
  onMoveDeck?: (deckId: number, targetParentId: number | null) => Promise<void>
}

function isDescendant(parent: DeckNode, targetId: number): boolean {
  if (parent.id === targetId) return true
  for (const child of parent.children) {
    if (isDescendant(child, targetId)) return true
  }
  return false
}

function DeckRow({
  node,
  adminMode,
  selectedDeckId,
  onSelect,
  onActivate,
  onAction,
  draggedDeck,
  dragOverId,
  isInvalidDrop,
  isDragJustEnded,
  onPointerDownRow,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDragEnter,
  onDrop,
}: {
  node: DeckNode
  adminMode: boolean
  selectedDeckId?: number | null
  onSelect?: (deck: DeckNode) => void
  onActivate?: (deck: DeckNode) => void
  onAction: (action: SelectedDeckAction) => void
  draggedDeck: DeckNode | null
  dragOverId: number | 'root' | null
  isInvalidDrop: boolean
  isDragJustEnded: () => boolean
  onPointerDownRow: (e: React.PointerEvent, node: DeckNode) => void
  onDragStart: (e: React.DragEvent, node: DeckNode) => void
  onDragEnd: (e: React.DragEvent) => void
  onDragOver: (e: React.DragEvent, node: DeckNode) => void
  onDragEnter: (e: React.DragEvent, node: DeckNode) => void
  onDrop: (e: React.DragEvent, node: DeckNode) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = node.children.length > 0
  const isSelected = selectedDeckId === node.id

  const isDraggingSelf = draggedDeck?.id === node.id
  const isTargetHover = dragOverId === node.id

  const handleCopyMoveId = () => {
    void navigator.clipboard.writeText(node.move.alias)
  }

  const handleRowClick = (e: React.MouseEvent) => {
    if (isDragJustEnded() || draggedDeck !== null) {
      e.preventDefault()
      e.stopPropagation()
      return
    }
    onSelect?.(node)
  }

  const handleRowDoubleClick = (e: React.MouseEvent) => {
    if (isDragJustEnded() || draggedDeck !== null) {
      e.preventDefault()
      e.stopPropagation()
      return
    }
    onSelect?.(node)
    onActivate?.(node)
  }

  const handleRowKeyDown = (e: React.KeyboardEvent) => {
    if (e.target !== e.currentTarget) return
    if (e.key === 'Enter') {
      e.preventDefault()
      onSelect?.(node)
      onActivate?.(node)
    } else if (e.key === ' ') {
      e.preventDefault()
      onSelect?.(node)
    }
  }

  return (
    <>
      <div
        data-node-id={node.id}
        role="button"
        tabIndex={0}
        aria-selected={isSelected}
        onPointerDown={(e) => onPointerDownRow(e, node)}
        className={cn(
          'deck-row group relative flex items-center justify-between py-1.5 sm:py-2 px-1 rounded-md border border-transparent cursor-grab active:cursor-grabbing select-none touch-manipulation transition-all duration-150',
          'hover:bg-[#fff8f5]',
          isSelected && 'is-selected bg-[#fff1e6]',
          isDraggingSelf && 'opacity-40 border-dashed border-orange-400 bg-orange-50/40 scale-[0.99] touch-none',
          isTargetHover && !isInvalidDrop && 'bg-orange-100/90 border-2 border-dashed border-orange-500 ring-2 ring-orange-200/50 shadow-md scale-[1.005]',
          isTargetHover && isInvalidDrop && 'bg-rose-50 border-2 border-dashed border-rose-400 ring-2 ring-rose-200/50 cursor-not-allowed',
        )}
        onClick={handleRowClick}
        onDoubleClick={handleRowDoubleClick}
        onKeyDown={handleRowKeyDown}
      >
        {/* Name Column */}
        <div
          className="deck-name-col flex flex-1 items-center min-w-0 pr-1.5 sm:pr-4"
          style={{ paddingLeft: `calc(${node.depth} * 0.85rem)` }}
        >
          {hasChildren ? (
            <button
              type="button"
              className="tree-toggle pointer-events-auto inline-flex size-5 sm:size-6 shrink-0 items-center justify-center rounded text-muted-foreground transition hover:bg-muted hover:text-orange-600 mr-1 sm:mr-2"
              data-expanded={expanded}
              aria-expanded={expanded}
              onPointerDown={(e) => e.stopPropagation()}
              onDoubleClick={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation()
                setExpanded((prev) => !prev)
              }}
            >
              <ChevronRight
                className={cn('size-3.5 sm:size-4 transition-transform duration-200', expanded && 'rotate-90')}
              />
            </button>
          ) : (
            <span className="tree-spacer inline-block size-5 sm:size-6 shrink-0 mr-1 sm:mr-2" />
          )}

          <span className="deck-name text-sm sm:text-base font-normal text-foreground truncate group-hover:text-orange-600 transition-colors">
            {node.name}
          </span>

          {/* Hover badge indicator when dragging over (Responsive for mobile & desktop) */}
          {isTargetHover && !isDraggingSelf && (
            <span
              className={cn(
                'ml-1.5 sm:ml-2 inline-flex items-center gap-1 text-[10px] sm:text-[11px] font-semibold px-1.5 sm:px-2 py-0.5 rounded-full shrink-0 shadow-xs animate-in fade-in zoom-in-95 duration-100 max-w-[130px] sm:max-w-none truncate',
                isInvalidDrop
                  ? 'bg-rose-100 text-rose-700 border border-rose-300'
                  : 'bg-orange-500 text-white border border-orange-600',
              )}
            >
              {isInvalidDrop
                ? '🚫 Không thể di chuyển'
                : `➕ Thả vào "${node.name}"`}
            </span>
          )}
        </div>

        {/* Stats Column */}
        <div className="deck-stats-col pointer-events-auto grid grid-cols-[repeat(3,38px)_26px] sm:grid-cols-[repeat(3,64px)_30px] gap-1 sm:gap-2 items-center text-right shrink-0">
          <span className="stat-num stat-new text-xs sm:text-base font-normal tabular-nums text-emerald-600">
            {node.counts.new.toLocaleString('vi-VN')}
          </span>
          <span className="stat-num stat-learn text-xs sm:text-base font-normal tabular-nums text-rose-600">
            {node.counts.learning.toLocaleString('vi-VN')}
          </span>
          <span className="stat-num stat-due text-xs sm:text-base font-semibold tabular-nums text-orange-600">
            {node.counts.due.toLocaleString('vi-VN')}
          </span>

          {/* Deck Settings Gear Dropdown */}
          <div className="deck-settings-wrapper flex justify-center items-center">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className={cn(
                    'deck-settings-btn inline-flex opacity-80 sm:opacity-0 sm:group-hover:opacity-75 data-[state=open]:opacity-100 size-6 sm:size-7 items-center justify-center rounded-full text-muted-foreground transition-all hover:opacity-100 hover:text-orange-700 hover:bg-orange-50 border border-transparent hover:border-orange-300',
                    isSelected && 'opacity-100',
                  )}
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={(e) => e.stopPropagation()}
                  onDoubleClick={(e) => e.stopPropagation()}
                  aria-label="Deck Settings"
                  title="Deck Settings"
                >
                  <GearFill className="size-3.5 sm:size-4" />
                </button>
              </DropdownMenuTrigger>

              <DropdownMenuContent align="end" className="w-56 p-1.5 rounded-xl shadow-lg border border-border">
                {adminMode ? (
                  <>
                    <DropdownMenuItem
                      className="cursor-pointer text-sm py-2 px-2.5 font-medium flex items-center gap-2"
                      onSelect={() => onAction({ type: 'rename', deck: node })}
                    >
                      <PencilSquare className="size-4 text-muted-foreground" />
                      <span>Rename Deck</span>
                    </DropdownMenuItem>

                    <DropdownMenuItem
                      className="cursor-pointer text-sm py-2 px-2.5 font-medium flex items-center gap-2"
                      onSelect={() => onAction({ type: 'move', deck: node })}
                    >
                      <ArrowLeftRight className="size-4 text-muted-foreground" />
                      <span>Move Deck</span>
                    </DropdownMenuItem>

                    <DropdownMenuItem
                      className="cursor-pointer text-sm py-2 px-2.5 font-medium flex items-center gap-2"
                      onSelect={handleCopyMoveId}
                    >
                      <Copy className="size-4 text-muted-foreground" />
                      <span>Copy Move ID</span>
                    </DropdownMenuItem>

                    <DropdownMenuSeparator className="my-1" />
                  </>
                ) : null}

                <DropdownMenuItem
                  className="cursor-pointer text-sm py-2 px-2.5 font-semibold text-orange-700 flex items-center gap-2"
                  onSelect={() => window.location.assign(node.actions.share)}
                >
                  <Share className="size-4 text-orange-600" />
                  <span>Share Deck</span>
                </DropdownMenuItem>

                <DropdownMenuSeparator className="my-1" />

                <DropdownMenuItem
                  className="cursor-pointer text-sm py-2 px-2.5 font-medium text-amber-700 focus:text-amber-800 focus:bg-amber-50 flex items-center gap-2"
                  onSelect={() => onAction({ type: 'reset', deck: node })}
                >
                  <ArrowCounterclockwise className="size-4 text-amber-600" />
                  <span>Reset Progress</span>
                </DropdownMenuItem>

                <DropdownMenuItem
                  className="cursor-pointer text-sm py-2 px-2.5 font-medium text-rose-700 focus:text-rose-800 focus:bg-rose-50 flex items-center gap-2"
                  onSelect={() => onAction({ type: 'delete', deck: node })}
                >
                  <TrashFill className="size-4 text-rose-600" />
                  <span>Delete Deck</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      {hasChildren && expanded
        ? node.children.map((child) => (
            <DeckRow
              key={child.id}
              node={child}
              adminMode={adminMode}
              selectedDeckId={selectedDeckId}
              onSelect={onSelect}
              onActivate={onActivate}
              onAction={onAction}
              draggedDeck={draggedDeck}
              dragOverId={dragOverId}
              isInvalidDrop={isInvalidDrop}
              isDragJustEnded={isDragJustEnded}
              onPointerDownRow={onPointerDownRow}
              onDragStart={onDragStart}
              onDragEnd={onDragEnd}
              onDragOver={onDragOver}
              onDragEnter={onDragEnter}
              onDrop={onDrop}
            />
          ))
        : null}
    </>
  )
}

export function DeckTree({
  nodes,
  adminMode,
  selectedDeckId = null,
  onSelect,
  onActivate,
  onAction,
  onMoveDeck,
}: DeckTreeProps) {
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

  return (
    <div className="deck-list flex flex-col divide-y divide-gray-100 relative">
      {/* Floating Ghost Badge preview attached to mouse cursor */}
      {draggedDeck && dragPos ? (
        <div
          className={cn(
            'fixed pointer-events-none z-50 flex items-center gap-2 px-3.5 py-2 rounded-xl shadow-2xl font-bold text-xs sm:text-sm border transition-all duration-75 transform -translate-x-1/2 -translate-y-1/2',
            isInvalidDrop
              ? 'bg-rose-600 text-white border-rose-400 shadow-rose-900/30 ring-4 ring-rose-500/20'
              : 'bg-orange-500 text-white border-orange-400 shadow-orange-900/30 ring-4 ring-orange-400/30',
          )}
          style={{
            left: `${dragPos.x}px`,
            top: `${dragPos.y}px`,
          }}
        >
          <span className="text-base sm:text-lg">{isInvalidDrop ? '🚫' : '📦'}</span>
          <span>
            {isInvalidDrop
              ? `Không thể di chuyển "${draggedDeck.name}" vào chính nó / deck con`
              : `Di chuyển "${draggedDeck.name}"`}
          </span>
          {dragOverId === 'root' ? (
            <span className="text-[11px] bg-white/25 px-2 py-0.5 rounded-md font-medium">
              → Thả vào Root
            </span>
          ) : dragOverId && typeof dragOverId === 'number' && !isInvalidDrop ? (
            <span className="text-[11px] bg-white/25 px-2 py-0.5 rounded-md font-medium">
              → Thả vào deck
            </span>
          ) : null}
        </div>
      ) : null}

      {/* Root Level Drop Zone shown when dragging a deck */}
      {draggedDeck ? (
        <div
          data-root-drop="true"
          className={cn(
            'root-drop-zone my-2 p-3 rounded-xl border-2 border-dashed text-center transition-all duration-200 cursor-pointer flex items-center justify-center gap-2 text-xs sm:text-sm font-semibold',
            dragOverId === 'root'
              ? 'bg-orange-100 border-orange-500 text-orange-700 shadow-md scale-[1.005]'
              : 'bg-orange-50/60 border-orange-300 text-orange-600 hover:bg-orange-100 hover:border-orange-400',
          )}
          onDragOver={handleDragOverRoot}
          onDrop={handleDropOnRoot}
        >
          <span>📍 Thả vào đây để chuyển <strong>“{draggedDeck.name}”</strong> ra ngoài cấp Root (không có deck cha)</span>
        </div>
      ) : null}

      {nodes.map((node) => (
        <DeckRow
          key={node.id}
          node={node}
          adminMode={adminMode}
          selectedDeckId={selectedDeckId}
          onSelect={onSelect}
          onActivate={onActivate}
          onAction={onAction}
          draggedDeck={draggedDeck}
          dragOverId={dragOverId}
          isInvalidDrop={isInvalidDrop}
          isDragJustEnded={isDragJustEnded}
          onPointerDownRow={handlePointerDownRow}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragOver={handleDragOverRow}
          onDragEnter={handleDragEnterRow}
          onDrop={handleDropOnRow}
        />
      ))}
    </div>
  )
}



