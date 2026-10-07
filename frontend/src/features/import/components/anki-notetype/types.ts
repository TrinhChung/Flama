export interface FlamaFieldDef {
  id: string
  name: string
  field_type: string
}

export interface FlamaNoteTypeOption {
  id: string
  name: string
  fields: FlamaFieldDef[]
}

export interface AnkiTemplateInfo {
  name: string
  front: string
  back: string
}

export interface AnkiModelDetail {
  name: string
  fields: string[]
  css: string
  templates: AnkiTemplateInfo[]
  existingFlamaId?: string
}

export type PreviewResponse = {
  front_html?: string
  back_html?: string
  front_renderer_payload?: unknown
  back_renderer_payload?: unknown
}
