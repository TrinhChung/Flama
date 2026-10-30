import { apiJson, apiRequest } from '@/shared/api/client'
import type { AutoPublishStatus } from '../model/types'

export function getAutoPublishStatus(itemId: string, signal?: AbortSignal) {
  return apiRequest<AutoPublishStatus>(
    `/api/marketplace/decks/${encodeURIComponent(itemId)}/auto-publish`, { signal },
  )
}

export function updateAutoPublishSetting(itemId: string, enabled: boolean) {
  return apiJson<AutoPublishStatus>(
    `/api/marketplace/decks/${encodeURIComponent(itemId)}/auto-publish`,
    'POST', { auto_publish_enabled: enabled },
  )
}
