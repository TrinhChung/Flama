import type { TemplateBindings, TemplateInputSpec } from '../model/types'

export type MappingField = { id: string; name: string; field_type: string }
export type MappingInput = TemplateInputSpec
export type MappingIssue =
  | { kind: 'unbound'; key: string; required: boolean; blocking: false }
  | { kind: 'field_out_of_scope'; key: string; fieldId: string; blocking: true }
  | { kind: 'type_mismatch'; key: string; fieldId: string; blocking: false }
  | { kind: 'unknown_input'; key: string; blocking: true }

const INPUT_TYPES = new Set(['text', 'richtext', 'markdown', 'image', 'audio', 'diagram', 'array'])
export function isTypeCompatible(inputType: string, fieldType: string): boolean {
  return inputType === fieldType && INPUT_TYPES.has(inputType)
}

export function suggestBindings(inputs: MappingInput[], fields: MappingField[]): TemplateBindings {
  return Object.fromEntries(inputs.map((input) => {
    const candidates = fields.filter((field) => field.name.trim().toLowerCase() === input.key.trim().toLowerCase())
    const target = candidates.find((field) => isTypeCompatible(input.type, field.field_type)) ?? candidates[0]
    return [input.key, target?.id ?? null]
  }))
}

export function validateBindings(
  inputs: MappingInput[],
  fields: MappingField[],
  bindings: TemplateBindings,
): MappingIssue[] {
  const issues: MappingIssue[] = []
  const fieldById = new Map(fields.map((field) => [field.id, field]))
  const inputKeys = new Set(inputs.map((input) => input.key))
  for (const input of inputs) {
    const fieldId = Object.hasOwn(bindings, input.key) ? bindings[input.key] : undefined
    if (fieldId === undefined || fieldId === null || fieldId === '') {
      issues.push({ kind: 'unbound', key: input.key, required: input.required, blocking: false })
      continue
    }
    const field = fieldById.get(fieldId)
    if (!field) {
      issues.push({ kind: 'field_out_of_scope', key: input.key, fieldId, blocking: true })
    } else if (!isTypeCompatible(input.type, field.field_type)) {
      issues.push({ kind: 'type_mismatch', key: input.key, fieldId, blocking: false })
    }
  }
  for (const key of Object.keys(bindings)) {
    if (!inputKeys.has(key)) issues.push({ kind: 'unknown_input', key, blocking: true })
  }
  return issues
}
