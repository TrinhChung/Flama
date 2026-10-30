import { apiJson, apiRequest } from '@/shared/api/client'
import type { BaseOverrideComparisonPage } from '../model/baseComparisonTypes'

export function getBaseOverrideComparison(installId: string, cursor: string | null, signal?: AbortSignal) {
  const params = new URLSearchParams({ limit: '50' })
  if (cursor) params.set('cursor', cursor)
  return apiRequest<BaseOverrideComparisonPage>(
    `/api/marketplace/installations/${encodeURIComponent(installId)}/base-overrides?${params}`, { signal },
  )
}

export function resetBaseOverride(installId: string, overrideId: string, expectedOverlayRevision: number) {
  return apiJson<{ overlay_revision: number }>(
    `/api/marketplace/installations/${encodeURIComponent(installId)}/overrides/${encodeURIComponent(overrideId)}`,
    'DELETE', { expected_overlay_revision: expectedOverlayRevision },
  )
}

export function keepBaseOverride(installId: string, overrideId: string, expectedOverlayRevision: number, expectedBaseHash: string) {
  return apiJson<{ overlay_revision: number }>(
    `/api/marketplace/installations/${encodeURIComponent(installId)}/overrides/${encodeURIComponent(overrideId)}/keep`,
    'POST', { expected_overlay_revision: expectedOverlayRevision, expected_base_hash: expectedBaseHash },
  )
}
