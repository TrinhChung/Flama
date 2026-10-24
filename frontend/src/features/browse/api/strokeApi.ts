import { API_BASE_URL } from '@/config/env'
import { apiJson } from '@/shared/api/client'
import type { GenerateStrokesPayload, GenerateStrokesResponse, EstimateBatchStrokesPayload, EstimateBatchStrokesResponse, BatchGenerateStrokesPayload, BatchGenerateStrokesResponse } from '@/entities/stroke'

export const strokeApi = {
  generateStrokes: (body: GenerateStrokesPayload) => apiJson<GenerateStrokesResponse>(`${API_BASE_URL}/strokes/generate`, 'POST', body),
  estimateBatchStrokes: (body: EstimateBatchStrokesPayload) => apiJson<EstimateBatchStrokesResponse>(`${API_BASE_URL}/strokes/estimate`, 'POST', body),
  batchGenerateStrokes: (body: BatchGenerateStrokesPayload) => apiJson<BatchGenerateStrokesResponse>(`${API_BASE_URL}/strokes/batch-generate`, 'POST', body),
}
