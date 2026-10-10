import { describe, expect, it } from 'vitest'
import type { MappingField, MappingInput } from './fieldMapping'
import { isTypeCompatible, suggestBindings, validateBindings } from './fieldMapping'

const input = (key: string, type: MappingInput['type'] = 'text', required = false): MappingInput => ({ key, label: key, type, required })
const fields: MappingField[] = [
  { id: 'wrong', name: 'Word', field_type: 'markdown' },
  { id: 'word-id', name: ' WORD ', field_type: 'text' },
  { id: 'picture-id', name: 'Picture', field_type: 'image' },
]

describe('template field mapping', () => {
  it.each(['text', 'richtext', 'markdown', 'image', 'audio', 'diagram'])('accepts exact %s only', (type) => {
    expect(isTypeCompatible(type, type)).toBe(true)
    expect(isTypeCompatible(type, type === 'text' ? 'markdown' : 'text')).toBe(false)
  })
  it('lets typed-answer inputs and text fields bind to each other only', () => {
    expect(isTypeCompatible('answers', 'text')).toBe(true)
    expect(isTypeCompatible('answers', 'answers')).toBe(true)
    expect(isTypeCompatible('text', 'answers')).toBe(true)
    expect(isTypeCompatible('answers', 'richtext')).toBe(false)
    expect(isTypeCompatible('image', 'answers')).toBe(false)
  })
  it('rejects unknown types and rich text interchange', () => {
    expect(isTypeCompatible('unknown', 'unknown')).toBe(false)
    expect(isTypeCompatible('text', 'richtext')).toBe(false)
    expect(isTypeCompatible('audio', 'image')).toBe(false)
  })
  it('suggests by normalized key, skips wrong type and reuses IDs', () => {
    expect(suggestBindings([input('Word'), input('word'), input('Missing'), { ...input('Other'), label: 'Word' }], fields))
      .toEqual({ Word: 'word-id', word: 'word-id', Missing: null, Other: null })
  })
  it('treats omitted/null/empty recommended inputs as advisory', () => {
    expect(validateBindings([input('A', 'text', true), input('B'), input('C')], fields, { B: null, C: '' }))
      .toEqual([
        { kind: 'unbound', key: 'A', required: true, blocking: false },
        { kind: 'unbound', key: 'B', required: false, blocking: false },
        { kind: 'unbound', key: 'C', required: false, blocking: false },
      ])
  })
  it('orders input issues before unknown keys and blocks stale optional targets', () => {
    expect(validateBindings([input('A'), input('B'), input('C')], fields,
      { unknown2: null, C: null, B: 'picture-id', A: 'foreign', unknown1: 'word-id' }))
      .toEqual([
        { kind: 'field_out_of_scope', key: 'A', fieldId: 'foreign', blocking: true },
        { kind: 'type_mismatch', key: 'B', fieldId: 'picture-id', blocking: true },
        { kind: 'unbound', key: 'C', required: false, blocking: false },
        { kind: 'unknown_input', key: 'unknown2', blocking: true },
        { kind: 'unknown_input', key: 'unknown1', blocking: true },
      ])
  })
  it('allows repeated target and never mutates arguments', () => {
    const inputs = Object.freeze([Object.freeze(input('Word')), Object.freeze(input('word'))])
    const bindings = Object.freeze({ Word: 'word-id', word: 'word-id' })
    expect(validateBindings([...inputs], fields, bindings)).toEqual([])
    expect(suggestBindings([...inputs], fields)).toEqual(bindings)
    expect(bindings).toEqual({ Word: 'word-id', word: 'word-id' })
  })
  it('treats prototype-named input keys as ordinary own entries', () => {
    const keys = ['__proto__', 'constructor', 'toString']
    const inputs = keys.map((key) => input(key, 'text', true))
    const namedFields = keys.map((key, index) => ({ id: `field-${index}`, name: key, field_type: 'text' }))
    expect(validateBindings(inputs, namedFields, {})).toEqual(keys.map((key) => ({
      kind: 'unbound', key, required: true, blocking: false,
    })))
    const suggested = suggestBindings(inputs, namedFields)
    expect(Object.keys(suggested)).toEqual(keys)
    expect(Object.hasOwn(suggested, '__proto__')).toBe(true)
    expect(suggested.__proto__).toBe('field-0')
    expect(validateBindings(inputs, namedFields, suggested)).toEqual([])
    expect(Object.getPrototypeOf(suggested)).toBe(Object.prototype)
    expect(JSON.parse(JSON.stringify(suggested))).toEqual(Object.fromEntries(keys.map((key, index) => [key, `field-${index}`])))
  })
})
