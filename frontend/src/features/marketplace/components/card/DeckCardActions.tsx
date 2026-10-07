import React from 'react'
import {
  ArrowRight,
  BookOpen,
  CheckCircle,
  Eye,
  FileDiff,
  KeyRound,
  RefreshCcw,
  ShieldAlert,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import type { DeckCardItem } from '../DeckCard'

interface DeckCardActionsProps {
  item: DeckCardItem
  variant: 'marketplace' | 'installed'
  detailUrl: string
  isCourseDeck: boolean
  hasConflict: boolean
  targetReleaseId: string
  actionDataTour?: string
  actions?: React.ReactNode
}

export function DeckCardActions({
  item,
  variant,
  detailUrl,
  isCourseDeck,
  hasConflict,
  targetReleaseId,
  actionDataTour,
  actions,
}: DeckCardActionsProps) {
  const { t } = useTranslation('marketplace')

  if (actions) {
    return <>{actions}</>
  }

  if (variant === 'installed') {
    return (
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
              {t('card.handle_conflict', {
                count: item.pending_conflict_count || '!',
              })}
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
              {item.unread_update
                ? t('card.view_new_update')
                : t('card.view_update')}
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
            <Link to={`/flashcards/shared-decks/${item.id}/change-request`}>
              <FileDiff className="mr-1.5 size-3.5" />
              {t('card.contribute_edit')}
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
              {t('card.btn_study')}
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
              {t('card.btn_detail_short')}
            </Link>
          </Button>
        )}
      </div>
    )
  }

  return (
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
            {t('card.btn_study')}
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
            {t('card.btn_installed')}
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
            {t('card.btn_course_redeem')}
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
            {t('card.btn_details')}
            <ArrowRight className="ml-1 size-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </Button>
      )}
    </div>
  )
}
