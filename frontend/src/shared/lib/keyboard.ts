import type { KeyboardEvent } from 'react'

/** Enter that only confirms an IME candidate (Japanese, Vietnamese Telex…) must not submit. */
export function isImeEnter(e: Pick<KeyboardEvent<HTMLElement>, 'nativeEvent' | 'keyCode'>): boolean {
  return e.nativeEvent.isComposing || e.keyCode === 229
}
