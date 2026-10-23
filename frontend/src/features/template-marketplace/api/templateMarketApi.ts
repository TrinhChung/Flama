import { apiJson, apiRequest } from '@/shared/api/client'
import type {
  MarketTemplateCatalog,
  MarketTemplateDetail,
  MarketTemplateInstallResult,
  MarketTemplateParams,
  MarketTemplatePreview,
  TemplateListing,
  TemplateListingBody,
} from '../model/types'

const enc = encodeURIComponent

export const templateMarketQueryKeys = {
  all: ['template-market'] as const,
  catalog: (params: MarketTemplateParams) =>
    ['template-market', 'catalog', params.q ?? '', params.category ?? '', params.pricing_mode ?? 'all', params.sort ?? 'newest'] as const,
  detail: (id: string) => ['template-market', 'detail', id] as const,
  preview: (id: string) => ['template-market', 'preview', id] as const,
  listing: (id: string) => ['template-market', 'listing', id] as const,
}

export function fetchMarketTemplates(params: MarketTemplateParams = {}, signal?: AbortSignal): Promise<MarketTemplateCatalog> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.append(key, String(value))
  }
  const query = search.toString()
  return apiRequest<MarketTemplateCatalog>(`/api/marketplace/templates${query ? `?${query}` : ''}`, { signal })
}

export function fetchMarketTemplate(id: string, signal?: AbortSignal): Promise<MarketTemplateDetail> {
  return apiRequest<MarketTemplateDetail>(`/api/marketplace/templates/${enc(id)}`, { signal })
}

export function previewMarketTemplate(id: string): Promise<MarketTemplatePreview> {
  return apiJson<MarketTemplatePreview>(`/api/marketplace/templates/${enc(id)}/preview`, 'POST', {})
}

export function installMarketTemplate(id: string): Promise<MarketTemplateInstallResult> {
  return apiJson<MarketTemplateInstallResult>(`/api/marketplace/templates/${enc(id)}/install`, 'POST', {})
}

export function fetchTemplateListing(id: string, signal?: AbortSignal): Promise<TemplateListing> {
  return apiRequest<TemplateListing>(`/api/card-templates/${enc(id)}/marketplace`, { signal })
}

export function updateTemplateListing(id: string, body: TemplateListingBody): Promise<TemplateListing> {
  return apiJson<TemplateListing>(`/api/card-templates/${enc(id)}/marketplace`, 'PUT', body)
}
