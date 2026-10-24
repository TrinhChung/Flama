import type { TemplatePreviewArray } from '../model/types'

function isTextArray(value: unknown): value is TemplatePreviewArray {
  return Array.isArray(value) && value.every((item) => typeof item === 'string' || isTextArray(item))
}

/** JSON from an array sample editor becomes a native list. Text samples stay text. */
export function previewSampleValue(value: string, fieldType: string): string | TemplatePreviewArray {
  if (fieldType !== 'array') return value
  try {
    const parsed: unknown = JSON.parse(value)
    if (isTextArray(parsed)) return parsed
  } catch { /* Ordinary sample text is also valid, including deliberate mismatches. */ }
  return value
}
