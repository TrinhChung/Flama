import React from 'react'
import {
  ArrowRight,
  BookOpen,
  CheckCircle,
  Download,
  Eye,
  FileDiff,
  GraduationCap,
  KeyRound,
  Layers,
  RefreshCcw,
  ShieldAlert,
  Star,
  Zap,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

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

export function formatSyncStatus(value: string): string {
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
  const itemTitle = item.title || item.name || 'Bộ thẻ không tên'
  const detailUrl = `/marketplace/decks/${item.id}`
  const authorName =
    item.author?.account_name || item.author?.username || 'Cộng đồng Flama'
  const authorInitial = authorName.charAt(0).toUpperCase()
  const cardCount = item.card_count || item.note_count

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
        {/* Top Badges Row */}
        <div className="flex items-center justify-between gap-1.5 flex-wrap">
          {variant === 'installed' ? (
            <div className="flex items-center gap-1.5">
              <Badge
                variant={
                  item.install_bucket === 'using_now' ? 'default' : 'secondary'
                }
                className="px-2 py-0.5 text-xs font-semibold rounded-md truncate"
              >
                {item.install_bucket === 'using_now'
                  ? 'Đang sử dụng'
                  : item.install_bucket === 'owned'
                    ? 'Deck của bạn'
                    : 'Đã cài'}
              </Badge>
              {item.auto_update_enabled ? (
                <Badge
                  variant="outline"
                  className="px-1.5 py-0 text-[10px] font-semibold border-primary/30 text-primary bg-primary/5"
                >
                  <Zap className="mr-0.5 size-2.5 inline" />
                  Auto
                </Badge>
              ) : null}
            </div>
          ) : (
            <div className="flex items-center gap-1.5 truncate max-w-[65%]">
              <Badge
                variant="outline"
                className={`px-2.5 py-0.5 text-xs font-semibold rounded-md truncate border ${getCategoryBadgeStyle(
                  item.primary_category,
                )}`}
              >
                {item.primary_category || 'Chung'}
              </Badge>
              {isCourseDeck && (
                <Badge
                  variant="outline"
                  className="px-1.5 py-0.5 text-[10px] font-bold border-purple-500/30 text-purple-600 dark:text-purple-400 bg-purple-500/10 flex items-center gap-1"
                >
                  <GraduationCap className="size-2.5" />
                  Khóa học
                </Badge>
              )}
            </div>
          )}

          {/* Right Status / Price Badge */}
          {variant === 'installed' ? (
            hasConflict ? (
              <span className="truncate text-xs font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1">
                <ShieldAlert className="size-3 shrink-0" />
                {item.pending_conflict_count
                  ? `${item.pending_conflict_count} xung đột`
                  : 'Có xung đột'}
              </span>
            ) : item.update_available ? (
              <span className="truncate text-xs font-semibold text-primary">
                Có bản {item.available_release?.version_label || 'mới'}
              </span>
            ) : item.last_sync_status ? (
              <span className="truncate text-xs text-muted-foreground">
                {formatSyncStatus(item.last_sync_status)}
              </span>
            ) : null
          ) : isCourseDeck ? (
            <span className="inline-flex items-center gap-1 rounded-md px-2.5 py-0.5 text-xs font-semibold bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/20">
              <KeyRound className="size-3" />
              Mã khóa học
            </span>
          ) : item.student_discount_applied ? (
            <div className="flex items-center gap-1">
              <span className="text-[11px] text-muted-foreground line-through font-medium">
                {item.price_display}
              </span>
              <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
                <GraduationCap className="size-3 text-emerald-600 dark:text-emerald-400" />
                {item.effective_price_display || 'Miễn phí'}
              </span>
            </div>
          ) : (
            <span
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-0.5 text-xs font-semibold ${
                item.pricing_mode === 'free'
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20'
                  : 'bg-primary/10 text-primary border border-primary/20'
              }`}
            >
              {item.price_display || 'Miễn phí'}
            </span>
          )}
        </div>

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
          {item.description || 'Chưa có mô tả chi tiết cho bộ deck này.'}
        </p>
      </div>

      {/* Card Bottom Block */}
      <div className="mt-4 pt-3 border-t border-border/60 space-y-3">
        {/* Stats Row */}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          {item.rating_avg !== undefined ? (
            <span className="inline-flex items-center gap-1 font-semibold text-foreground">
              <Star className="size-3.5 fill-amber-400 text-amber-500" />
              <span className="tabular-nums">
                {item.rating_avg.toFixed(1)}
                {item.rating_count ? (
                  <span className="text-[11px] font-normal text-muted-foreground ml-0.5">
                    ({item.rating_count})
                  </span>
                ) : null}
              </span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
              <BookOpen className="size-3 text-primary" />
              <span>{item.lesson_count ? `${item.lesson_count} bài` : '1 bài'}</span>
            </span>
          )}

          <div className="flex items-center gap-2 font-medium">
            {item.lesson_count && item.rating_avg !== undefined ? (
              <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hidden xs:inline-flex">
                <BookOpen className="size-3 text-primary" />
                <span className="tabular-nums">{item.lesson_count} bài</span>
              </span>
            ) : null}

            {item.note_count ? (
              <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                <Layers className="size-3 text-primary" />
                <span className="tabular-nums">
                  {item.note_count.toLocaleString('vi-VN')} từ
                </span>
              </span>
            ) : cardCount ? (
              <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                <Layers className="size-3 text-primary" />
                <span className="tabular-nums">{cardCount} thẻ</span>
              </span>
            ) : null}

            {item.install_count !== undefined ? (
              <span className="inline-flex items-center gap-1">
                <Download className="size-3.5 text-primary" />
                <span className="tabular-nums">
                  {item.install_count.toLocaleString('vi-VN')} lượt
                </span>
              </span>
            ) : null}
          </div>
        </div>

        {/* Action Buttons */}
        {actions ? (
          actions
        ) : variant === 'installed' ? (
          <div className="space-y-2">
            {hasConflict && item.deck_install_id ? (
              <Button
                size="sm"
                asChild
                className="h-8.5 w-full rounded-xl text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white shadow-xs"
              >
                <Link
                  to={`/installed-decks/${item.deck_install_id}/updates/${targetReleaseId}`}
                >
                  <ShieldAlert className="mr-1.5 size-3.5" />
                  Xử lý xung đột ({item.pending_conflict_count || '!'})
                </Link>
              </Button>
            ) : item.update_available &&
              item.deck_install_id &&
              item.available_release ? (
              <Button
                size="sm"
                asChild
                className="h-8.5 w-full rounded-xl text-xs font-bold"
              >
                <Link
                  to={`/installed-decks/${item.deck_install_id}/updates/${item.available_release.id}`}
                >
                  <RefreshCcw className="mr-1.5 size-3.5" />
                  {item.unread_update ? 'Xem cập nhật mới' : 'Xem cập nhật'}
                </Link>
              </Button>
            ) : null}
            {item.deck_install_id &&
            item.install_bucket !== 'owned' &&
            !hasConflict ? (
              <Button
                variant="outline"
                size="sm"
                asChild
                className="h-8.5 w-full rounded-xl text-xs font-semibold"
              >
                <Link
                  to={`/flashcards/shared-decks/${item.id}/change-request`}
                >
                  <FileDiff className="mr-1.5 size-3.5" />
                  Đóng góp chỉnh sửa
                </Link>
              </Button>
            ) : null}
            {item.installed_deck_id ? (
              <Button
                size="sm"
                asChild
                data-tour={actionDataTour}
                className="w-full h-8.5 text-xs font-bold rounded-xl shadow-xs"
              >
                <Link to={`/study?deck_id=${item.installed_deck_id}`}>
                  <BookOpen className="mr-1.5 size-3.5" />
                  Học ngay
                </Link>
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                asChild
                data-tour={actionDataTour}
                className="w-full h-8.5 text-xs font-semibold rounded-xl"
              >
                <Link to={detailUrl}>
                  <Eye className="mr-1.5 size-3.5" />
                  Chi tiết
                </Link>
              </Button>
            )}
          </div>
        ) : (
          <div>
            {item.installed_deck_id ? (
              <Button
                size="sm"
                asChild
                data-tour={actionDataTour}
                className="w-full h-9 text-xs font-semibold rounded-xl shadow-xs"
              >
                <Link to={`/study?deck_id=${item.installed_deck_id}`}>
                  <BookOpen className="mr-1.5 size-3.5" />
                  Học ngay
                </Link>
              </Button>
            ) : item.is_installed ? (
              <Button
                variant="outline"
                size="sm"
                asChild
                data-tour={actionDataTour}
                className="w-full h-9 text-xs font-semibold rounded-xl border-emerald-500/40 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10"
              >
                <Link to={detailUrl}>
                  <CheckCircle className="mr-1.5 size-3.5 text-emerald-500" />
                  Đã cài đặt
                </Link>
              </Button>
            ) : isCourseDeck ? (
              <Button
                variant="outline"
                size="sm"
                asChild
                data-tour={actionDataTour}
                className="w-full h-9 text-xs font-semibold rounded-xl border-purple-500/40 text-purple-700 dark:text-purple-300 hover:bg-purple-500/10"
              >
                <Link to={detailUrl}>
                  <KeyRound className="mr-1.5 size-3.5 text-purple-600 dark:text-purple-400" />
                  Xem khóa học & Nhập mã
                </Link>
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                asChild
                data-tour={actionDataTour}
                className="w-full h-9 text-xs font-semibold rounded-xl hover:bg-primary hover:text-primary-foreground hover:border-primary transition-all"
              >
                <Link to={detailUrl}>
                  <Eye className="mr-1.5 size-3.5" />
                  Xem chi tiết
                  <ArrowRight className="ml-1 size-3.5 transition-transform group-hover:translate-x-0.5" />
                </Link>
              </Button>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
