import type { ReactNode, MouseEvent } from 'react'
import {
  ChevronDown,
  ChevronRight,
  CheckSquare,
  Square,
  CheckCircle2,
  XCircle,
  Layers,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { CardDiffGroup } from '@/entities/card-diff'

export type NoteTypeDiffGroupProps = {
  group: CardDiffGroup
  isCollapsed: boolean
  allSelected: boolean
  someSelected: boolean
  onToggleCollapse: (noteTypeId: string) => void
  onToggleSelectGroup: (noteTypeId: string) => void
  onApproveGroup?: (noteTypeId: string, noteIds: string[]) => void
  onRejectGroup?: (noteTypeId: string, noteIds: string[]) => void
  children?: ReactNode
  className?: string
}

export function NoteTypeDiffGroup({
  group,
  isCollapsed,
  allSelected,
  someSelected,
  onToggleCollapse,
  onToggleSelectGroup,
  onApproveGroup,
  onRejectGroup,
  children,
  className = '',
}: NoteTypeDiffGroupProps) {
  const noteIds = group.items.map((item) => item.id)

  const handleCheckboxClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    onToggleSelectGroup(group.noteTypeId)
  }

  const handleApproveGroup = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    onApproveGroup?.(group.noteTypeId, noteIds)
  }

  const handleRejectGroup = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    onRejectGroup?.(group.noteTypeId, noteIds)
  }

  return (
    <div
      className={`rounded-2xl border border-border/80 bg-card overflow-hidden shadow-2xs transition-colors ${className}`}
      data-testid={`note-type-group-${group.noteTypeId}`}
    >
      {/* Group Header */}
      <div
        onClick={() => onToggleCollapse(group.noteTypeId)}
        className="flex flex-wrap items-center justify-between gap-2 sm:gap-3 p-3 sm:px-4 bg-muted/30 hover:bg-muted/50 cursor-pointer select-none transition-colors border-b border-border/50"
        role="button"
        tabIndex={0}
        aria-expanded={!isCollapsed}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onToggleCollapse(group.noteTypeId)
          }
        }}
      >
        {/* Left: Collapse icon, Checkbox, Title & Count Badges */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 min-w-0">
          <div className="text-muted-foreground hover:text-foreground">
            {isCollapsed ? (
              <ChevronRight className="size-4" />
            ) : (
              <ChevronDown className="size-4" />
            )}
          </div>

          {/* Group Select All Checkbox */}
          <button
            type="button"
            onClick={handleCheckboxClick}
            className="shrink-0 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded cursor-pointer"
            aria-label={
              allSelected
                ? `Bỏ chọn toàn bộ nhóm ${group.noteTypeName}`
                : `Chọn toàn bộ nhóm ${group.noteTypeName}`
            }
            data-testid={`group-checkbox-${group.noteTypeId}`}
          >
            {allSelected ? (
              <CheckSquare className="size-4 text-primary" />
            ) : someSelected ? (
              <div className="flex items-center justify-center size-4 rounded border border-primary bg-primary/20 text-primary">
                <span className="block w-2 h-0.5 bg-primary rounded-xs" />
              </div>
            ) : (
              <Square className="size-4" />
            )}
          </button>

          <div className="flex items-center gap-2 min-w-0">
            <Layers className="size-4 text-primary shrink-0" />
            <span
              className="font-semibold text-sm text-foreground truncate"
              title={group.noteTypeName}
            >
              {group.noteTypeName}
            </span>
            <span className="text-xs text-muted-foreground font-mono">
              ({group.totalCount} thẻ)
            </span>
          </div>

          {/* Breakdown Badges */}
          <div className="flex items-center gap-1.5 ml-1">
            {group.addedCount > 0 && (
              <Badge
                variant="outline"
                className="text-[10px] h-4 px-1.5 font-mono text-emerald-700 bg-emerald-500/10 border-emerald-500/20 dark:text-emerald-300"
              >
                +{group.addedCount}
              </Badge>
            )}
            {group.modifiedCount > 0 && (
              <Badge
                variant="outline"
                className="text-[10px] h-4 px-1.5 font-mono text-amber-800 bg-amber-500/10 border-amber-500/20 dark:text-amber-300"
              >
                ~{group.modifiedCount}
              </Badge>
            )}
            {group.removedCount > 0 && (
              <Badge
                variant="outline"
                className="text-[10px] h-4 px-1.5 font-mono text-rose-700 bg-rose-500/10 border-rose-500/20 dark:text-rose-300"
              >
                -{group.removedCount}
              </Badge>
            )}
            {group.conflictCount > 0 && (
              <Badge
                variant="outline"
                className="text-[10px] h-4 px-1.5 font-mono text-amber-700 bg-amber-500/10 border-amber-500/20 dark:text-amber-300"
              >
                !{group.conflictCount}
              </Badge>
            )}
          </div>
        </div>

        {/* Right: Group-Level Quick Actions */}
        <div className="flex items-center gap-1.5">
          {onApproveGroup && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleApproveGroup}
              className="h-7 px-2 text-xs text-emerald-700 hover:text-emerald-800 dark:text-emerald-400 hover:bg-emerald-500/10 gap-1 font-medium cursor-pointer"
              title="Chấp nhận tất cả thay đổi trong nhóm này"
              data-testid={`approve-group-${group.noteTypeId}`}
            >
              <CheckCircle2 className="size-3.5" />
              <span className="hidden sm:inline">Chấp nhận cả nhóm</span>
            </Button>
          )}

          {onRejectGroup && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleRejectGroup}
              className="h-7 px-2 text-xs text-rose-700 hover:text-rose-800 dark:text-rose-400 hover:bg-rose-500/10 gap-1 font-medium cursor-pointer"
              title="Từ chối tất cả thay đổi trong nhóm này"
              data-testid={`reject-group-${group.noteTypeId}`}
            >
              <XCircle className="size-3.5" />
              <span className="hidden sm:inline">Từ chối cả nhóm</span>
            </Button>
          )}
        </div>
      </div>

      {/* Group Content when expanded */}
      {!isCollapsed && children && (
        <div className="p-2 sm:p-3 space-y-2 animate-in fade-in">
          {children}
        </div>
      )}
    </div>
  )
}
