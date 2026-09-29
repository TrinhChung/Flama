import type { Rating } from '../types'
import type { SchedulerCardState, SchedulerDecision } from './types'

export const NOTE_STORAGE_PROFILE = 'note-mysql-float-text.v1'

/** MySQL FLOAT text-protocol round trip, matching the NOTE server profile. */
export function legacyFloatRoundTrip(value: number): number {
  const stored = Math.fround(value)
  if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isFinite(stored)) {
    throw new Error('Legacy FLOAT requires a finite value within its range.')
  }
  if (stored === 0) return stored // Preserve signed zero.

  // Round the exact binary32 rational to six significant digits, ties to even.
  // Number.toPrecision(6) rounds ties away from zero (1.015625 is a counterexample).
  const bytes = new DataView(new ArrayBuffer(4))
  bytes.setFloat32(0, Math.abs(stored))
  const bits = bytes.getUint32(0)
  const exponentBits = (bits >>> 23) & 0xff
  const significand = (bits & 0x7fffff) + (exponentBits ? 0x800000 : 0)
  const binaryExponent = exponentBits ? exponentBits - 150 : -149
  let numerator = BigInt(significand)
  let denominator = 1n
  if (binaryExponent >= 0) numerator <<= BigInt(binaryExponent)
  else denominator <<= BigInt(-binaryExponent)

  const decimalExponent = Number(Math.abs(stored).toExponential().split('e')[1])
  const scale = 5 - decimalExponent
  if (scale >= 0) numerator *= 10n ** BigInt(scale)
  else denominator *= 10n ** BigInt(-scale)
  let rounded = numerator / denominator
  const doubledRemainder = (numerator % denominator) * 2n
  if (doubledRemainder > denominator
    || (doubledRemainder === denominator && rounded % 2n !== 0n)) {
    rounded += 1n
  }
  return Number(`${stored < 0 ? '-' : ''}${rounded}e${decimalExponent - 5}`)
}

export function normalizeNoteTransitionState(state: SchedulerCardState): SchedulerCardState {
  return {
    ...state,
    interval_days: legacyFloatRoundTrip(state.interval_days),
    ease: legacyFloatRoundTrip(state.ease),
    memory_state: state.memory_state ? {
      stability: legacyFloatRoundTrip(state.memory_state.stability),
      difficulty: legacyFloatRoundTrip(state.memory_state.difficulty),
    } : null,
  }
}

export function normalizeNoteDecision(decision: SchedulerDecision): SchedulerDecision {
  const outcomes = { ...decision.outcomes }
  for (const rating of Object.keys(outcomes) as Rating[]) {
    outcomes[rating] = normalizeNoteTransitionState(outcomes[rating])
  }
  return { ...decision, outcomes }
}
