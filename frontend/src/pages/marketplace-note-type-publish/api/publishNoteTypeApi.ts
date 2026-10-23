import { apiJson, apiRequest } from '@/shared/api/client'
import type { TemplateListingDraft } from '@/entities/card-template'

export type SimpleNoteType = { id: string; name: string; field_count?: number; publish_status?: string; is_marketplace_install?: boolean }
export type PublishTemplateOption = TemplateListingDraft & {
  template_id: string
  source_template_id: string
  name: string
  author: { id: number; username: string }
  is_owned: boolean
  requires_publication: boolean
  release_id: string | null
  marketplace_status: string
}
export const publishNoteTypeApi = {
  listNoteTypes: () => apiRequest<{ items: SimpleNoteType[] }>('/api/note-types'),
  detail: (id: string) => apiRequest<any>(`/api/note-types/${encodeURIComponent(id)}`),
  options: (id: string, signal?: AbortSignal) => apiRequest<{ note_type_id: string; templates: PublishTemplateOption[] }>(`/api/marketplace/note-types/${encodeURIComponent(id)}/publish-options`, { signal }),
  publish: (id: string, body: unknown) => apiJson(`/api/note-types/${encodeURIComponent(id)}/publish`, 'POST', body),
}
