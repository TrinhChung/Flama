import { fieldValueToText, normalizeAnswersValue } from '@/lib/answersField'

/**
 * Splitting existing field values into one answer per line, entirely on the
 * frontend. The server only validates the shape of what is sent and applies it.
 */

export type SplitPresetId = 'newline' | 'comma' | 'semicolon' | 'jp_comma' | 'slash' | 'numbered' | 'middle_dot'

export const SPLIT_PRESETS: ReadonlyArray<{ id: SplitPresetId; pattern: string; defaultOn: boolean }> = [
  { id: 'newline', pattern: '\\n', defaultOn: true },
  { id: 'comma', pattern: '[,，]', defaultOn: true },
  { id: 'semicolon', pattern: '[;；]', defaultOn: true },
  { id: 'jp_comma', pattern: '、', defaultOn: false },
  { id: 'slash', pattern: '[/／]', defaultOn: false },
  { id: 'numbered', pattern: '(?:^|\\s)(?:\\d{1,2}[.)]|[①-⑳])\\s*', defaultOn: false },
  // Off by default: katakana compound names (ジョン・スミス) use the middle dot.
  { id: 'middle_dot', pattern: '・', defaultOn: false },
]

export const DEFAULT_SPLIT_PRESETS: ReadonlySet<SplitPresetId> = new Set(
  SPLIT_PRESETS.filter((preset) => preset.defaultOn).map((preset) => preset.id),
)

/** Reasons a converted value deserves a look before applying. */
export type ConversionFlag = 'html' | 'sound' | 'empty' | 'duplicates' | 'long'

export const LONG_ANSWER_LENGTH = 80

export type SplitResult = { value: string; answers: string[]; flags: ConversionFlag[] }

export function splitToAnswers(raw: unknown, presets: ReadonlySet<SplitPresetId>): SplitResult {
  const source = typeof raw === 'string' ? raw : ''
  let text = fieldValueToText(source)
  if (!presets.has('newline')) text = text.replace(/\n+/g, ' ')
  const patterns = SPLIT_PRESETS.filter((preset) => preset.id !== 'newline' && presets.has(preset.id)).map((preset) => preset.pattern)
  const separator = patterns.length ? new RegExp(patterns.join('|'), 'u') : null
  const parts = text.split('\n').flatMap((line) => (separator ? line.split(separator) : [line]))
  const kept = parts.map((part) => part.normalize('NFC').replace(/\s+/g, ' ').trim()).filter(Boolean)
  const value = normalizeAnswersValue(kept.join('\n'))
  const answers = value ? value.split('\n') : []
  const flags: ConversionFlag[] = []
  if (/<[a-z/][^>]*>/i.test(source)) flags.push('html')
  if (/\[sound:[^\]]*\]/i.test(source)) flags.push('sound')
  if (source.trim() && !answers.length) flags.push('empty')
  if (kept.length > answers.length) flags.push('duplicates')
  if (answers.some((answer) => Array.from(answer).length > LONG_ANSWER_LENGTH)) flags.push('long')
  return { value, answers, flags }
}

export type ConversionNote = { note_id: string; value: string }

export type RestorableFieldType = 'text' | 'richtext' | 'markdown'

export type AnswersBackup = {
  schema_version: 'flama-answers-backup.v1'
  note_type_id: string
  field_id: string
  field_name: string
  original_type: RestorableFieldType
  created_at: string
  notes: ConversionNote[]
}

export function buildAnswersBackup(input: {
  noteTypeId: string
  fieldId: string
  fieldName: string
  originalType: RestorableFieldType
  notes: ReadonlyArray<ConversionNote>
  now?: Date
}): AnswersBackup {
  return {
    schema_version: 'flama-answers-backup.v1',
    note_type_id: input.noteTypeId,
    field_id: input.fieldId,
    field_name: input.fieldName,
    original_type: input.originalType,
    created_at: (input.now ?? new Date()).toISOString(),
    notes: input.notes.map((note) => ({ note_id: note.note_id, value: note.value })),
  }
}

export type BackupParseError = 'invalid' | 'other_field'

/** Read a backup file; it must belong to this NoteType field and restore a text-like type. */
export function parseAnswersBackup(
  raw: unknown,
  expected: { noteTypeId: string; fieldId: string },
): { ok: true; backup: AnswersBackup } | { ok: false; error: BackupParseError } {
  if (typeof raw !== 'object' || raw === null) return { ok: false, error: 'invalid' }
  const value = raw as Record<string, unknown>
  const notes = value.notes
  if (
    value.schema_version !== 'flama-answers-backup.v1'
    || typeof value.note_type_id !== 'string'
    || typeof value.field_id !== 'string'
    || typeof value.field_name !== 'string'
    || !['text', 'richtext', 'markdown'].includes(String(value.original_type))
    || typeof value.created_at !== 'string'
    || !Array.isArray(notes)
    || notes.some((note) => (
      typeof note !== 'object' || note === null
      || typeof (note as Record<string, unknown>).note_id !== 'string'
      || typeof (note as Record<string, unknown>).value !== 'string'
    ))
  ) return { ok: false, error: 'invalid' }
  if (value.note_type_id !== expected.noteTypeId || value.field_id !== expected.fieldId) {
    return { ok: false, error: 'other_field' }
  }
  return { ok: true, backup: value as unknown as AnswersBackup }
}

/** Offer a JSON file to the browser; nothing is stored on the server. */
export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
