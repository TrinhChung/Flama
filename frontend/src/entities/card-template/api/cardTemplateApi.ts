import { apiJson, apiRequest } from '@/shared/api/client'
import type {
  CardTemplateItem,
  DeckCardTypesResponse,
  NoteTypeTemplatesResponse,
  TemplateApplication,
  TemplateApplicationPatch,
  TemplateApplicationsResponse,
  TemplateAttachmentBody,
  TemplateLibraryDetail,
  TemplateLibraryParams,
  TemplateLibraryPreview,
  TemplateLibraryResponse,
  TemplateLibraryTemplate,
  TemplatePreviewBody,
  TemplateUpdateResponse,
  StudyTemplateInputsResponse,
  StudyTemplatePreset,
  StudyTemplatePresetWrite,
  TemplateVersionDetail,
  TemplateVersionList,
  TemplateWriteBody,
} from '../model/types'

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

export function fetchTemplateVersions(templateId: string, signal?: AbortSignal): Promise<TemplateVersionList> {
  return apiRequest<TemplateVersionList>(`/api/card-templates/${enc(templateId)}/versions`, { signal })
}

export function fetchTemplateVersion(
  templateId: string,
  versionId: string,
  signal?: AbortSignal,
): Promise<TemplateVersionDetail> {
  return apiRequest<TemplateVersionDetail>(
    `/api/card-templates/${enc(templateId)}/versions/${enc(versionId)}`,
    { signal },
  )
}

export function restoreTemplateVersion(
  templateId: string,
  versionId: string,
  changeNote?: string,
): Promise<CardTemplateItem> {
  return apiJson<CardTemplateItem>(
    `/api/card-templates/${enc(templateId)}/versions/${enc(versionId)}/restore`,
    'POST',
    changeNote ? { change_note: changeNote } : {},
  )
}

export function fetchTemplateLibrary(
  params: TemplateLibraryParams = {},
  signal?: AbortSignal,
): Promise<TemplateLibraryResponse> {
  const searchParams = new URLSearchParams()
  if (params.q !== undefined && params.q !== '') {
    searchParams.append('q', params.q)
  }
  if (params.group !== undefined && (params.group as string) !== '') {
    searchParams.append('group', params.group)
  }
  if (params.category !== undefined && params.category !== '') {
    searchParams.append('category', params.category)
  }
  if (params.include_archived === true) {
    searchParams.append('include_archived', 'true')
  }
  if (params.compact === true) searchParams.append('compact', '1')
  if (params.page !== undefined) searchParams.append('page', String(params.page))
  if (params.page_size !== undefined) searchParams.append('page_size', String(params.page_size))
  const qs = searchParams.toString()
  const url = qs ? `/api/card-templates?${qs}` : '/api/card-templates'
  return apiRequest<TemplateLibraryResponse>(url, { signal })
}

export function fetchLibraryTemplate(id: string, signal?: AbortSignal): Promise<TemplateLibraryDetail> {
  return apiRequest<TemplateLibraryDetail>(`/api/card-templates/${enc(id)}`, { signal })
}

export function createLibraryTemplate(
  body: TemplateWriteBody & { name: string },
): Promise<TemplateLibraryTemplate> {
  return apiJson<TemplateLibraryTemplate>('/api/card-templates', 'POST', body)
}

export function updateLibraryTemplate(
  id: string,
  body: TemplateWriteBody,
): Promise<TemplateUpdateResponse> {
  return apiJson<TemplateUpdateResponse>(`/api/card-templates/${enc(id)}`, 'PATCH', body)
}

export function previewLibraryTemplate(
  id: string,
  body: TemplatePreviewBody,
  signal?: AbortSignal,
): Promise<TemplateLibraryPreview> {
  return apiRequest<TemplateLibraryPreview>(`/api/card-templates/${enc(id)}/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

export function archiveLibraryTemplate(
  id: string,
  archived: boolean,
): Promise<TemplateLibraryTemplate> {
  return apiJson<TemplateLibraryTemplate>(`/api/card-templates/${enc(id)}/archive`, 'PATCH', {
    archived,
  })
}

export function duplicateLibraryTemplate(
  id: string,
  body: { name?: string } = {},
): Promise<TemplateLibraryTemplate> {
  return apiJson<TemplateLibraryTemplate>(`/api/card-templates/${enc(id)}/duplicate`, 'POST', body)
}

export function fetchTemplateApplications(
  noteTypeId: string,
  includeRetired = false,
  signal?: AbortSignal,
): Promise<TemplateApplicationsResponse> {
  const path = `/api/note-types/${enc(noteTypeId)}/template-applications`
  const url = includeRetired ? `${path}?include_retired=true` : path
  return apiRequest<TemplateApplicationsResponse>(url, { signal })
}

export function attachLibraryTemplate(
  noteTypeId: string,
  body: TemplateAttachmentBody,
): Promise<TemplateApplication> {
  return apiJson<TemplateApplication>(
    `/api/note-types/${enc(noteTypeId)}/template-applications`,
    'POST',
    body,
  )
}

export function updateTemplateApplication(
  noteTypeId: string,
  applicationId: string,
  body: TemplateApplicationPatch,
): Promise<TemplateApplication> {
  return apiJson<TemplateApplication>(
    `/api/note-types/${enc(noteTypeId)}/template-applications/${enc(applicationId)}`,
    'PATCH',
    body,
  )
}

export function retireTemplateApplication(
  noteTypeId: string,
  applicationId: string,
): Promise<TemplateApplication> {
  return apiJson<TemplateApplication>(
    `/api/note-types/${enc(noteTypeId)}/template-applications/${enc(applicationId)}`,
    'DELETE',
  )
}

export function fetchStudyTemplateInputs(
  deckId: number | string,
  signal?: AbortSignal,
): Promise<StudyTemplateInputsResponse> {
  return apiRequest<StudyTemplateInputsResponse>(
    `/api/study/scopes/deck/${enc(String(deckId))}/compositions?include_template_inputs=1&include_counts=1`,
    { signal },
  )
}

export function fetchStudyTemplatePreset(
  deckId: number | string,
  signal?: AbortSignal,
): Promise<StudyTemplatePreset> {
  return apiRequest<StudyTemplatePreset>(
    `/api/decks/${enc(String(deckId))}/study-template-preset`,
    { signal },
  )
}

export function saveStudyTemplatePreset(
  deckId: number | string,
  payload: StudyTemplatePresetWrite,
): Promise<StudyTemplatePreset> {
  return apiJson<StudyTemplatePreset>(
    `/api/decks/${enc(String(deckId))}/study-template-preset`,
    'PUT',
    payload,
  )
}
