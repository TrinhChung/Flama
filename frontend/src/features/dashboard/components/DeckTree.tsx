import { cn } from '@/lib/utils'
import type { DeckNode, SelectedDeckAction } from '../types'
import { useDeckTreeDragDrop } from '../hooks/useDeckTreeDragDrop'
import { useDeckTreeExpanded } from '../hooks/useDeckTreeExpanded'
import { DeckRow } from './DeckRow'

export type DeckTreeProps = {
  nodes: DeckNode[]
  adminMode: boolean
  selectedDeckId?: number | null
  onSelect?: (deck: DeckNode) => void
  onActivate?: (deck: DeckNode) => void
  onAction: (action: SelectedDeckAction) => void
  onMoveDeck?: (deckId: number, targetParentId: number | null) => Promise<void>
  isExpanded?: (deckId: number) => boolean
  onToggleExpand?: (deckId: number) => void
}

export function DeckTree({
  nodes,
  adminMode,
  selectedDeckId = null,
  onSelect,
  onActivate,
  onAction,
  onMoveDeck,
  isExpanded,
  onToggleExpand,
}: DeckTreeProps) {
  const expandedState = useDeckTreeExpanded(nodes, selectedDeckId)
  const activeIsExpanded = isExpanded ?? expandedState.isExpanded
  const activeToggleExpand = onToggleExpand ?? expandedState.toggleExpand
  const {
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
  } = useDeckTreeDragDrop(onMoveDeck)

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
          isExpanded={activeIsExpanded}
          onToggleExpand={activeToggleExpand}
        />
      ))}
    </div>
  )
}
