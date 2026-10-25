import { useCallback, useMemo } from 'react'
import { useQueries, useQueryClient, type UseQueryResult } from '@tanstack/react-query'
import { createDeckSummaryLoader } from '../api/deckSummaryLoader'
import { ApiError } from '@/shared/api/client'
import type { BrowseDeck } from '../types'

export function useBrowseDeckSummaries(deckIds: number[]) {
  const queryClient = useQueryClient()
  const loadSummary = useMemo(createDeckSummaryLoader, [])
  const combine = useCallback((results: UseQueryResult<BrowseDeck, Error>[]) => ({
    byId: new Map(deckIds.map((id, index) => [id, results[index].data])),
    error: results.find((result) => result.isError)?.error,
  }), [deckIds])
  const results = useQueries({
    queries: deckIds.map((id) => ({
      queryKey: ['browse', 'decks', 'summary', id],
      queryFn: ({ signal }: { signal: AbortSignal }) => loadSummary(id, signal),
      staleTime: 30_000,
      retry: (failures: number, error: Error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failures < 1,
    })),
    combine,
  })
  const ensureDeckSummary = useCallback((id: number) => queryClient.fetchQuery({
    queryKey: ['browse', 'decks', 'summary', id],
    queryFn: ({ signal }) => loadSummary(id, signal),
    staleTime: 30_000,
  }), [queryClient, loadSummary])
  return { ...results, ensureDeckSummary }
}
