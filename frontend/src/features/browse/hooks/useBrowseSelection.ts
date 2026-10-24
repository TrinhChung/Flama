import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { BrowseCardRow } from '../types'

export function useBrowseSelection(cards: BrowseCardRow[]) {
  const [selectedCards, setSelectedCards] = useState<string[]>([])
  const selectedCardSet = useMemo(() => new Set(selectedCards), [selectedCards])

  // Retain identity only for selected rows, including selections on other pages.
  const selectedNoteIdsRef = useRef(new Map<string, string>())
  useEffect(() => {
    for (const id of selectedNoteIdsRef.current.keys()) {
      if (!selectedCardSet.has(id)) selectedNoteIdsRef.current.delete(id)
    }
    for (const row of cards) {
      if (selectedCardSet.has(row.card_id)) selectedNoteIdsRef.current.set(row.card_id, row.note_id)
    }
  }, [cards, selectedCardSet])

  // Keyboard shortcuts
  const cardsRef = useRef(cards)
  cardsRef.current = cards
  const selectedCardsCountRef = useRef(selectedCards.length)
  selectedCardsCountRef.current = selectedCards.length

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeEl = document.activeElement
      const isEditingText =
        activeEl instanceof HTMLInputElement ||
        activeEl instanceof HTMLTextAreaElement ||
        Boolean((activeEl as HTMLElement | null)?.isContentEditable)

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
        if (!isEditingText && cardsRef.current.length > 0) {
          e.preventDefault()
          setSelectedCards(cardsRef.current.map((c) => c.card_id))
        }
      } else if (e.key === 'Escape') {
        if (!isEditingText && selectedCardsCountRef.current > 0) {
          e.preventDefault()
          setSelectedCards([])
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const allSelected = useMemo(
    () => cards.length > 0 && cards.every((card) => selectedCardSet.has(card.card_id)),
    [cards, selectedCardSet],
  )

  const handleToggleSelectAllCards = useCallback(() => {
    setSelectedCards(allSelected ? [] : cards.map((c) => c.card_id))
  }, [allSelected, cards])

  const handleToggleCardSelected = useCallback((cardId: string, selected: boolean) => {
    setSelectedCards((current) => {
      if (selected) return current.includes(cardId) ? current : [...current, cardId]
      return current.filter((id) => id !== cardId)
    })
  }, [])


  return { selectedCards, setSelectedCards, selectedCardSet, selectedNoteIdsRef, allSelected, handleToggleSelectAllCards, handleToggleCardSelected }
}
