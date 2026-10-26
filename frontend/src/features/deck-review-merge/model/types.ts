import type {
  CardDiff,
  CardDiffGroup,
  CardDiffSummary,
  DiffFilterState,
} from '@/entities/card-diff'

export type BatchReviewAction = 'batch_approve' | 'batch_reject'

export type BatchActionPayload = {
  action: 'approve' | 'reject'
  noteIds: string[]
  noteTypeId?: string
}

export type FlatWorkspaceHeaderRow = {
  type: 'header'
  id: string
  group: CardDiffGroup
  isCollapsed: boolean
  allSelected: boolean
  someSelected: boolean
}

export type FlatWorkspaceCardRow = {
  type: 'card'
  id: string
  item: CardDiff
  groupIndex: number
  cardIndex: number
}

export type FlatWorkspaceRow = FlatWorkspaceHeaderRow | FlatWorkspaceCardRow

export type HighVolumeDiffWorkspaceProps = {
  items: CardDiff[]
  groups?: CardDiffGroup[]
  onApproveSelected?: (selectedIds: string[]) => Promise<void> | void
  onRejectSelected?: (selectedIds: string[]) => Promise<void> | void
  onApproveGroup?: (noteTypeId: string, noteIds: string[]) => Promise<void> | void
  onRejectGroup?: (noteTypeId: string, noteIds: string[]) => Promise<void> | void
  initialFilters?: Partial<DiffFilterState>
  containerHeight?: number | string
  estimateItemHeight?: number
  className?: string
  isProcessing?: boolean
  emptyTitle?: string
  emptyDescription?: string
}

export type DiffFilterToolbarProps = {
  filters: DiffFilterState
  summary: CardDiffSummary
  groups: CardDiffGroup[]
  visibleCount: number
  selectedCount: number
  onFiltersChange: (filters: DiffFilterState) => void
  onToggleSelectAllVisible: () => void
  className?: string
}

export type BatchActionBarProps = {
  selectedCount: number
  totalCount: number
  onApprove: () => Promise<void> | void
  onReject: () => Promise<void> | void
  onClear: () => void
  isProcessing?: boolean
  className?: string
}

export type CardDiffItemProps = {
  item: CardDiff
  isSelected: boolean
  onToggle: (id: string, shiftKey: boolean) => void
  className?: string
}

export type NoteTypeDiffGroupProps = {
  group: CardDiffGroup
  isCollapsed: boolean
  allSelected: boolean
  someSelected: boolean
  onToggleCollapse: (noteTypeId: string) => void
  onToggleSelectGroup: (noteTypeId: string) => void
  onApproveGroup?: (noteTypeId: string, noteIds: string[]) => void
  onRejectGroup?: (noteTypeId: string, noteIds: string[]) => void
  className?: string
}
