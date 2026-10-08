import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation } from '@tanstack/react-query'
import { Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import '@/shared/config/i18n'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { deleteNoteTypeTemplate, renameNoteTypeTemplate } from '@/entities/card-template'
import { ConfirmDialog } from '@/shared/ui'
import { templateErrorMessage } from '../lib/templateErrors'

export type TemplateManagementBarProps = {
  noteTypeId: string
  template: { id: string; name: string; is_default?: boolean } | null
  noteCount: number | null // null = đang tải hoặc lỗi
  templateCount: number // tổng số template của NoteType
  onRenamed: () => void // trang invalidate query
  onDeleted: (deletedTemplateId: string) => void // trang chọn template khác + invalidate
}

export function TemplateManagementBar({
  noteTypeId,
  template,
  noteCount,
  templateCount,
  onRenamed,
  onDeleted,
}: TemplateManagementBarProps) {
  const { t } = useTranslation('note_types')
  const [isRenameOpen, setIsRenameOpen] = useState(false)
  const [renameValue, setRenameValue] = useState('')
  const [renameError, setRenameError] = useState<string | null>(null)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)

  const isInvalidNoteTypeId = !noteTypeId.trim()

  const renameMutation = useMutation({
    mutationFn: (newName: string) => {
      if (isInvalidNoteTypeId) {
        throw new Error('noteTypeId is required')
      }
      return renameNoteTypeTemplate(noteTypeId, template?.id ?? '', newName)
    },
    onSuccess: () => {
      toast.success(t('template_bar.messages.rename_success'))
      setIsRenameOpen(false)
      onRenamed()
    },
    onError: (error: unknown) => {
      toast.error(t('template_bar.messages.rename_error'), {
        description: templateErrorMessage(error),
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => {
      if (isInvalidNoteTypeId) {
        throw new Error('noteTypeId is required')
      }
      return deleteNoteTypeTemplate(noteTypeId, template?.id ?? '')
    },
    onSuccess: () => {
      toast.success(t('template_bar.messages.delete_success'))
      setIsDeleteOpen(false)
      if (template) {
        onDeleted(template.id)
      }
    },
    onError: (error: unknown) => {
      toast.error(t('template_bar.messages.delete_error'), {
        description: templateErrorMessage(error),
      })
    },
  })

  if (!template) {
    return null
  }

  const deleteDisabled = template.is_default || templateCount <= 1
  const deleteDisabledReason = template.is_default
    ? t('template_bar.cannot_delete_default')
    : templateCount <= 1
      ? t('template_bar.cannot_delete_single')
      : null

  const openRename = () => {
    if (isInvalidNoteTypeId || renameMutation.isPending) return
    setRenameValue(template.name)
    setRenameError(null)
    setIsRenameOpen(true)
  }

  const openDelete = () => {
    if (isInvalidNoteTypeId || deleteDisabled || deleteMutation.isPending) return
    setIsDeleteOpen(true)
  }

  const handleRenameSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (isInvalidNoteTypeId || renameMutation.isPending) return
    const trimmed = renameValue.trim()
    if (!trimmed) {
      setRenameError(t('template_bar.rename_dialog.error_empty'))
      return
    }
    if (trimmed.length > 255) {
      setRenameError(t('template_bar.rename_dialog.error_max_length'))
      return
    }
    if (trimmed === template.name) {
      setIsRenameOpen(false)
      return
    }
    renameMutation.mutate(trimmed)
  }

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        {template.is_default ? <Badge variant="secondary">{t('template_bar.default_badge')}</Badge> : null}
        <Badge variant="outline">
          {noteCount == null
            ? t('template_bar.note_count_loading')
            : t('template_bar.note_count', { count: noteCount })}
        </Badge>
        <div className="ml-auto flex items-center gap-1.5">
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2.5 text-xs font-semibold rounded-lg gap-1.5"
            onClick={openRename}
          >
            <Pencil className="size-3.5" aria-hidden="true" /> {t('template_bar.rename_btn')}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2.5 text-xs font-semibold text-destructive hover:bg-destructive/10 rounded-lg gap-1.5"
            onClick={openDelete}
            disabled={deleteDisabled}
            title={deleteDisabledReason ?? undefined}
          >
            <Trash2 className="size-3.5" aria-hidden="true" /> {t('template_bar.delete_btn')}
          </Button>
        </div>
      </div>

      {isRenameOpen && (
        <Dialog
          open={isRenameOpen}
          onOpenChange={(open) => {
            if (renameMutation.isPending) return
            setIsRenameOpen(open)
          }}
        >
          <DialogContent className="sm:max-w-md" showCloseButton={!renameMutation.isPending}>
            <form onSubmit={handleRenameSubmit}>
              <DialogHeader>
                <DialogTitle>{t('template_bar.rename_dialog.title')}</DialogTitle>
              </DialogHeader>
              <div className="py-4 space-y-2">
                <Label htmlFor="template-name-input">{t('template_bar.rename_dialog.label')}</Label>
                <Input
                  id="template-name-input"
                  value={renameValue}
                  onChange={(e) => {
                    setRenameValue(e.target.value)
                    if (renameError) setRenameError(null)
                  }}
                  disabled={renameMutation.isPending}
                  autoFocus
                />
                {renameError ? (
                  <p className="text-xs text-destructive">{renameError}</p>
                ) : null}
              </div>
              <DialogFooter className="gap-2 sm:gap-0">
                <Button
                  type="button"
                  variant="outline"
                  disabled={renameMutation.isPending}
                  onClick={() => setIsRenameOpen(false)}
                >
                  {t('template_bar.rename_dialog.cancel')}
                </Button>
                <Button type="submit" disabled={renameMutation.isPending}>
                  {t('template_bar.rename_dialog.submit')}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}

      {isDeleteOpen && (
        <ConfirmDialog
          open={isDeleteOpen}
          onOpenChange={(open) => {
            if (deleteMutation.isPending) return
            setIsDeleteOpen(open)
          }}
          variant="destructive"
          title={t('template_bar.delete_dialog.title', { name: template.name })}
          description={t('template_bar.delete_dialog.description')}
          confirmText={t('template_bar.delete_dialog.confirm')}
          cancelText={t('template_bar.delete_dialog.cancel')}
          isLoading={deleteMutation.isPending}
          onConfirm={async () => {
            if (isInvalidNoteTypeId) return
            try {
              await deleteMutation.mutateAsync()
            } catch {
              // Handled in onError
            }
          }}
        >
          <p className="text-sm text-muted-foreground">
            {t('template_bar.delete_dialog.note_count_warning', { count: noteCount ?? 0 })}
          </p>
        </ConfirmDialog>
      )}
    </>
  )
}
