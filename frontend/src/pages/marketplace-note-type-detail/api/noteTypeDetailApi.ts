import { apiJson, apiRequest } from '@/shared/api/client'
import type { SharedNoteTypeDetail, PreviewResponse, InstallResult } from '../model/types'
const detailPath = (id: string) => `/api/marketplace/note-types/${encodeURIComponent(id)}`
export const noteTypeDetailApi = {
  detail: (id: string) => apiRequest<SharedNoteTypeDetail>(detailPath(id)),
  preview: (id: string, templateId: string, applicationId?: string | null) => applicationId
    ? apiJson<PreviewResponse>(`${detailPath(id)}/templates/${encodeURIComponent(templateId)}/preview`, 'POST', { application_id: applicationId })
    : apiJson<PreviewResponse>(`${detailPath(id)}/templates/${encodeURIComponent(templateId)}/preview`, 'POST'),
  install: (id: string) => apiJson<InstallResult>(`${detailPath(id)}/install`, 'POST'),
  installTemplate: (id: string, templateId: string) => apiJson<InstallResult>(`${detailPath(id)}/templates/${encodeURIComponent(templateId)}/install`, 'POST'),
  save: (id: string, currentlySaved: boolean) => apiJson(`${detailPath(id)}/save`, currentlySaved ? 'DELETE' : 'POST'),
  rate: (id: string, body: { rating: number; comment?: string }) => apiJson(`${detailPath(id)}/rate`, 'POST', body),
  status: (id: string, body: { publish_status: 'private' | 'published' }) => apiJson(`${detailPath(id)}/publish`, 'POST', body),
  publishOptions: (id: string) => apiRequest<{ templates: { is_owned: boolean; requires_publication: boolean }[] }>(`${detailPath(id)}/publish-options`),
}
