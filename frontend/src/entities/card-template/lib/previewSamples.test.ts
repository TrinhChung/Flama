import { describe, expect, it } from 'vitest'
import { defaultTemplateSample, previewSampleValue, sampleMediaUrl, templateSampleValues } from './previewSamples'

describe('preview sample transport', () => {
  it('keeps an array editor JSON list including nested and empty items', () => {
    expect(previewSampleValue('["one",["two",""],"one"]', 'array')).toEqual(['one', ['two', ''], 'one'])
  })
  it('keeps text samples and deliberate mismatches as text', () => {
    expect(previewSampleValue('["one"]', 'text')).toBe('["one"]')
    expect(previewSampleValue('one|two', 'array')).toBe('one|two')
    expect(previewSampleValue('', 'array')).toBe('')
  })
  it('generates typed defaults and preserves explicit empty values and prototype-like keys', () => {
    const values = templateSampleValues([{ key: 'options', type: 'array' }, { key: 'image', type: 'image' }, { key: '__proto__', type: 'text' }], JSON.parse('{"__proto__":""}'))
    expect(values.options).toEqual(['First item', 'Second item', 'Third item'])
    expect(values.image).toBe('/store/sample-image.png')
    expect(values.__proto__).toBe('')
    expect(defaultTemplateSample('markdown')).toContain('##')
    expect(templateSampleValues([{ key: 'options', type: 'array' }], { options: [] })).toEqual({ options: [] })
  })
  it('loads only safe media references in the form', () => {
    for (const unsafe of ['javascript:alert(1)', 'data:image/svg+xml,<svg/>', '//other.test/file.png', 'https://user:secret@example.test/a', 'https://example.test/"x']) expect(sampleMediaUrl(unsafe)).toBe('')
    expect(sampleMediaUrl('/store/sample-image.png')).toBe('/store/sample-image.png')
    expect(sampleMediaUrl('/media/proxy/sample-image')).toBe('/media/proxy/sample-image')
    expect(sampleMediaUrl('https://example.test/image.webp')).toBe('https://example.test/image.webp')
    expect(sampleMediaUrl('http://127.0.0.1:4789/media/proxy/a')).toBe('http://127.0.0.1:4789/media/proxy/a')
  })
})
