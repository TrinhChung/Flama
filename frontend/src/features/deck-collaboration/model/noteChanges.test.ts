import { describe, expect, it } from 'vitest'
import type { ChangeRequestItem, LocalChangeItem } from '../types'
import {
  buildNoteFieldRows,
  groupContributionChanges,
  groupContributionPages,
  groupNotesByDeck,
  requiredFieldAdditions,
} from './noteChanges'
import {
  SELECT_ALL,
  countSelected,
  isKeySelected,
  selectionRequest,
  setKeysSelected,
} from './selection'

function item(id: string, noteId: string, field: string, before: unknown, after: unknown,
  extra: Partial<ChangeRequestItem> = {}): ChangeRequestItem {
  return { id, change_type: 'note_field_set', source_ref_id: noteId, path_key: field,
    before_value: before, after_value: after, effective_after_value: after, is_conflict: false,
    metadata: { field_name: field, source_note_id: noteId, source_note_label: `label ${noteId}` }, ...extra }
}

describe('contribution note grouping', () => {
  it('groups field changes by note and keeps structure changes apart', () => {
    const local: LocalChangeItem = { change_type: 'field_def_update', local_ref_id: 'override-1',
      path_key: 'name', before_value: 'Meaning', after_value: 'Nghĩa',
      metadata_json: { field_name: 'Meaning', property_name: 'name' } }
    const grouped = groupContributionChanges([
      local,
      item('a', 'n1', 'Meaning', 'dog', 'hound'),
      item('b', 'n2', 'Meaning', 'cat', 'kitty'),
      item('c', 'n1', 'Image', { __missing__: true }, '/media/proxy/abc'),
    ])
    expect(grouped.notes.map((note) => [note.noteId, note.changes.map((change) => change.itemId)]))
      .toEqual([['n1', ['a', 'c']], ['n2', ['b']]])
    expect(grouped.notes[0].changes[1].before).toBeUndefined()
    expect(grouped.schema).toMatchObject([{ key: 'field_def_update:override-1:name', property: 'name' }])
  })

  it('treats a removed field as empty and uses the conflict decision', () => {
    const grouped = groupContributionChanges([
      item('a', 'n1', 'Meaning', 'dog', 'dog', { change_type: 'note_field_remove', after_value: { __missing__: true } }),
      item('b', 'n1', 'Reading', 'いぬ', 'イヌ', { effective_after_value: 'いぬ (chosen)', review_decision: 'declined' }),
    ])
    expect(grouped.notes[0].changes.map((change) => [change.after, change.reviewDecision]))
      .toEqual([[undefined, null], ['いぬ (chosen)', 'declined']])
  })

  it('lays the note out in field order with unchanged values from the note', () => {
    const [note] = groupContributionChanges([item('a', 'n1', 'Reading', 'いぬ', 'イヌ')]).notes
    const rows = buildNoteFieldRows(
      note,
      [{ name: 'Word', field_type: 'text' }, { name: 'Reading', field_type: 'text' }, { name: 'Audio', field_type: 'audio' }],
      { label: '犬', values: { Word: '犬', Reading: 'いぬ' } },
    )
    expect(rows.map((row) => [row.name, row.before, row.after, Boolean(row.change)])).toEqual([
      ['Word', '犬', '犬', false],
      ['Reading', 'いぬ', 'イヌ', true],
      ['Audio', undefined, undefined, false],
    ])
  })

  it('finds learner-added fields that selected note changes need', () => {
    const { notes } = groupContributionChanges([
      item('a', 'n1', 'Extra', undefined, 'x', {
        metadata: { field_name: 'Extra', source_note_id: 'n1', local_added_field_def_id: 'added-1' } }),
      item('b', 'n2', 'Meaning', 'cat', 'kitty'),
    ])
    expect([...requiredFieldAdditions(notes, (note) => note.noteId === 'n1')]).toEqual(['added-1'])
    expect(requiredFieldAdditions(notes, (note) => note.noteId === 'n2').size).toBe(0)
  })
})

describe('sub-deck groups', () => {
  it('puts notes under their folders in tree order, unknown folders last', () => {
    const { notes } = groupContributionChanges([
      item('a', 'n1', 'Meaning', 'dog', 'hound'),
      item('b', 'n2', 'Meaning', 'cat', 'kitty'),
      item('c', 'n3', 'Meaning', 'cow', 'ox'),
      item('d', 'n4', 'Meaning', 'pig', 'hog'),
    ])
    const lesson = { key: '7', path: ['N5', 'Lesson 1'], order: 1 }
    const groups = groupNotesByDeck(notes, {
      n1: { label: '', values: null, deck: lesson },
      n2: { label: '', values: null, deck: { key: '5', path: ['N5'], order: 0 } },
      n3: { label: '', values: null, deck: lesson },
      n4: { label: '', values: null },
    })
    expect(groups.map((group) => [group.key, group.path, group.notes.map((note) => note.noteId)])).toEqual([
      ['5', ['N5'], ['n2']],
      ['7', ['N5', 'Lesson 1'], ['n1', 'n3']],
      ['', [], ['n4']],
    ])
  })
})

describe('loaded pages', () => {
  it('keeps earlier notes identical when a page is added, so their cards skip rendering', () => {
    const first = { items: [item('a', 'n1', 'Meaning', 'dog', 'hound')] }
    const second = { items: [item('b', 'n2', 'Meaning', 'cat', 'kitty')] }
    const before = groupContributionPages([first])
    const after = groupContributionPages([first, second])
    expect(after.notes[0]).toBe(before.notes[0])
    expect(after.notes.map((note) => note.noteId)).toEqual(['n1', 'n2'])
  })

  it('joins a note larger than a page that continues on the next one', () => {
    const grouped = groupContributionPages([
      { items: [item('a', 'n1', 'Meaning', 'dog', 'hound')] },
      { items: [item('b', 'n1', 'Reading', 'いぬ', 'イヌ'), item('c', 'n2', 'Meaning', 'cat', 'kitty')] },
    ])
    expect(grouped.notes.map((note) => [note.noteId, note.changes.map((change) => change.itemId)]))
      .toEqual([['n1', ['a', 'b']], ['n2', ['c']]])
  })
})

describe('partly loaded selections', () => {
  it('describes "all except" and "only" selections for the server', () => {
    const unticked = setKeysSelected(SELECT_ALL, ['n2'], false)
    expect(isKeySelected(unticked, 'n1')).toBe(true)
    expect(isKeySelected(unticked, 'unloaded')).toBe(true)
    expect(countSelected(unticked, 10)).toBe(9)
    expect(selectionRequest(unticked)).toEqual({ mode: 'all_except', ids: ['n2'] })

    const picked = setKeysSelected({ base: 'none', toggled: new Set() }, ['n3', 'n4'], true)
    expect(isKeySelected(picked, 'unloaded')).toBe(false)
    expect(selectionRequest(setKeysSelected(picked, ['n4'], false))).toEqual({ mode: 'only', ids: ['n3'] })
  })
})
