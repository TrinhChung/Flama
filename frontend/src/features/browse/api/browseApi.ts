import { API_BASE_URL } from '@/config/env'
import { apiBlob, apiJson, apiRequest } from '@/shared/api/client'
import type { BrowseCardsResponse, BrowseDeck, BrowseSortBy, BrowseSortDir, BrowseStatusFilter, CardDetailResponse, NoteTypeSummary } from '../types'

export type BrowseCardsParams = {
  q: string; deck_id: number | ''; status: BrowseStatusFilter; sort_by: BrowseSortBy
  sort_dir: BrowseSortDir; page: number; per_page: number
}
export type BrowseNoteCreate = { note_type_id: string; deck_id: number; field_values: Record<string, unknown>; tags?: string[] }
export type BrowseNoteUpdate = {
  field_values: Record<string, unknown>; deck_id?: number; tags?: string[]
  expected_content_revision?: number; expected_field_schema_revision?: number; expected_overlay_revision?: number
}
type VoiceVoxGenerate = {
  card_ids?: string[]; deck_id?: number; source_field: string; destination_field: string
  character_id?: string; api_key?: string; append_audio?: boolean; use_opus?: boolean; settings?: Record<string, number>
}
type VoiceVoxPreview = { text: string; character_id?: string; api_key?: string; use_opus?: boolean; settings?: Record<string, number> }

/** Separate response shape, while retaining broad ['note-types'] invalidation. */
export const browseQueryKeys = { noteTypes: ['note-types', 'browse', 'compact'] as const }

export const browseApi = {
  fetchDecks: (signal?: AbortSignal) => apiRequest<{ decks: BrowseDeck[] }>(`${API_BASE_URL}/browse/decks`, { signal }),
  fetchNoteTypes: (signal?: AbortSignal) => apiRequest<{ items: NoteTypeSummary[] }>(`${API_BASE_URL}/note-types?compact=1`, { signal }),
  fetchCards(params: BrowseCardsParams, signal?: AbortSignal) {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) if (value !== '') query.set(key, String(value))
    return apiRequest<BrowseCardsResponse>(`${API_BASE_URL}/browse/cards?${query}`, { signal })
  },
  fetchCardDetail: (id: string, signal?: AbortSignal) => apiRequest<CardDetailResponse>(`${API_BASE_URL}/browse/cards/${encodeURIComponent(id)}`, { signal }),
  createNote: (body: BrowseNoteCreate) => apiJson<{ id: string; card_ids?: Array<string | number>; first_card_id?: string | number }>(`${API_BASE_URL}/notes`, 'POST', body),
  updateCard: (id: string, body: BrowseNoteUpdate) => apiJson<{ detail: CardDetailResponse }>(`${API_BASE_URL}/browse/cards/${encodeURIComponent(id)}`, 'PATCH', body),
  deleteNote: (id: string) => apiJson(`${API_BASE_URL}/browse/notes/${encodeURIComponent(id)}`, 'DELETE'),
  deleteNotes: (noteIds: string[]) => apiJson<{ success: boolean; deleted_count?: number }>(`${API_BASE_URL}/browse/notes/batch-delete`, 'POST', { note_ids: noteIds }),
  generateVoiceVox: (body: VoiceVoxGenerate) => apiJson(`${API_BASE_URL}/browse/voicevox/generate`, 'POST', body),
  // These provider routes were already canonical /api URLs, independent of API_BASE_URL's path.
  fetchVoiceVoxProfile: (signal?: AbortSignal) => apiRequest<{ profile?: { has_api_key: boolean; key_status: string } }>('/api/tts/providers/voicevox/profile', { signal }),
  saveVoiceVoxProfile: (body: { api_key: string; validate_key: boolean }) => apiJson('/api/tts/providers/voicevox/profile', 'PUT', body),
  fetchVoiceVoxVoices: (api_key?: string) => apiJson<{ items: Array<{ id: string; label: string; speaker_name: string; style_name: string }> }>('/api/tts/providers/voicevox/voices', 'POST', { api_key }),
  previewVoiceVox: (body: VoiceVoxPreview) => apiBlob('/api/browse/voicevox/preview', { method: 'POST', body: JSON.stringify(body) }),
}
