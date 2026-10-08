import {
  Bug,
  CheckCircle2,
  Clock,
  Lightbulb,
  MessageSquare,
  Palette,
  RefreshCw,
  XCircle,
} from 'lucide-react'
import type { FeedbackCategory } from '../types'

export const ROUTE_KEY_MAP: Record<string, string> = {
  '/dashboard': 'screens.dashboard',
  '/statistics': 'screens.statistics',
  '/browse': 'screens.browse',
  '/study': 'screens.study',
  '/note-types': 'screens.note_types',
  '/installed-decks': 'screens.installed_decks',
  '/import': 'screens.import',
  '/marketplace/decks/publish': 'screens.marketplace_decks_publish',
  '/marketplace/decks': 'screens.marketplace_decks',
  '/marketplace/note-types/publish': 'screens.marketplace_note_types_publish',
  '/marketplace/note-types': 'screens.marketplace_note_types',
  '/orders': 'screens.orders',
  '/settings/yomitan': 'screens.settings_yomitan',
  '/settings/mcp-tokens': 'screens.settings_mcp_tokens',
  '/feedback': 'screens.feedback',
  '/tickets': 'screens.tickets',
  '/admin/users': 'screens.admin_users',
  '/admin/permissions': 'screens.admin_permissions',
  '/admin/payments': 'screens.admin_payments',
  '/admin/tts': 'screens.admin_tts',
  '/admin/image-library': 'screens.admin_image_library',
  '/admin/support': 'screens.admin_support',
}

export const ROUTE_NAME_MAP: Record<string, string> = {
  '/dashboard': 'Trang chủ / Tổng quan',
  '/statistics': 'Thống kê học tập',
  '/browse': 'Duyệt từ vựng & Thẻ ghi nhớ',
  '/study': 'Màn hình Học Flashcard',
  '/note-types': 'Quản lý Loại thẻ',
  '/installed-decks': 'Bộ thẻ đã cài',
  '/import': 'Import thẻ',
  '/marketplace/decks/publish': 'Đăng bộ thẻ',
  '/marketplace/decks': 'Kho bộ thẻ (Marketplace)',
  '/marketplace/note-types/publish': 'Đăng loại thẻ',
  '/marketplace/note-types': 'Kho loại thẻ',
  '/orders': 'Danh sách đơn hàng',
  '/settings/yomitan': 'Cài đặt Kết nối Yomitan',
  '/settings/mcp-tokens': 'MCP Access Tokens',
  '/feedback': 'Góp ý & Báo lỗi',
  '/tickets': 'Danh sách Ticket hỗ trợ',
  '/admin/users': 'Admin - Quản lý người dùng',
  '/admin/permissions': 'Admin - Phân quyền',
  '/admin/payments': 'Admin - Quản lý thanh toán',
  '/admin/tts': 'Admin - TTS Provider',
  '/admin/image-library': 'Admin - Thư viện ảnh',
  '/admin/support': 'Admin - Cấu hình Ủng hộ',
}

export const COMMON_SCREEN_PRESETS = [
  { label: 'Học Flashcard', url: '/study' },
  { label: 'Duyệt từ vựng', url: '/browse' },
  { label: 'Quản lý loại thẻ', url: '/note-types' },
  { label: 'Marketplace', url: '/marketplace/decks' },
  { label: 'Trang chủ', url: '/dashboard' },
]

export function getCommonScreenPresets(t?: (key: any, fallback?: any) => string) {
  if (!t) return COMMON_SCREEN_PRESETS
  return [
    { label: t('feedback.presets.study', 'Học Flashcard'), url: '/study' },
    { label: t('feedback.presets.browse', 'Duyệt từ vựng'), url: '/browse' },
    { label: t('feedback.presets.note_types', 'Quản lý loại thẻ'), url: '/note-types' },
    { label: t('feedback.presets.marketplace', 'Marketplace'), url: '/marketplace/decks' },
    { label: t('feedback.presets.dashboard', 'Trang chủ'), url: '/dashboard' },
  ]
}

