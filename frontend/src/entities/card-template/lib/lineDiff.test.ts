import { describe, expect, it } from 'vitest'
import { diffLines, type DiffLine, summarizeDiff } from './lineDiff'

function formatLine(line: DiffLine): string {
  return `${line.kind[0]}:${line.text}:${line.oldLine ?? '-'}:${line.newLine ?? '-'}`
}

function formatDiff(lines: DiffLine[]): string {
  return lines.map(formatLine).join(' | ')
}

describe('lineDiff', () => {
  it('handles identical multiline strings', () => {
    const diff = diffLines('a\nb\nc', 'a\nb\nc')
    expect(formatDiff(diff)).toBe('s:a:1:1 | s:b:2:2 | s:c:3:3')
  })

  it('handles single line replacement', () => {
    const diff = diffLines('a\nb\nc', 'a\nx\nc')
    expect(formatDiff(diff)).toBe('s:a:1:1 | r:b:2:- | a:x:-:2 | s:c:3:3')
  })

  it('handles empty old text (all added)', () => {
    const diff = diffLines('', 'x\ny')
    expect(formatDiff(diff)).toBe('a:x:-:1 | a:y:-:2')
  })

  it('handles empty new text (all removed)', () => {
    const diff = diffLines('x\ny', '')
    expect(formatDiff(diff)).toBe('r:x:1:- | r:y:2:-')
  })

  it('handles both empty texts', () => {
    const diff = diffLines('', '')
    expect(diff).toEqual([])
  })

  it('normalizes CRLF line endings', () => {
    const diff = diffLines('a\r\nb', 'a\nb')
    expect(formatDiff(diff)).toBe('s:a:1:1 | s:b:2:2')
  })

  it('handles trailing newline addition', () => {
    const diff = diffLines('a\nb', 'a\nb\n')
    expect(formatDiff(diff)).toBe('s:a:1:1 | s:b:2:2 | a::-:3')
  })

  it('handles multiple additions and removals with LCS', () => {
    const diff = diffLines('a\nb\nc\nd', 'b\nc\ne')
    expect(formatDiff(diff)).toBe('r:a:1:- | s:b:2:1 | s:c:3:2 | r:d:4:- | a:e:-:3')
  })

  it('falls back to all removed then all added when cell count exceeds maxCells', () => {
    const diff = diffLines('a\nb', 'c\nd', 3)
    expect(formatDiff(diff)).toBe('r:a:1:- | r:b:2:- | a:c:-:1 | a:d:-:2')
  })

  it('summarizes diff additions and removals correctly', () => {
    const diff = diffLines('a\nb\nc\nd', 'b\nc\ne')
    expect(summarizeDiff(diff)).toEqual({ added: 1, removed: 2 })
  })

  it('computes 2,000-line diff (4,000,000 cells) within reasonable time', () => {
    const linesA = Array.from({ length: 2000 }, (_, i) => `line ${i}`).join('\n')
    const linesB = Array.from({ length: 2000 }, (_, i) => (i % 2 === 0 ? `line ${i}` : `line ${i} mod`)).join('\n')
    const t0 = performance.now()
    const diff = diffLines(linesA, linesB)
    const elapsed = performance.now() - t0
    expect(diff.length).toBe(3000) // 1000 same, 1000 removed, 1000 added
    const summary = summarizeDiff(diff)
    expect(summary).toEqual({ added: 1000, removed: 1000 })
    expect(elapsed).toBeLessThan(1500)
  })

  it('triggers fallback when line count exceeds maxCells', () => {
    const linesA = Array.from({ length: 2001 }, (_, i) => `line ${i}`).join('\n')
    const linesB = Array.from({ length: 2000 }, (_, i) => `line ${i}`).join('\n')
    // 2001 * 2000 = 4,002,000 > 4,000,000
    const diff = diffLines(linesA, linesB)
    const summary = summarizeDiff(diff)
    expect(summary).toEqual({ added: 2000, removed: 2001 })
  })

  it('safely handles nullish or undefined inputs', () => {
    const diffNull = diffLines(null as unknown as string, undefined as unknown as string)
    expect(diffNull).toEqual([])

    const diffOneNull = diffLines(undefined as unknown as string, 'line 1\nline 2')
    expect(formatDiff(diffOneNull)).toBe('a:line 1:-:1 | a:line 2:-:2')
  })

  it('handles mixed CRLF and LF with intermediate empty lines', () => {
    const oldText = 'a\r\n\r\nb\r\n'
    const newText = 'a\n\nb\n'
    const diff = diffLines(oldText, newText)
    expect(formatDiff(diff)).toBe('s:a:1:1 | s::2:2 | s:b:3:3 | s::4:4')
  })
})
