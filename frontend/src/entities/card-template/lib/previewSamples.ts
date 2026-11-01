import type { TemplatePreviewArray } from '../model/types'
import type { TemplateSampleField, TemplateSampleValue, TemplateSampleValues } from '../model/previewSamples'

export function isTextArray(value: unknown, depth = 0): value is TemplatePreviewArray {
  return depth <= 8 && Array.isArray(value) && value.every((item) => typeof item === 'string' || isTextArray(item, depth + 1))
}

/** JSON from an array sample editor becomes a native list. Text samples stay text. */
export function previewSampleValue(value: TemplateSampleValue, fieldType: string): TemplateSampleValue {
  if (Array.isArray(value)) return value
  if (fieldType !== 'array') return value
  try {
    const parsed: unknown = JSON.parse(value)
    if (isTextArray(parsed)) return parsed
  } catch { /* Ordinary sample text is also valid, including deliberate mismatches. */ }
  return value
}

/** Samples are preview data, never defaults written into notes or templates. */
export function defaultTemplateSample(fieldType: string): TemplateSampleValue {
  switch (fieldType) {
    case 'array': return ['First item', 'Second item', 'Third item']
    case 'richtext': return '<p><strong>Sample text</strong> with <em>formatting</em>.</p>'
    case 'markdown': return '## Sample heading\n\n**Sample text**\n\n- First item\n- Second item'
    case 'image': return '/store/sample-image.png'
    case 'audio': return '/store/sample-audio.mp3'
    case 'diagram': return '/store/sample-diagram.svg'
    default: return 'Sample text'
  }
}

export function templateSampleValues(fields: ReadonlyArray<TemplateSampleField>, overrides: TemplateSampleValues): TemplateSampleValues {
  return Object.fromEntries(fields.map((field) => [field.key,
    Object.hasOwn(overrides, field.key) ? previewSampleValue(overrides[field.key], field.type) : defaultTemplateSample(field.type),
  ]))
}

/** A display URL for the sample form. The preview API still validates media. */
export function sampleMediaUrl(value: string): string {
  const url = value.trim()
  if (/[\s"'<>]/.test(url)) return ''
  if (/^\/(?:media\/)?(?:store|proxy|library)\/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(url)) return url
  if (/^\/static\/strokes\/[A-Za-z0-9_-]+\/[A-Fa-f0-9]+\.svg$/.test(url)) return url
  try {
    const parsed = new URL(url)
    if (parsed.username || parsed.password) return ''
    if (parsed.protocol === 'https:' || parsed.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname)) return parsed.href
  } catch { /* The form keeps incomplete edits without loading them. */ }
  return ''
}
