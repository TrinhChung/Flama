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

export type BatchMediaItemInput = {
  itemId?: string
  noteId: string
  fieldName: string
  blob: Blob
  filename?: string
}

export type BatchUploadMediaResponseItem = {
  item_id: string
  note_id: string
  field_name: string
  asset_id?: string
  url?: string
  filename?: string
  status: 'success' | 'failed'
  error?: string
  message?: string
}

export type BatchUploadMediaResponse = {
  success: boolean
  success_count: number
  failed_count: number
  items: BatchUploadMediaResponseItem[]
}

export async function uploadNoteMediaBatch(
  items: BatchMediaItemInput[]
): Promise<BatchUploadMediaResponse> {
  if (items.length === 0) {
    return { success: true, success_count: 0, failed_count: 0, items: [] }
  }

  const formData = new FormData()
  const manifest = items.map((item, idx) => {
    const fileKey = `file_${idx}`
    formData.append(fileKey, item.blob, item.filename || `tts_${item.noteId}.wav`)
    return {
      item_id: item.itemId ?? String(idx),
      note_id: item.noteId,
      field_name: item.fieldName,
      file_key: fileKey,
    }
  })

  formData.append('manifest', JSON.stringify(manifest))

  return apiRequest<BatchUploadMediaResponse>('/api/notes/media/batch', {
    method: 'POST',
    body: formData,
  })
}
