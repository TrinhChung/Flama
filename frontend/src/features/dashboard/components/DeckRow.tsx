import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import {
  ArrowLeftRight,
  ArrowCounterclockwise,
  ChevronRight,
  Copy,
  GearFill,
  PencilSquare,
  Share,
  TrashFill,
  Upload,
} from '@/shared/components/Icons'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { Layers, Printer } from 'lucide-react'
import type { DeckNode, SelectedDeckAction } from '../types'

export interface DeckRowProps {
  node: DeckNode
  adminMode: boolean
  selectedDeckId?: number | null
  dataTour?: string
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
  isExpanded?: (deckId: number) => boolean
  onToggleExpand?: (deckId: number) => void
}

export function DeckRow({
  node,
  adminMode,
  selectedDeckId,
  dataTour,
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
  isExpanded,
  onToggleExpand,
}: DeckRowProps) {
  const { t, i18n } = useTranslation('dashboard')
  const navigate = useNavigate()
  const numberLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'
  const [localExpanded, setLocalExpanded] = useState(false)
  const lastPointerTypeRef = useRef<string>('mouse')
  const hasChildren = node.children.length > 0
  const expanded = isExpanded ? isExpanded(node.id) : localExpanded
  const isSelected = selectedDeckId === node.id

  const isDraggingSelf = draggedDeck?.id === node.id
  const isTargetHover = dragOverId === node.id

  const handleCopyMoveId = () => {
    void navigator.clipboard.writeText(node.move.alias)
  }

  const handleRowPointerDown = (e: React.PointerEvent) => {
    lastPointerTypeRef.current = e.pointerType || 'mouse'
    onPointerDownRow(e, node)
  }

  const handleRowClick = (e: React.MouseEvent) => {
    if (isDragJustEnded() || draggedDeck !== null) {
      e.preventDefault()
      e.stopPropagation()
      return
    }
    const isTouchOrPen =
      lastPointerTypeRef.current === 'touch' || lastPointerTypeRef.current === 'pen'
    if (isTouchOrPen && isSelected) {
      onSelect?.(node)
      onActivate?.(node)
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
    if (lastPointerTypeRef.current === 'touch' || lastPointerTypeRef.current === 'pen') {
      return
    }
    onSelect?.(node)
    onActivate?.(node)
  }

  const handleRowContextMenu = (e: React.MouseEvent) => {
    if (
      lastPointerTypeRef.current === 'touch' ||
      lastPointerTypeRef.current === 'pen' ||
      draggedDeck !== null
    ) {
      e.preventDefault()
    }
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
        data-tour={dataTour}
        role="button"
        tabIndex={0}
        aria-selected={isSelected}
        onPointerDown={handleRowPointerDown}
        onContextMenu={handleRowContextMenu}
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
                if (onToggleExpand) {
                  onToggleExpand(node.id)
                } else {
                  setLocalExpanded((prev) => !prev)
                }
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

          {/* Hover badge indicator when dragging over */}
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
                ? t('tree.row.cannot_move_badge')
                : t('tree.row.drop_into_badge', { name: node.name })}
            </span>
          )}
        </div>

        {/* Stats Column */}
        <div className="deck-stats-col pointer-events-auto grid grid-cols-[repeat(3,38px)_26px] sm:grid-cols-[repeat(3,64px)_30px] gap-1 sm:gap-2 items-center text-right shrink-0">
          <span className="stat-num stat-new text-xs sm:text-base font-normal tabular-nums text-emerald-600">
            {node.counts.new.toLocaleString(numberLocale)}
          </span>
          <span className="stat-num stat-learn text-xs sm:text-base font-normal tabular-nums text-rose-600">
            {node.counts.learning.toLocaleString(numberLocale)}
          </span>
          <span className="stat-num stat-due text-xs sm:text-base font-semibold tabular-nums text-orange-600">
            {node.counts.due.toLocaleString(numberLocale)}
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
                  aria-label={t('tree.row.settings_aria')}
                  title={t('tree.row.settings_aria')}
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
                      <span>{t('tree.row.menu.rename')}</span>
                    </DropdownMenuItem>

                    <DropdownMenuItem
                      className="cursor-pointer text-sm py-2 px-2.5 font-medium flex items-center gap-2"
                      onSelect={() => onAction({ type: 'move', deck: node })}
                    >
                      <ArrowLeftRight className="size-4 text-muted-foreground" />
                      <span>{t('tree.row.menu.move')}</span>
                    </DropdownMenuItem>

                    <DropdownMenuItem
                      className="cursor-pointer text-sm py-2 px-2.5 font-medium flex items-center gap-2"
                      onSelect={handleCopyMoveId}
                    >
                      <Copy className="size-4 text-muted-foreground" />
                      <span>{t('tree.row.menu.copy_move_id')}</span>
                    </DropdownMenuItem>

                    <DropdownMenuSeparator className="my-1" />
                  </>
                ) : null}

                <DropdownMenuItem
                  className="cursor-pointer text-sm py-2 px-2.5 font-semibold text-orange-700 flex items-center gap-2"
                  onSelect={() => window.location.assign(node.actions.share)}
                >
                  <Share className="size-4 text-orange-600" />
                  <span>{t('tree.row.menu.share')}</span>
                </DropdownMenuItem>

                <DropdownMenuItem
                  className="cursor-pointer text-sm py-2 px-2.5 font-medium flex items-center gap-2"
                  onSelect={() => navigate(`/flashcards/import?deck_id=${node.id}`)}
                >
                  <Upload className="size-4 text-muted-foreground" />
                  <span>{t('tree.row.menu.import_cards')}</span>
                </DropdownMenuItem>

                <DropdownMenuItem
                  className="cursor-pointer text-sm py-2 px-2.5 font-medium flex items-center gap-2"
                  onSelect={() => onAction({ type: 'card-types', deck: node })}
                >
                  <Layers className="size-4 text-orange-600" />
                  <span>{t('tree.row.menu.card_types')}</span>
                </DropdownMenuItem>

                <DropdownMenuItem
                  className="cursor-pointer text-sm py-2 px-2.5 font-medium flex items-center gap-2"
                  onSelect={() => onAction({ type: 'worksheet', deck: node })}
                >
                  <Printer className="size-4 text-orange-600" />
                  <span>{t('tree.row.menu.worksheet')}</span>
                </DropdownMenuItem>

                <DropdownMenuSeparator className="my-1" />

                <DropdownMenuItem
                  className="cursor-pointer text-sm py-2 px-2.5 font-medium text-amber-700 focus:text-amber-800 focus:bg-amber-50 flex items-center gap-2"
                  onSelect={() => onAction({ type: 'reset', deck: node })}
                >
                  <ArrowCounterclockwise className="size-4 text-amber-600" />
                  <span>{t('tree.row.menu.reset_progress')}</span>
                </DropdownMenuItem>

                <DropdownMenuItem
                  className="cursor-pointer text-sm py-2 px-2.5 font-medium text-rose-700 focus:text-rose-800 focus:bg-rose-50 flex items-center gap-2"
                  onSelect={() => onAction({ type: 'delete', deck: node })}
                >
                  <TrashFill className="size-4 text-rose-600" />
                  <span>{t('tree.row.menu.delete_deck')}</span>
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
              isExpanded={isExpanded}
              onToggleExpand={onToggleExpand}
            />
          ))
        : null}
    </>
  )
}
