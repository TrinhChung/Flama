import '@/shared/config/i18n'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  CheckCircle2,
  LayoutDashboard,
  ArrowRight,
  Trophy,
  Printer,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { LazyDeckWorksheetModal } from '@/features/worksheets/components/LazyDeckWorksheetModal'
import { StudyCompletionBreakdown } from './StudyCompletionBreakdown'
import { StudyCompletionDeckStatus } from './StudyCompletionDeckStatus'
import { StudyCompletionStatsGrid } from './StudyCompletionStatsGrid'
import type {
  StudySessionCommitReceipt,
  StudySessionEvent,
} from '../types'
import type {
  PersistedStudySession,
  StudySessionAccumulatedStats,
} from '../session/sessionStore'

type StudyCompletionCardProps = {
  deckName?: string | null
  deckId?: string | null
  session: PersistedStudySession | null
  receipt: StudySessionCommitReceipt | null
  totalSessionStats?: StudySessionAccumulatedStats | null
  counts: { new: number; learning: number; due: number }
  isBusy: boolean
  onCommit: () => void
}

export function StudyCompletionCard({
  deckName,
  deckId,
  session,
  receipt,
  totalSessionStats,
  counts,
  isBusy,
  onCommit,
}: StudyCompletionCardProps) {
  const { t } = useTranslation('study')
  const [isWorksheetOpen, setIsWorksheetOpen] = useState(false)
  const isCommitted = Boolean(receipt)
  const events = useMemo(() => session?.events ?? [], [session?.events])

  const numericDeckId = useMemo(() => {
    if (!deckId) return null
    const parsed = Number(deckId)
    return Number.isFinite(parsed) ? parsed : null
  }, [deckId])

  const stats = useMemo(() => {
    // If totalSessionStats was provided directly from hook:
    if (totalSessionStats) {
      const totalRatings = totalSessionStats.total_reviews
      const againCount = totalSessionStats.again_count
      const hardCount = totalSessionStats.hard_count
      const goodCount = totalSessionStats.good_count
      const easyCount = totalSessionStats.easy_count
      const totalDurationMs = totalSessionStats.total_duration_ms

      const totalRatingsSafe = totalRatings || 1
      const retentionRate = Math.round(
        ((goodCount + easyCount) / totalRatingsSafe) * 100,
      )

      const totalSeconds = Math.round(totalDurationMs / 1000)
      const minutes = Math.floor(totalSeconds / 60)
      const seconds = totalSeconds % 60
      const timeFormatted =
        minutes > 0
          ? (seconds > 0
              ? t('completion.time_format_minutes', { minutes, seconds })
              : t('completion.time_format_only_minutes', { minutes }))
          : t('completion.time_format_seconds', { seconds })

      return {
        againCount,
        hardCount,
        goodCount,
        easyCount,
        totalRatings,
        retentionRate: totalRatings > 0 ? retentionRate : 100,
        timeFormatted: totalRatings > 0 ? timeFormatted : '0s',
      }
    }

    const acc = session?.accumulated_stats
    let againCount = acc?.again_count ?? 0
    let hardCount = acc?.hard_count ?? 0
    let goodCount = acc?.good_count ?? 0
    let easyCount = acc?.easy_count ?? 0
    let totalDurationMs = acc?.total_duration_ms ?? 0
    let totalRatings = acc?.total_reviews ?? 0

    // When not yet committed, events in session.events have NOT been rolled into accumulated_stats yet.
    if (!isCommitted && events.length > 0) {
      events.forEach((ev: StudySessionEvent) => {
        totalDurationMs += ev.duration_ms || 0
        if (ev.rating === 'again') againCount += 1
        else if (ev.rating === 'hard') hardCount += 1
        else if (ev.rating === 'good') goodCount += 1
        else if (ev.rating === 'easy') easyCount += 1
      })
      totalRatings += events.length
    } else if (totalRatings === 0 && events.length > 0) {
      events.forEach((ev: StudySessionEvent) => {
        totalDurationMs += ev.duration_ms || 0
        if (ev.rating === 'again') againCount += 1
        else if (ev.rating === 'hard') hardCount += 1
        else if (ev.rating === 'good') goodCount += 1
        else if (ev.rating === 'easy') easyCount += 1
      })
      totalRatings += events.length
    }

    // Fallback if receipt has applied counts but events/accumulated were cleared
    if (totalRatings === 0 && receipt?.applied_event_count) {
      totalRatings = receipt.applied_event_count
      if (receipt.rating_counts) {
        againCount = receipt.rating_counts.again || 0
        hardCount = receipt.rating_counts.hard || 0
        goodCount = receipt.rating_counts.good || 0
        easyCount = receipt.rating_counts.easy || 0
      }
    }

    const totalRatingsSafe = totalRatings || 1
    const retentionRate = Math.round(
      ((goodCount + easyCount) / totalRatingsSafe) * 100,
    )

    const totalSeconds = Math.round(totalDurationMs / 1000)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    const timeFormatted =
      minutes > 0
        ? (seconds > 0
            ? t('completion.time_format_minutes', { minutes, seconds })
            : t('completion.time_format_only_minutes', { minutes }))
        : t('completion.time_format_seconds', { seconds })

    return {
      againCount,
      hardCount,
      goodCount,
      easyCount,
      totalRatings,
      retentionRate: totalRatings > 0 ? retentionRate : 100,
      timeFormatted: totalRatings > 0 ? timeFormatted : '0s',
    }
  }, [events, isCommitted, receipt, session?.accumulated_stats, t, totalSessionStats])

  const appliedCount = stats.totalRatings || (receipt?.applied_event_count ?? events.length)

  return (
    <div className="w-full max-w-2xl mx-auto py-4 sm:py-6 px-3 sm:px-4 my-auto">
      <div className="rounded-2xl border border-border/80 bg-card p-4 sm:p-8 space-y-4 sm:space-y-6 text-center shadow-xs">
        {/* Header (Symmetrical & Centered) */}
        <div className="space-y-2 sm:space-y-3">
          <div className="inline-flex items-center justify-center size-11 sm:size-12 rounded-xl bg-muted border border-border/60 text-foreground mx-auto">
            {isCommitted ? (
              <CheckCircle2 className="size-5 sm:size-6 text-emerald-600 dark:text-emerald-400" />
            ) : (
              <Trophy className="size-5 sm:size-6 text-amber-500" />
            )}
          </div>

          <div className="space-y-1">
            <div className="inline-flex items-center justify-center gap-1.5 px-3 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border/60 max-w-full truncate">
              <span>{deckName || (deckId ? `Deck #${deckId}` : t('page.session_title'))}</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-foreground tracking-tight">
              {isCommitted
                ? t('completion.session_synced')
                : t('completion.completed_today')}
            </h2>
            <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              {isCommitted
                ? t('completion.synced_description', { appliedCount })
                : t('completion.completed_description')}
            </p>
          </div>
        </div>

        {/* 3 Equal-Width Metrics Cards (Symmetrical Row) */}
        <StudyCompletionStatsGrid
          totalRatings={stats.totalRatings}
          timeFormatted={stats.timeFormatted}
          retentionRate={stats.retentionRate}
        />

        {/* 4 Equal-Width Rating Breakdown Cards (Symmetrical Grid) */}
        <StudyCompletionBreakdown
          totalRatings={stats.totalRatings}
          againCount={stats.againCount}
          hardCount={stats.hardCount}
          goodCount={stats.goodCount}
          easyCount={stats.easyCount}
        />

        {/* 3 Equal-Width Deck Status Cards (Symmetrical Grid) */}
        <StudyCompletionDeckStatus counts={counts} />

        {/* Action Controls */}
        <div className="pt-2">
          {!isCommitted ? (
            <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-center sm:gap-3">
              <Button
                type="button"
                disabled={isBusy}
                onClick={onCommit}
                size="lg"
                className="w-full sm:w-auto h-11 px-6 rounded-xl bg-primary hover:bg-primary/95 text-primary-foreground font-semibold text-xs sm:text-sm shadow-xs"
              >
                {isBusy ? (
                  <>
                    <div className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" />
                    <span>{t('completion.syncing')}</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="size-4 mr-2" />
                    <span>{t('completion.end_and_sync')}</span>
                  </>
                )}
              </Button>

              <div className="grid grid-cols-2 sm:flex sm:items-center gap-2 sm:gap-3 w-full sm:w-auto">
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  onClick={() => setIsWorksheetOpen(true)}
                  className="w-full sm:w-auto h-10 sm:h-11 px-3 sm:px-5 rounded-xl font-semibold text-xs sm:text-sm gap-2 border-primary/25 text-primary hover:bg-primary/5 hover:border-primary/40"
                  title={t('completion.create_worksheet_tooltip')}
                >
                  <Printer className="size-4 shrink-0 text-primary" />
                  <span className="truncate">{t('completion.create_worksheet')}</span>
                </Button>

                <Button
                  asChild
                  variant="outline"
                  size="lg"
                  className="w-full sm:w-auto h-10 sm:h-11 px-3 sm:px-6 rounded-xl font-semibold text-xs sm:text-sm gap-2"
                >
                  <Link to="/dashboard">
                    <LayoutDashboard className="size-4 shrink-0" />
                    <span className="truncate">{t('completion.back_to_dashboard')}</span>
                  </Link>
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-center sm:gap-3">
              <Button
                type="button"
                variant="outline"
                size="lg"
                onClick={() => setIsWorksheetOpen(true)}
                className="w-full sm:w-auto h-11 px-5 rounded-xl font-semibold text-xs sm:text-sm gap-2 border-primary/30 bg-primary/5 hover:bg-primary/10 text-primary shadow-xs"
                title={t('completion.create_worksheet_cta_tooltip')}
              >
                <Printer className="size-4 text-primary shrink-0" />
                <span>{t('completion.create_worksheet_cta')}</span>
              </Button>

              <div className="grid grid-cols-2 sm:flex sm:items-center gap-2 sm:gap-3 w-full sm:w-auto">
                <Button
                  asChild
                  variant="outline"
                  size="lg"
                  className="w-full sm:w-auto h-10 sm:h-11 px-3 sm:px-5 rounded-xl font-semibold text-xs sm:text-sm gap-2"
                >
                  <Link to="/dashboard">
                    <LayoutDashboard className="size-4 shrink-0" />
                    <span className="truncate">{t('completion.back_to_dashboard')}</span>
                  </Link>
                </Button>

                <Button
                  asChild
                  variant="default"
                  size="lg"
                  className="w-full sm:w-auto h-10 sm:h-11 px-3 sm:px-6 rounded-xl font-semibold text-xs sm:text-sm gap-2 shadow-xs"
                >
                  <Link to="/vocabulary">
                    <span className="truncate">{t('completion.study_another_deck')}</span>
                    <ArrowRight className="size-4 shrink-0" />
                  </Link>
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Printable Worksheet Live Studio Modal */}
      {isWorksheetOpen ? (
        <LazyDeckWorksheetModal
          open={isWorksheetOpen}
          onOpenChange={setIsWorksheetOpen}
          deckId={numericDeckId}
          deckName={deckName || undefined}
        />
      ) : null}
    </div>
  )
}
