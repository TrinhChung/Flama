import type {
  ChangeRequestConflict,
  ChangeRequestItem,
  LocalChangeItem,
  NoteContext,
  NoteFieldDef,
  ReviewDecision,
} from '../types'

/** A stored request item, or a local change that has not been sent yet. */
export type ContributionChange = ChangeRequestItem | LocalChangeItem

const NOTE_CHANGE_TYPES = new Set(['note_field_set', 'note_field_remove'])

export type FieldChange = {
  /** The item id once stored; local changes get a stable synthetic key. */
  key: string
  itemId: string | null
  fieldName: string
  /** `undefined` when the field had no value. */
  before: unknown
  /** `undefined` when the change empties the field. */
  after: unknown
  conflict: ChangeRequestConflict | null
  hasUnresolvedConflict: boolean
  reviewDecision: ReviewDecision | null
  /** Set when the value goes into a field the contributor added. */
  addedFieldId: string | null
}

export type NoteChange = {
  noteId: string
  label: string
  changes: FieldChange[]
}

export type SchemaChange = {
  key: string
  itemId: string | null
  changeType: string
  fieldName: string
  /** For field updates: name, field_type, required or position. */
  property: string | null
  before: unknown
  after: unknown
  localRefId: string | null
  reviewDecision: ReviewDecision | null
  hasUnresolvedConflict: boolean
}

export type GroupedContribution = {
  notes: NoteChange[]
  schema: SchemaChange[]
}

export type NoteFieldRow = {
  name: string
  fieldType: string
  before: unknown
  after: unknown
  change: FieldChange | null
}

export function isMissingValue(value: unknown): boolean {
  return Boolean(
    value
    && typeof value === 'object'
    && !Array.isArray(value)
    && (value as Record<string, unknown>).__missing__ === true,
  )
}

function present(value: unknown): unknown {
  return isMissingValue(value) ? undefined : value
}

