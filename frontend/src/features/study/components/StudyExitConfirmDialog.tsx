import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation('study')

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && !isCommitting) {
          onContinueStudy()
        }
      }}
    >
      <DialogContent
        className="sm:max-w-md p-6 rounded-2xl border-border/80"
        showCloseButton={!isCommitting}
      >
        <DialogHeader className="space-y-3">
          <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-orange-500/10 text-orange-600 dark:bg-orange-500/20 dark:text-orange-400 border border-orange-500/20 shadow-xs">
            <LogOut className="size-6" aria-hidden="true" />
          </div>
          <DialogTitle className="text-center text-xl font-bold text-foreground">
            {t('exit_dialog.title')}
          </DialogTitle>
          <DialogDescription className="text-center text-sm leading-relaxed text-muted-foreground">
            {eventsCount > 0
              ? t('exit_dialog.uncommitted_description', { eventsCount })
              : t('exit_dialog.generic_description')}
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="mt-4 sm:mt-6 -mx-6 -mb-6 p-4 sm:p-5 flex flex-col gap-3 rounded-b-2xl border-t bg-muted/40 sm:flex-col">
          {eventsCount > 0 ? (
            <div className="flex flex-col sm:flex-row-reverse sm:items-center sm:justify-between gap-3 w-full">
              <div className="flex flex-col sm:flex-row gap-2 sm:justify-end w-full sm:w-auto">
                <Button
                  type="button"
                  disabled={isCommitting}
                  onClick={onSaveAndExit}
                  className="w-full sm:w-auto h-11 sm:h-10 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-xs transition-all text-sm order-1 sm:order-2"
                >
                  {isCommitting ? (
                    <LoaderCircle className="mr-2 size-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <CheckCircle2 className="mr-2 size-4" aria-hidden="true" />
                  )}
                  {isCommitting
                    ? t('exit_dialog.saving_progress')
                    : t('exit_dialog.save_and_exit')}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={isCommitting}
                  onClick={onContinueStudy}
                  className="w-full sm:w-auto h-11 sm:h-10 rounded-xl border-border/80 font-medium text-sm order-2 sm:order-1 hover:bg-muted"
                >
                  <Play className="mr-2 size-4" aria-hidden="true" />
                  {t('exit_dialog.continue_study')}
                </Button>
              </div>

              <div className="text-center sm:text-left pt-1 sm:pt-0">
                <button
                  type="button"
                  disabled={isCommitting}
                  onClick={onDiscardAndExit}
                  className="min-h-[36px] inline-flex items-center justify-center text-xs text-muted-foreground hover:text-rose-600 dark:hover:text-rose-400 underline underline-offset-4 transition disabled:opacity-50 px-1"
                >
                  {t('exit_dialog.discard_and_exit')}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row sm:justify-end gap-2.5 w-full">
              <Button
                type="button"
                variant="outline"
                disabled={isCommitting}
                onClick={onContinueStudy}
                className="w-full sm:w-auto h-11 sm:h-10 rounded-xl border-border/80 font-medium text-sm order-2 sm:order-1"
              >
                <Play className="mr-2 size-4" aria-hidden="true" />
                {t('exit_dialog.continue_study')}
              </Button>
              <Button
                type="button"
                disabled={isCommitting}
                onClick={onDiscardAndExit}
                variant="destructive"
                className="w-full sm:w-auto h-11 sm:h-10 rounded-xl font-semibold text-sm order-1 sm:order-2"
              >
                {t('exit_dialog.exit_session')}
              </Button>
            </div>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}