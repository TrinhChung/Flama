import { describe, expect, it } from 'vitest'
import type { TemplateInputSpec } from '@/entities/card-template'
import { inputSchemaIssues, templateInputTypes } from './inputSchemaValidation'
const input = (key: string): TemplateInputSpec => ({ key, label: key, type: 'text', required: false })
describe('inputSchemaIssues follows backend schema rules', () => {
  it('accepts all exact types and recommended fields without a binding', () => {
    expect(templateInputTypes).toEqual(['text', 'richtext', 'markdown', 'image', 'audio', 'diagram'])
    expect(inputSchemaIssues(templateInputTypes.map((type) => ({ key: type, label: type, type, required: true })))).toEqual([])
  })
  it.each(['', ' A', 'A ', '.', 'FrontSide', '{{A}}', '#A', '^A', '/A', '!A', '>A', '&A', '=A', 'A\nB'])('rejects reserved or whitespace key %j', (key) => { expect(inputSchemaIssues([input(key)]).length).toBeGreaterThan(0) })
  it('reports duplicates and labels over 255 without mutating values', () => {
    const value = [input('A'), { ...input('A'), label: 'x'.repeat(256) }]
    expect(inputSchemaIssues(value)).toEqual(expect.arrayContaining([{ index: 1, message: 'Key input phải duy nhất.' }, { index: 1, message: 'Nhãn tối đa 255 ký tự.' }]))
    expect(value[1].label.length).toBe(256)
  })
})
