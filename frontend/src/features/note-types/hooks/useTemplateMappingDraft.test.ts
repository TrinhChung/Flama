import { describe, expect, it } from 'vitest'
import { mappingSampleValues } from './useTemplateMappingDraft'

describe('mapping preview field projection', () => {
  const inputs = [{ key: 'Word', label: 'Word', type: 'text' as const, required: true }, { key: 'Audio', label: 'Audio', type: 'audio' as const, required: false }]
  const fields = [{ id: 'text-id', name: 'Renamed', field_type: 'text' }, { id: 'audio-id', name: 'Voice', field_type: 'audio' }]
  it('uses IDs, retains explicit empty samples, and leaves mapped media to safe system samples', () => {
    expect(mappingSampleValues(inputs, fields, { Word: 'text-id', Audio: 'audio-id' }, { 'text-id': '' })).toEqual({ Word: '' })
    expect(mappingSampleValues(inputs, fields, { Word: 'text-id', Audio: 'audio-id' }, {})).toEqual({ Word: 'Renamed' })
  })
  it('renders invalid and unbound inputs empty rather than fabricating complete mappings', () => {
    expect(mappingSampleValues(inputs, fields, { Word: 'audio-id', Audio: 'missing' }, {})).toEqual({ Word: '', Audio: '' })
  })
  it('treats prototype-looking keys as real own keys and allows one field for multiple inputs', () => {
    const schema = [{ key: '__proto__', label: '', type: 'text' as const, required: false }, { key: 'constructor', label: '', type: 'text' as const, required: false }]
    const bindings = Object.fromEntries(schema.map((input) => [input.key, 'text-id']))
    expect(mappingSampleValues(schema, fields, bindings, { 'text-id': 'same' })).toEqual(Object.fromEntries(schema.map((input) => [input.key, 'same'])))
  })
})
