import { useQuery } from '@tanstack/react-query'
import { cardTemplateQueryKeys, fetchDeckCardTypes } from '@/entities/card-template'

export function useDeckCardTypes(deckId: number, open: boolean) {
  return useQuery({
    queryKey: cardTemplateQueryKeys.deckCardTypes(deckId),
    queryFn: ({ signal }) => fetchDeckCardTypes(deckId, signal),
    enabled: open,
  })
}
