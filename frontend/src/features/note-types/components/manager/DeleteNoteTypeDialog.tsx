import { useTranslation } from 'react-i18next'
import { AlertCircle, LoaderCircle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
export interface DeleteNoteTypeDialogProps {
  noteType: { id: string; name: string } | null
  isOpen: boolean
  onClose: () => void
  isAdmin: boolean
  purgeNoteType: boolean
  onPurgeChange: (purge: boolean) => void
  onConfirmDelete: () => void
  isDeleting: boolean
}

export function DeleteNoteTypeDialog({
  noteType,
  isOpen,
  onClose,
  isAdmin,
  purgeNoteType,
  onPurgeChange,
  onConfirmDelete,
  isDeleting,
}: DeleteNoteTypeDialogProps) {
  const { t } = useTranslation('note_types')

  if (!noteType) return null

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('manager.delete_dialog.title')}</DialogTitle>
          <DialogDescription>
            {t('manager.delete_dialog.description', { name: noteType.name })}
          </DialogDescription>
        </DialogHeader>

        {isAdmin && (
          <div className="space-y-3 p-3 rounded-lg border border-destructive/20 bg-destructive/5 dark:bg-destructive/10">
            <div className="flex items-center gap-2">
              <input
                id="purge-notetype-checkbox"
                type="checkbox"
                checked={purgeNoteType}
                onChange={(e) => onPurgeChange(e.target.checked)}
                className="size-4 rounded border-input text-destructive focus:ring-destructive accent-destructive cursor-pointer"
              />
              <Label
                htmlFor="purge-notetype-checkbox"
                className="font-bold text-destructive cursor-pointer select-none"
              >
                {t('manager.delete_dialog.purge_label')}
              </Label>
            </div>
            {purgeNoteType && (
              <Alert variant="destructive" className="border-none bg-transparent p-0 flex items-start">
                <AlertCircle className="size-4 mt-0.5 text-destructive shrink-0" />
                <AlertDescription className="text-xs text-destructive/90 font-medium ml-2 leading-relaxed">
                  {t('manager.delete_dialog.purge_warning')}
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            {t('manager.delete_dialog.cancel')}
          </Button>
          <Button
            variant="destructive"
            disabled={isDeleting}
            onClick={onConfirmDelete}
          >
            {isDeleting ? <LoaderCircle className="animate-spin mr-1.5 size-4" /> : null}
            {purgeNoteType
              ? t('manager.delete_dialog.purge_btn')
              : t('manager.delete_dialog.delete_btn')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
