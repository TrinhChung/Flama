import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiRequest } from '@/shared/api/client'
import { toDeckOptions } from '../lib/deckOptions'
import type { DeckListItem } from '../model/types'

export const deckListQueryKey = ['browse-decks-tree'] as const

export async function fetchDeckList(): Promise<DeckListItem[]> {
  const res = await apiRequest<{ decks: DeckListItem[] }>('/api/browse/decks')
  return res.decks || []
}

/** Accessible decks plus their picker options, shared by every deck tree picker. */
export function useDeckOptionsQuery({ staleTime }: { staleTime?: number } = {}) {
  const query = useQuery({
    queryKey: deckListQueryKey,
    queryFn: fetchDeckList,
    staleTime,
  })
  const decks = useMemo(() => query.data || [], [query.data])
  const deckOptions = useMemo(() => toDeckOptions(decks), [decks])
  return { decks, deckOptions, isLoading: query.isLoading }
}
