import { useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  Layers,
  ListOrdered,
  LoaderCircle,
  Pause,
  Play,
  Trash2,
  Volume2,
  XCircle,
  Zap,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import type { AudioDeckJob, AudioJobItem } from '../types'

type DeckAudioQueueMonitorProps = {
  jobs: AudioDeckJob[]
  activeJob: AudioDeckJob | null
  concurrency?: number
  onConcurrencyChange?: (concurrency: number) => void
  onPause: () => void
  onResume: (jobId: string) => void
  onCancel: (jobId: string) => void
  onRemove: (jobId: string) => void
  onClearCompleted: () => void
}

export function DeckAudioQueueMonitor({
  jobs,
  activeJob,
  concurrency = 3,
  onConcurrencyChange,
  onPause,
  onResume,
  onCancel,
  onRemove,
  onClearCompleted,
}: DeckAudioQueueMonitorProps) {
  const { t } = useTranslation('audio')
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const displayedJob =
    (selectedJobId ? jobs.find((j) => j.id === selectedJobId) : null) ||
    activeJob ||
    jobs[0] ||
    null

  const queuedJobs = jobs.filter((j) => j.status === 'queued')
  const completedJobs = jobs.filter((j) => j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled')

  const handlePlayAsset = (url?: string) => {
    if (!url) return
    if (audioRef.current) {
      audioRef.current.pause()
    }
    const audio = new Audio(url)
    audioRef.current = audio
    audio.play().catch(() => {})
  }

  if (jobs.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border/70 p-8 text-center bg-card/40">
        <ListOrdered className="mx-auto size-9 text-muted-foreground/60 mb-2.5" />
        <h3 className="text-sm font-bold text-foreground">{t('queue.empty_queue')}</h3>
        <p className="text-xs text-muted-foreground max-w-md mx-auto mt-1">
          Chọn một bộ thẻ (Deck) bên trên và bấm &ldquo;Bắt đầu tạo âm thanh&rdquo; hoặc &ldquo;Thêm vào hàng đợi&rdquo; để xếp lịch tạo tự động.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Top Section: Active / Selected Deck Monitor Card */}
      {displayedJob && (
        <Card className="rounded-2xl border-border/70 shadow-xs overflow-hidden">
          <CardHeader className="p-4 sm:p-5 border-b bg-muted/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Layers className="size-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <CardTitle className="text-sm sm:text-base font-bold text-foreground">
                    {displayedJob.deckName}
                  </CardTitle>
                  <Badge
                    variant={
                      displayedJob.status === 'running'
                        ? 'default'
                        : displayedJob.status === 'completed'
                          ? 'outline'
                          : displayedJob.status === 'paused'
                            ? 'secondary'
                            : 'outline'
                    }
                    className={`text-[11px] font-semibold ${
                      displayedJob.status === 'completed'
                        ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30'
                        : displayedJob.status === 'paused'
                          ? 'bg-amber-500/10 text-amber-600 border-amber-500/30'
                          : ''
                    }`}
                  >
                    {displayedJob.status === 'running' && (
                      <LoaderCircle className="mr-1 size-3 animate-spin" />
                    )}
                    {displayedJob.status === 'running'
                      ? t('queue.status_synthesizing')
                      : displayedJob.status === 'queued'
                        ? t('queue.status_pending')
                        : displayedJob.status === 'paused'
                          ? t('queue.pause_button')
                          : displayedJob.status === 'completed'
                            ? t('queue.status_completed')
                            : displayedJob.status === 'cancelled'
                              ? t('queue.status_skipped')
                              : t('queue.status_failed')}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Chế độ: {displayedJob.mode === 'missing_and_broken' ? 'Chỉ bù từ thiếu & hỏng' : 'Tạo lại toàn bộ'} • Tổng {displayedJob.items.length} mục
                </p>
              </div>
            </div>

            {/* Action Buttons & Concurrency Selector */}
            <div className="flex flex-wrap items-center gap-2.5 self-end sm:self-center">
              {/* Concurrency Selector */}
              <div className="flex items-center gap-1 bg-muted/40 p-1 rounded-xl border border-border/50">
                <span className="text-[11px] font-semibold text-muted-foreground px-1.5 flex items-center gap-1">
                  <Zap className="size-3 text-amber-500" />
                  <span>Số luồng:</span>
                </span>
                {[1, 2, 3, 5].map((cnt) => (
                  <button
                    key={cnt}
                    type="button"
                    onClick={() => onConcurrencyChange?.(cnt)}
                    className={`px-2 py-0.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                      concurrency === cnt
                        ? 'bg-primary text-primary-foreground shadow-xs'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/60'
                    }`}
                    title={`${cnt} luồng song song`}
                  >
                    {cnt}
                  </button>
                ))}
              </div>

              {displayedJob.status === 'running' && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onPause}
                  className="h-8 text-xs gap-1.5"
                >
                  <Pause className="size-3.5" />
                  <span>{t('queue.pause_button')}</span>
                </Button>
              )}

              {displayedJob.status === 'paused' && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => onResume(displayedJob.id)}
                  className="h-8 text-xs gap-1.5"
                >
                  <Play className="size-3.5" />
                  <span>{t('queue.resume_button')}</span>
                </Button>
              )}

              {(displayedJob.status === 'running' || displayedJob.status === 'queued' || displayedJob.status === 'paused') && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onCancel(displayedJob.id)}
                  className="h-8 text-xs text-destructive hover:bg-destructive/10"
                >
                  <XCircle className="size-3.5 mr-1" />
                  <span>{t('queue.cancel_all_button')}</span>
                </Button>
              )}
            </div>
          </CardHeader>

          <CardContent className="p-4 sm:p-5 space-y-5">
            {/* Progress Bar & Counter */}
            <div className="space-y-2.5 rounded-xl border border-border/50 bg-muted/20 p-4">
              <div className="flex justify-between items-center text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-foreground">
                    Tiến độ hoàn thành:
                  </span>
                  <span className="font-mono text-primary font-bold">
                    {displayedJob.stats.completedItems} / {displayedJob.items.length} mục
                  </span>
                  {displayedJob.stats.failedItems > 0 && (
                    <span className="text-destructive font-semibold">
                      ({displayedJob.stats.failedItems} lỗi)
                    </span>
                  )}
                </div>
                <span className="font-mono text-base font-extrabold text-primary">
                  {displayedJob.stats.progressPercent}%
                </span>
              </div>
              <Progress value={displayedJob.stats.progressPercent} className="h-2.5 rounded-full" />

              {/* Multi-thread Live Speed & Realtime Indicators */}
              {displayedJob.status === 'running' && (
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-border/40 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20 font-bold text-[11px] gap-1">
                      <Zap className="size-3 animate-pulse text-amber-500" />
                      <span>{displayedJob.stats.activeWorkers || 1} luồng song song</span>
                    </Badge>

                    {displayedJob.stats.itemsPerSecond && displayedJob.stats.itemsPerSecond > 0 ? (
                      <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20 font-mono text-[11px] font-bold gap-1">
                        <Activity className="size-3" />
                        <span>~{displayedJob.stats.itemsPerSecond} từ/giây</span>
                      </Badge>
                    ) : null}

                    {displayedJob.stats.estimatedSecondsRemaining !== undefined && displayedJob.stats.estimatedSecondsRemaining > 0 ? (
                      <span className="text-muted-foreground text-[11px]">
                        Ước tính còn: <strong className="text-foreground">{displayedJob.stats.estimatedSecondsRemaining > 60 ? `${Math.ceil(displayedJob.stats.estimatedSecondsRemaining / 60)} phút` : `${displayedJob.stats.estimatedSecondsRemaining}s`}</strong>
                      </span>
                    ) : null}
                  </div>

                  {/* Active words currently running in parallel */}
                  {displayedJob.stats.activeWords && displayedJob.stats.activeWords.length > 0 ? (
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground flex-wrap">
                      <span className="text-[11px] font-semibold text-foreground shrink-0">Đang chạy:</span>
                      <div className="flex items-center gap-1 flex-wrap">
                        {displayedJob.stats.activeWords.map((w, idx) => (
                          <Badge key={idx} variant="secondary" className="text-[10px] bg-primary/10 text-primary border-primary/20 font-medium py-0">
                            {w}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ) : displayedJob.stats.currentWord ? (
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <LoaderCircle className="size-3 animate-spin text-primary shrink-0" />
                      <span>
                        Đang xử lý: <strong className="text-foreground">{displayedJob.stats.currentWord}</strong>
                      </span>
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            {/* Live Items Table */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-foreground flex items-center justify-between">
                <span>Chi tiết các từ vựng ({displayedJob.items.length})</span>
                <span className="text-[11px] font-normal text-muted-foreground">
                  Tự động cuộn theo tiến trình
                </span>
              </h4>

              <div className="max-h-64 overflow-y-auto rounded-xl border border-border/60 bg-card divide-y divide-border/40">
                {displayedJob.items.map((item: AudioJobItem, idx: number) => (
                  <div
                    key={item.id}
                    className={`flex items-center justify-between p-2.5 text-xs transition-colors ${
                      item.status === 'synthesizing' || item.status === 'uploading'
                        ? 'bg-primary/5'
                        : item.status === 'failed'
                          ? 'bg-rose-500/5'
                          : ''
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="font-mono text-[11px] text-muted-foreground w-6 text-right shrink-0">
                        #{idx + 1}
                      </span>
                      <div className="min-w-0">
                        <p className="font-bold text-foreground truncate">
                          {item.word}
                        </p>
                        <p className="text-[11px] text-muted-foreground truncate">
                          {item.sourceField} $\rightarrow$ {item.destinationField}: &ldquo;{item.text}&rdquo;
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {item.status === 'pending' && (
                        <Badge variant="outline" className="text-[10px] text-muted-foreground">
                          <Clock className="mr-1 size-2.5" />
                          {t('queue.status_pending')}
                        </Badge>
                      )}
                      {item.status === 'synthesizing' && (
                        <Badge className="text-[10px] bg-primary/20 text-primary border-primary/30">
                          <LoaderCircle className="mr-1 size-2.5 animate-spin" />
                          {t('queue.status_synthesizing')}
                        </Badge>
                      )}
                      {item.status === 'uploading' && (
                        <Badge className="text-[10px] bg-sky-500/20 text-sky-600 border-sky-500/30">
                          <LoaderCircle className="mr-1 size-2.5 animate-spin" />
                          {t('queue.status_uploading')}
                        </Badge>
                      )}
                      {item.status === 'done' && (
                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-600 border-emerald-500/30">
                            <CheckCircle2 className="mr-1 size-2.5" />
                            {t('queue.status_completed')}
                          </Badge>
                          {item.assetUrl && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => handlePlayAsset(item.assetUrl)}
                              className="size-6 text-primary hover:bg-primary/10"
                            >
                              <Volume2 className="size-3" />
                            </Button>
                          )}
                        </div>
                      )}
                      {item.status === 'failed' && (
                        <Badge variant="destructive" className="text-[10px]" title={item.error}>
                          <AlertCircle className="mr-1 size-2.5" />
                          {t('queue.status_failed')}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Bottom Grid: Waiting Queue & History */}
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Waiting Queue */}
        <Card className="rounded-2xl border-border/70 shadow-xs">
          <CardHeader className="p-4 border-b bg-muted/20 flex flex-row items-center justify-between">
            <CardTitle className="text-xs font-bold text-foreground flex items-center gap-2">
              <ListOrdered className="size-3.5 text-primary" />
              <span>Hàng đợi đang chờ ({queuedJobs.length})</span>
            </CardTitle>
            <span className="text-[11px] text-muted-foreground">
              Tự động chạy tiếp theo
            </span>
          </CardHeader>
          <CardContent className="p-3.5 space-y-2">
            {queuedJobs.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">
                Không có Deck nào đang chờ.
              </p>
            ) : (
              queuedJobs.map((qJob: AudioDeckJob, idx: number) => (
                <div
                  key={qJob.id}
                  onClick={() => setSelectedJobId(qJob.id)}
                  className={`flex items-center justify-between p-2.5 rounded-xl border cursor-pointer transition-all ${
                    selectedJobId === qJob.id
                      ? 'border-primary/50 bg-primary/5 shadow-2xs'
                      : 'border-border/50 bg-card hover:bg-muted/30'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="flex size-5 items-center justify-center rounded-md bg-muted text-[10px] font-bold text-muted-foreground shrink-0">
                      #{idx + 1}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-foreground truncate">
                        {qJob.deckName}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        {qJob.items.length} mục • {qJob.mode === 'missing_and_broken' ? 'Bù thiếu/hỏng' : 'Toàn bộ'}
                      </p>
                    </div>
                  </div>

                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      onRemove(qJob.id)
                    }}
                    className="h-7 text-xs text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Completed History */}
        <Card className="rounded-2xl border-border/70 shadow-xs">
          <CardHeader className="p-4 border-b bg-muted/20 flex flex-row items-center justify-between">
            <CardTitle className="text-xs font-bold text-foreground flex items-center gap-2">
              <CheckCircle2 className="size-3.5 text-emerald-600" />
              <span>Lịch sử hoàn tất ({completedJobs.length})</span>
            </CardTitle>
            {completedJobs.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onClearCompleted}
                className="h-6 text-[11px] text-muted-foreground hover:text-foreground"
              >
                {t('queue.clear_history_button')}
              </Button>
            )}
          </CardHeader>
          <CardContent className="p-3.5 space-y-2">
            {completedJobs.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">
                Chưa có tác vụ nào hoàn tất trong phiên này.
              </p>
            ) : (
              completedJobs.map((cJob: AudioDeckJob) => (
                <div
                  key={cJob.id}
                  onClick={() => setSelectedJobId(cJob.id)}
                  className={`flex items-center justify-between p-2.5 rounded-xl border cursor-pointer transition-all ${
                    selectedJobId === cJob.id
                      ? 'border-primary/50 bg-primary/5 shadow-2xs'
                      : 'border-border/50 bg-card hover:bg-muted/30'
                  }`}
                >
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-foreground truncate">
                      {cJob.deckName}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {cJob.stats.completedItems} / {cJob.items.length} mục đã tạo thành công
                    </p>
                  </div>

                  <Badge
                    variant="outline"
                    className={`text-[10px] ${
                      cJob.status === 'completed'
                        ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30'
                        : 'bg-rose-500/10 text-rose-600 border-rose-500/30'
                    }`}
                  >
                    {cJob.status === 'completed' ? t('queue.status_completed') : t('queue.status_failed')}
                  </Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
