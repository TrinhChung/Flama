import { CheckCircle2, Layers, LayoutTemplate, ShieldCheck, Sparkles } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { CascadingSyncSummaryModalProps } from '../model/types'

export function CascadingSyncSummaryModal({
  open,
  onOpenChange,
  summary,
  onStartStudy,
  onClose,
}: CascadingSyncSummaryModalProps) {
  if (!summary) return null

  const handleClose = () => {
    onOpenChange(false)
    onClose?.()
  }

  const handleStartStudy = () => {
    onStartStudy?.()
    onOpenChange(false)
  }

  const versionText = summary.from_version_label
    ? `${summary.from_version_label} → ${summary.version_label}`
    : summary.version_label

  const totalCardsUpdated =
    summary.cards_updated ??
    (summary.cards_added ?? 0) + (summary.cards_modified ?? 0) + (summary.cards_removed ?? 0)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="cascading-sync-modal"
        className="max-w-lg rounded-2xl sm:p-6 space-y-4"
      >
        <DialogHeader className="text-left space-y-2">
          <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="size-6 shrink-0" />
            <DialogTitle className="text-lg font-bold text-foreground">
              Cập nhật Deck thành công ({versionText})
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            Bộ thẻ <span className="font-semibold text-foreground break-words" title={summary.deck_title}>{summary.deck_title}</span> đã được
            tự động đồng bộ đầy đủ cấu trúc Note Types và Templates đi kèm trong 1 click.
          </DialogDescription>
        </DialogHeader>

        {/* Prominent SRS Safety Reassurance Banner */}
        <div
          data-testid="srs-progress-guarantee"
          className="flex items-start gap-2 sm:gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 sm:p-4 text-xs text-emerald-900 dark:text-emerald-200"
        >
          <ShieldCheck className="size-5 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
          <div className="space-y-0.5">
            <p className="font-semibold text-emerald-800 dark:text-emerald-300">
              Toàn bộ tiến độ học (SRS / Flashcards) và lịch sử ôn tập được bảo toàn 100%
            </p>
            <p className="text-[11px] text-emerald-700/90 dark:text-emerald-300/80">
              {summary.progress_preserved_count.toLocaleString()} thẻ học giữ nguyên vẹn chu kỳ ôn tập,
              mức độ ghi nhớ (stability) và lịch sử đánh giá.
            </p>
          </div>
        </div>

        {/* Summary Stat Cards & List */}
        <div className="space-y-3 rounded-xl border bg-muted/20 p-3 sm:p-4 text-xs">
          {/* Synchronized Cards Stat */}
          <div
            data-testid="cards-sync-stat"
            className="flex flex-wrap items-center justify-between gap-1 pb-2 sm:pb-3 border-b"
          >
            <span className="font-semibold text-foreground">Thẻ học đã đồng bộ</span>
            <div className="flex items-center gap-2">
              <span className="font-medium text-foreground">
                {totalCardsUpdated.toLocaleString()} thẻ đã cập nhật
              </span>
              {(summary.cards_added !== undefined ||
                summary.cards_modified !== undefined ||
                summary.cards_removed !== undefined) && (
                <div className="flex items-center gap-1.5 font-mono text-[11px]">
                  {summary.cards_added !== undefined && (
                    <span className="text-emerald-600 dark:text-emerald-400">
                      +{summary.cards_added}
                    </span>
                  )}
                  {summary.cards_modified !== undefined && (
                    <span className="text-blue-600 dark:text-blue-400">
                      ~{summary.cards_modified}
                    </span>
                  )}
                  {summary.cards_removed !== undefined && (
                    <span className="text-rose-500 dark:text-rose-400">
                      -{summary.cards_removed}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Note Types Updated List */}
          <div data-testid="note-types-sync-list" className="space-y-1.5">
            <div className="flex items-center gap-1.5 font-semibold text-muted-foreground">
              <Layers className="size-3.5" />
              <span>Note Types đã cập nhật ({summary.note_types_updated.length})</span>
            </div>
            {summary.note_types_updated.length === 0 ? (
              <p className="pl-5 text-muted-foreground text-[11px]">Không có thay đổi cấu trúc Loại thẻ.</p>
            ) : (
              summary.note_types_updated.map((nt) => (
                <div
                  key={nt.id}
                  className="flex items-center justify-between pl-5 text-muted-foreground"
                >
                  <span
                    className="text-foreground font-medium truncate max-w-[200px] sm:max-w-xs"
                    title={nt.name}
                  >
                    {nt.name}
                  </span>
                  <Badge variant="outline" className="text-[10px] h-4 font-mono">
                    {nt.version}
                  </Badge>
                </div>
              ))
            )}
          </div>

          {/* Templates Updated List */}
          <div data-testid="templates-sync-list" className="space-y-1.5 pt-1">
            <div className="flex items-center gap-1.5 font-semibold text-muted-foreground">
              <LayoutTemplate className="size-3.5" />
              <span>Templates đã cập nhật ({summary.templates_updated.length})</span>
            </div>
            {summary.templates_updated.length === 0 ? (
              <p className="pl-5 text-muted-foreground text-[11px]">Không có thay đổi Mẫu thẻ.</p>
            ) : (
              summary.templates_updated.map((tpl) => (
                <div
                  key={tpl.id}
                  className="flex items-center justify-between pl-5 text-muted-foreground"
                >
                  <span
                    className="text-foreground font-medium truncate max-w-[200px] sm:max-w-xs"
                    title={tpl.name}
                  >
                    {tpl.name}
                  </span>
                  <span className="font-mono text-[11px] text-primary">
                    {tpl.from_version ? `${tpl.from_version} → ${tpl.to_version}` : tpl.to_version}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Modal Actions */}
        <DialogFooter className="flex flex-col sm:flex-row gap-2 pt-2">
          <Button
            variant="outline"
            data-testid="close-modal-btn"
            onClick={handleClose}
            className="w-full sm:w-auto h-9 sm:h-8"
          >
            Đóng
          </Button>
          <Button
            data-testid="start-study-btn"
            onClick={handleStartStudy}
            className="w-full sm:w-auto h-9 sm:h-8 gap-1.5"
          >
            <Sparkles className="size-3.5" />
            <span>Bắt đầu học ngay</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
