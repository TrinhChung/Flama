import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../api/dashboardApi'
import { dashboardQueryKey } from '../api'
import type { DeckNode } from '../types'

/**
 * The note type a new sub-deck of `deck` inherits: the deck's own, else the
 * server's fallback (its oldest Note, or its install). The dashboard payload
 * carries only the deck's own type, so the fallback is fetched on demand.
 */
export function useInheritedNoteType(deck: DeckNode | null | undefined, enabled: boolean) {
  const needsFallback = Boolean(enabled && deck && !deck.note_type_id)
  const query = useQuery({
    queryKey: [...dashboardQueryKey, 'deck-note-type', deck?.id],
    queryFn: () => dashboardApi.getDeckNoteType(deck!.id),
    enabled: needsFallback,
  })
  return {
    noteTypeId: deck?.note_type_id || query.data?.note_type_id || '',
    isPending: needsFallback && query.isPending,
  }
}
