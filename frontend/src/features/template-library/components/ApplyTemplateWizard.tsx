import '@/shared/config/i18n'
import { useId } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { FieldMappingEditor } from '@/entities/card-template'
import { ApiError } from '@/shared/api/client'
import { useApplyTemplate, useApplyTemplateDialog } from '../hooks/useApplyTemplate'
import type { ApplyTemplateWizardProps, ApplyTemplateFormProps } from '../model/applyTemplate'
export type { ApplyTemplateWizardProps } from '../model/applyTemplate'

export function ApplyTemplateForm(props: ApplyTemplateFormProps) {
  const { t } = useTranslation('card_templates')
  const { t: mappingT } = useTranslation('template_mapping')
  const form = useApplyTemplate(props)
  const id = useId()
  const errorMessage = form.error instanceof ApiError && form.error.code === 'APPLICATION_EXISTS'
    ? t('apply_wizard.error_conflict')
    : form.error?.message
  return <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (form.step === 2) void form.submit() }}>
    <DialogHeader>
      <DialogTitle>{form.step === 1 ? t('apply_wizard.step1_title') : t('apply_wizard.step2_title')}</DialogTitle>
      <DialogDescription>{t('apply_wizard.description')}</DialogDescription>
    </DialogHeader>
    {form.noteTypes.isPending && <p role="status" className="text-muted-foreground">{t('apply_wizard.loading_note_types')}</p>}
    {form.noteTypes.isError && <Alert variant="destructive"><AlertDescription>
      {form.noteTypes.error.message}
      <Button type="button" variant="outline" className="mt-2" onClick={() => void form.noteTypes.refetch()}>{t('apply_wizard.retry')}</Button>
    </AlertDescription></Alert>}
    {form.noteTypes.data?.items.length === 0 && <div className="space-y-2 text-muted-foreground">
      <p>{t('apply_wizard.empty_note_types')}</p>
      <Button type="button" variant="outline" onClick={() => void form.noteTypes.refetch()}>{t('apply_wizard.reload')}</Button>
    </div>}
    {props.initialNoteTypeId && form.noteTypes.isSuccess && !form.selected && <Alert variant="destructive"><AlertDescription>{mappingT('unavailable_note_type')}</AlertDescription></Alert>}
    {!props.initialNoteTypeId && Boolean(form.noteTypes.data?.items.length) && <div className="space-y-2">
      <Label htmlFor={`${id}-note-type`}>{t('apply_wizard.note_type_label')}</Label>
      <NativeSelect id={`${id}-note-type`} className="w-full" value={form.selectedId} disabled={form.pending}
        onChange={(event) => form.selectNoteType(event.target.value)}>
        <NativeSelectOption value="">{t('apply_wizard.select_placeholder')}</NativeSelectOption>
        {form.noteTypes.data!.items.map((item) => <NativeSelectOption key={item.id} value={item.id}>
          {item.name}{item.is_marketplace_install ? t('apply_wizard.marketplace_suffix') : ''}
        </NativeSelectOption>)}
      </NativeSelect>
      {form.selected?.is_marketplace_install && <Badge variant="secondary">{t('apply_wizard.marketplace_badge')}</Badge>}
    </div>}
    {props.initialNoteTypeId && form.selected?.is_marketplace_install && <Badge variant="secondary">{t('apply_wizard.marketplace_badge')}</Badge>}
    {form.step === 2 && form.selected && <>
      <div className="space-y-2">
        <Label htmlFor={`${id}-name`}>{mappingT('display_name')}</Label>
        <Input id={`${id}-name`} value={form.displayName} maxLength={255} disabled={form.pending}
          aria-invalid={!form.displayName.trim() || (form.error instanceof ApiError && form.error.field === 'display_name')}
          onChange={(event) => form.setDisplayName(event.target.value)} />
      </div>
      <FieldMappingEditor inputs={props.template.input_schema} fields={form.selected.field_defs}
        bindings={form.bindings} onChange={form.setBindings} issues={form.issues} disabled={form.pending} />
    </>}
    {props.template.archived_at && <p className="text-muted-foreground">{t('apply_wizard.unarchive_warning')}</p>}
    {errorMessage && <Alert variant="destructive"><AlertDescription>{errorMessage}</AlertDescription></Alert>}
    {form.error instanceof ApiError && form.error.code === 'APPLICATION_EXISTS' && <div className="space-y-2">
      {form.existingApplications.data?.items.filter((item) => item.template_id === props.template.id).map((item) => <Button key={item.id} variant="outline" asChild>
        <Link to={`/flashcards/note-types/${encodeURIComponent(form.selectedId)}/templates/${encodeURIComponent(item.id)}`} onClick={() => props.onOpenChange(false)}>
          {mappingT('open_existing')}: {item.display_name || item.template.name}
        </Link>
      </Button>)}
      {form.existingApplications.isError && <Button type="button" variant="outline" onClick={() => void form.existingApplications.refetch()}>{mappingT('retry')}</Button>}
    </div>}
    <DialogFooter>
      {props.onBack ? <Button type="button" variant="outline" disabled={form.pending} onClick={props.onBack}>{mappingT('back_to_library')}</Button>
        : form.step === 2 && !props.initialNoteTypeId && <Button type="button" variant="outline" disabled={form.pending} onClick={() => form.setStep(1)}>{t('apply_wizard.back')}</Button>}
      <Button type="button" variant="outline" disabled={form.pending} onClick={() => props.onOpenChange(false)}>{t('apply_wizard.cancel')}</Button>
      {form.step === 1
        ? <Button key="continue" type="button" disabled={!form.selected} onClick={(event) => {
          // Cancel native activation before React renders the submit button for step two.
          event.preventDefault()
          form.setStep(2)
        }}>{t('apply_wizard.continue')}</Button>
        : <Button key="attach" type="submit" disabled={form.invalid || form.pending}>{form.pending ? t('apply_wizard.attaching') : props.submitLabel ?? t('apply_wizard.attach')}</Button>}
    </DialogFooter>
  </form>
}

export function ApplyTemplateWizard({ open, ...props }: ApplyTemplateWizardProps) {
  const { pending, setPending } = useApplyTemplateDialog(open)
  return <Dialog open={open} onOpenChange={(nextOpen) => { if (!pending) props.onOpenChange(nextOpen) }}>
    {open && <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-xl" showCloseButton={!pending}
      onEscapeKeyDown={(event) => { if (pending) event.preventDefault() }} onPointerDownOutside={(event) => { if (pending) event.preventDefault() }}>
      <ApplyTemplateForm key={`${props.template.id}:${props.initialNoteTypeId ?? ''}:${props.initialOccurrenceKey ?? 'compat'}`} {...props} onPendingChange={setPending} />
    </DialogContent>}
  </Dialog>
}
