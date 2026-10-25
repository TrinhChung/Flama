import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ApiError } from '@/shared/api/client'
import { browseApi, browseQueryKeys } from '../api/browseApi'
import type { BrowseCardRow } from '../types'
import type { useBrowseFilters } from './useBrowseFilters'
import { useBrowseDeckSummaries } from './useBrowseDeckSummaries'

const EMPTY_BROWSE_CARDS: BrowseCardRow[] = []

/** A 4xx (bad filter, missing deck) will fail the same way again. */
function retryUnlessClientError(failureCount: number, error: Error) {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
  return failureCount < 1
}

export function useBrowseData(filters: ReturnType<typeof useBrowseFilters>) {
  const { debouncedQuery, selectedDeckId, statusFilter, sortBy, sortDir, page, setPage, perPage } = filters
  // Decks Tree Query
  const structureQuery = useQuery({
    queryKey: ['browse', 'decks', 'structure'],
    queryFn: ({ signal }) => browseApi.fetchDeckStructure(signal),
  })
  const [visibleDeckIds, setVisibleDeckIds] = useState<number[]>([])
  const summaryIds = useMemo(() => [...new Set([
    ...(selectedDeckId === null ? [] : [selectedDeckId]), ...visibleDeckIds,
  ])].sort((a, b) => a - b), [selectedDeckId, visibleDeckIds])
  const summaries = useBrowseDeckSummaries(summaryIds)
  const decks = useMemo(() => (structureQuery.data?.decks || []).map((deck) => {
    const summary = summaries.byId.get(deck.id)
    return summary ? { ...deck, ...summary } : deck
  }), [structureQuery.data, summaries.byId])
  // Retain the existing workspace contract while keeping server caches separate.
  const decksQuery = { ...structureQuery, data: structureQuery.data ? { decks } : undefined }

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
    queryFn: async ({ signal }) => {
      const result = await browseApi.fetchCards({
        q: debouncedQuery,
        deck_id: selectedDeckId !== null ? selectedDeckId : '',
        status: statusFilter,
        sort_by: sortBy,
        sort_dir: sortDir,
        page,
        per_page: perPage,
      }, signal)
      return { ...result, per_page: result.per_page ?? perPage }
    },
    // Retain rows only while paging inside the same deck/filter/sort scope.
    placeholderData: (previous, previousQuery) => {
      const previousScope = previousQuery?.queryKey.slice(2, 7)
      const scope = [debouncedQuery, selectedDeckId, statusFilter, sortBy, sortDir]
      return previousScope?.every((value, index) => value === scope[index]) ? previous : undefined
    },
    retry: retryUnlessClientError,
  })

  const cards = cardsQuery.data?.items || EMPTY_BROWSE_CARDS
  const displayedPage = cardsQuery.data?.page ?? page
  const displayedPerPage = cardsQuery.data?.per_page ?? perPage

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


  const selectedDeckSummaryPending = selectedDeckId !== null && selectedDeck?.summary_loaded !== true
  return { decksQuery, noteTypesQuery, cardsQuery, cards, selectedDeck, refetchCards, setVisibleDeckIds, selectedDeckSummaryPending, deckSummaryError: summaries.error, displayedPage, displayedPerPage, ensureDeckSummary: summaries.ensureDeckSummary }
}
