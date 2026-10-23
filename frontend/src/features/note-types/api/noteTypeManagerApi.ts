import { apiJson, apiRequest } from '@/shared/api/client'
import type { NoteTypeItem, NoteTypesResponse } from '../model/managerTypes'

export const noteTypeManagerQueryKey = ['note-types', 'manager-summary'] as const

export function fetchNoteTypeSummaries(signal?: AbortSignal) {
  return apiRequest<NoteTypesResponse>('/api/note-types?summary=1', { signal })
}

export function createNoteType(name: string) {
  return apiJson<NoteTypeItem>('/api/note-types', 'POST', { name })
}
