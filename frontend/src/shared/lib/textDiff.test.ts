import { describe, expect, it } from 'vitest'
import { diffText } from './textDiff'

function marked(segments: { text: string; changed: boolean }[]) {
  return segments.filter((segment) => segment.changed).map((segment) => segment.text)
}

describe('diffText', () => {
  it('marks changed words and keeps the rest', () => {
    const diff = diffText('to eat food', 'to eat dinner')!
    expect(marked(diff.before)).toEqual(['food'])
    expect(marked(diff.after)).toEqual(['dinner'])
    expect(diff.after.map((segment) => segment.text).join('')).toBe('to eat dinner')
  })

  it('diffs Japanese character by character', () => {
    const diff = diffText('食べる', '食べた')!
    expect(marked(diff.before)).toEqual(['る'])
    expect(marked(diff.after)).toEqual(['た'])
  })

  it('gives up on texts too long to compare cheaply', () => {
    expect(diffText('word '.repeat(900), 'other')).toBeNull()
  })
})
