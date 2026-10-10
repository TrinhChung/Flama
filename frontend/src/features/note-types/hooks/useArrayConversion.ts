import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { normalizeArrayValue } from '@/lib/arrayField'
import {
  DEFAULT_SPLIT_PRESETS,
  buildArrayBackup,
  downloadJson,
  splitToArray,
  type ArrayBackup,
  type ConversionFlag,
  type ConversionNote,
  type SplitPresetId,
} from '../lib/arrayConversion'
import type { FieldDefItem } from './useNoteTypeFields'

export type ArrayConversionSource = {
  schema_version: 'field-array-conversion.v1'
  field: FieldDefItem
  convertible: boolean
  blocked_reason: string | null
  notes: ConversionNote[]
}

export type ArrayConversionResult = {
  schema_version: 'field-array-conversion.v1'
  field: FieldDefItem
  note_count: number
  changed_note_count: number
}

type ConversionWrite = {
  target_type: string
  expected_field_type: string
  notes: Array<{ note_id: string; expected: string; value: string }>
}

export type ConversionRow = {
  noteId: string
  original: string
  value: string
  items: string[]
  flags: ConversionFlag[]
  edited: boolean
  unchanged: boolean
}

const conversionPath = (noteTypeId: string, fieldId: string) =>
  `/note-types/${encodeURIComponent(noteTypeId)}/fields/${encodeURIComponent(fieldId)}/array-conversion`

export const arrayConversionQueryKey = (noteTypeId: string, fieldId: string) =>
  ['field-array-conversion', noteTypeId, fieldId] as const

function useConversionSource(noteTypeId: string, fieldId: string, enabled: boolean) {
  return useQuery({
    queryKey: arrayConversionQueryKey(noteTypeId, fieldId),
    queryFn: () => appApi.get<ArrayConversionSource>(conversionPath(noteTypeId, fieldId)),
    enabled,
    staleTime: 0,
    gcTime: 0,
  })
}

function useConversionWrite(noteTypeId: string, fieldId: string, onDone: (result: ArrayConversionResult) => void) {
  return useMutation({
    mutationFn: (body: ConversionWrite) =>
      appApi.mutate<ArrayConversionResult>(conversionPath(noteTypeId, fieldId), 'POST', body),
    onSuccess: onDone,
  })
}

/** Split every Note value on the frontend, preview, back up, then apply in one request. */
export function useArrayConversion({ noteTypeId, field, enabled, onDone }: {
  noteTypeId: string
  field: FieldDefItem
  enabled: boolean
  onDone: (result: ArrayConversionResult) => void
}) {
  const source = useConversionSource(noteTypeId, field.id, enabled)
  const [presets, setPresets] = useState<ReadonlySet<SplitPresetId>>(() => new Set(DEFAULT_SPLIT_PRESETS))
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [backupAt, setBackupAt] = useState<number | null>(null)
  const write = useConversionWrite(noteTypeId, field.id, onDone)

  const rows = useMemo<ConversionRow[]>(() => (source.data?.notes ?? []).map((note) => {
    const override = overrides[note.note_id]
    const split = override === undefined ? splitToArray(note.value, presets) : null
    const value = split ? split.value : normalizeArrayValue(override)
    return {
      noteId: note.note_id,
      original: note.value,
      value,
      items: value ? value.split('\n') : [],
      flags: split ? split.flags : [],
      edited: override !== undefined,
      unchanged: value === note.value,
    }
  }), [overrides, presets, source.data])

  const summary = useMemo(() => ({
    total: rows.length,
    flagged: rows.filter((row) => row.flags.length > 0).length,
    unchanged: rows.filter((row) => row.unchanged).length,
  }), [rows])

  const togglePreset = (id: SplitPresetId) => {
    setPresets((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  const setOverride = (noteId: string, text: string | undefined) => {
    setOverrides((current) => {
      const next = { ...current }
      if (text === undefined) delete next[noteId]
      else next[noteId] = text
      return next
    })
  }
  const downloadBackup = () => {
    const originalType = source.data?.field.field_type
    if (!source.data || (originalType !== 'text' && originalType !== 'richtext' && originalType !== 'markdown')) return
    const backup = buildArrayBackup({
      noteTypeId,
      fieldId: field.id,
      fieldName: source.data.field.name,
      originalType,
      notes: source.data.notes,
    })
    downloadJson(`flama-backup-${source.data.field.name}-${backup.created_at.slice(0, 10)}.json`, backup)
    setBackupAt(source.dataUpdatedAt)
  }
  const apply = () => {
    if (!source.data) return
    write.mutate({
      target_type: 'array',
      expected_field_type: source.data.field.field_type,
      notes: rows.map((row) => ({ note_id: row.noteId, expected: row.original, value: row.value })),
    })
  }

  return {
    source,
    rows,
    summary,
    presets,
    togglePreset,
    setOverride,
    // A backup only counts for the values it saved; a reload asks for a new one.
    backupReady: backupAt !== null && backupAt === source.dataUpdatedAt,
    downloadBackup,
    apply,
    write,
  }
}

/** Restore a converted field from its backup file, keeping Notes created since then as they are. */
export function useArrayRestore({ noteTypeId, field, enabled, onDone }: {
  noteTypeId: string
  field: FieldDefItem
  enabled: boolean
  onDone: (result: ArrayConversionResult) => void
}) {
  const source = useConversionSource(noteTypeId, field.id, enabled)
  const write = useConversionWrite(noteTypeId, field.id, onDone)
  const plan = (backup: ArrayBackup) => {
    const saved = new Map(backup.notes.map((note) => [note.note_id, note.value]))
    const current = source.data?.notes ?? []
    return {
      restored: current.filter((note) => saved.has(note.note_id)).length,
      kept: current.filter((note) => !saved.has(note.note_id)).length,
      gone: backup.notes.filter((note) => !current.some((item) => item.note_id === note.note_id)).length,
      body: {
        target_type: backup.original_type,
        expected_field_type: source.data?.field.field_type ?? field.field_type,
        notes: current.map((note) => ({
          note_id: note.note_id,
          expected: note.value,
          value: saved.get(note.note_id) ?? note.value,
        })),
      } satisfies ConversionWrite,
    }
  }
  return { source, write, plan }
}
