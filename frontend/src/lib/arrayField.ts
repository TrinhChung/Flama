/**
 * The `array` field type stores a list of plain-text items, one per line.
 * Editors keep that shape clean on save; a template decides what the items mean
 * (accepted answers, choices, …).
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

export function isArrayField(fieldType: string | null | undefined): boolean {
  return (fieldType || '').toLowerCase() === ARRAY_FIELD_TYPE
}

/** Trim lines and drop empty ones. An array keeps order and repeated items. */
export function normalizeArrayValue(value: string): string {
  const lines: string[] = []
  for (const raw of value.split(/\r\n|\r|\n/)) {
    const line = raw.normalize('NFC').replace(/\s+/g, ' ').trim()
    if (!line) continue
    lines.push(line)
  }
  return lines.join('\n')
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