export function resolveScreenName(
  urlInput: string,
  fallbackDefault?: string,
  t?: (key: any, fallback?: any) => string
): string {
  const trimmed = urlInput.trim()
  if (!trimmed) {
    return (
      fallbackDefault ||
      (t
        ? t('feedback.unrecognized_screen', '(Vui lòng nhập URL để tự động nhận diện)')
        : '(Vui lòng nhập URL để tự động nhận diện)')
    )
  }

  let pathname = trimmed
  try {
    if (trimmed.includes('://')) {
      pathname = new URL(trimmed).pathname
    } else {
      pathname = trimmed.split('?')[0].split('#')[0]
    }
  } catch {
    pathname = trimmed
  }

  const lowerPath = pathname.toLowerCase()
  for (const [route, title] of Object.entries(ROUTE_NAME_MAP)) {
    if (lowerPath === route.toLowerCase() || lowerPath.startsWith(route.toLowerCase())) {
      const key = ROUTE_KEY_MAP[route]
      if (t && key) {
        return t(`feedback.${key}`, title)
      }
      return title
    }
  }

  const segments = pathname.replace(/^\/+|\/+$/g, '').split('/')
  if (!segments[0]) {
    return t
      ? t('feedback.screens.dashboard_default', 'Trang chủ (Dashboard)')
      : 'Trang chủ (Dashboard)'
  }

  return segments
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(' > ')
}

export function formatRelativeTime(
  isoString: string,
  t: (key: any, options?: any) => string,
  locale = 'vi-VN'
): string {
  try {
    const date = new Date(isoString)
    const now = new Date()
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000)

    if (diffSec < 60) return t('relative_time.just_now')
    if (diffSec < 3600) return t('relative_time.minutes_ago', { count: Math.floor(diffSec / 60) })
    if (diffSec < 86400) return t('relative_time.hours_ago', { count: Math.floor(diffSec / 3600) })
    if (diffSec < 604800) return t('relative_time.days_ago', { count: Math.floor(diffSec / 86400) })
    return date.toLocaleDateString(locale)
  } catch {
    return isoString
  }
}

export function getStatusMap(t: (key: any) => string): Record<string, { label: string; badge: string; icon: any }> {
  return {
    open: {
      label: t('status.open'),
      badge: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-300/40',
      icon: Clock,
    },
    in_progress: {
      label: t('status.in_progress'),
      badge: 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border border-blue-300/40',
      icon: RefreshCw,
    },
    resolved: {
      label: t('status.resolved'),
      badge: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-300/40',
      icon: CheckCircle2,
    },
    rejected: {
      label: t('status.rejected'),
      badge: 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border border-rose-300/40',
      icon: XCircle,
    },
    closed: {
      label: t('status.closed'),
      badge: 'bg-slate-500/15 text-slate-700 dark:text-slate-400 border border-slate-300/40',
      icon: XCircle,
    },
  }
}

export function getCategories(t: (key: any) => string): {
  key: FeedbackCategory
  title: string
  subtitle: string
  icon: any
  color: string
  activeBorder: string
  activeBg: string
  placeholderTitle: string
  placeholderDesc: string
}[] {
  return [
    {
      key: 'bug',
      title: t('category.bug.title'),
      subtitle: t('category.bug.subtitle'),
      icon: Bug,
      color: 'text-rose-500',
      activeBorder: 'border-rose-500/80 ring-1 ring-rose-500/40',
      activeBg: 'bg-rose-500/10 text-foreground',
      placeholderTitle: t('category.bug.placeholder_title'),
      placeholderDesc: t('category.bug.placeholder_desc'),
    },
    {
      key: 'feature',
      title: t('category.feature.title'),
      subtitle: t('category.feature.subtitle'),
      icon: Lightbulb,
      color: 'text-amber-500',
      activeBorder: 'border-amber-500/80 ring-1 ring-amber-500/40',
      activeBg: 'bg-amber-500/10 text-foreground',
      placeholderTitle: t('category.feature.placeholder_title'),
      placeholderDesc: t('category.feature.placeholder_desc'),
    },
    {
      key: 'ui',
      title: t('category.ui.title'),
      subtitle: t('category.ui.subtitle'),
      icon: Palette,
      color: 'text-purple-500',
      activeBorder: 'border-purple-500/80 ring-1 ring-purple-500/40',
      activeBg: 'bg-purple-500/10 text-foreground',
      placeholderTitle: t('category.ui.placeholder_title'),
      placeholderDesc: t('category.ui.placeholder_desc'),
    },
    {
      key: 'other',
      title: t('category.other.title'),
      subtitle: t('category.other.subtitle'),
      icon: MessageSquare,
      color: 'text-blue-500',
      activeBorder: 'border-blue-500/80 ring-1 ring-blue-500/40',
      activeBg: 'bg-blue-500/10 text-foreground',
      placeholderTitle: t('category.other.placeholder_title'),
      placeholderDesc: t('category.other.placeholder_desc'),
    },
  ]
}
