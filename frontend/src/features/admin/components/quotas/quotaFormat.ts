import { Bot, ImageUp, Plug, type LucideIcon } from 'lucide-react'
import {
  UNLIMITED_QUOTA,
  type QuotaKind,
  type QuotaLimitSource,
  type QuotaPeriod,
  type QuotaUnit,
  type QuotaUser,
} from '../../types/quotas'

export const QUOTA_KINDS: QuotaKind[] = ['api', 'mcp', 'media']
export const QUOTA_PERIODS: QuotaPeriod[] = ['day', 'month', 'year']

export const QUOTA_KIND_META: Record<QuotaKind, { label: string; short: string; description: string; icon: LucideIcon }> = {
  api: {
    label: 'API (Flama Connect)',
    short: 'API',
    description: 'Request dùng token qua Flama Connect: Yomitan, AnkiConnect, asbplayer…',
    icon: Plug,
  },
  mcp: {
    label: 'MCP (trợ lý AI)',
    short: 'MCP',
    description: 'Mỗi lệnh tools/call tới tool riêng tư. initialize, tools/list và tool công khai không bị tính.',
    icon: Bot,
  },
  media: {
    label: 'Upload ảnh & audio',
    short: 'Upload',
    description: 'Tổng dung lượng file tải lên hoặc crawl về và được lưu trên máy chủ (MB).',
    icon: ImageUp,
  },
}

export const QUOTA_PERIOD_LABELS: Record<QuotaPeriod, string> = {
  day: 'ngày',
  month: 'tháng',
  year: 'năm',
}

export const QUOTA_STATS_PERIOD_LABELS: Record<QuotaPeriod, string> = {
  day: 'Hôm nay',
  month: 'Tháng này',
  year: 'Năm nay',
}

export const QUOTA_SOURCE_LABELS: Record<QuotaLimitSource, string> = {
  admin: 'Admin',
  override: 'Quota riêng',
  role: 'Theo vai trò',
}

export function isUnlimited(limit: number): boolean {
  return limit <= UNLIMITED_QUOTA
}

export function formatQuotaAmount(value: number, unit: QuotaUnit): string {
  const amount = value.toLocaleString('vi-VN', { maximumFractionDigits: unit === 'MB' ? 2 : 0 })
  return unit === 'MB' ? `${amount} MB` : `${amount} request`
}

export function formatQuotaLimit(limit: number, unit: QuotaUnit, period?: QuotaPeriod): string {
  if (isUnlimited(limit)) return 'Không giới hạn'
  const amount = formatQuotaAmount(limit, unit)
  return period ? `${amount} / ${QUOTA_PERIOD_LABELS[period]}` : amount
}

/** Share of the limit already used, capped at 100; null when unlimited. */
export function quotaUsagePercent(used: number, limit: number): number | null {
  if (isUnlimited(limit)) return null
  if (limit === 0) return used > 0 ? 100 : 0
  return Math.min(100, Math.round((used / limit) * 100))
}

export function formatLocalDate(isoDate: string | null): string {
  if (!isoDate) return 'Không thời hạn'
  const [year, month, day] = isoDate.split('-')
  return `${day}/${month}/${year}`
}

export function quotaUserLabel(user: QuotaUser | undefined): string {
  if (!user) return '—'
  return user.display_name || user.username
}
