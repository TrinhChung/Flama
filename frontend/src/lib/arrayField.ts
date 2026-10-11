/**
 * The `array` field type stores a JSON list of plain-text items (older values
 * may still be one item per line). Editors show one item per line and the server
 * stores the lines as a list; the renderer passes the list to the template as is.
 */
export const ARRAY_FIELD_TYPE = 'array'

const NAMED_ENTITIES: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
}

function decodeEntities(value: string): string {
  return value.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (match, entity: string) => {
    if (entity[0] === '#') {
      const code = entity[1] === 'x' || entity[1] === 'X'
        ? Number.parseInt(entity.slice(2), 16)
        : Number.parseInt(entity.slice(1), 10)
      return Number.isFinite(code) && code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : match
    }
    return NAMED_ENTITIES[entity.toLowerCase()] ?? match
  })
}

/** Visible text of a field value: line breaks kept, markup and sound refs dropped. */
export function fieldValueToText(raw: unknown): string {
  if (typeof raw !== 'string' || !raw) return ''
  const withBreaks = raw
    .replace(/\r\n?/g, '\n')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/?(div|p|li)\b[^>]*>/gi, '\n')
  const withoutMarkup = withBreaks
    .replace(/<[^>]*>/g, '')
    .replace(/\[sound:[^\]]*\]/gi, '')
  return decodeEntities(withoutMarkup)
}

/**
 * Text an editor shows for a stored value: array items one per line. Keep the
 * stored list in form state until the user edits it, so an untouched (nested)
 * array is saved back unchanged.
 */
export function fieldValueEditorText(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => fieldValueEditorText(item)).join('\n')
  return value === null || value === undefined ? '' : String(value)
}

export function isArrayField(fieldType: string | null | undefined): boolean {
  return (fieldType || '').toLowerCase() === ARRAY_FIELD_TYPE
}

/** Trim lines and drop empty ones. An array keeps order and repeated items. Also parses JSON array if supplied. */
export function normalizeArrayValue(value: string): string {
  if (typeof value !== 'string' || !value) return ''
  const trimmed = value.trim()
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        return parsed
          .map((item) => (typeof item === 'string' ? item : String(item)).normalize('NFC').replace(/\s+/g, ' ').trim())
          .filter(Boolean)
          .join('\n')
      }
    } catch {
      // not valid JSON, fall back to line splitting
    }
  }

  const lines: string[] = []
  for (const raw of value.split(/\r\n|\r|\n/)) {
    const line = raw.normalize('NFC').replace(/\s+/g, ' ').trim()
    if (!line) continue
    lines.push(line)
  }
  return lines.join('\n')
}

/** Check if text is a valid JSON array syntax */
export function isValidArrayJson(text: string): boolean {
  if (typeof text !== 'string') return false
  const trimmed = text.trim()
  if (!trimmed.startsWith('[') || !trimmed.endsWith(']')) return false
  try {
    const parsed = JSON.parse(trimmed)
    return Array.isArray(parsed)
  } catch {
    return false
  }
}

/** Extract list of string items from any array representation (lines, list, or JSON code) */
export function parseArrayItems(input: unknown): string[] {
  if (Array.isArray(input)) {
    return input.map((item) => (typeof item === 'string' ? item.trim() : fieldValueEditorText(item))).filter(Boolean)
  }
  if (typeof input !== 'string' || !input) return []
  const trimmed = input.trim()
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        return parsed.map((item) => (typeof item === 'string' ? item.trim() : String(item).trim())).filter(Boolean)
      }
    } catch {
      // not valid JSON, fall back to line splitting
    }
  }
  const lines: string[] = []
  for (const raw of trimmed.split(/\r\n|\r|\n/)) {
    const line = raw.normalize('NFC').replace(/\s+/g, ' ').trim()
    if (!line) continue
    lines.push(line)
  }
  return lines
}

/** Convert array field value (lines or list) into formatted JSON array code string */
export function arrayLinesToCode(value: unknown, multiline = true): string {
  const items = parseArrayItems(value)
  if (items.length === 0) return '[]'
  return multiline && items.length > 1
    ? JSON.stringify(items, null, 2)
    : JSON.stringify(items)
}

/** Convert JSON array code string to lines format */
export function arrayCodeToLines(codeText: string): string {
  const items = parseArrayItems(codeText)
  return items.join('\n')
}

/** Normalize only the values of `array` fields; other fields pass through untouched. */
export function normalizeArrayFieldValues<T extends Record<string, string>>(
  values: T,
  fields: ReadonlyArray<{ name: string; field_type?: string | null }>,
): T {
  const arrayFields = fields.filter((field) => isArrayField(field.field_type))
  if (!arrayFields.length) return values
  const next: Record<string, string> = { ...values }
  for (const field of arrayFields) {
    if (typeof next[field.name] === 'string') next[field.name] = normalizeArrayValue(next[field.name])
  }
  return next as T
}

