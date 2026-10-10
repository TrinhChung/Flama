import { ApiError } from '@/shared/api/client'

/** Server error codes of the answers conversion that have a localized message. */
export const KNOWN_CONVERSION_ERRORS = [
  'NOTES_CHANGED',
  'FIELD_CHANGED',
  'FIELD_RENAME_IN_PROGRESS',
  'FIELD_NOT_CONVERTIBLE',
  'INVALID_ANSWERS_VALUE',
  'INVALID_FIELD_VALUE',
] as const

export type KnownConversionError = (typeof KNOWN_CONVERSION_ERRORS)[number]

export function knownConversionError(error: unknown): KnownConversionError | null {
  if (!(error instanceof ApiError)) return null
  return (KNOWN_CONVERSION_ERRORS as readonly string[]).includes(error.code)
    ? (error.code as KnownConversionError)
    : null
}
