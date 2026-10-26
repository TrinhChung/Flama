import { useState, useMemo, useRef, useCallback, useEffect } from 'react'
import { Layers } from 'lucide-react'
import {
  calculateDiffSummary,
  groupCardDiffsByNoteType,
  type DiffFilterState,
} from '@/entities/card-diff'
import { useVirtualDiffList } from '../hooks/useVirtualDiffList'
import { DiffFilterToolbar } from './DiffFilterToolbar'
import { BatchActionBar } from './BatchActionBar'
import { CardDiffItem } from './CardDiffItem'
import { NoteTypeDiffGroup } from './NoteTypeDiffGroup'
import type {
  FlatWorkspaceRow,
  HighVolumeDiffWorkspaceProps,
} from '../model/types'

export function HighVolumeDiffWorkspace({
  items,
  groups: providedGroups,
  onApproveSelected,
  onRejectSelected,
  onApproveGroup,
  onRejectGroup,
  initialFilters,
  containerHeight = 'max(380px, min(65vh, calc(100dvh - 280px)))',
  estimateItemHeight = 68,
  className = '',
  isProcessing = false,
  emptyTitle = 'Không có thay đổi nào',
  emptyDescription = 'Không có mục nào phù hợp với bộ lọc hiện tại.',
}: HighVolumeDiffWorkspaceProps) {
  // Filter state
  const [filters, setFilters] = useState<DiffFilterState>(() => ({
    changeType: initialFilters?.changeType ?? 'all',
    noteTypeId: initialFilters?.noteTypeId ?? 'all',
    searchQuery: initialFilters?.searchQuery ?? '',
  }))

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [lastSelectedId, setLastSelectedId] = useState<string | null>(null)

  // Collapsed groups state
  const [collapsedGroupIds, setCollapsedGroupIds] = useState<Set<string>>(new Set())

  // Overall summary calculated from all input items
  const summary = useMemo(() => calculateDiffSummary(items), [items])

  // All groups from items
  const allGroups = useMemo(
    () => providedGroups ?? groupCardDiffsByNoteType(items),
    [providedGroups, items],
  )

  // Filter items based on active criteria
  const filteredItems = useMemo(() => {
    const query = filters.searchQuery.trim().toLowerCase()

    return items.filter((item) => {
      // 1. Filter by Note Type
      if (filters.noteTypeId !== 'all' && item.noteTypeId !== filters.noteTypeId) {
        return false
      }

      // 2. Filter by Change Type
      if (filters.changeType !== 'all' && item.changeType !== filters.changeType) {
        return false
      }

      // 3. Search query filter
      if (query) {
        const matchPrimary = item.primaryText?.toLowerCase().includes(query)
        const matchSecondary = item.secondaryText?.toLowerCase().includes(query)
        const matchNoteType = item.noteTypeName?.toLowerCase().includes(query)
        const matchFieldDiffs = item.fieldDiffs?.some(
          (f) =>
            f.fieldName.toLowerCase().includes(query) ||
            String(f.before ?? '').toLowerCase().includes(query) ||
            String(f.after ?? '').toLowerCase().includes(query),
        )

        if (!matchPrimary && !matchSecondary && !matchNoteType && !matchFieldDiffs) {
          return false
        }
      }

      return true
    })
  }, [items, filters])

  // Filtered groups
  const filteredGroups = useMemo(
    () => groupCardDiffsByNoteType(filteredItems),
    [filteredItems],
  )

  // Flattened rows for virtualization (Group Headers + Cards)
  const flatRows = useMemo<FlatWorkspaceRow[]>(() => {
    const rows: FlatWorkspaceRow[] = []

    filteredGroups.forEach((group, gIdx) => {
      const isCollapsed = collapsedGroupIds.has(group.noteTypeId)
      const groupItemIds = group.items.map((i) => i.id)
      const allSelected =
        groupItemIds.length > 0 && groupItemIds.every((id) => selectedIds.has(id))
      const someSelected =
        !allSelected && groupItemIds.some((id) => selectedIds.has(id))

      // Push Header Row
      rows.push({
        type: 'header',
        id: `header_${group.noteTypeId}`,
        group,
        isCollapsed,
        allSelected,
        someSelected,
      })

      // If not collapsed, push Card Rows
      if (!isCollapsed) {
        group.items.forEach((item, cIdx) => {
          rows.push({
            type: 'card',
            id: item.id,
            item,
            groupIndex: gIdx,
            cardIndex: cIdx,
          })
        })
      }
    })

    return rows
  }, [filteredGroups, collapsedGroupIds, selectedIds])

  // Virtualization container
  const containerRef = useRef<HTMLDivElement>(null)

  const getItemHeight = useCallback(
    (index: number) => {
      const row = flatRows[index]
      if (!row) return estimateItemHeight
      return row.type === 'header' ? 52 : estimateItemHeight
    },
    [flatRows, estimateItemHeight],
  )

  const { virtualRows, paddingTop, paddingBottom, resetSearchBypass } = useVirtualDiffList({
    count: flatRows.length,
    containerRef,
    estimateHeight: estimateItemHeight,
    getItemHeight,
    overscan: 12,
  })

  // Recover virtualization on Escape or container scroll after in-browser search (Ctrl+F)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        resetSearchBypass()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [resetSearchBypass])

  const handleContainerScroll = useCallback(() => {
    resetSearchBypass()
  }, [resetSearchBypass])

  // Selection handlers
  const handleToggleCard = useCallback(
    (id: string, shiftKey: boolean) => {
      setSelectedIds((prev) => {
        const next = new Set(prev)

        if (shiftKey && lastSelectedId) {
          const visibleCardIds = filteredItems.map((i) => i.id)
          const lastIdx = visibleCardIds.indexOf(lastSelectedId)
          const currIdx = visibleCardIds.indexOf(id)

          if (lastIdx !== -1 && currIdx !== -1) {
            const start = Math.min(lastIdx, currIdx)
            const end = Math.max(lastIdx, currIdx)
            for (let i = start; i <= end; i++) {
              next.add(visibleCardIds[i])
            }
            return next
          }
        }

        if (next.has(id)) {
          next.delete(id)
        } else {
          next.add(id)
        }

        return next
      })

      setLastSelectedId(id)
    },
    [lastSelectedId, filteredItems],
  )

  const handleToggleSelectGroup = useCallback(
    (noteTypeId: string) => {
      const group = filteredGroups.find((g) => g.noteTypeId === noteTypeId)
      if (!group) return

      const groupItemIds = group.items.map((i) => i.id)
      const allSelected = groupItemIds.every((id) => selectedIds.has(id))

      setSelectedIds((prev) => {
        const next = new Set(prev)
        if (allSelected) {
          groupItemIds.forEach((id) => next.delete(id))
        } else {
          groupItemIds.forEach((id) => next.add(id))
        }
        return next
      })
    },
    [filteredGroups, selectedIds],
  )

  const handleToggleSelectAllVisible = useCallback(() => {
    const visibleIds = filteredItems.map((i) => i.id)
    const allSelected =
      visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id))

    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (allSelected) {
        visibleIds.forEach((id) => next.delete(id))
      } else {
        visibleIds.forEach((id) => next.add(id))
      }
      return next
    })
  }, [filteredItems, selectedIds])

  const handleToggleCollapse = useCallback((noteTypeId: string) => {
    setCollapsedGroupIds((prev) => {
      const next = new Set(prev)
      if (next.has(noteTypeId)) {
        next.delete(noteTypeId)
      } else {
        next.add(noteTypeId)
      }
      return next
    })
  }, [])

  // Batch action callbacks
  const handleApproveSelected = useCallback(async () => {
    if (selectedIds.size === 0) return
    const ids = Array.from(selectedIds)
    await onApproveSelected?.(ids)
  }, [selectedIds, onApproveSelected])

  const handleRejectSelected = useCallback(async () => {
    if (selectedIds.size === 0) return
    const ids = Array.from(selectedIds)
    await onRejectSelected?.(ids)
  }, [selectedIds, onRejectSelected])

  const handleApproveGroupAction = useCallback(
    async (noteTypeId: string, noteIds: string[]) => {
      if (onApproveGroup) {
        await onApproveGroup(noteTypeId, noteIds)
      } else if (onApproveSelected) {
        await onApproveSelected(noteIds)
      }
    },
    [onApproveGroup, onApproveSelected],
  )

  const handleRejectGroupAction = useCallback(
    async (noteTypeId: string, noteIds: string[]) => {
      if (onRejectGroup) {
        await onRejectGroup(noteTypeId, noteIds)
      } else if (onRejectSelected) {
        await onRejectSelected(noteIds)
      }
    },
    [onRejectGroup, onRejectSelected],
  )

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set())
    setLastSelectedId(null)
  }, [])

  return (
    <div
      className={`relative space-y-4 max-w-7xl mx-auto w-full ${className}`}
      data-testid="high-volume-diff-workspace"
    >
      {/* Multi-Criteria Filter & Search Toolbar */}
      <DiffFilterToolbar
        filters={filters}
        summary={summary}
        groups={allGroups}
        visibleCount={filteredItems.length}
        selectedCount={selectedIds.size}
        onFiltersChange={setFilters}
        onToggleSelectAllVisible={handleToggleSelectAllVisible}
      />

      {/* Main Diff Content */}
      {filteredItems.length === 0 ? (
        <div
          className="rounded-2xl border border-dashed border-border/80 bg-muted/20 px-6 py-14 text-center"
          data-testid="empty-diff-state"
        >
          <Layers className="size-10 mx-auto text-muted-foreground/60 mb-2" />
          <h3 className="font-semibold text-foreground text-sm">{emptyTitle}</h3>
          <p className="mt-1 text-xs text-muted-foreground">{emptyDescription}</p>
        </div>
      ) : (
        <div
          ref={containerRef}
          onScroll={handleContainerScroll}
          className="relative overflow-y-auto rounded-2xl border border-border/80 bg-muted/10 p-2 sm:p-3 space-y-2 focus:outline-none max-h-[58vh] sm:max-h-[65vh] lg:max-h-[calc(100dvh-20rem)]"
          style={{ maxHeight: containerHeight }}
          data-testid="virtualized-diff-container"
          tabIndex={0}
          aria-label="Danh sách thay đổi thẻ học"
        >
          {/* Top Virtual Spacer */}
          <div
            style={{ height: `${paddingTop}px` }}
            aria-hidden="true"
            data-testid="virtual-spacer-top"
          />

          {/* Rendered Virtual Rows */}
          {virtualRows.map((virtualRow) => {
            const row = flatRows[virtualRow.index]
            if (!row) return null

            if (row.type === 'header') {
              return (
                <NoteTypeDiffGroup
                  key={row.id}
                  group={row.group}
                  isCollapsed={row.isCollapsed}
                  allSelected={row.allSelected}
                  someSelected={row.someSelected}
                  onToggleCollapse={handleToggleCollapse}
                  onToggleSelectGroup={handleToggleSelectGroup}
                  onApproveGroup={handleApproveGroupAction}
                  onRejectGroup={handleRejectGroupAction}
                />
              )
            }

            const isSelected = selectedIds.has(row.item.id)
            return (
              <CardDiffItem
                key={row.item.id}
                item={row.item}
                isSelected={isSelected}
                onToggle={handleToggleCard}
              />
            )
          })}

          {/* Bottom Virtual Spacer */}
          <div
            style={{ height: `${paddingBottom}px` }}
            aria-hidden="true"
            data-testid="virtual-spacer-bottom"
          />
        </div>
      )}

      {/* Persistent / Floating Batch Action Bar */}
      <BatchActionBar
        selectedCount={selectedIds.size}
        totalCount={filteredItems.length}
        onApprove={handleApproveSelected}
        onReject={handleRejectSelected}
        onClear={handleClearSelection}
        isProcessing={isProcessing}
      />
    </div>
  )
}
