import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ConfirmDialog } from '@/shared/ui'
import type { TemplateLibraryDraft } from '../model/useTemplateLibraryEditor'

export function TemplateInformationDialog({ draft, onApply, onClose, onDirtyChange }: {
  draft: TemplateLibraryDraft
  onApply: (patch: Partial<TemplateLibraryDraft>) => void
  onClose: () => void
  onDirtyChange: (dirty: boolean) => void
}) {
  const { t } = useTranslation('card_templates')
  const [info, setInfo] = useState({ name: draft.name, primary_category: draft.primary_category, description: draft.description })
  const [discardOpen, setDiscardOpen] = useState(false)
  const dirty = info.name !== draft.name || info.description !== draft.description || info.primary_category !== draft.primary_category
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false) }, [dirty, onDirtyChange])
  return <>
    <Dialog open onOpenChange={(open) => { if (!open) { if (dirty) setDiscardOpen(true); else onClose() } }}><DialogContent className="sm:max-w-lg">
      <DialogHeader><DialogTitle>{t('setup.information')}</DialogTitle><DialogDescription>{t('setup.information_description')}</DialogDescription></DialogHeader>
      <div className="space-y-4">
        <div className="space-y-2"><Label htmlFor="library-template-name">{t('detail.name_label')}</Label><Input id="library-template-name" value={info.name} maxLength={255} onChange={(event) => setInfo({ ...info, name: event.target.value })} /></div>
        <div className="space-y-2"><Label htmlFor="library-template-category">{t('detail.category_label')}</Label><Input id="library-template-category" value={info.primary_category} maxLength={120} onChange={(event) => setInfo({ ...info, primary_category: event.target.value })} /></div>
        <div className="space-y-2"><Label htmlFor="library-template-description">{t('detail.description_label')}</Label><Textarea id="library-template-description" value={info.description} onChange={(event) => setInfo({ ...info, description: event.target.value })} /></div>
      </div>
      <DialogFooter><Button variant="outline" onClick={onClose}>{t('setup.cancel')}</Button><Button disabled={!info.name.trim()} onClick={() => { onApply(info); onClose() }}>{t('setup.apply_draft')}</Button></DialogFooter>
    </DialogContent></Dialog>
    <ConfirmDialog open={discardOpen} onOpenChange={setDiscardOpen} title={t('setup.discard_information_title')} description={t('setup.discard_information_description')} cancelText={t('setup.keep_editing')} confirmText={t('setup.discard')} onConfirm={onClose} />
  </>
}
