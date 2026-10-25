import { apiJson } from '@/shared/api/client'

export type DeckPublishStatus = 'private' | 'published'

/** The listing PATCH owns visibility; a release stays pinned while the deck is private. */
export function updateDeckPublishStatus(deckItemId: string, publishStatus: DeckPublishStatus) {
  return apiJson(`/api/shared/decks/${encodeURIComponent(deckItemId)}`, 'PATCH', { publish_status: publishStatus })
}
