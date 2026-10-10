import { describe, expect, it } from 'vitest'
import type { TemplateInputSpec } from '@/entities/card-template'
import { inputSchemaIssues, templateInputTypes, withInputType } from './inputSchemaValidation'
const input = (key: string): TemplateInputSpec => ({ key, label: key, type: 'text', required: false })
describe('inputSchemaIssues follows backend schema rules', () => {
  it('accepts all exact types and recommended fields without a binding', () => {
    expect(templateInputTypes).toEqual(['text', 'richtext', 'markdown', 'image', 'audio', 'diagram', 'answers'])
    expect(inputSchemaIssues(templateInputTypes.map((type) => ({ key: type, label: type, type, required: true })))).toEqual([])
  })
  it('allows several answers inputs and keeps no typing options', () => {
    const value: TemplateInputSpec[] = [{ ...input('A'), type: 'answers' }, { ...input('B'), type: 'answers' }]
    expect(inputSchemaIssues(value)).toEqual([])
    expect(withInputType(input('A'), 'answers')).toEqual({ ...input('A'), type: 'answers' })
    expect(withInputType({ ...input('A'), type: 'answers', typing: { show_length: false, hints: true } }, 'answers')).toEqual({ ...input('A'), type: 'answers' })
  })
  // Parked 2026-10-10 with the host typing mode (STUDY_TYPING_ANSWER_PLAN §12).
  it.skip('allows only one typed-answer input', () => {
    const value: TemplateInputSpec[] = [{ ...input('A'), type: 'answers' }, { ...input('B'), type: 'answers' }]
    expect(inputSchemaIssues(value)).toEqual([{ index: 1, message: 'Mỗi mẫu chỉ có một input đáp án gõ.' }])
  })
  it.skip('adds typing options with the answers type and drops them when switching away', () => {
    const answers = withInputType(input('A'), 'answers')
    expect(answers).toEqual({ ...input('A'), type: 'answers', typing: { show_length: true, hints: true } })
    expect(withInputType({ ...answers, typing: { show_length: false, hints: true } }, 'answers').typing).toEqual({ show_length: false, hints: true })
    expect(withInputType(answers, 'text')).toEqual(input('A'))
  })
  it.each(['', ' A', 'A ', '.', 'FrontSide', '{{A}}', '#A', '^A', '/A', '!A', '>A', '&A', '=A', 'A\nB'])('rejects reserved or whitespace key %j', (key) => { expect(inputSchemaIssues([input(key)]).length).toBeGreaterThan(0) })
  it('reports duplicates and labels over 255 without mutating values', () => {
    const value = [input('A'), { ...input('A'), label: 'x'.repeat(256) }]
    expect(inputSchemaIssues(value)).toEqual(expect.arrayContaining([{ index: 1, message: 'Key input phải duy nhất.' }, { index: 1, message: 'Nhãn tối đa 255 ký tự.' }]))
    expect(value[1].label.length).toBe(256)
  })
})
