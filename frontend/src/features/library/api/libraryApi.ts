import { apiRequest } from '@/shared/api/client'
import type { DeckCardItem } from '@/entities/marketplace-deck'

export function getInstalledDecks() {
  return apiRequest<{ items: DeckCardItem[] }>('/api/marketplace/installed-decks')
}
