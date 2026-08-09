import { apiRequest } from '@/shared/api/client'

export type UploadMediaResponse = {
  asset_id?: string
  field_name?: string
  filename?: string
  url?: string
}

export async function uploadNoteMediaBlob(
  noteId: string,
  fieldName: string,
  blob: Blob,
  filename: string = 'voicevox_tts.wav'
): Promise<UploadMediaResponse> {
  const formData = new FormData()
  formData.append('field_name', fieldName)
  formData.append('file', blob, filename)

  const endpoint = `/api/notes/${encodeURIComponent(noteId)}/media`
  return apiRequest<UploadMediaResponse>(endpoint, {
    method: 'POST',
    body: formData,
  })
}
