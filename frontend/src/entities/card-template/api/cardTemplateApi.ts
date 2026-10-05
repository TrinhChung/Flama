import { apiJson, apiRequest } from '@/shared/api/client'
import type { CardTemplateItem, DeckCardTypesResponse, NoteTypeTemplatesResponse } from '../model/types'

const enc = encodeURIComponent

export function fetchNoteTypeTemplates(noteTypeId: string, signal?: AbortSignal) {
  return apiRequest<NoteTypeTemplatesResponse>(`/api/note-types/${enc(noteTypeId)}/templates`, { signal })
}

export function fetchDeckCardTypes(deckId: number | string, signal?: AbortSignal) {
  return apiRequest<DeckCardTypesResponse>(
    `/api/study/scopes/deck/${enc(String(deckId))}/compositions?include_counts=1`,
    { signal },
  )
}

export function createNoteTypeTemplate(
  noteTypeId: string,
  body: { name?: string; front_html?: string; back_html?: string; shared_css?: string },
) {
  return apiJson<CardTemplateItem>(`/api/note-types/${enc(noteTypeId)}/templates`, 'POST', body)
}

export function renameNoteTypeTemplate(noteTypeId: string, templateId: string, name: string) {
  return apiJson<CardTemplateItem>(`/api/note-types/${enc(noteTypeId)}/templates/${enc(templateId)}`, 'PATCH', { name })
}

export function deleteNoteTypeTemplate(noteTypeId: string, templateId: string) {
  return apiJson<{ success: boolean }>(`/api/note-types/${enc(noteTypeId)}/templates/${enc(templateId)}`, 'DELETE')
}
