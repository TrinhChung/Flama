import type {
  ForgotPasswordPayload,
  LoginPayload,
  RegisterPayload,
  ResetPasswordPayload,
} from '../features/auth/api'

import type {
  CreateDeckForm,
  MoveDeckForm,
  RenameDeckForm,
} from '../features/dashboard/schemas'
import { API_BASE_URL, resolveBackendUrl } from '../config/env'
import type {
  DashboardOverview,
  DashboardPayload,
  DeckNode,
} from '../features/dashboard/types'
import type {
  StatisticsConfig,
  StatisticsFilters,
  TodayFutureStats,
  UserStudyTimeFilters,
  UserStudyTimeResponse,
} from '../features/statistics/types'
import {
  apiJson,
  apiJsonKeepalive,
  apiRequest,
  getBrowserTimezone,
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

type DashboardRow = {
  deck_id: number
  parent_id: number | null
  move_alias: string
  move_token?: string
  parent_move_alias?: string | null
  parent_move_token?: string | null
  label: string
  href?: string
  depth: number
  new_count: number
  learn_count: number
  due_count: number
  note_type_id?: string | null
  children: DashboardRow[]
}

type DashboardResponse = {
  items: DashboardRow[]
  summary: {
    new: number
    learning: number
    due: number
    total_due: number
  }
  admin_mode: boolean
  stats_initial_year: number
}

type StatisticsResponse = {
  decks: Array<{ id: number; name: string; parent_id?: number | null }>
  selected_deck_id: number | null
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

function toDeckNode(row: DashboardRow): DeckNode {
  return {
    id: row.deck_id,
    parent_id: row.parent_id,
    name: row.label,
    depth: row.depth,
    study_url: `/study?deck_id=${row.deck_id}`,
    note_type_id: row.note_type_id ?? null,
    counts: {
      new: row.new_count,
      learning: row.learn_count,
      due: row.due_count,
    },
    move: {
      alias: row.move_alias,
      token: row.move_token ?? '',
      parent_alias: row.parent_move_alias ?? null,
      parent_token: row.parent_move_token ?? null,
    },
    actions: {
      rename: `${API_BASE}/decks/${row.deck_id}`,
      move: `${API_BASE}/decks/${row.deck_id}`,
      delete: `${API_BASE}/decks/${row.deck_id}`,
      reset: `${API_BASE}/decks/${row.deck_id}/progress-reset`,
      share: `/marketplace/decks/publish?deck_id=${row.deck_id}`,
    },
    children: row.children.map(toDeckNode),
  }
}

function toDashboard(payload: DashboardResponse): DashboardPayload {
  return {
    decks: payload.items.map(toDeckNode),
    totals: {
      new: payload.summary.new,
      learning: payload.summary.learning,
      due: payload.summary.due,
    },
    admin_mode: payload.admin_mode,
    stats_initial_year: payload.stats_initial_year,
    actions: {
      create: `${API_BASE}/decks`,
      move: `${API_BASE}/decks`,
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

  async getDashboard(): Promise<DashboardPayload> {
    const payload = await apiRequest<DashboardResponse>(
      `${API_BASE}/dashboard?compact=1`,
      { includeTimezone: false },
    )
    return toDashboard(payload)
  },

  async getDashboardOverview(year: number): Promise<DashboardOverview> {
    const query = new URLSearchParams({ year: String(year) })
    const tz = getBrowserTimezone()
    if (tz) query.set('timezone', tz)
    return apiRequest<DashboardOverview>(
      `${API_BASE}/statistics/overview?${query}`,
      { includeTimezone: false },
    )
  },

  async createDeck(values: CreateDeckForm) {
    return apiJson(`${API_BASE}/decks`, 'POST', {
      name: values.name,
      path: values.deck_path,
      parent_id: values.parent_id || null,
      note_type_id: values.note_type_id || null,
    })
  },

  async renameDeck(deckId: number, values: RenameDeckForm) {
    return apiJson(`${API_BASE}/decks/${deckId}`, 'PATCH', values)
  },

  async moveDeck(deckId: number, values: MoveDeckForm) {
    return apiJson(`${API_BASE}/decks/${deckId}`, 'PATCH', {
      parent_id: values.parent_id || null,
    })
  },

  async deleteDeck(deckId: number, params?: { purge?: boolean }) {
    const suffix = params?.purge ? '?purge=true' : ''
    return apiJson(`${API_BASE}/decks/${deckId}${suffix}`, 'DELETE')
  },

  async resetDeck(deckId: number) {
    return apiJson(`${API_BASE}/decks/${deckId}/progress-reset`, 'POST', {})
  },

  async getStatisticsConfig(): Promise<StatisticsConfig> {
    const payload = await apiRequest<StatisticsResponse>(
      `${API_BASE}/statistics`,
    )
    return {
      decks: payload.decks.map(({ id, name }) => ({ id, name })),
      initial_deck_id: payload.selected_deck_id,
    }
  },

  async getTodayFutureStats(
    filters: StatisticsFilters,
  ): Promise<TodayFutureStats> {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
    const params = new URLSearchParams({
      scope: filters.scope,
      history_range: filters.historyRange,
      future_range: filters.futureRange,
      backlog: String(filters.backlog),
      timezone: tz,
    })
    if (filters.deckId !== null) {
      params.set('deck_id', String(filters.deckId))
    }
    return apiRequest<TodayFutureStats>(
      `${API_BASE}/statistics/today-future?${params.toString()}`,
    )
  },

  async getUserStudyTimeStats(
    filters: UserStudyTimeFilters,
  ): Promise<UserStudyTimeResponse> {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
    const params = new URLSearchParams({
      scope: filters.scope,
      range: filters.range,
      timezone: tz,
    })
    if (filters.deckId !== null) {
      params.set('deck_id', String(filters.deckId))
    }
    if (filters.startDate) {
      params.set('start_date', filters.startDate)
    }
    if (filters.endDate) {
      params.set('end_date', filters.endDate)
    }
    return apiRequest<UserStudyTimeResponse>(
      `${API_BASE}/statistics/study-time?${params.toString()}`,
    )
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

