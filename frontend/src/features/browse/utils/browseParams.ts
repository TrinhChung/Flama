/** Parse a `deck_id` URL param; anything but a positive integer is ignored (the API rejects it with 400). */
export function parseDeckIdParam(raw: string | null): number | null {
  const trimmed = raw?.trim() ?? ''
  if (!/^\d+$/.test(trimmed)) return null
  const value = Number(trimmed)
  return Number.isSafeInteger(value) && value > 0 ? value : null
}
