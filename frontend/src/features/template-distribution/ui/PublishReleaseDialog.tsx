import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

export interface PublishReleaseDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onPublish: (body: { version_label: string; change_note?: string }) => Promise<void>
  isPublishing: boolean
  defaultVersionLabel?: string
}

export function PublishReleaseDialog({
  open,
  onOpenChange,
  onPublish,
  isPublishing,
  defaultVersionLabel = '',
}: PublishReleaseDialogProps) {
  const { t } = useTranslation('card_templates')
  const [versionLabel, setVersionLabel] = useState(defaultVersionLabel)
  const [changeNote, setChangeNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedLabel = versionLabel.trim()
    if (!trimmedLabel) {
      setError(t('distribution.version_label_required'))
      return
    }
    setError(null)
    try {
      await onPublish({
        version_label: trimmedLabel,
        change_note: changeNote.trim() || undefined,
      })
      onOpenChange(false)
      setVersionLabel('')
      setChangeNote('')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('distribution.publish_error'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('distribution.dialog_publish_title')}</DialogTitle>
          <DialogDescription>{t('distribution.dialog_publish_desc')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="release-version-label">{t('distribution.version_label')}</Label>
            <Input
              id="release-version-label"
              placeholder={t('distribution.version_label_placeholder')}
              value={versionLabel}
              onChange={(e) => {
                setVersionLabel(e.target.value)
                if (error) setError(null)
              }}
              disabled={isPublishing}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="release-change-note">{t('distribution.change_note_label')}</Label>
            <Textarea
              id="release-change-note"
              placeholder={t('distribution.change_note_placeholder')}
              value={changeNote}
              onChange={(e) => setChangeNote(e.target.value)}
              disabled={isPublishing}
              rows={3}
            />
          </div>

          {error && <p className="text-xs text-destructive">{error}</p>}

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPublishing}
            >
              {t('setup.cancel')}
            </Button>
            <Button type="submit" disabled={isPublishing || !versionLabel.trim()}>
              {isPublishing ? t('distribution.publishing') : t('distribution.btn_publish')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
