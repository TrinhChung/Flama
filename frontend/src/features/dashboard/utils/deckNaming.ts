/**
 * Utility for intelligent deck name suggestion and auto-incrementing.
 */

/**
 * Generates the next sequential deck name based on a reference deck name.
 * - If the reference deck has numbers (e.g. "N1:Bài 1", "Lesson 01", "Day 9"), it increments the last number sequence.
 * - Preserves zero-padding if present (e.g. "Bài 09" -> "Bài 10", "Day 01" -> "Day 02").
 * - If no numbers exist (e.g. "Kanji"), it appends " 2".
 * - If existingNames are provided, it avoids collisions with sibling decks by finding the next available number.
 */
export function suggestNextDeckName(
  baseName: string | null | undefined,
  existingNames: string[] = [],
): string {
  if (!baseName || !baseName.trim()) {
    return ''
  }

  const trimmed = baseName.trim()
  const existingSet = new Set(
    existingNames.map((name) => name.trim().toLowerCase()).filter(Boolean),
  )

  const numberMatches = Array.from(trimmed.matchAll(/\d+/g))

  const generateCandidate = (step: number): string => {
    if (numberMatches.length > 0) {
      const lastMatch = numberMatches[numberMatches.length - 1]
      const digitsStr = lastMatch[0]
      const matchIndex = lastMatch.index ?? 0
      const currentNum = parseInt(digitsStr, 10)
      const nextNum = currentNum + step

      const isPadded = digitsStr.length > 1 && digitsStr.startsWith('0')
      const formattedNum = isPadded
        ? String(nextNum).padStart(digitsStr.length, '0')
        : String(nextNum)

      return (
        trimmed.slice(0, matchIndex) +
        formattedNum +
        trimmed.slice(matchIndex + digitsStr.length)
      )
    }

    return step === 1 ? `${trimmed} 2` : `${trimmed} ${step + 1}`
  }

  // Find the first candidate that doesn't collide with existing siblings
  for (let step = 1; step <= 1000; step++) {
    const candidate = generateCandidate(step)
    if (!existingSet.has(candidate.toLowerCase())) {
      return candidate
    }
  }

  return generateCandidate(1)
}
