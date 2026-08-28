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

export async function fetchDeckWorksheetMeta(deckId: number): Promise<DeckWorksheetMeta> {
  return apiRequest<DeckWorksheetMeta>(`/api/decks/${deckId}/worksheets/meta`)
}

export async function generateWorksheetPreview(
  request: WorksheetGenerationRequest,
): Promise<WorksheetPreviewResponse> {
  return apiJson<WorksheetPreviewResponse>('/api/worksheets/preview', 'POST', request)
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
