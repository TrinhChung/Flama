import { describe, expect, it } from 'vitest'
import { templateInputReferences } from './templateInputReferences'

describe('templateInputReferences uses the renderer parser', () => {
  const inputs = [{ key: 'Word', label: '', type: 'text' as const, required: false }, { key: 'Audio', label: '', type: 'audio' as const, required: false }]
  it('finds conditional, unescaped and derived media references and ignores comments and FrontSide', () => {
    const result = templateInputReferences('{{#Word}}{{{Word}}}{{/Word}}{{! Word }}{{#Audio_urls}}{{.}}{{/Audio_urls}}', '{{^Word}}{{& Word}}{{/Word}}{{FrontSide}}<audio src="{{Audio_url}}"></audio>{{Missing}}', inputs)
    expect([...result.front]).toEqual(['Word', 'Audio']); expect([...result.back]).toEqual(['Word', 'Audio']); expect(result.unknown).toEqual(['Missing']); expect(result.parseErrors).toEqual([])
  })
  it('handles changed delimiters and reports incomplete syntax instead of guessing deletion safety', () => {
    expect([...templateInputReferences('{{=<% %>=}}<%Word%>', '', inputs).front]).toEqual(['Word'])
    expect(templateInputReferences('{{#Word}}', '', inputs).parseErrors).toHaveLength(1)
  })
})
