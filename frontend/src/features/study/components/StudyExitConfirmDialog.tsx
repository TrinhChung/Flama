import { CheckCircle2, LoaderCircle, LogOut, Play } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

export interface StudyExitConfirmDialogProps {
  open: boolean
  eventsCount: number
  isCommitting?: boolean
  onSaveAndExit: () => void
  onContinueStudy: () => void
  onDiscardAndExit: () => void
}

export function StudyExitConfirmDialog({
  open,
  eventsCount,
  isCommitting = false,
  onSaveAndExit,
  onContinueStudy,
  onDiscardAndExit,
}: StudyExitConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(nextOpen) => {
      if (!nextOpen && !isCommitting) {
        onContinueStudy()
      }
    }}>
      <DialogContent
        className="sm:max-w-md p-6"
        showCloseButton={!isCommitting}
      >
        <DialogHeader className="space-y-3">
          <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-amber-500/10 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400">
            <LogOut className="size-6" aria-hidden="true" />
          </div>
          <DialogTitle className="text-center text-xl font-bold text-foreground">
            Kết thúc phiên học?
          </DialogTitle>
          <DialogDescription className="text-center text-sm leading-relaxed text-muted-foreground">
            {eventsCount > 0 ? (
              <>
                Bạn đã trả lời{' '}
                <strong className="font-semibold text-foreground">
                  {eventsCount} thẻ
                </strong>{' '}
                trong phiên này chưa đồng bộ lên máy chủ. Bạn có muốn lưu lại tiến độ trước khi rời đi không?
              </>
            ) : (
              'Bạn có chắc chắn muốn rời khỏi phiên học hiện tại không?'
            )}
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="mt-4 flex flex-col-reverse gap-2 sm:flex-col sm:gap-2">
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              disabled={isCommitting}
              onClick={onContinueStudy}
              className="w-full sm:w-auto"
            >
              <Play className="mr-2 size-4" aria-hidden="true" />
              Tiếp tục học
            </Button>
            {eventsCount > 0 ? (
              <Button
                type="button"
                disabled={isCommitting}
                onClick={onSaveAndExit}
                className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700 text-white font-semibold dark:bg-emerald-600 dark:hover:bg-emerald-700"
              >
                {isCommitting ? (
                  <LoaderCircle className="mr-2 size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="mr-2 size-4" aria-hidden="true" />
                )}
                {isCommitting ? 'Đang lưu tiến độ…' : 'Lưu & Thoát'}
              </Button>
            ) : (
              <Button
                type="button"
                disabled={isCommitting}
                onClick={onDiscardAndExit}
                variant="default"
                className="w-full sm:w-auto"
              >
                Thoát phiên
              </Button>
            )}
          </div>

          {eventsCount > 0 && (
            <div className="text-center pt-1">
              <button
                type="button"
                disabled={isCommitting}
                onClick={onDiscardAndExit}
                className="text-xs text-muted-foreground hover:text-rose-600 dark:hover:text-rose-400 underline underline-offset-4 transition disabled:opacity-50"
              >
                Thoát không lưu tiến độ này
              </button>
            </div>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}