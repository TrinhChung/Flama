/**
 * Typing-answer comparison for Study (typing-compare.v1).
 *
 * The frontend alone decides correct/incorrect; nothing here is sent to the
 * server. Accepted answers are the lines of the bound field. Comparison only
 * ignores differences that never change meaning (Unicode composition,
 * whitespace, letter case); diacritics, kana script and punctuation are exact.
 */

import { fieldValueToText } from '@/lib/arrayField'

export const TYPING_COMPARE_VERSION = 'typing-compare.v1'

export type TypingInputConfig = {
  key: string
  showLength: boolean
  hints: boolean
}

/** The template's typing input, or null when absent or malformed (e.g. a stale restored snapshot). */
export function readTypingInput(template: { typing_input?: unknown } | null | undefined): TypingInputConfig | null {
  const raw = template?.typing_input
  if (typeof raw !== 'object' || raw === null) return null
  const value = raw as Record<string, unknown>
  if (
    value.schema_version !== 'study-typing-input.v1'
    || typeof value.key !== 'string'
    || !value.key
    || typeof value.show_length !== 'boolean'
    || typeof value.hints !== 'boolean'
  ) return null
  return { key: value.key, showLength: value.show_length, hints: value.hints }
}

export { fieldValueToText }

/** Normalized form used for matching: only meaning-preserving differences removed. */
export function normalizeTypedAnswer(value: string): string {
  return value
    .normalize('NFC')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
    .normalize('NFC')
}

/** Accepted answers: one per visible line, trimmed, empty and duplicate lines dropped. */
export function parseAnswerLines(raw: unknown): string[] {
  const answers: string[] = []
  const seen = new Set<string>()
  for (const line of fieldValueToText(raw).split('\n')) {
    const answer = line.normalize('NFC').replace(/\s+/g, ' ').trim()
    const key = normalizeTypedAnswer(answer)
    if (!key || seen.has(key)) continue
    seen.add(key)
    answers.push(answer)
  }
  return answers
}

/** Index of the accepted answer the typed text matches, or -1. */
export function matchTypedAnswer(typed: string, answers: readonly string[]): number {
  const key = normalizeTypedAnswer(typed)
  if (!key) return -1
  return answers.findIndex((answer) => normalizeTypedAnswer(answer) === key)
}

const graphemeSegmenter = typeof Intl !== 'undefined' && typeof Intl.Segmenter === 'function'
  ? new Intl.Segmenter(undefined, { granularity: 'grapheme' })
  : null

/** User-perceived characters, so a letter with diacritics or one kana is one cell. */
export function splitGraphemes(value: string): string[] {
  const text = value.normalize('NFC')
  if (graphemeSegmenter) return Array.from(graphemeSegmenter.segment(text), (part) => part.segment)
  return Array.from(text)
}

export type AnswerMaskCell =
  | { kind: 'space' }
  | { kind: 'char'; char: string; revealed: boolean }

/** Hidden cells for the canonical answer; the first `revealedCount` characters are shown. */
export function answerMask(answer: string, revealedCount: number): AnswerMaskCell[] {
  const cells: AnswerMaskCell[] = []
  let shown = 0
  for (const grapheme of splitGraphemes(answer.trim())) {
    if (/^\s+$/.test(grapheme)) {
      if (cells.length && cells[cells.length - 1].kind !== 'space') cells.push({ kind: 'space' })
      continue
    }
    cells.push({ kind: 'char', char: grapheme, revealed: shown < revealedCount })
    shown += 1
  }
  return cells
}

/** Hints stop one character short of the whole answer. */
export function maxHintCount(answer: string): number {
  const characters = answerMask(answer, 0).filter((cell) => cell.kind === 'char').length
  return Math.max(0, characters - 1)
}
