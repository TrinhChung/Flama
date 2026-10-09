import '@/shared/config/i18n'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LoaderCircle, SlidersHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { TemplateBindings } from '@/entities/card-template'
import { PageError } from '@/shared/components/PageState'
import { TemplateInputBindingEditor } from './TemplateInputBindingEditor'
import type { StudyTemplateMapping, StudyTemplatePreparationEntry } from '../hooks/useStudyTemplatePreparation'

export type StudyTemplateFieldsDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  templateName?: string | null
  entry?: StudyTemplatePreparationEntry | null
  mapping?: StudyTemplateMapping | null
  loading?: boolean
  saving?: boolean
  error?: unknown
  /** The open study session is reopened with the saved map. */
  appliesToSession?: boolean
  onSave: (bindings: TemplateBindings | null) => void
}

export function StudyTemplateFieldsDialog({
  open,
  onOpenChange,
  templateName,
  entry,
  mapping,
  loading = false,
  saving = false,
  error,
  appliesToSession = false,
  onSave,
}: StudyTemplateFieldsDialogProps) {
  const { t } = useTranslation('study')
  return (
    <Dialog open={open} onOpenChange={(next) => { if (!saving) onOpenChange(next) }}>
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 p-0 sm:max-w-2xl">
        <DialogHeader className="border-b border-border/70 px-5 pt-5 pb-4 pr-12">
          <DialogTitle className="flex items-center gap-2 text-base font-bold">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400">
              <SlidersHorizontal className="size-4" aria-hidden="true" />
            </span>
            {t('fields.title')}
          </DialogTitle>
          <DialogDescription className="text-xs leading-5">
            {t('fields.description', { name: templateName || '' })}
          </DialogDescription>
        </DialogHeader>
        {entry && mapping ? (
          <FieldsForm
            entry={entry}
            mapping={mapping}
            saving={saving}
            error={error}
            appliesToSession={appliesToSession}
            onCancel={() => onOpenChange(false)}
            onSave={onSave}
          />
        ) : (
          <div className="px-5 py-8">
            {loading || !error ? (
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                <LoaderCircle className="size-4 animate-spin text-primary" aria-hidden="true" />
                {t('fields.loading')}
              </div>
            ) : <PageError error={error} />}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function FieldsForm({
  entry,
  mapping,
  saving,
  error,
  appliesToSession,
  onCancel,
  onSave,
}: {
  entry: StudyTemplatePreparationEntry
  mapping: StudyTemplateMapping
  saving: boolean
  error?: unknown
  appliesToSession: boolean
  onCancel: () => void
  onSave: (bindings: TemplateBindings | null) => void
}) {
  const { t } = useTranslation('study')
  // The dialog content remounts on every open, so the draft starts fresh.
  const [draft, setDraft] = useState<TemplateBindings>(() => ({ ...mapping.inputBindings }))
  return (
    <>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {error ? <PageError error={error} /> : null}
        {entry.input_schema.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('fields.no_inputs')}</p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">{t('fields.unmapped_hint')}</p>
            <TemplateInputBindingEditor
              inputSchema={entry.input_schema}
              fieldDefs={entry.field_defs}
              value={draft}
              onChange={setDraft}
              staleInputs={mapping.staleInputs}
              disabled={saving}
            />
          </>
        )}
      </div>
      <DialogFooter className="mx-0 mb-0 flex-col gap-2 rounded-b-xl border-t border-border/70 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-[11px] text-muted-foreground">{appliesToSession ? t('fields.apply_hint') : t('fields.remember_hint')}</p>
        <div className="flex flex-wrap justify-end gap-2">
          {mapping.customized ? (
            <Button type="button" variant="ghost" size="sm" disabled={saving} onClick={() => onSave(null)}>
              {t('fields.reset')}
            </Button>
          ) : null}
          <Button type="button" variant="outline" size="sm" disabled={saving} onClick={onCancel}>
            {t('fields.cancel')}
          </Button>
          <Button type="button" size="sm" disabled={saving || entry.input_schema.length === 0} onClick={() => onSave(draft)}>
            {appliesToSession ? t('fields.save_and_apply') : t('fields.save')}
          </Button>
        </div>
      </DialogFooter>
    </>
  )
}
