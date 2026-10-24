import { useCallback, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { cn } from '@/lib/utils'
import type { DeckNode, SelectedDeckAction } from '../types'
import { useDeckTreeDragDrop } from '../hooks/useDeckTreeDragDrop'
import { useDeckTreeExpanded } from '../hooks/useDeckTreeExpanded'
import { useWindowedRows } from '../hooks/useWindowedRows'
import { flattenVisibleDecks } from '../utils/flattenDeckTree'
import { DeckRow } from './DeckRow'

export type DeckTreeProps = {
  nodes: DeckNode[]
  adminMode: boolean
  selectedDeckId?: number | null
  onSelect?: (deck: DeckNode) => void
  onActivate?: (deck: DeckNode) => void
  onAction: (action: SelectedDeckAction) => void
  onMoveDeck?: (deckId: number, targetParentId: number | null) => Promise<void>
}

// Spacers stand in for unmounted rows; zero borders keep them out of the divider rhythm.
function RowSpacer({ height, anchorRef, position }: {
  height: number
  anchorRef?: React.Ref<HTMLDivElement>
  position: 'before' | 'after'
}) {
  return <div ref={anchorRef} aria-hidden="true" data-virtual-spacer={position} style={{ height, borderWidth: 0 }} />
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
  const { t } = useTranslation('dashboard')
  const { expandedDeckIds, toggleExpand } = useDeckTreeExpanded(nodes, selectedDeckId)
  const rows = useMemo(() => flattenVisibleDecks(nodes, expandedDeckIds), [nodes, expandedDeckIds])
  const {
    draggedDeck,
    dragPos,
    ghostRef,
    dragOverId,
    isInvalidDrop,
    isDragActive,
    isDragJustEnded,
    handlePointerDownRow,
  } = useDeckTreeDragDrop(onMoveDeck)
  const listRef = useRef<HTMLDivElement>(null)
  const anchorRef = useRef<HTMLDivElement>(null)
  const rowWindow = useWindowedRows(rows.length, anchorRef, listRef)

  // When the focused row unmounts (scrolled out of the window, or its branch
  // collapsed) the list holds focus instead of <body>, so Tab continues from the
  // visible rows; the row takes focus back if it mounts again first.
  const lostFocusDeckIdRef = useRef<number | null>(null)
  const handleRowUnmountWhileFocused = useCallback((deckId: number) => {
    lostFocusDeckIdRef.current = deckId
    listRef.current?.focus({ preventScroll: true })
  }, [])
  const claimRestoredFocus = useCallback((deckId: number) => {
    if (lostFocusDeckIdRef.current !== deckId || document.activeElement !== listRef.current) return false
    lostFocusDeckIdRef.current = null
    return true
  }, [])
  const handleListFocus = useCallback((e: React.FocusEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) lostFocusDeckIdRef.current = null
  }, [])
  const handleListBlur = useCallback((e: React.FocusEvent<HTMLDivElement>) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) lostFocusDeckIdRef.current = null
  }, [])

  return (
    <div
      ref={listRef}
      tabIndex={-1}
      onFocus={handleListFocus}
      onBlur={handleListBlur}
      className="deck-list flex flex-col divide-y divide-gray-100 relative focus:outline-none"
    >
      {/* Floating Ghost Badge preview attached to mouse cursor */}
      {draggedDeck && dragPos ? (
        <div
          ref={ghostRef}
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
              ? t('tree.drag.invalid_move', { name: draggedDeck.name })
              : t('tree.drag.moving', { name: draggedDeck.name })}
          </span>
          {dragOverId === 'root' ? (
            <span className="text-[11px] bg-white/25 px-2 py-0.5 rounded-md font-medium">
              {t('tree.drag.drop_to_root')}
            </span>
          ) : dragOverId && typeof dragOverId === 'number' && !isInvalidDrop ? (
            <span className="text-[11px] bg-white/25 px-2 py-0.5 rounded-md font-medium">
              {t('tree.drag.drop_to_deck')}
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
        >
          <span>{t('tree.drag.root_drop_prompt', { name: draggedDeck.name })}</span>
        </div>
      ) : null}

      {rowWindow.enabled ? (
        <RowSpacer height={rowWindow.paddingTop} anchorRef={anchorRef} position="before" />
      ) : null}

      {rows.slice(rowWindow.start, rowWindow.end).map((node, offset) => {
        const index = rowWindow.start + offset
        return (
          <DeckRow
            key={node.id}
            node={node}
            adminMode={adminMode}
            isSelected={selectedDeckId === node.id}
            expanded={expandedDeckIds.has(node.id)}
            dataTour={index === 0 ? 'dash-deck-row-first' : undefined}
            onSelect={onSelect}
            onActivate={onActivate}
            onAction={onAction}
            onToggleExpand={toggleExpand}
            isDraggingSelf={draggedDeck?.id === node.id}
            dropHover={dragOverId === node.id ? (isInvalidDrop ? 'invalid' : 'valid') : null}
            isDragActive={isDragActive}
            isDragJustEnded={isDragJustEnded}
            onPointerDownRow={handlePointerDownRow}
            onUnmountWhileFocused={handleRowUnmountWhileFocused}
            claimRestoredFocus={claimRestoredFocus}
          />
        )
      })}

      {rowWindow.enabled && rowWindow.paddingBottom > 0 ? (
        <RowSpacer height={rowWindow.paddingBottom} position="after" />
      ) : null}
    </div>
  )
}
