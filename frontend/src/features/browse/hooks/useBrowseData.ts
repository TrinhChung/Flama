import { useCallback, useEffect } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ApiError } from '@/shared/api/client'
import { browseApi, browseQueryKeys } from '../api/browseApi'
import type { BrowseCardRow } from '../types'
import type { useBrowseFilters } from './useBrowseFilters'

const EMPTY_BROWSE_CARDS: BrowseCardRow[] = []

/** A 4xx (bad filter, missing deck) will fail the same way again. */
function retryUnlessClientError(failureCount: number, error: Error) {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
  return failureCount < 1
}

export function useBrowseData(filters: ReturnType<typeof useBrowseFilters>) {
  const { debouncedQuery, selectedDeckId, statusFilter, sortBy, sortDir, page, setPage, perPage } = filters
  // Decks Tree Query
  const decksQuery = useQuery({
    queryKey: ['browse', 'decks'],
    queryFn: ({ signal }) => browseApi.fetchDecks(signal),
  })

  // Note Types Query for Card Creation
  const noteTypesQuery = useQuery({
    queryKey: browseQueryKeys.noteTypes,
    queryFn: ({ signal }) => browseApi.fetchNoteTypes(signal),
  })

  // Cards List Query
  const cardsQuery = useQuery({
    queryKey: [
      'browse',
      'cards',
      debouncedQuery,
      selectedDeckId,
      statusFilter,
      sortBy,
      sortDir,
      page,
      perPage,
    ],
    queryFn: ({ signal }) =>
      browseApi.fetchCards({
        q: debouncedQuery,
        deck_id: selectedDeckId !== null ? selectedDeckId : '',
        status: statusFilter,
        sort_by: sortBy,
        sort_dir: sortDir,
        page,
        per_page: perPage,
      }, signal),
    placeholderData: keepPreviousData,
    retry: retryUnlessClientError,
  })

  const cards = cardsQuery.data?.items || EMPTY_BROWSE_CARDS

  // Pull the page back inside the result, e.g. after deleting the last rows.
  const confirmedPageCount = cardsQuery.isPlaceholderData ? null : cardsQuery.data?.pages
  useEffect(() => {
    if (confirmedPageCount === undefined || confirmedPageCount === null) return
    const lastPage = Math.max(1, confirmedPageCount)
    if (page > lastPage) setPage(lastPage)
  }, [confirmedPageCount, page, setPage])

  const { refetch: refetchCardsQuery } = cardsQuery
  const refetchCards = useCallback(() => {
    void refetchCardsQuery()
  }, [refetchCardsQuery])

  const selectedDeck =
    selectedDeckId !== null
      ? (decksQuery.data?.decks || []).find((deck) => deck.id === selectedDeckId) || null
      : null


  return { decksQuery, noteTypesQuery, cardsQuery, cards, selectedDeck, refetchCards }
}
