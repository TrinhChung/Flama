/** MAX_TAG_LENGTH / MAX_TAG_COUNT in app/validators/flashcard_input.py. */
export const NOTE_TAG_MAX_LENGTH = 64
export const NOTE_TAG_MAX_COUNT = 50

/** Approximates Python's str.casefold(), which the backend uses to dedupe tags. */
export function tagDedupeKey(tag: string): string {
  return tag.toUpperCase().toLowerCase()
}
