import { useState } from 'react'
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
  onAction: (action: SelectedDeckAction) => void
}

function DeckRow({
  node,
  adminMode,
  selectedDeckId,
  onSelect,
  onAction,
}: {
  node: DeckNode
  adminMode: boolean
  selectedDeckId?: number | null
  onSelect?: (deck: DeckNode) => void
  onAction: (action: SelectedDeckAction) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = node.children.length > 0
  const isSelected = selectedDeckId === node.id

  const handleCopyMoveId = () => {
    void navigator.clipboard.writeText(node.move.alias)
  }

  return (
    <>
      <div
        className={cn(
          'deck-row group flex items-center justify-between py-2 px-1 rounded-md border-b border-transparent cursor-pointer transition-all hover:bg-[#fff8f5]',
          isSelected && 'is-selected bg-[#fff1e6]',
        )}
        onClick={() => onSelect?.(node)}
      >
        {/* Name Column */}
        <div
          className="deck-name-col flex flex-1 items-center min-w-0 pr-4"
          style={{ paddingLeft: `${node.depth * 1.5}rem` }}
        >
          {hasChildren ? (
            <button
              type="button"
              className="tree-toggle inline-flex size-6 shrink-0 items-center justify-center rounded text-muted-foreground transition hover:bg-muted hover:text-orange-600 mr-2"
              data-expanded={expanded}
              aria-expanded={expanded}
              onClick={(e) => {
                e.stopPropagation()
                setExpanded((prev) => !prev)
              }}
            >
              <ChevronRight
                className={cn('size-4 transition-transform duration-200', expanded && 'rotate-90')}
              />
            </button>
          ) : (
            <span className="tree-spacer inline-block size-6 shrink-0 mr-2" />
          )}

          <span
            className="deck-name text-base font-normal text-foreground truncate group-hover:text-orange-600 transition-colors"
            onDoubleClick={(e) => {
              e.stopPropagation()
              window.location.assign(node.study_url)
            }}
          >
            {node.name}
          </span>
        </div>

        {/* Stats Column */}
        <div className="deck-stats-col grid grid-cols-[repeat(3,64px)_30px] gap-2 items-center text-right">
          <span className="stat-num stat-new text-base font-normal tabular-nums text-emerald-600">
            {node.counts.new.toLocaleString('vi-VN')}
          </span>
          <span className="stat-num stat-learn text-base font-normal tabular-nums text-rose-600">
            {node.counts.learning.toLocaleString('vi-VN')}
          </span>
          <span className="stat-num stat-due text-base font-semibold tabular-nums text-orange-600">
            {node.counts.due.toLocaleString('vi-VN')}
          </span>

          {/* Deck Settings Gear Dropdown */}
          <div className="deck-settings-wrapper flex justify-center items-center">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className={cn(
                    'deck-settings-btn hidden group-hover:inline-flex size-7 items-center justify-center rounded-full text-muted-foreground opacity-75 transition-all hover:opacity-100 hover:text-orange-700 hover:bg-orange-50 border border-transparent hover:border-orange-300 hover:rotate-12',
                    isSelected && 'inline-flex opacity-100',
                  )}
                  onClick={(e) => e.stopPropagation()}
                  aria-label="Deck Settings"
                  title="Deck Settings"
                >
                  <GearFill className="size-4" />
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
              onAction={onAction}
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
  onAction,
}: DeckTreeProps) {
  return (
    <div className="deck-list flex flex-col divide-y divide-gray-100">
      {nodes.map((node) => (
        <DeckRow
          key={node.id}
          node={node}
          adminMode={adminMode}
          selectedDeckId={selectedDeckId}
          onSelect={onSelect}
          onAction={onAction}
        />
      ))}
    </div>
  )
}
