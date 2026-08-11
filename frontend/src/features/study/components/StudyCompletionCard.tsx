import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  CheckCircle2,
  LayoutDashboard,
  ArrowRight,
  Trophy,
  BarChart2,
  Layers,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import type {
  StudySessionCommitReceipt,
  StudySessionEvent,
} from '../types'
import type { PersistedStudySession } from '../session/sessionStore'

type StudyCompletionCardProps = {
  deckName?: string | null
  deckId?: string | null
  session: PersistedStudySession | null
  receipt: StudySessionCommitReceipt | null
  counts: { new: number; learning: number; due: number }
  isBusy: boolean
  onCommit: () => void
}

export function StudyCompletionCard({
  deckName,
  deckId,
  session,
  receipt,
  counts,
  isBusy,
  onCommit,
}: StudyCompletionCardProps) {
  const events = useMemo(() => session?.events ?? [], [session?.events])
  const appliedCount = receipt?.applied_event_count ?? events.length

  const stats = useMemo(() => {
    let againCount = 0
    let hardCount = 0
    let goodCount = 0
    let easyCount = 0
    let totalDurationMs = 0

    events.forEach((ev: StudySessionEvent) => {
      totalDurationMs += ev.duration_ms || 0
      if (ev.rating === 'again') againCount += 1
      else if (ev.rating === 'hard') hardCount += 1
      else if (ev.rating === 'good') goodCount += 1
      else if (ev.rating === 'easy') easyCount += 1
    })

    const totalRatings = events.length || 1
    const retentionRate = Math.round(
      ((goodCount + easyCount) / totalRatings) * 100,
    )

    const totalSeconds = Math.round(totalDurationMs / 1000)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    const timeFormatted =
      minutes > 0
        ? `${minutes} phút ${seconds > 0 ? `${seconds}s` : ''}`
        : `${seconds}s`

    return {
      againCount,
      hardCount,
      goodCount,
      easyCount,
      totalRatings: events.length,
      retentionRate: events.length > 0 ? retentionRate : 100,
      timeFormatted: events.length > 0 ? timeFormatted : '0s',
    }
  }, [events])

  const isCommitted = Boolean(receipt)

  return (
    <div className="w-full max-w-2xl mx-auto py-6 px-4">
      <div className="rounded-2xl border border-border/80 bg-card p-6 sm:p-8 space-y-6 text-center shadow-xs">
        {/* Header (Symmetrical & Centered) */}
        <div className="space-y-3">
          <div className="inline-flex items-center justify-center size-12 rounded-xl bg-muted border border-border/60 text-foreground mx-auto">
            {isCommitted ? (
              <CheckCircle2 className="size-6 text-emerald-600 dark:text-emerald-400" />
            ) : (
              <Trophy className="size-6 text-amber-500" />
            )}
          </div>

          <div className="space-y-1">
            <div className="inline-flex items-center justify-center gap-1.5 px-3 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border/60">
              <span>{deckName || (deckId ? `Deck #${deckId}` : 'Phiên học')}</span>
            </div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">
              {isCommitted
                ? 'Đã đồng bộ phiên học'
                : 'Hoàn thành lượt học hôm nay'}
            </h2>
            <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              {isCommitted
                ? `Hệ thống đã lưu thành công ${appliedCount} lượt trả lời thẻ.`
                : 'Tất cả các thẻ cần học hôm nay đã được ôn tập xong.'}
            </p>
          </div>
        </div>

        {/* 3 Equal-Width Metrics Cards (Symmetrical Row) */}
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-0.5">
            <span className="block text-xs font-medium text-muted-foreground">
              Đã ôn
            </span>
            <span className="text-lg font-bold text-foreground">
              {stats.totalRatings} thẻ
            </span>
          </div>

          <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-0.5">
            <span className="block text-xs font-medium text-muted-foreground">
              Thời gian
            </span>
            <span className="text-lg font-bold text-foreground truncate block">
              {stats.timeFormatted}
            </span>
          </div>

          <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-0.5">
            <span className="block text-xs font-medium text-muted-foreground">
              Tỉ lệ đúng
            </span>
            <span className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
              {stats.retentionRate}%
            </span>
          </div>
        </div>

        {/* 4 Equal-Width Rating Breakdown Cards (Symmetrical Grid) */}
        {stats.totalRatings > 0 ? (
          <div className="space-y-2 text-left">
            <div className="flex items-center justify-between text-xs font-medium text-muted-foreground px-0.5">
              <span className="flex items-center gap-1.5">
                <BarChart2 className="size-3.5 text-muted-foreground" />
                Chi tiết đánh giá
              </span>
              <span>{stats.totalRatings} lượt</span>
            </div>

            <div className="grid grid-cols-4 gap-2 text-center text-xs">
              <div className="p-2 rounded-xl bg-rose-500/10 border border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300">
                <span className="block text-[11px] font-medium opacity-80">Quên</span>
                <span className="text-sm font-bold">{stats.againCount}</span>
              </div>
              <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-200 dark:border-amber-900/40 text-amber-700 dark:text-amber-300">
                <span className="block text-[11px] font-medium opacity-80">Khó</span>
                <span className="text-sm font-bold">{stats.hardCount}</span>
              </div>
              <div className="p-2 rounded-xl bg-blue-500/10 border border-blue-200 dark:border-blue-900/40 text-blue-700 dark:text-blue-300">
                <span className="block text-[11px] font-medium opacity-80">Tốt</span>
                <span className="text-sm font-bold">{stats.goodCount}</span>
              </div>
              <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-200 dark:border-emerald-900/40 text-emerald-700 dark:text-emerald-300">
                <span className="block text-[11px] font-medium opacity-80">Dễ</span>
                <span className="text-sm font-bold">{stats.easyCount}</span>
              </div>
            </div>
          </div>
        ) : null}

        {/* 3 Equal-Width Deck Status Cards (Symmetrical Grid) */}
        <div className="space-y-2 text-left">
          <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground px-0.5">
            <Layers className="size-3.5 text-muted-foreground" />
            <span>Trạng thái thẻ trong Deck</span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="p-2.5 rounded-xl border border-border/60 bg-muted/20">
              <span className="block text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                Mới
              </span>
              <span className="text-sm font-bold text-foreground">{counts.new}</span>
            </div>

            <div className="p-2.5 rounded-xl border border-border/60 bg-muted/20">
              <span className="block text-[11px] font-medium text-amber-600 dark:text-amber-400">
                Đang học
              </span>
              <span className="text-sm font-bold text-foreground">{counts.learning}</span>
            </div>

            <div className="p-2.5 rounded-xl border border-border/60 bg-muted/20">
              <span className="block text-[11px] font-medium text-rose-600 dark:text-rose-400">
                Đến hạn
              </span>
              <span className="text-sm font-bold text-foreground">{counts.due}</span>
            </div>
          </div>
        </div>

        {/* Centered Actions */}
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
          {!isCommitted ? (
            <Button
              type="button"
              disabled={isBusy}
              onClick={onCommit}
              size="lg"
              className="w-full sm:w-auto h-11 px-6 rounded-xl bg-primary hover:bg-primary/95 text-primary-foreground font-semibold text-xs sm:text-sm"
            >
              {isBusy ? (
                <>
                  <div className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" />
                  <span>Đang đồng bộ…</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="size-4 mr-2" />
                  <span>Kết thúc & Đồng bộ phiên</span>
                </>
              )}
            </Button>
          ) : null}

          <Button
            asChild
            variant={isCommitted ? 'default' : 'outline'}
            size="lg"
            className="w-full sm:w-auto h-11 px-6 rounded-xl font-semibold text-xs sm:text-sm gap-2"
          >
            <Link to="/dashboard">
              <LayoutDashboard className="size-4" />
              <span>Về Dashboard</span>
            </Link>
          </Button>

          {isCommitted ? (
            <Button
              asChild
              variant="outline"
              size="lg"
              className="w-full sm:w-auto h-11 px-6 rounded-xl font-semibold text-xs sm:text-sm gap-2"
            >
              <Link to="/vocabulary">
                <span>Học deck khác</span>
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
