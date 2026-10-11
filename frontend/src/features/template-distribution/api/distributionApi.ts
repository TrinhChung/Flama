import { apiJson, apiRequest } from '@/shared/api/client'
import type {
  ApplyTemplateUpdateBody,
  PendingUpdateDto,
  PublishReleaseResponse,
  PublishTemplateReleaseBody,
  TemplatePublicationDto,
  TemplateReleasesResponse,
  TemplateSubscriptionDto,
} from '../model/types'

const enc = encodeURIComponent

function generateIdempotencyKey(): string {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `ik_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export const distributionApi = {
  getPublication(templateId: string, signal?: AbortSignal): Promise<TemplatePublicationDto> {
    return apiRequest<TemplatePublicationDto>(`/api/card-templates/${enc(templateId)}/publication`, { signal })
  },

  updatePublicationSettings(
    templateId: string,
    body: { auto_publish_enabled: boolean },
  ): Promise<TemplatePublicationDto> {
    return apiJson<TemplatePublicationDto>(
      `/api/card-templates/${enc(templateId)}/publication`,
      'PATCH',
      body,
    )
  },

  getReleases(
    templateId: string,
    params?: { limit?: number; before_sequence?: number },
    signal?: AbortSignal,
  ): Promise<TemplateReleasesResponse> {
    const sp = new URLSearchParams()
    if (params?.limit !== undefined) sp.append('limit', String(params.limit))
    if (params?.before_sequence !== undefined) sp.append('before_sequence', String(params.before_sequence))
    const qs = sp.toString()
    const url = qs
      ? `/api/card-templates/${enc(templateId)}/releases?${qs}`
      : `/api/card-templates/${enc(templateId)}/releases`
    return apiRequest<TemplateReleasesResponse>(url, { signal })
  },

  publishRelease(
    templateId: string,
    body: PublishTemplateReleaseBody,
    idempotencyKey?: string,
  ): Promise<PublishReleaseResponse> {
    const key = idempotencyKey || generateIdempotencyKey()
    return apiRequest<PublishReleaseResponse>(`/api/card-templates/${enc(templateId)}/releases`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': key,
      },
      body: JSON.stringify(body),
    })
  },

  getSubscription(templateId: string, signal?: AbortSignal): Promise<TemplateSubscriptionDto> {
    return apiRequest<TemplateSubscriptionDto>(`/api/card-templates/${enc(templateId)}/subscription`, { signal })
  },

  updateSubscriptionSettings(
    templateId: string,
    body: { auto_update_enabled: boolean },
  ): Promise<TemplateSubscriptionDto> {
    return apiJson<TemplateSubscriptionDto>(
      `/api/card-templates/${enc(templateId)}/subscription`,
      'PATCH',
      body,
    )
  },

  prepareUpdate(
    templateId: string,
    body: {
      release_id: string
      expected_applied_release_id?: string
      expected_current_version_id?: string
      idempotency_key?: string
    },
  ): Promise<PendingUpdateDto> {
    return apiJson<PendingUpdateDto>(
      `/api/card-templates/${enc(templateId)}/prepare-update`,
      'POST',
      body,
    )
  },

  applyUpdate(templateId: string, body: ApplyTemplateUpdateBody): Promise<TemplateSubscriptionDto> {
    return apiJson<TemplateSubscriptionDto>(
      `/api/card-templates/${enc(templateId)}/apply-update`,
      'POST',
      body,
    )
  },

  resetToUpstream(templateId: string): Promise<TemplateSubscriptionDto> {
    return apiJson<TemplateSubscriptionDto>(
      `/api/card-templates/${enc(templateId)}/reset-to-upstream`,
      'POST',
      {},
    )
  },
}
