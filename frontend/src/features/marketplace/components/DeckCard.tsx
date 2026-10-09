import '@/shared/config/i18n'
import type { ParseKeys, TFunction } from 'i18next'
import React from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/card'
import { DeckCardBadges } from './card/DeckCardBadges'
import { DeckCardStats } from './card/DeckCardStats'
import { DeckCardActions } from './card/DeckCardActions'

export type DeckCardItem = {
  id: string
  title?: string
  name?: string
  description?: string | null
  primary_category?: string | null
  rating_avg?: number
  rating_count?: number
  install_count?: number
  card_count?: number
  note_count?: number
  lesson_count?: number
  total_decks?: number
  has_subdecks?: boolean
  price_display?: string
  pricing_mode?: string
  distribution_mode?: string
  requires_access_key?: boolean
  is_installed?: boolean
  installed_deck_id?: number | null
  deck_install_id?: string | null
  install_bucket?: string
  last_sync_status?: string | null
  auto_update_enabled?: boolean
  pending_conflict_count?: number
  update_available?: boolean
  unread_update?: boolean
  available_release?: {
    id: string
    sequence_no: number
    version_label: string
    published_at?: string | null
  } | null
  badges?: string[]
  tags?: string[]
  author?: {
    username?: string
    account_name?: string
  } | null
  has_student_offer?: boolean
  student_offer_mode?: string
  student_discount_percent?: number | null
  student_discount_applied?: boolean
  effective_price_display?: string
}

export function getCategoryBadgeStyle(categoryName: string | null | undefined): string {
  if (!categoryName) return 'bg-muted text-muted-foreground border-border/60'
  const lower = categoryName.toLowerCase()
  if (
    lower.includes('ielts') ||
    lower.includes('toeic') ||
    lower.includes('vstep') ||
    lower.includes('tiếng anh')
  ) {
    return 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20'
  }
  if (lower.includes('topik') || lower.includes('tiếng hàn')) {
    return 'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/20'
  }
  if (
    lower.includes('hsk') ||
    lower.includes('tiếng trung') ||
    lower.includes('tocfl')
  ) {
    return 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/20'
  }
  if (
    lower.includes('aws') ||
    lower.includes('azure') ||
    lower.includes('it') ||
    lower.includes('công nghệ') ||
    lower.includes('code')
  ) {
    return 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20'
  }
  if (lower.includes('n5') || lower.includes('n4')) {
    return 'bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/20'
  }
  if (lower.includes('n3')) {
    return 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20'
  }
  if (
    lower.includes('n2') ||
    lower.includes('n1') ||
    lower.includes('tiếng nhật')
  ) {
    return 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20'
  }
  if (lower.includes('kanji') || lower.includes('hán tự')) {
    return 'bg-primary/10 text-primary border-primary/20'
  }
  if (
    lower.includes('thpt') ||
    lower.includes('y dược') ||
    lower.includes('học thuật')
  ) {
    return 'bg-teal-500/10 text-teal-700 dark:text-teal-400 border-teal-500/20'
  }
  if (
    lower.includes('ngữ pháp') ||
    lower.includes('cloze') ||
    lower.includes('đục lỗ')
  ) {
    return 'bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border-indigo-500/20'
  }
  if (
    lower.includes('hỏi đáp') ||
    lower.includes('q&a') ||
    lower.includes('mẫu chuẩn') ||
    lower.includes('từ vựng')
  ) {
    return 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-400 border-cyan-500/20'
  }
  return 'bg-muted text-muted-foreground border-border/60'
}

export function formatSyncStatus(value: string, t?: TFunction<'marketplace'>): string {
  if (t) {
    const localized = t(`sync_status.${value}` as Extract<ParseKeys<'marketplace'>, `sync_status.${string}`>)
    if (localized && !localized.startsWith('sync_status.')) {
      return localized
    }
  }
  const labels: Record<string, string> = {
    needs_sync: 'Đóng góp cần đồng bộ',
    draft: 'Đóng góp bản nháp',
    has_conflict: 'Có xung đột',
    conflict: 'Có xung đột cần xử lý',
    synced: 'Đã cập nhật',
    detached: 'Đã tách độc lập',
    error: 'Lỗi đồng bộ',
    pending_review: 'Đang chờ duyệt',
    rejected: 'Đóng góp bị từ chối',
    merged: 'Đóng góp đã merge',
  }
  return labels[value] || value.replaceAll('_', ' ')
}

export interface DeckCardProps {
  item: DeckCardItem
  variant?: 'marketplace' | 'installed'
  dataTour?: string
  actionDataTour?: string
  actions?: React.ReactNode
  className?: string
}

export function DeckCard({
  item,
  variant = 'marketplace',
  dataTour,
  actionDataTour,
  actions,
  className = '',
}: DeckCardProps) {
  const { t } = useTranslation('marketplace')

  const itemTitle = item.title || item.name || t('card.no_title')
  const detailUrl = `/marketplace/decks/${item.id}`
  const authorName =
    item.author?.account_name || item.author?.username || t('card.community_author')
  const authorInitial = authorName.charAt(0).toUpperCase()

  const isCourseDeck =
    item.distribution_mode === 'course_key' || Boolean(item.requires_access_key)

  const hasConflict =
    item.last_sync_status === 'conflict' ||
    Boolean(item.pending_conflict_count && item.pending_conflict_count > 0)
  const targetReleaseId = item.available_release?.id || 'conflict'

  return (
    <Card
      data-tour={dataTour}
      className={`group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-md rounded-2xl ${
        hasConflict
          ? 'border-amber-500/50 bg-amber-500/5 ring-1 ring-amber-500/20'
          : ''
      } ${className}`}
    >
      {/* Card Main Info Block */}
      <div className="flex flex-col flex-1 space-y-2.5">
        <DeckCardBadges
          item={item}
          variant={variant}
          isCourseDeck={isCourseDeck}
          hasConflict={hasConflict}
          getCategoryBadgeStyle={getCategoryBadgeStyle}
          formatSyncStatus={(val) => formatSyncStatus(val, t)}
        />

        {/* Title */}
        <h3 className="text-sm sm:text-base font-bold tracking-tight text-foreground line-clamp-1 group-hover:text-primary transition-colors leading-snug">
          <Link
            to={detailUrl}
            className="hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
          >
            {itemTitle}
          </Link>
        </h3>

        {/* Author Row */}
        {item.author?.username ? (
          <Link
            to={`/profile/${item.author.username}`}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors group/author w-fit max-w-full"
          >
            <div className="flex size-4 sm:size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px] ring-1 ring-primary/20 group-hover/author:ring-primary">
              {authorInitial}
            </div>
            <span className="font-medium text-foreground/80 group-hover/author:text-primary truncate">
              {authorName}
            </span>
          </Link>
        ) : (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground truncate">
            <div className="flex size-4 sm:size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px] ring-1 ring-primary/20">
              {authorInitial}
            </div>
            <span className="font-medium text-foreground/80 truncate">
              {authorName}
            </span>
          </div>
        )}

        {/* Description */}
        <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
          {item.description || t('card.no_desc_deck')}
        </p>
      </div>

      {/* Card Bottom Block */}
      <div className="mt-4 pt-3 border-t border-border/60 space-y-3">
        <DeckCardStats item={item} />

        <DeckCardActions
          item={item}
          variant={variant}
          detailUrl={detailUrl}
          isCourseDeck={isCourseDeck}
          hasConflict={hasConflict}
          targetReleaseId={targetReleaseId}
          actionDataTour={actionDataTour}
          actions={actions}
        />
      </div>
    </Card>
  )
}
