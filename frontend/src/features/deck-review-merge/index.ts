/**
 * Public API for features/deck-review-merge (FSD v2.1)
 */

export { HighVolumeDiffWorkspace } from './components/HighVolumeDiffWorkspace'
export { DiffFilterToolbar } from './components/DiffFilterToolbar'
export { BatchActionBar } from './components/BatchActionBar'
export { CardDiffItem } from './components/CardDiffItem'
export { NoteTypeDiffGroup } from './components/NoteTypeDiffGroup'
export { useVirtualDiffList } from './hooks/useVirtualDiffList'
export type { VirtualRow, VirtualDiffListOptions, VirtualDiffListResult } from './hooks/useVirtualDiffList'

export type {
  BatchReviewAction,
  BatchActionPayload,
  FlatWorkspaceRow,
  FlatWorkspaceHeaderRow,
  FlatWorkspaceCardRow,
  HighVolumeDiffWorkspaceProps,
  DiffFilterToolbarProps,
  BatchActionBarProps,
  CardDiffItemProps,
  NoteTypeDiffGroupProps,
} from './model/types'
