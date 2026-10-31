import type { ChangeSelectionMode } from '../types'
import type { FieldChange, NoteChange, SchemaChange } from './noteChanges'

export type CheckState = boolean | 'indeterminate'

/** One note's ticks as plain values, so an unchanged card can skip rendering. */
export type NoteTicks = {
  checked: CheckState
  /** One '1'/'0' per change of the note, in order; empty for whole-note picking. */
  fieldMask: string
}

/**
 * What the change list may tick. Contributors pick whole notes and the field
 * structure as one group; owners can also pick single fields and items.
 * The toggle callbacks keep their identity across renders.
 */
export type NoteSelectionControls = {
  granularity: 'note' | 'field'
  noteTicks: (note: NoteChange) => NoteTicks
  onToggleNote: (note: NoteChange, selected: boolean) => void
  onToggleField: (change: FieldChange, selected: boolean) => void
  schemaGranularity: 'group' | 'item'
  /** `change` is null for the whole group. */
  schemaState: (change: SchemaChange | null) => CheckState
  setSchema: (change: SchemaChange | null, selected: boolean) => void
  /** A field addition kept because a selected note writes into that field. */
  schemaRequired: (change: SchemaChange) => boolean
  selectAll: () => void
  selectNone: () => void
  selectedCount: number
  totalCount: number
  unit: 'note' | 'change'
}

/**
 * A selection over a list that may not be fully loaded: "everything except
 * these keys" or "only these keys". Unloaded rows follow `base`.
 */
export type ChangeSelection = {
  base: 'all' | 'none'
  toggled: ReadonlySet<string>
}

export const SELECT_ALL: ChangeSelection = { base: 'all', toggled: new Set() }
export const SELECT_NONE: ChangeSelection = { base: 'none', toggled: new Set() }

/** Key of the learner's field-structure changes, sent or skipped together. */
export const SCHEMA_SELECTION_KEY = '__schema__'

export function isKeySelected(selection: ChangeSelection, key: string): boolean {
  return selection.base === 'all' ? !selection.toggled.has(key) : selection.toggled.has(key)
}

export function setKeysSelected(
  selection: ChangeSelection,
  keys: string[],
  selected: boolean,
): ChangeSelection {
  const toggled = new Set(selection.toggled)
  const toggle = selected !== (selection.base === 'all')
  for (const key of keys) {
    if (toggle) toggled.add(key)
    else toggled.delete(key)
  }
  return { base: selection.base, toggled }
}

export function selectsEverything(selection: ChangeSelection): boolean {
  return selection.base === 'all' && selection.toggled.size === 0
}

/** Selected count out of `total` keys, ignoring keys outside `countedKeys`. */
export function countSelected(
  selection: ChangeSelection,
  total: number,
  isCounted: (key: string) => boolean = () => true,
): number {
  const toggled = [...selection.toggled].filter(isCounted).length
  return selection.base === 'all' ? Math.max(0, total - toggled) : toggled
}

export function selectionRequest(
  selection: ChangeSelection,
  isCounted: (key: string) => boolean = () => true,
): { mode: ChangeSelectionMode; ids: string[] } {
  return {
    mode: selection.base === 'all' ? 'all_except' : 'only',
    ids: [...selection.toggled].filter(isCounted),
  }
}
