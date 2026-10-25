import { describe, expect, it } from 'vitest'
import { mappingSampleValues } from './useTemplateMappingDraft'

describe('mapping preview field projection', () => {
  const inputs = [{ key: 'Word', label: 'Word', type: 'text' as const, required: true }, { key: 'Audio', label: 'Audio', type: 'audio' as const, required: false }]
  const fields = [{ id: 'text-id', name: 'Renamed', field_type: 'text' }, { id: 'audio-id', name: 'Voice', field_type: 'audio' }]
  it('uses IDs, retains explicit empty samples, and leaves mapped media to safe system samples', () => {
    expect(mappingSampleValues(inputs, fields, { Word: 'text-id', Audio: 'audio-id' }, { 'text-id': '' })).toEqual({ Word: '', Audio: '/media/proxy/sample-audio' })
    expect(mappingSampleValues(inputs, fields, { Word: 'text-id', Audio: 'audio-id' }, {})).toEqual({ Word: 'Sample text', Audio: '/media/proxy/sample-audio' })
  })
  it('keeps mismatched sources and only renders missing targets empty', () => {
    expect(mappingSampleValues(inputs, fields, { Word: 'audio-id', Audio: 'missing' }, {})).toEqual({ Word: '/media/proxy/sample-audio', Audio: '' })
  })
  it('treats prototype-looking keys as real own keys and allows one field for multiple inputs', () => {
    const schema = [{ key: '__proto__', label: '', type: 'text' as const, required: false }, { key: 'constructor', label: '', type: 'text' as const, required: false }]
    const bindings = Object.fromEntries(schema.map((input) => [input.key, 'text-id']))
    expect(mappingSampleValues(schema, fields, bindings, { 'text-id': 'same' })).toEqual(Object.fromEntries(schema.map((input) => [input.key, 'same'])))
  })
})

it('keeps nested JSON lists in mapped samples without coercing JSON-looking text', () => {
  const schema = [{ key: 'answer', label: 'Answer', type: 'audio' as const, required: false }]
  const fields = [{ id: 'a', name: 'Items', field_type: 'array' }]
  expect(mappingSampleValues(schema, fields, { answer: 'a' }, { a: '["one",["two"]]' })).toEqual({ answer: ['one', ['two']] })
  expect(mappingSampleValues(schema, [{ ...fields[0], field_type: 'text' }], { answer: 'a' }, { a: '["one"]' })).toEqual({ answer: '["one"]' })
})
