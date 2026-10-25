export type QuotaKind = 'api' | 'mcp' | 'media'
export type QuotaPeriod = 'day' | 'month' | 'year'
export type QuotaUnit = 'requests' | 'MB'
export type QuotaLimitSource = 'admin' | 'override' | 'role'

/** -1 means unlimited for every limit value. */
export const UNLIMITED_QUOTA = -1

export type QuotaPolicy = {
  kind: QuotaKind
  unit: QuotaUnit
  enforce: boolean
  period: QuotaPeriod
  role_limits: Record<string, number>
  is_default: boolean
  updated_at: string | null
  updated_by_user_id: number | null
}

export type QuotaRole = {
  id: number
  code: string
  name: string
  user_count: number
}

export type QuotaUser = {
  id: number
  username: string
  display_name?: string
  account_name?: string
  email?: string
  role_code?: string
  role_name?: string | null
  is_admin?: boolean
  is_disabled?: boolean
  avatar_url?: string | null
  missing?: boolean
}

export type QuotaEffective = {
  limit_value: number
  period: QuotaPeriod
  enforce: boolean
  source: QuotaLimitSource
  expires_on: string | null
}

export type QuotaRankingRow = {
  user: QuotaUser
  used: number
  effective?: QuotaEffective
}

export type QuotaUsage = {
  period: QuotaPeriod
  period_token: string
  reset_epoch: number
  total: number
  top: QuotaRankingRow[]
  over: QuotaRankingRow[]
}

export type QuotaOverride = {
  user_id: number
  kind: QuotaKind
  unit: QuotaUnit
  limit_value: number
  period: QuotaPeriod | null
  effective_period: QuotaPeriod
  expires_at: string | null
  expires_on: string | null
  is_active: boolean
  note: string
  updated_by_user_id: number | null
  updated_at: string | null
  used?: number
  user?: QuotaUser
}

export type QuotaOverview = {
  settings: {
    metering_enabled: boolean
    backend: 'redis' | 'local'
    timezone: string
    cache_ttl_seconds: number
    stats_period: QuotaPeriod
  }
  roles: QuotaRole[]
  policies: QuotaPolicy[]
  usage: Record<QuotaKind, QuotaUsage>
  overrides: QuotaOverride[]
}

export type QuotaUserKindDetail = {
  kind: QuotaKind
  unit: QuotaUnit
  effective: QuotaEffective
  role_limit: number
  override: QuotaOverride | null
  usage: Record<QuotaPeriod, number>
}

export type QuotaUserDetail = {
  user: QuotaUser
  quotas: QuotaUserKindDetail[]
}

export type QuotaPolicyPayload = {
  enforce?: boolean
  period?: QuotaPeriod
  role_limits?: Record<string, number>
}

export type QuotaOverridePayload = {
  limit_value: number
  period: QuotaPeriod | null
  expires_on: string | null
  note: string
}
