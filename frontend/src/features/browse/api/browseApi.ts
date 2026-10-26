import { API_BASE_URL } from '@/shared/config/env'
import { apiBlob, apiJson, apiRequest } from '@/shared/api/client'
import type { BrowseCardRow, BrowseCardsResponse, BrowseDeck, BrowseSortBy, BrowseSortDir, BrowseStatusFilter, CardDetailResponse, NoteTypeSummary } from '../types'

type NoteRow = Omit<BrowseCardRow, 'card_id'>
type NoteDetail = Omit<CardDetailResponse, 'card'> & { row: NoteRow }
// Existing UI component names retain "card"; their identities now refer to Notes.
const editorRow = (row: NoteRow): BrowseCardRow => ({ ...row, card_id: row.note_id })
const editorDetail = ({ row, ...detail }: NoteDetail): CardDetailResponse => ({ ...detail, card: editorRow(row) })

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

export { browseQueryKeys } from './browseQueryKeys'

export const browseApi = {
  fetchDecks: (signal?: AbortSignal) => apiRequest<{ decks: BrowseDeck[] }>(`${API_BASE_URL}/browse/decks?view=notes`, { signal }),
  fetchDeckStructure: (signal?: AbortSignal) => apiRequest<{ decks: BrowseDeck[] }>(`${API_BASE_URL}/browse/decks?view=notes&structure_only=1`, { signal }),
  fetchDeckSummaries: (deckIds: number[], signal?: AbortSignal) => apiRequest<{ decks: BrowseDeck[] }>(`${API_BASE_URL}/browse/decks/summaries?${new URLSearchParams({ deck_ids: deckIds.join(',') })}`, { signal, reportUnavailable: false }),
  fetchNoteTypes: (signal?: AbortSignal) => apiRequest<{ items: NoteTypeSummary[] }>(`${API_BASE_URL}/note-types?compact=1`, { signal }),
  async fetchCards(params: BrowseCardsParams, signal?: AbortSignal) {
    const query = new URLSearchParams()
    query.set('view', 'rows')
    for (const [key, value] of Object.entries(params)) if (value !== '') query.set(key, String(value))
    const result = await apiRequest<Omit<BrowseCardsResponse, 'items'> & { items: NoteRow[] }>(`${API_BASE_URL}/browse/notes?${query}`, { signal })
    return { ...result, items: result.items.map(editorRow) }
  },
  fetchCardDetail: async (id: string, signal?: AbortSignal) => editorDetail(await apiRequest<NoteDetail>(`${API_BASE_URL}/browse/notes/${encodeURIComponent(id)}?view=editor`, { signal })),
  createNote: (body: BrowseNoteCreate) => apiJson<{ id: string; card_ids?: Array<string | number>; first_card_id?: string | number }>(`${API_BASE_URL}/notes`, 'POST', body),
  async updateCard(id: string, body: BrowseNoteUpdate) {
    const result = await apiJson<{ detail: NoteDetail }>(`${API_BASE_URL}/browse/notes/${encodeURIComponent(id)}?view=editor`, 'PATCH', body)
    return { ...result, detail: editorDetail(result.detail) }
  },
  deleteNote: (id: string) => apiJson(`${API_BASE_URL}/browse/notes/${encodeURIComponent(id)}`, 'DELETE'),
  deleteNotes: (noteIds: string[]) => apiJson<{ success: boolean; deleted_count?: number }>(`${API_BASE_URL}/browse/notes/batch-delete`, 'POST', { note_ids: noteIds }),
  generateVoiceVox: ({ card_ids, ...body }: VoiceVoxGenerate) => apiJson(`${API_BASE_URL}/browse/voicevox/generate`, 'POST', { ...body, note_ids: card_ids }),
  // These provider routes were already canonical /api URLs, independent of API_BASE_URL's path.
  fetchVoiceVoxProfile: (signal?: AbortSignal) => apiRequest<{ profile?: { has_api_key: boolean; key_status: string } }>('/api/tts/providers/voicevox/profile', { signal }),
  saveVoiceVoxProfile: (body: { api_key: string; validate_key: boolean }) => apiJson('/api/tts/providers/voicevox/profile', 'PUT', body),
  fetchVoiceVoxVoices: (api_key?: string) => apiJson<{ items: Array<{ id: string; label: string; speaker_name: string; style_name: string }> }>('/api/tts/providers/voicevox/voices', 'POST', { api_key }),
  previewVoiceVox: (body: VoiceVoxPreview) => apiBlob('/api/browse/voicevox/preview', { method: 'POST', body: JSON.stringify(body) }),
}
