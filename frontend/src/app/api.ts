import type { GenerateStrokesPayload, GenerateStrokesResponse, EstimateBatchStrokesPayload, EstimateBatchStrokesResponse, BatchGenerateStrokesPayload, BatchGenerateStrokesResponse } from '@/entities/stroke'
import { API_BASE_URL, resolveBackendUrl } from '../config/env'
import {
  apiJson,
  apiJsonKeepalive,
  apiRequest,
  setCsrfToken,
} from '../shared/api/client'
import type {
  FrontendBootstrap,
  FrontendLinks,
  FrontendUser,
} from '../shared/types/api'

const API_BASE = API_BASE_URL

function apiUrl(path: string) {
  if (/^https?:\/\//i.test(path)) {
    return path
  }
  if (path.startsWith('/api/')) {
    return resolveBackendUrl(path)
  }
  return `${API_BASE}/${path.replace(/^\/+/, '')}`
}

const links: FrontendLinks = {
  react_root: '/',
  dashboard: '/dashboard',
  statistics: '/statistics',
  legacy_dashboard: '/dashboard',
  browse: '/browse',
  study: '/study',
  note_types: '/note-types',
  installed_decks: '/installed-decks',
  flashcard_import: '/sync',
  shared_decks: '/marketplace/decks',
  shared_note_types: '/marketplace/note-types',
  orders: '/orders',
  support: '/support',
  terms: '/terms',
  privacy: '/privacy',
  cookies: '/cookies',
  admin_analytics: '/admin/analytics',
  admin_users: '/admin/users',
  admin_fees: '/admin/fees',
  admin_payments: '/admin/payments',
  admin_tts: '/admin/tts',
  admin_mcp_tokens: '/admin/mcp-tokens',
}

type SessionResponse = {
  authenticated: boolean
  user: FrontendUser | null
  csrf_token: string
}

function toBootstrap(payload: SessionResponse): FrontendBootstrap {
  const isAdmin = Boolean(payload.user?.is_admin)
  setCsrfToken(payload.csrf_token)
  return {
    api_version: 'v1',
    csrf_token: payload.csrf_token,
    user: payload.user,
    messages: [],
    support_contact_email: '',
    links: {
      ...links,
      admin_analytics: isAdmin ? links.admin_analytics : null,
      admin_users: isAdmin ? links.admin_users : null,
      admin_payments: isAdmin ? links.admin_payments : null,
      admin_tts: isAdmin ? links.admin_tts : null,
      admin_mcp_tokens: isAdmin ? links.admin_mcp_tokens : null,
    },
  }
}


export const appApi = {
  async get<T>(
    path: string,
    params?: Record<string, string | number | boolean | null | undefined>,
  ): Promise<T> {
    const search = new URLSearchParams()
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        search.set(key, String(value))
      }
    })
    const suffix = search.size ? `?${search.toString()}` : ''
    return apiRequest<T>(`${apiUrl(path)}${suffix}`)
  },

  async mutate<T>(
    path: string,
    method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    body?: unknown,
  ): Promise<T> {
    return apiJson<T>(apiUrl(path), method, body)
  },

  async mutateKeepalive<T>(
    path: string,
    method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    body?: unknown,
  ): Promise<T> {
    return apiJsonKeepalive<T>(apiUrl(path), method, body)
  },

  async mutateFormData<T>(
    path: string,
    method: 'POST' | 'PUT' | 'PATCH',
    formData: FormData,
  ): Promise<T> {
    return apiRequest<T>(apiUrl(path), {
      method,
      body: formData,
    })
  },

  async getBootstrap(): Promise<FrontendBootstrap> {
    const payload = await apiRequest<SessionResponse>(`${API_BASE}/session`, { includeTimezone: false })
    return toBootstrap(payload)
  },

  async generateStrokes(payload: GenerateStrokesPayload): Promise<GenerateStrokesResponse> {
    return apiJson<GenerateStrokesResponse>(`${API_BASE}/strokes/generate`, 'POST', payload)
  },

  async estimateBatchStrokes(payload: EstimateBatchStrokesPayload): Promise<EstimateBatchStrokesResponse> {
    return apiJson<EstimateBatchStrokesResponse>(`${API_BASE}/strokes/estimate`, 'POST', payload)
  },

  async batchGenerateStrokes(payload: BatchGenerateStrokesPayload): Promise<BatchGenerateStrokesResponse> {
    return apiJson<BatchGenerateStrokesResponse>(`${API_BASE}/strokes/batch-generate`, 'POST', payload)
  },
}

export type { GenerateStrokesPayload, GenerateStrokesResponse, StrokeItem, EstimateBatchStrokesPayload, EstimateBatchStrokesResponse, BatchGenerateStrokesPayload, BatchGenerateStrokesResponse } from '@/entities/stroke'
