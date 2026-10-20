import { fieldValueEditorText } from '@/lib/arrayField'

export interface NoteFieldLayoutField {
  name: string
  field_type?: string | null
}

const MULTILINE_FIELD_TYPES = new Set(['richtext', 'markdown'])
const MULTILINE_NAME_HINTS = ['meaning', 'example', 'sentence', 'notes']
const MULTILINE_VALUE_LENGTH = 50

export function normalizedFieldType(field: NoteFieldLayoutField): string {
  return (field.field_type || 'text').toLowerCase()
}

/** Field type and name never change for a field, so they may be read on every render. */
export function fieldShapePrefersMultiline(field: NoteFieldLayoutField): boolean {
  if (MULTILINE_FIELD_TYPES.has(normalizedFieldType(field))) return true
  const name = field.name.toLowerCase()
  return MULTILINE_NAME_HINTS.some((hint) => name.includes(hint))
}

export function valuePrefersMultiline(value: unknown): boolean {
  const text = fieldValueEditorText(value)
  return text.length > MULTILINE_VALUE_LENGTH || text.includes('\n')
}

/** Textarea vs Input for a note field, from its type, its name and the stored value (never the live draft). */
export function prefersMultilineEditor(field: NoteFieldLayoutField, storedValue: unknown): boolean {
  return fieldShapePrefersMultiline(field) || valuePrefersMultiline(storedValue)
}
