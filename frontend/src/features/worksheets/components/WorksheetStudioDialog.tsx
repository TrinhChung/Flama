import type { ReactNode } from 'react'
import { LoaderCircle, Printer, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'

const STUDIO_DIALOG_CLASS =
  'fixed inset-0 z-50 flex flex-col w-full h-[100dvh] max-w-none translate-x-0 translate-y-0 top-0 left-0 p-0 gap-0 overflow-hidden rounded-none border-0 ring-0 bg-background sm:fixed sm:top-1/2 sm:left-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 sm:w-[98vw] sm:max-w-none sm:h-[96vh] sm:rounded-2xl sm:border sm:border-border sm:shadow-2xl sm:ring-1 sm:ring-foreground/10'

export interface WorksheetStudioDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}

/**
 * The single full-screen dialog frame of the studio. Loading states render
 * inside it, so opening the studio animates exactly one dialog.
 */
export function WorksheetStudioDialog({ open, onOpenChange, children }: WorksheetStudioDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false} className={STUDIO_DIALOG_CLASS}>
        {children}
      </DialogContent>
    </Dialog>
  )
}

/** Placeholder shown inside the studio frame while its code or translations load. */
export function WorksheetStudioLoadState({
  onOpenChange,
  failed = false,
}: {
  onOpenChange: (open: boolean) => void
  failed?: boolean
}) {
  // Only the preloaded `common` namespace: suspending here would escape the studio frame.
  const { t } = useTranslation('common')
  return (
    <div className="relative flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="absolute top-3 right-3 size-8 rounded-lg text-muted-foreground hover:text-foreground"
        onClick={() => onOpenChange(false)}
        aria-label={t('close')}
        title={t('close')}
      >
        <X className="size-4" />
      </Button>
      <div className="size-10 rounded-xl bg-orange-500/15 text-orange-600 dark:text-orange-400 flex items-center justify-center shadow-xs">
        <Printer className="size-5" />
      </div>
      <DialogTitle className="text-base font-bold text-foreground">{t('worksheet_loader.title')}</DialogTitle>
      <DialogDescription className="text-xs text-muted-foreground">
        {failed ? t('worksheet_loader.failed') : t('worksheet_loader.loading')}
      </DialogDescription>
      {!failed && (
        <div role="status" className="flex justify-center py-2">
          <LoaderCircle className="size-6 animate-spin text-muted-foreground" aria-hidden="true" />
          <span className="sr-only">{t('worksheet_loader.sr_loading')}</span>
        </div>
      )}
    </div>
  )
}
