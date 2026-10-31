export type TextDiffSegment = {
  text: string
  changed: boolean
}

export type TextDiff = {
  before: TextDiffSegment[]
  after: TextDiffSegment[]
}

// CJK has no spaces, so each character is its own token; other scripts diff by word.
const TOKEN_PATTERN = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]|[\p{L}\p{N}_]+|\s+|[^]/gu
const MAX_TOKENS = 800

function tokenize(text: string): string[] {
  return text.match(TOKEN_PATTERN) || []
}

function pushSegment(segments: TextDiffSegment[], text: string, changed: boolean) {
  const last = segments[segments.length - 1]
  if (last && last.changed === changed) last.text += text
  else segments.push({ text, changed })
}

/**
 * Word/character level diff of two texts for side-by-side highlighting.
 * Returns null for texts too long to diff cheaply; show them unmarked.
 */
export function diffText(before: string, after: string): TextDiff | null {
  const left = tokenize(before)
  const right = tokenize(after)
  if (left.length > MAX_TOKENS || right.length > MAX_TOKENS) return null
  const width = right.length + 1
  // lengths[i * width + j]: longest common subsequence of left[i:] and right[j:].
  const lengths = new Uint16Array((left.length + 1) * width)
  for (let i = left.length - 1; i >= 0; i -= 1) {
    for (let j = right.length - 1; j >= 0; j -= 1) {
      lengths[i * width + j] = left[i] === right[j]
        ? lengths[(i + 1) * width + j + 1] + 1
        : Math.max(lengths[(i + 1) * width + j], lengths[i * width + j + 1])
    }
  }
  const diff: TextDiff = { before: [], after: [] }
  let i = 0
  let j = 0
  while (i < left.length || j < right.length) {
    if (i < left.length && j < right.length && left[i] === right[j]) {
      pushSegment(diff.before, left[i], false)
      pushSegment(diff.after, right[j], false)
      i += 1
      j += 1
    } else if (j >= right.length || (i < left.length && lengths[(i + 1) * width + j] >= lengths[i * width + j + 1])) {
      pushSegment(diff.before, left[i], true)
      i += 1
    } else {
      pushSegment(diff.after, right[j], true)
      j += 1
    }
  }
  return diff
}
