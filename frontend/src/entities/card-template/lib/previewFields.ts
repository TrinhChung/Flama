import type { TemplateInputSpec } from '../model/types'

export type PreviewFieldDef = { id: string; name: string; field_type: string; position: number }

/**
 * Field definitions handed to the sandbox renderer for template previews. Library and
 * mapping previews render a template's inputs (not Note Type fields), so IDs are positional.
 */
export function inputSchemaPreviewFields(inputs: ReadonlyArray<Pick<TemplateInputSpec, 'key' | 'type'>>): PreviewFieldDef[] {
  return inputs.map((input, position) => ({ id: `f_${position}`, name: input.key, field_type: input.type, position }))
}