function metadataOf(change: ContributionChange): Record<string, unknown> {
  return 'metadata' in change ? change.metadata || {} : change.metadata_json || {}
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

/** Matches the server's change signature, so local keys survive a refetch. */
export function contributionChangeKey(change: ContributionChange): string {
  if ('id' in change && change.id) return String(change.id)
  return `${change.change_type}:${change.local_ref_id || ''}:${change.path_key || ''}`
}

export function contributionNoteId(change: ContributionChange): string | null {
  if (!NOTE_CHANGE_TYPES.has(change.change_type)) return null
  return text(metadataOf(change).source_note_id) || text(change.source_ref_id)
}

function effectiveAfter(change: ContributionChange): unknown {
  return 'effective_after_value' in change ? change.effective_after_value : change.after_value
}

function storedDecision(change: ContributionChange): ReviewDecision | null {
  return 'review_decision' in change ? change.review_decision || null : null
}

function conflictOf(change: ContributionChange) {
  const conflict = 'conflict' in change ? change.conflict || null : null
  const isConflict = 'is_conflict' in change && change.is_conflict
  return { conflict, hasUnresolvedConflict: Boolean(isConflict && (!conflict || !conflict.resolved_at)) }
}

/** Group atomic field changes into whole notes, keeping the server's order. */
export function groupContributionChanges(changes: ContributionChange[]): GroupedContribution {
  const notes = new Map<string, NoteChange>()
  const schema: SchemaChange[] = []
  for (const change of changes) {
    const metadata = metadataOf(change)
    const fieldName = text(metadata.field_name) || change.path_key || ''
    const noteId = contributionNoteId(change)
    const itemId = 'id' in change && change.id ? String(change.id) : null
    const { conflict, hasUnresolvedConflict } = conflictOf(change)
    if (!noteId) {
      schema.push({
        key: contributionChangeKey(change),
        itemId,
        changeType: change.change_type,
        fieldName,
        property: text(metadata.property_name),
        before: present(change.before_value),
        after: present(effectiveAfter(change)),
        localRefId: change.local_ref_id || null,
        reviewDecision: storedDecision(change),
        hasUnresolvedConflict,
      })
      continue
    }
    let note = notes.get(noteId)
    if (!note) {
      note = { noteId, label: text(metadata.source_note_label) || '', changes: [] }
      notes.set(noteId, note)
    }
    note.changes.push({
      key: contributionChangeKey(change),
      itemId,
      fieldName,
      before: present(change.before_value),
      after: change.change_type === 'note_field_remove' ? undefined : present(effectiveAfter(change)),
      conflict,
      hasUnresolvedConflict,
      reviewDecision: storedDecision(change),
      addedFieldId: text(metadata.local_added_field_def_id),
    })
  }
  return { notes: [...notes.values()], schema }
}

const groupedPages = new WeakMap<ContributionChange[], GroupedContribution>()

/**
 * Group loaded pages, reusing each page's notes so cards for pages already on
 * screen keep their identity (and skip re-rendering) when another page loads.
 */
export function groupContributionPages(pages: Array<{ items: ContributionChange[] }>): GroupedContribution {
  const notes: NoteChange[] = []
  const schema: SchemaChange[] = []
  for (const page of pages) {
    let grouped = groupedPages.get(page.items)
    if (!grouped) {
      grouped = groupContributionChanges(page.items)
      groupedPages.set(page.items, grouped)
    }
    for (const note of grouped.notes) {
      const last = notes[notes.length - 1]
      // Pages end on whole notes; only a note larger than a page continues.
      if (last?.noteId === note.noteId) {
        notes[notes.length - 1] = { ...last, changes: [...last.changes, ...note.changes] }
      } else {
        notes.push(note)
      }
    }
    schema.push(...grouped.schema)
  }
  return { notes, schema }
}

export type DeckGroup = {
  /** '' for notes whose sub-deck is unknown. */
  key: string
  path: string[]
  notes: NoteChange[]
}

/**
 * Put loaded notes under their sub-decks, in folder-tree order. The server
 * lists changes folder by folder, so a later page usually extends the last group.
 */
export function groupNotesByDeck(
  notes: NoteChange[],
  contexts: Record<string, NoteContext>,
): DeckGroup[] {
  const groups = new Map<string, DeckGroup & { order: number }>()
  for (const note of notes) {
    const deck = contexts[note.noteId]?.deck
    const key = deck?.key || ''
    let group = groups.get(key)
    if (!group) {
      group = { key, path: deck?.path || [], order: deck?.order ?? Number.MAX_SAFE_INTEGER, notes: [] }
      groups.set(key, group)
    }
    group.notes.push(note)
  }
  return [...groups.values()]
    .sort((left, right) => left.order - right.order)
    .map(({ key, path, notes: groupNotes }) => ({ key, path, notes: groupNotes }))
}

/**
 * Lay a note out like the Browse editor: every field in note-type order, with
 * the contributor's value beside the current one. Fields unknown to the note
 * type (rare, stale schema) still show when they changed.
 */
export function buildNoteFieldRows(
  note: NoteChange,
  fieldDefs: NoteFieldDef[],
  context: NoteContext | null | undefined,
): NoteFieldRow[] {
  const changesByName = new Map(note.changes.map((change) => [change.fieldName, change]))
  const values = context?.values || null
  const rows: NoteFieldRow[] = fieldDefs.map((field) => {
    const change = changesByName.get(field.name) || null
    changesByName.delete(field.name)
    const before = change ? change.before : values?.[field.name]
    return {
      name: field.name,
      fieldType: field.field_type || 'text',
      before,
      after: change ? change.after : before,
      change,
    }
  })
  for (const change of changesByName.values()) {
    rows.push({ name: change.fieldName, fieldType: 'text', before: change.before, after: change.after, change })
  }
  return rows
}

/** Note ids of field additions the selected note changes write into. */
export function requiredFieldAdditions(
  notes: NoteChange[],
  isChangeSelected: (note: NoteChange, change: FieldChange) => boolean,
): Set<string> {
  const needed = new Set<string>()
  for (const note of notes) {
    for (const change of note.changes) {
      if (change.addedFieldId && isChangeSelected(note, change)) needed.add(change.addedFieldId)
    }
  }
  return needed
}

export function sameValue(left: unknown, right: unknown): boolean {
  if (left === right) return true
  if (left === undefined || right === undefined) return false
  return JSON.stringify(left) === JSON.stringify(right)
}
