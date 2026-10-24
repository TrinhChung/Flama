import { describe, expect, it } from 'vitest'
import { previewSampleValue } from './previewSamples'

describe('preview sample transport', () => {
  it('keeps an array editor JSON list including nested and empty items', () => {
    expect(previewSampleValue('["one",["two",""],"one"]', 'array')).toEqual(['one', ['two', ''], 'one'])
  })
  it('keeps text samples and deliberate mismatches as text', () => {
    expect(previewSampleValue('["one"]', 'text')).toBe('["one"]')
    expect(previewSampleValue('one|two', 'array')).toBe('one|two')
    expect(previewSampleValue('', 'array')).toBe('')
  })
})
