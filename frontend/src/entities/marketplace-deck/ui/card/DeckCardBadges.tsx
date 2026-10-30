import {
  GraduationCap,
  KeyRound,
  ShieldAlert,
  Zap,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import type { DeckCardItem } from '../DeckCard'

interface DeckCardBadgesProps {
  item: DeckCardItem
  variant: 'marketplace' | 'installed'
  isCourseDeck: boolean
  hasConflict: boolean
  getCategoryBadgeStyle: (cat: string | null | undefined) => string
  formatSyncStatus: (val: string) => string
}

export function DeckCardBadges({
  item,
  variant,
  isCourseDeck,
  hasConflict,
  getCategoryBadgeStyle,
  formatSyncStatus,
}: DeckCardBadgesProps) {
  const { t } = useTranslation('marketplace')

  return (
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
              ? t('card.using_now')
              : item.install_bucket === 'owned'
                ? t('card.owned')
                : t('card.installed')}
          </Badge>
          {item.auto_update_enabled ? (
            <Badge
              variant="outline"
              className="px-1.5 py-0 text-[10px] font-semibold border-primary/30 text-primary bg-primary/5"
            >
              <Zap className="mr-0.5 size-2.5 inline" />
              {t('card.auto')}
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
            {item.primary_category || t('card.general_category')}
          </Badge>
          {isCourseDeck && (
            <Badge
              variant="outline"
              className="px-1.5 py-0.5 text-[10px] font-bold border-purple-500/30 text-purple-600 dark:text-purple-400 bg-purple-500/10 flex items-center gap-1"
            >
              <GraduationCap className="size-2.5" />
              {t('card.course_badge')}
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
              ? t('card.has_conflicts', { count: item.pending_conflict_count })
              : t('card.has_conflict')}
          </span>
        ) : item.content_model !== 'published_base' && item.update_available ? (
          <span className="truncate text-xs font-semibold text-primary">
            {t('card.update_available', {
              label: item.available_release?.version_label || t('card.new_release'),
            })}
          </span>
        ) : item.last_sync_status ? (
          <span className="truncate text-xs text-muted-foreground">
            {formatSyncStatus(item.last_sync_status)}
          </span>
        ) : null
      ) : isCourseDeck ? (
        <span className="inline-flex items-center gap-1 rounded-md px-2.5 py-0.5 text-xs font-semibold bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/20">
          <KeyRound className="size-3" />
          {t('card.course_key_badge')}
        </span>
      ) : item.student_discount_applied ? (
        <div className="flex items-center gap-1">
          <span className="text-[11px] text-muted-foreground line-through font-medium">
            {item.price_display}
          </span>
          <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
            <GraduationCap className="size-3 text-emerald-600 dark:text-emerald-400" />
            {item.effective_price_display || t('card.free')}
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
          {item.price_display || t('card.free')}
        </span>
      )}
    </div>
  )
}
