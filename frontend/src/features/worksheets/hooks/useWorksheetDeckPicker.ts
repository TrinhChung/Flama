import { useEffect, useState } from 'react'
import { useDeckOptionsQuery } from '@/entities/deck'
import { fetchDeckWorksheetMeta } from '../api'
import type { DeckWorksheetMeta } from '../types'
import { hasMixedNoteTypes } from '../utils/worksheetMeta'

const DECK_LIST_STALE_TIME_MS = 60 * 1000

/** Deck tree data plus worksheet metadata/validation for the highlighted deck. */
export function useWorksheetDeckPicker(selectedDeckId: number | null) {
  const [activeDeckId, setActiveDeckId] = useState<number | null>(selectedDeckId)
  const [deckMeta, setDeckMeta] = useState<DeckWorksheetMeta | null>(null)
  const [isLoadingMeta, setIsLoadingMeta] = useState<boolean>(false)
  const [metaError, setMetaError] = useState<string | null>(null)

  const { deckOptions, isLoading: isLoadingDecks } = useDeckOptionsQuery({
    staleTime: DECK_LIST_STALE_TIME_MS,
  })

  // Fetch metadata whenever a deck is selected
  useEffect(() => {
    if (!activeDeckId) {
      setDeckMeta(null)
      setMetaError(null)
      return
    }

    let isMounted = true
    setIsLoadingMeta(true)
    setMetaError(null)

    fetchDeckWorksheetMeta(activeDeckId)
      .then((meta) => {
        if (!isMounted) return
        setDeckMeta(meta)
      })
      .catch((err) => {
        if (!isMounted) return
        setMetaError(String(err?.message || err || 'Không thể tải thông tin bộ thẻ'))
      })
      .finally(() => {
        if (isMounted) setIsLoadingMeta(false)
      })

    return () => {
      isMounted = false
    }
  }, [activeDeckId])

  // Validation rules: deck must have exactly 1 note type and at least one note
  const hasMultipleNoteTypes = hasMixedNoteTypes(deckMeta)
  const isEmptyDeck = Boolean(deckMeta && deckMeta.total_notes === 0)
  const canProceed = Boolean(
    activeDeckId && deckMeta && !hasMultipleNoteTypes && !isEmptyDeck && !isLoadingMeta,
  )

  return {
    deckOptions,
    isLoadingDecks,
    activeDeckId,
    setActiveDeckId,
    deckMeta,
    isLoadingMeta,
    metaError,
    hasMultipleNoteTypes,
    isEmptyDeck,
    canProceed,
  }
}
