/**
 * Domain entity types for Card Diffs and Hierarchical Review Merge.
 * Layer: entities/card-diff (FSD v2.1)
 */

export type DiffChangeType = 'added' | 'modified' | 'removed' | 'conflict'

export type DiffChangeFilter = 'all' | DiffChangeType

export type FieldDiff = {
  fieldDefId?: string
  fieldName: string
  fieldType?: string
  before?: unknown
  after?: unknown
  isConflict?: boolean
}

export type CardDiff = {
  id: string
  noteId: string
  noteTypeId: string
  noteTypeName: string
  changeType: DiffChangeType
  primaryText: string
  secondaryText?: string
  fieldDiffs?: FieldDiff[]
  status?: 'pending' | 'approved' | 'rejected'
}

export type CardDiffGroup = {
  noteTypeId: string
  noteTypeName: string
  items: CardDiff[]
  totalCount: number
  addedCount: number
  modifiedCount: number
  removedCount: number
  conflictCount: number
}

export type DiffFilterState = {
  changeType: DiffChangeFilter
  noteTypeId: string
  searchQuery: string
}

export type CardDiffSummary = {
  totalNotes: number
  addedCount: number
  modifiedCount: number
  removedCount: number
  conflictCount: number
}

/**
 * Pure helper to aggregate flat CardDiff items into NoteType groups with item counts.
 */
export function groupCardDiffsByNoteType(items: CardDiff[]): CardDiffGroup[] {
  const groupsMap = new Map<string, CardDiffGroup>()

  for (const item of items) {
    let group = groupsMap.get(item.noteTypeId)
    if (!group) {
      group = {
        noteTypeId: item.noteTypeId,
        noteTypeName: item.noteTypeName || item.noteTypeId,
        items: [],
        totalCount: 0,
        addedCount: 0,
        modifiedCount: 0,
        removedCount: 0,
        conflictCount: 0,
      }
      groupsMap.set(item.noteTypeId, group)
    }

    group.items.push(item)
    group.totalCount += 1
    if (item.changeType === 'added') group.addedCount += 1
    else if (item.changeType === 'modified') group.modifiedCount += 1
    else if (item.changeType === 'removed') group.removedCount += 1
    else if (item.changeType === 'conflict') group.conflictCount += 1
  }

  return Array.from(groupsMap.values())
}

/**
 * Pure helper to calculate total change summary from CardDiff items.
 */
export function calculateDiffSummary(items: CardDiff[]): CardDiffSummary {
  let addedCount = 0
  let modifiedCount = 0
  let removedCount = 0
  let conflictCount = 0

  for (const item of items) {
    if (item.changeType === 'added') addedCount += 1
    else if (item.changeType === 'modified') modifiedCount += 1
    else if (item.changeType === 'removed') removedCount += 1
    else if (item.changeType === 'conflict') conflictCount += 1
  }

  return {
    totalNotes: items.length,
    addedCount,
    modifiedCount,
    removedCount,
    conflictCount,
  }
}
