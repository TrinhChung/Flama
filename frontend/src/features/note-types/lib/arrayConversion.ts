import { fieldValueToText, normalizeArrayValue } from '@/lib/arrayField'

/**
 * Splitting existing field values into one item per line, entirely on the
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
export type ConversionFlag = 'html' | 'sound' | 'empty' | 'duplicates' | 'long' | 'brackets'

export const LONG_ITEM_LENGTH = 80
/** Same cap as the server (MAX_CONVERSION_NOTES); bigger NoteTypes need a chunked design. */
export const MAX_CONVERSION_NOTES = 20_000

export type SplitResult = { value: string; items: string[]; flags: ConversionFlag[] }

const OPENING = '(（[［【「『{｛'
const CLOSING = ')）]］】」』}｝'
const BRACKETS = /[(（[［【「『{｛]/u

/** Split on separators outside brackets only: "số tấm (giấy, ảnh, vé)" stays one item. */
function splitOutsideBrackets(line: string, separator: RegExp | null): string[] {
  if (!separator) return [line]
  const parts: string[] = []
  let depth = 0
  let start = 0
  let index = 0
  while (index < line.length) {
    const char = line[index]
    if (OPENING.includes(char)) depth += 1
    else if (CLOSING.includes(char)) depth = Math.max(0, depth - 1)
    if (depth === 0) {
      separator.lastIndex = index
      const match = separator.exec(line)
      if (match && match[0].length > 0) {
        parts.push(line.slice(start, index))
        index += match[0].length
        start = index
        continue
      }
    }
    index += 1
  }
  parts.push(line.slice(start))
  return parts
}

export function splitToArray(raw: unknown, presets: ReadonlySet<SplitPresetId>): SplitResult {
  const source = typeof raw === 'string' ? raw : ''
  let text = fieldValueToText(source)
  if (!presets.has('newline')) text = text.replace(/\n+/g, ' ')
  const patterns = SPLIT_PRESETS.filter((preset) => preset.id !== 'newline' && presets.has(preset.id)).map((preset) => preset.pattern)
  // Sticky: a separator only counts where the scan stands, so brackets can shield it.
  const separator = patterns.length ? new RegExp(patterns.join('|'), 'uy') : null
  const parts = text.split('\n').flatMap((line) => splitOutsideBrackets(line, separator))
  const kept = parts.map((part) => part.normalize('NFC').replace(/\s+/g, ' ').trim()).filter(Boolean)
  const value = normalizeArrayValue(kept.join('\n'))
  const items = value ? value.split('\n') : []
  const flags: ConversionFlag[] = []
  if (/<[a-z/][^>]*>/i.test(source)) flags.push('html')
  if (/\[sound:[^\]]*\]/i.test(source)) flags.push('sound')
  if (source.trim() && !items.length) flags.push('empty')
  if (kept.length > items.length) flags.push('duplicates')
  if (items.some((item) => Array.from(item).length > LONG_ITEM_LENGTH)) flags.push('long')
  // A bracketed note stays inside its item (a learner would have to type it too); worth a look.
  if (items.some((item) => BRACKETS.test(item))) flags.push('brackets')
  return { value, items, flags }
}

export type ConversionNote = { note_id: string; value: string }

export type RestorableFieldType = 'text' | 'richtext' | 'markdown'

export type ArrayBackup = {
  schema_version: 'flama-array-backup.v1'
  note_type_id: string
  field_id: string
  field_name: string
  original_type: RestorableFieldType
  created_at: string
  notes: ConversionNote[]
}

export function buildArrayBackup(input: {
  noteTypeId: string
  fieldId: string
  fieldName: string
  originalType: RestorableFieldType
  notes: ReadonlyArray<ConversionNote>
  now?: Date
}): ArrayBackup {
  return {
    schema_version: 'flama-array-backup.v1',
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
export function parseArrayBackup(
  raw: unknown,
  expected: { noteTypeId: string; fieldId: string },
): { ok: true; backup: ArrayBackup } | { ok: false; error: BackupParseError } {
  if (typeof raw !== 'object' || raw === null) return { ok: false, error: 'invalid' }
  const value = raw as Record<string, unknown>
  const notes = value.notes
  if (
    value.schema_version !== 'flama-array-backup.v1'
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
  return { ok: true, backup: value as unknown as ArrayBackup }
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
