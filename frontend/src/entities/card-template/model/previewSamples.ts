import type { TemplatePreviewArray } from './types'

export type TemplateSampleValue = string | TemplatePreviewArray
export type TemplateSampleValues = Record<string, TemplateSampleValue>
export type TemplateSampleField = { key: string; type: string }

export type SampleValueItem = TemplateSampleField & {
  label: string
  placeholder?: string
}
