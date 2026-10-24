import { apiRequest } from '@/shared/api/client'
import type { DeckScanResponse } from '../types'

export async function scanDeckAudio(deckId: number, referenceKind: 'card' | 'note' = 'card'): Promise<DeckScanResponse> {
  return apiRequest<DeckScanResponse>('/api/flashcards/audio/deck-scan', {
    method: 'POST',
    body: JSON.stringify({ deck_id: deckId, ...(referenceKind === 'note' ? { reference_kind: 'note' } : {}) }),
  })
}
