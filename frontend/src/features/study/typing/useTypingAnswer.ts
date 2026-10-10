import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { answerMask, matchTypedAnswer, maxHintCount } from './typingAnswer'

/** `skipped`: the card was flipped (Skip / Show answer) without a correct answer. */
export type TypingOutcome = 'pending' | 'incorrect' | 'correct' | 'skipped'

export type UseTypingAnswerOptions = {
  answers: readonly string[]
  revealed: boolean
  onCorrect: () => void
}

/**
 * Local state of one card's typed answer. The caller remounts it per card, so
 * nothing leaks between cards and nothing is persisted or sent anywhere.
 */
export function useTypingAnswer({ answers, revealed, onCorrect }: UseTypingAnswerOptions) {
  const [value, setValueState] = useState('')
  const [outcome, setOutcome] = useState<TypingOutcome>('pending')
  const [attempts, setAttempts] = useState(0)
  const [wrongAttempts, setWrongAttempts] = useState(0)
  const [hintsUsed, setHintsUsed] = useState(0)
  const canonical = answers[0] ?? ''
  const maxHints = useMemo(() => maxHintCount(canonical), [canonical])
  const mask = useMemo(() => answerMask(canonical, hintsUsed), [canonical, hintsUsed])
  const wasRevealed = useRef(revealed)

  useEffect(() => {
    // Only a flip seen here counts as a skip; a card restored already flipped
    // (undo) carries no typing outcome.
    if (revealed && !wasRevealed.current) {
      setOutcome((current) => (current === 'correct' ? current : 'skipped'))
    }
    wasRevealed.current = revealed
  }, [revealed])

  const setValue = useCallback((next: string) => {
    setValueState(next)
    setOutcome((current) => (current === 'incorrect' ? 'pending' : current))
  }, [])

  /** Returns true when correct (and flips the card), false when wrong, null when ignored. */
  const submit = useCallback((): boolean | null => {
    if (revealed || !value.trim()) return null
    setAttempts((count) => count + 1)
    if (matchTypedAnswer(value, answers) < 0) {
      setWrongAttempts((count) => count + 1)
      setOutcome('incorrect')
      return false
    }
    setOutcome('correct')
    onCorrect()
    return true
  }, [answers, onCorrect, revealed, value])

  const revealHint = useCallback(() => {
    setHintsUsed((count) => Math.min(maxHints, count + 1))
  }, [maxHints])

  return {
    value,
    setValue,
    outcome,
    attempts,
    wrongAttempts,
    hintsUsed,
    maxHints,
    mask,
    canonical,
    submit,
    revealHint,
  }
}
