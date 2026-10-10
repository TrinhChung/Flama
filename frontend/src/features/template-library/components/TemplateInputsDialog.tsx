import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { TemplateInputSpec } from '@/entities/card-template'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ConfirmDialog } from '@/shared/ui'
import { TemplateInputSchemaEditor } from './TemplateInputSchemaEditor'
import { inputSchemaIssues } from '../lib/inputSchemaValidation'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  value: TemplateInputSpec[]
  persistedKeys: string[]
  onApply: (inputs: TemplateInputSpec[]) => void
  frontHtml: string
  backHtml: string
  applicationCount: number
  onDirtyChange?: (dirty: boolean) => void
}

// Mounted once per opening so edits remain local until Apply.
export function TemplateInputsDialog({ open, onOpenChange, value, onApply, onDirtyChange, ...editorProps }: Props) {
  const { t } = useTranslation('card_templates')
  const [draft, setDraft] = useState(() => value.map((input) => ({ ...input })))
  const [discardOpen, setDiscardOpen] = useState(false)
  const dirty = JSON.stringify(value) !== JSON.stringify(draft)
  useEffect(() => { onDirtyChange?.(dirty); return () => onDirtyChange?.(false) }, [dirty, onDirtyChange])
  const close = () => onOpenChange(false)
  return <>
    <Dialog open={open} onOpenChange={(next) => { if (!next && dirty) setDiscardOpen(true); else onOpenChange(next) }}>
      <DialogContent className="flex h-[100dvh] max-h-[100dvh] max-w-full flex-col rounded-none sm:h-[min(720px,85dvh)] sm:max-h-[85dvh] sm:max-w-[940px] sm:rounded-2xl">
        <DialogHeader className="pr-8"><DialogTitle>{t('input_schema.title')}</DialogTitle><DialogDescription>{t('setup.inputs_description')}</DialogDescription></DialogHeader>
        <TemplateInputSchemaEditor value={draft} onChange={setDraft} {...editorProps} />
        <DialogFooter className="shrink-0"><Button variant="outline" onClick={close}>{t('setup.cancel')}</Button><Button disabled={inputSchemaIssues(draft).length > 0} onClick={() => { onApply(draft); close() }}>{t('setup.apply_draft')}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
    <ConfirmDialog open={discardOpen} onOpenChange={setDiscardOpen} title={t('setup.discard_inputs_title')} description={t('setup.discard_inputs_description')} cancelText={t('setup.keep_editing')} confirmText={t('setup.discard')} onConfirm={() => { setDiscardOpen(false); close() }} />
  </>
}
