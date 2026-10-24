import { apiRequest } from '@/shared/api/client'

type AudioDetail = {
  card: { word: string }
  fields?: Array<{ name: string; field_type?: string }>
  note: { id: string; note_type_name?: string; field_values?: Record<string, unknown> }
  can_upload_media?: boolean
}

type NoteAudioDetail = Omit<AudioDetail, 'card'> & { row: AudioDetail['card'] }

/** Keep the audio workflow's detail shape for both Browse selector contracts. */
export async function fetchBrowseAudioDetail(id: string, targetKind: 'card' | 'note'): Promise<AudioDetail> {
  const path = `/api/browse/${targetKind === 'note' ? 'notes' : 'cards'}/${encodeURIComponent(id)}`
  if (targetKind === 'note') {
    const { row, ...detail } = await apiRequest<NoteAudioDetail>(path)
    return { ...detail, card: row }
  }
  return apiRequest<AudioDetail>(path)
}
