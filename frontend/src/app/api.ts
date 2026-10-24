import type {
  ForgotPasswordPayload,
  LoginPayload,
  RegisterPayload,
  ResetPasswordPayload,
} from '../features/auth/api'

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

type LoginResponse = SessionResponse & {
  next_url: string
}

type RegisterResponse = {
  created: boolean
  user: Pick<FrontendUser, 'id' | 'email' | 'username'>
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

  async login(payload: LoginPayload) {
    const result = await apiJson<LoginResponse>(
      `${API_BASE}/auth/login`,
      'POST',
      payload,
    )
    const bootstrap = toBootstrap(result)
    if (!bootstrap.user) {
      throw new Error('The server did not create an authenticated session.')
    }
    return {
      user: bootstrap.user,
      redirect_to: result.next_url || '/dashboard',
    }
  },

  async register(payload: RegisterPayload) {
    await apiJson<RegisterResponse>(`${API_BASE}/auth/register`, 'POST', payload)
    return {
      message: 'Đăng ký thành công. Bạn có thể đăng nhập ngay.',
      redirect_to: '/login',
    }
  },

  async forgotPassword(payload: ForgotPasswordPayload) {
    return apiJson<{ success: boolean; message: string }>(
      `${API_BASE}/auth/forgot-password`,
      'POST',
      payload,
    )
  },

  async resetPassword(payload: ResetPasswordPayload) {
    return apiJson<{ success: boolean; message: string }>(
      `${API_BASE}/auth/reset-password`,
      'POST',
      payload,
    )
  },


  async logout() {
    const result = await apiJson<SessionResponse>(
      `${API_BASE}/session`,
      'DELETE',
    )
    toBootstrap(result)
    return { redirect_to: '/' }
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

export type GenerateStrokesPayload = {
  text: string
  locale?: string
  format?: 'html' | 'urls' | 'raw'
  deduplicate?: boolean
  max_characters?: number
}

export type StrokeItem = {
  char: string
  hex: string
  url: string
  available: boolean
}

export type GenerateStrokesResponse = {
  locale: string
  characters: string[]
  items: StrokeItem[]
  output: string
  missing_count: number
  missing_characters: string[]
}

export type EstimateBatchStrokesPayload = {
  source_field: string
  target_field: string
  locale?: string
  deck_id?: number | null
  note_ids?: string[]
  card_ids?: string[]
  overwrite?: boolean
  max_characters?: number
}

export type EstimateBatchStrokesResponse = {
  total_notes: number
  notes_to_update: number
  notes_skipped: number
  unique_characters: number
  cached_characters: number
  new_characters: number
  estimated_seconds: number
  estimated_human: string
  is_heavy_task: boolean
  friendly_summary: string
  has_mixed_note_types?: boolean
  error?: string
  code?: string
  note_types?: string[]
}

export type BatchGenerateStrokesPayload = {
  source_field: string
  target_field: string
  locale?: string
  deck_id?: number | null
  note_ids?: string[]
  card_ids?: string[]
  format?: 'html' | 'urls' | 'raw'
  overwrite?: boolean
  max_characters?: number
}

export type BatchGenerateStrokesResponse = {
  total_processed: number
  updated: number
  skipped: number
  missing_characters: string[]
}

