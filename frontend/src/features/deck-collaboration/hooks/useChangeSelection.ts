import { startTransition, useCallback, useEffect, useMemo, useState } from 'react'
import {
  requiredFieldAdditions,
  type FieldChange,
  type GroupedContribution,
  type NoteChange,
  type SchemaChange,
} from '../model/noteChanges'
import {
  SCHEMA_SELECTION_KEY,
  SELECT_ALL,
  SELECT_NONE,
  countSelected,
  isKeySelected,
  selectionRequest,
  selectsEverything,
  setKeysSelected,
  type ChangeSelection,
  type NoteSelectionControls,
  type NoteTicks,
} from '../model/selection'
import type { ContributionSendSelection, ReviewSelection } from '../types'

const isNoteKey = (key: string) => key !== SCHEMA_SELECTION_KEY

/** Contributor picks whole notes, plus the field structure as one group. */
export function useContributionSelection({
  grouped,
  totalNotes,
  resetKey,
}: {
  grouped: GroupedContribution
  totalNotes: number
  resetKey: string
}) {
  const [selection, setSelection] = useState<ChangeSelection>(SELECT_ALL)

  useEffect(() => {
    setSelection(SELECT_ALL)
  }, [resetKey])

  const schemaSelected = isKeySelected(selection, SCHEMA_SELECTION_KEY)
  const neededAdditions = useMemo(
    () => requiredFieldAdditions(grouped.notes, (note) => isKeySelected(selection, note.noteId)),
    [grouped.notes, selection],
  )
  const selectedNotes = countSelected(selection, totalNotes, isNoteKey)

  // Toggles only read the previous state, so cards can keep them across renders.
  const onToggleNote = useCallback((note: NoteChange, selected: boolean) => {
    setSelection((current) => setKeysSelected(current, [note.noteId], selected))
  }, [])
  const setSchema = useCallback((_change: SchemaChange | null, selected: boolean) => {
    setSelection((current) => setKeysSelected(current, [SCHEMA_SELECTION_KEY], selected))
  }, [])
  // Every card changes at once, so render in a transition that yields to input.
  const selectAll = useCallback(() => startTransition(() => setSelection(SELECT_ALL)), [])
  const selectNone = useCallback(() => startTransition(() => setSelection(SELECT_NONE)), [])

  const controls: NoteSelectionControls = {
    granularity: 'note',
    noteTicks: (note): NoteTicks => ({ checked: isKeySelected(selection, note.noteId), fieldMask: '' }),
    onToggleNote,
    onToggleField: noToggle,
    schemaGranularity: 'group',
    schemaState: () => schemaSelected,
    setSchema,
    schemaRequired: (change) => Boolean(
      !schemaSelected
      && change.changeType === 'field_def_add'
      && change.localRefId
      && neededAdditions.has(change.localRefId),
    ),
    selectAll,
    selectNone,
    selectedCount: selectedNotes,
    totalCount: totalNotes,
    unit: 'note',
  }

  const request = selectionRequest(selection, isNoteKey)
  const payload: ContributionSendSelection = {
    mode: request.mode,
    note_ids: request.ids,
    include_schema_changes: schemaSelected,
  }

  return {
    controls,
    payload,
    hasSelection: selectedNotes > 0 || (schemaSelected && grouped.schema.length > 0),
  }
}

function noToggle() {}

function noteItemIds(note: NoteChange): string[] {
  return note.changes.flatMap((change) => (change.itemId ? [change.itemId] : []))
}

/** Owner picks notes, single fields or single structure changes to accept. */
export function useReviewSelection({
  grouped,
  totalItems,
  resetKey,
}: {
  grouped: GroupedContribution
  totalItems: number
  resetKey: string
}) {
  const [selection, setSelection] = useState<ChangeSelection>(SELECT_ALL)

  useEffect(() => {
    setSelection(SELECT_ALL)
  }, [resetKey])

  const isItemSelected = (itemId: string | null) => Boolean(itemId && isKeySelected(selection, itemId))
  const neededAdditions = useMemo(
    () => requiredFieldAdditions(grouped.notes, (_note, change) =>
      Boolean(change.itemId && isKeySelected(selection, change.itemId))),
    [grouped.notes, selection],
  )
  const selectedCount = countSelected(selection, totalItems)

  const onToggleNote = useCallback((note: NoteChange, selected: boolean) => {
    setSelection((current) => setKeysSelected(current, noteItemIds(note), selected))
  }, [])
  const onToggleField = useCallback((change: FieldChange, selected: boolean) => {
    if (change.itemId) setSelection((current) => setKeysSelected(current, [change.itemId as string], selected))
  }, [])
  const setSchema = useCallback((change: SchemaChange | null, selected: boolean) => {
    if (change?.itemId) setSelection((current) => setKeysSelected(current, [change.itemId as string], selected))
  }, [])
  const selectAll = useCallback(() => startTransition(() => setSelection(SELECT_ALL)), [])
  const selectNone = useCallback(() => startTransition(() => setSelection(SELECT_NONE)), [])

  const controls: NoteSelectionControls = {
    granularity: 'field',
    noteTicks: (note): NoteTicks => {
      let chosen = 0
      const fieldMask = note.changes.map((change) => {
        const selected = isItemSelected(change.itemId)
        if (selected) chosen += 1
        return selected ? '1' : '0'
      }).join('')
      return {
        checked: chosen === 0 ? false : chosen === note.changes.length ? true : 'indeterminate',
        fieldMask,
      }
    },
    onToggleNote,
    onToggleField,
    schemaGranularity: 'item',
    schemaState: (change) => isItemSelected(change?.itemId || null),
    setSchema,
    schemaRequired: (change) => Boolean(
      change.changeType === 'field_def_add'
      && change.localRefId
      && neededAdditions.has(change.localRefId)
      && !isItemSelected(change.itemId),
    ),
    selectAll,
    selectNone,
    selectedCount,
    totalCount: totalItems,
    unit: 'change',
  }

  const request = selectionRequest(selection)
  const payload: ReviewSelection | undefined = selectsEverything(selection)
    ? undefined
    : { mode: request.mode, item_ids: request.ids }

  return {
    controls,
    payload,
    acceptsEverything: selectsEverything(selection),
    hasSelection: selectedCount > 0,
  }
}
