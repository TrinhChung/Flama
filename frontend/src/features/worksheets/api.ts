import { apiJson, apiRequest } from '@/shared/api/client'
import type {
  DeckWorksheetMeta,
  WorksheetGenerationRequest,
  WorksheetPreviewResponse,
  WorksheetTemplate,
} from './types'

export async function fetchWorksheetTemplates(): Promise<WorksheetTemplate[]> {
  const data = await apiRequest<{ templates: WorksheetTemplate[] }>('/api/worksheets/templates')
  return data.templates
}

export async function fetchWorksheetMeta(deckId?: number | null): Promise<DeckWorksheetMeta> {
  if (deckId && deckId > 0) {
    return apiRequest<DeckWorksheetMeta>(`/api/decks/${deckId}/worksheets/meta`)
  }
  return apiRequest<DeckWorksheetMeta>('/api/worksheets/meta')
}

export async function fetchDeckWorksheetMeta(deckId?: number | null): Promise<DeckWorksheetMeta> {
  return fetchWorksheetMeta(deckId)
}

export async function generateWorksheetPreview(
  request: WorksheetGenerationRequest & { signal?: AbortSignal },
  optionalSignal?: AbortSignal,
): Promise<WorksheetPreviewResponse> {
  const { signal: requestSignal, ...payload } = request
  const activeSignal = optionalSignal || requestSignal
  return activeSignal
    ? apiJson<WorksheetPreviewResponse>('/api/worksheets/preview', 'POST', payload, { signal: activeSignal })
    : apiJson<WorksheetPreviewResponse>('/api/worksheets/preview', 'POST', payload)
}

export async function renderWorksheetHtml(
  request: WorksheetGenerationRequest | WorksheetPreviewResponse,
): Promise<string> {
  const data = await apiJson<{ html: string }>(
    '/api/worksheets/render-html?format=json',
    'POST',
    request,
  )
  return data?.html || ''
}
