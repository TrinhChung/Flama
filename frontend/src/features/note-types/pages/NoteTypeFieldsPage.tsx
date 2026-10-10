import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { ArrowLeft, BookOpen, LoaderCircle, Pencil, Save, Share2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import { useUnsavedChangesGuard } from '@/shared/hooks/useUnsavedChangesGuard'
import { cardTemplateQueryKeys, fetchTemplateApplications } from '@/entities/card-template'
import { useNoteTypeFields } from '../hooks/useNoteTypeFields'
import { NoteTypeSetupShell } from '../components/NoteTypeSetupShell'
import { DeleteNoteTypeDialog } from '../components/manager/DeleteNoteTypeDialog'
import { FieldListCard } from '../components/fields/FieldListCard'
import { AddFieldCard } from '../components/fields/AddFieldCard'
import { EditFieldCard } from '../components/fields/EditFieldCard'
import { FieldEditorPreview } from '../components/fields/FieldEditorPreview'
import { FieldAnswersConversionEntry } from '../components/fields/FieldAnswersConversionEntry'

export function NoteTypeFieldsPage() {
  const { t } = useTranslation('note_types')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const editor = useNoteTypeFields(appApi)
  const { noteTypeId, query, detailQuery, fields, selectedField, selectedFieldId, isAddingField, isBusy } = editor
  const bootstrapQuery = useBootstrap()
  const isAdmin = Boolean(bootstrapQuery.data?.user?.is_admin)
  const [mobileDetail, setMobileDetail] = useState(false)
  const [samples, setSamples] = useState<Record<string, string>>({})
  const [sampleFiles, setSampleFiles] = useState<Record<string, File | null>>({})
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteNoteTypeOpen, setDeleteNoteTypeOpen] = useState(false)
  const [purgeNoteType, setPurgeNoteType] = useState(false)
  const [renameOpen, setRenameOpen] = useState(false)
  const [renameValue, setRenameValue] = useState('')
  const [renameError, setRenameError] = useState<string | null>(null)
  const renameButtonRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { setMobileDetail(false); setSamples({}); setSampleFiles({}); setDeleteOpen(false); setRenameOpen(false); setDeleteNoteTypeOpen(false); setPurgeNoteType(false) }, [noteTypeId])
  const applicationsQuery = useQuery({
    queryKey: cardTemplateQueryKeys.applications(noteTypeId ?? ''),
    queryFn: ({ signal }) => fetchTemplateApplications(noteTypeId!, false, signal),
    enabled: Boolean(noteTypeId),
  })
  const applications = applicationsQuery.data?.items.filter((item) => item.status_code === 'ACTIVE') ?? []
  const usedBy = selectedField ? applications.filter((item) => Object.values(item.input_bindings).includes(selectedField.id)) : []
  const { requestNavigation, confirmDialog } = useUnsavedChangesGuard(editor.isDirty || editor.isOrderDirty, t('setup.unsaved_field'), {
    onSave: async () => {
      if (editor.isDirty) await editor.saveDraft()
      if (editor.isOrderDirty) await editor.saveOrder()
    },
    onDiscard: () => {
      if (editor.isDirty) editor.discardDraft()
      if (editor.isOrderDirty) editor.discardOrder()
    },
  })
  const requestAction = (action: () => void) => {
    if (isBusy) return
    if (editor.isDirty) requestNavigation(action)
    else action()
  }
  const goTo = (to: string) => { if (!isBusy) requestNavigation(() => navigate(to)) }
  const renameMutation = useMutation({
    mutationFn: (name: string) => appApi.mutate(`/note-types/${encodeURIComponent(noteTypeId!)}`, 'PATCH', { name }),
    onSuccess: async () => {
      setRenameOpen(false)
      toast.success(t('setup.rename_success'))
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] }),
        queryClient.invalidateQueries({ queryKey: ['note-types'] }),
      ])
    },
    onError: (error: Error) => setRenameError(error.message),
  })

  const deleteNoteTypeMutation = useMutation<unknown, Error, { id: string; purge?: boolean }>({
    mutationFn: ({ id, purge }) => {
      const suffix = purge ? '?purge=true' : ''
      return appApi.mutate(`/note-types/${encodeURIComponent(id)}${suffix}`, 'DELETE')
    },
    onSuccess: () => {
      toast.success(t('manager.messages.delete_success'))
      void queryClient.invalidateQueries({ queryKey: ['note-types'] })
      navigate('/flashcards/note-types')
    },
    onError: (error: Error) => {
      toast.error(t('manager.messages.delete_error'), { description: error.message })
    },
  })

  if (query.isPending || detailQuery.isPending) return <PageLoading label={t('fields.loading')} />
  if (query.error || detailQuery.error) return <Page><PageError error={query.error ?? detailQuery.error} /></Page>

  const fieldType = isAddingField ? editor.newType : editor.editType
  const sampleKey = `${isAddingField ? 'new' : selectedFieldId}:${fieldType}`
  const preview = <FieldEditorPreview key={sampleKey} fieldType={fieldType} value={samples[sampleKey] ?? ''}
    localFile={sampleFiles[sampleKey]} onFileChange={(file) => setSampleFiles((old) => ({ ...old, [sampleKey]: file }))}
    onChange={(value) => setSamples((old) => ({ ...old, [sampleKey]: value }))} />
  const usage = <section className="space-y-2 border-t pt-4">
    <h3 className="text-xs font-semibold text-muted-foreground">{t('setup.used_by')}</h3>
    {applicationsQuery.error ? <p role="alert" className="text-xs text-destructive">{t('setup.usage_error')}</p> : applicationsQuery.isPending ? <p role="status" className="text-xs text-muted-foreground">{t('setup.usage_loading')}</p> :
      usedBy.length ? <div className="flex flex-wrap gap-2">{usedBy.map((item) => <Button key={item.id} variant="outline" size="sm" type="button"
        className="h-auto max-w-full whitespace-normal text-left text-xs" disabled={isBusy}
        onClick={() => goTo(`/flashcards/note-types/${encodeURIComponent(noteTypeId!)}/templates/${encodeURIComponent(item.id)}`)}>{item.display_name || item.template.name}</Button>)}</div> :
        <p className="text-xs text-muted-foreground">{t('setup.unused_field')}</p>}
    {selectedField && editor.editType !== selectedField.field_type && usedBy.length > 0 &&
      <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200">{t('setup.type_change_warning')}</p>}
  </section>
  const isPublished = ['published', 'unlisted'].includes(detailQuery.data?.publish_status ?? '')
  const shareLink = isPublished ? `/marketplace/note-types/${noteTypeId}` : `/marketplace/note-types/publish?id=${noteTypeId}`

  return (
    <NoteTypeSetupShell noteTypeId={noteTypeId ?? ''} name={detailQuery.data?.name ?? t('detail.header.fallback_title')}
      activeTab="fields" fill fieldCount={fields.length} templateCount={applicationsQuery.data ? applications.length : undefined}
      onNavigate={goTo} actions={<>
        {editor.canSave && (
          <span role="status" className="text-xs font-medium text-amber-600 dark:text-amber-400">
            {t('setup.unsaved_field', { defaultValue: 'Chưa lưu thay đổi' })}
          </span>
        )}
        <Button size="sm" disabled={isBusy || !editor.canSave} onClick={() => { void editor.saveAll().catch(() => undefined) }}>
          {isBusy ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
          {t('setup.save_field')}
        </Button>
        <Button ref={renameButtonRef} variant="outline" size="sm" disabled={isBusy} onClick={() => {
          setRenameValue(detailQuery.data?.name ?? ''); setRenameError(null); setRenameOpen(true)
        }}><Pencil className="size-4" />{t('setup.rename')}</Button>
        <Button variant="outline" size="sm" asChild><Link to={shareLink} onClick={(event) => {
          if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) { event.preventDefault(); goTo(shareLink) }
        }}><Share2 className="size-4" />{t(isPublished ? 'detail.header.view_marketplace' : 'detail.header.share_marketplace')}</Link></Button>
        <Button variant="ghost" size="sm" asChild><Link to="/flashcards/note-types/guide" target="_blank" rel="noopener noreferrer"><BookOpen className="size-4" />{t('detail.header.guide_btn')}</Link></Button>
        <Button
          variant="outline"
          size="sm"
          disabled={isBusy || deleteNoteTypeMutation.isPending}
          className="text-destructive border-destructive/30 hover:bg-destructive/10 hover:text-destructive gap-1.5"
          onClick={() => {
            setPurgeNoteType(false)
            setDeleteNoteTypeOpen(true)
          }}
        >
          <Trash2 className="size-4" />
          {t('setup.delete_notetype_btn', { defaultValue: 'Xóa Note Type' })}
        </Button>
      </>}>
      <div className="grid gap-3 sm:gap-4 lg:gap-5 md:grid-cols-[minmax(240px,0.7fr)_minmax(0,1.3fr)] lg:grid-cols-[minmax(260px,0.75fr)_minmax(0,1.5fr)] xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] 2xl:grid-cols-[minmax(20rem,24rem)_minmax(0,1fr)] 2xl:max-w-[110rem] 2xl:mx-auto w-full md:min-h-[34rem] lg:min-h-0 lg:flex-1 items-stretch">
        <div className={cn('h-full min-h-0 flex flex-col min-h-[min(28rem,calc(100svh-11rem))] md:min-h-0', mobileDetail ? 'hidden md:flex' : 'flex')}>
          <FieldListCard fields={fields} selectedFieldId={selectedFieldId} isAddingField={isAddingField}
            onSelectField={(id) => {
              if (id === selectedFieldId && !isAddingField) { setMobileDetail(true); return }
              requestAction(() => { editor.selectField(id); setMobileDetail(true) })
            }}
            onStartAddField={() => requestAction(() => { editor.startAddField(); setMobileDetail(true) })}
            onDragStart={editor.handleDragStart} onDrop={(id) => requestAction(() => editor.handleDrop(id))}
            onMoveUp={(index) => requestAction(() => editor.handleMoveUp(index))}
            onMoveDown={(index) => requestAction(() => editor.handleMoveDown(index))} isReordering={isBusy} />
        </div>
        <div className={cn('min-w-0 h-full min-h-0 flex flex-col min-h-[min(30rem,calc(100svh-11rem))] md:min-h-0', mobileDetail ? 'flex' : 'hidden md:flex')}>
          <Button variant="ghost" size="sm" className="md:hidden gap-1.5 -ml-1 text-xs shrink-0 mb-2 self-start h-8 px-2" disabled={isBusy}
            onClick={() => requestAction(() => setMobileDetail(false))}><ArrowLeft className="size-3.5" />{t('setup.back_to_fields')}</Button>
          {isAddingField ? <AddFieldCard newName={editor.newName} onNewNameChange={editor.setNewName} newType={editor.newType} onNewTypeChange={editor.setNewType}
            required={editor.newRequired} onRequiredChange={editor.setNewRequired} identity={editor.newIdentity} onIdentityChange={editor.setNewIdentity}
            preview={preview} error={editor.formError} isPending={isBusy}
            onCancel={() => requestAction(() => { editor.cancelAddField(); setMobileDetail(false) })}
            onSubmit={(event) => { event.preventDefault(); void editor.saveAll().catch(() => undefined) }} /> :
            selectedField ? <EditFieldCard selectedField={selectedField} editName={editor.editName} onEditNameChange={editor.setEditName}
              editType={editor.editType} onEditTypeChange={editor.setEditType} editRequired={editor.editRequired} onEditRequiredChange={editor.setEditRequired}
              editIdentity={editor.editIdentity} onEditIdentityChange={editor.setEditIdentity}
              preview={preview} usage={usage} error={editor.formError} isDirty={editor.canSave}
              typeConversion={noteTypeId ? <FieldAnswersConversionEntry noteTypeId={noteTypeId} field={selectedField} dirty={editor.isDirty}
                onChanged={() => { void editor.refreshFields() }} /> : undefined}
              isUpdating={isBusy} isDeleting={editor.deleteMutation.isPending}
              onDelete={() => requestAction(() => setDeleteOpen(true))}
              onSubmit={(event) => { event.preventDefault(); void editor.saveAll().catch(() => undefined) }} /> :
              <Card className="border-dashed bg-muted/20 flex flex-col items-center justify-center p-8 sm:p-10 text-center rounded-2xl h-full"><p className="text-sm text-muted-foreground">{t('fields.empty_selection')}</p></Card>}
        </div>
      </div>
      {confirmDialog}
      <ConfirmDialog open={deleteOpen} onOpenChange={setDeleteOpen} title={t('setup.delete_title')}
        description={t('fields.edit_card.confirm_delete', { name: selectedField?.name })} variant="destructive"
        confirmText={t('fields.edit_card.delete_btn')} cancelText={t('fields.add_card.cancel')} isLoading={editor.deleteMutation.isPending}
        onConfirm={async () => {
          if (!noteTypeId || !selectedField || selectedField.identity_role === 'primary') return
          try { await editor.deleteMutation.mutateAsync({ id: noteTypeId, fieldId: selectedField.id }); setDeleteOpen(false); setMobileDetail(false) } catch { /* The field form keeps the server error. */ }
        }} />
      <Dialog open={renameOpen} onOpenChange={(open) => { if (!renameMutation.isPending) setRenameOpen(open) }}>
        <DialogContent onCloseAutoFocus={(event) => { event.preventDefault(); renameButtonRef.current?.focus() }}
          onEscapeKeyDown={(event) => { if (renameMutation.isPending) event.preventDefault() }}
          onPointerDownOutside={(event) => { if (renameMutation.isPending) event.preventDefault() }}>
          <DialogHeader><DialogTitle>{t('setup.rename_title')}</DialogTitle><DialogDescription>{t('setup.rename_description')}</DialogDescription></DialogHeader>
          <form className="space-y-4" onSubmit={(event) => {
            event.preventDefault()
            if (!renameValue.trim()) { setRenameError(t('setup.rename_required')); return }
            renameMutation.mutate(renameValue.trim())
          }}>
            <Label htmlFor="note-type-name">{t('setup.name')}</Label>
            <Input id="note-type-name" value={renameValue} maxLength={255} disabled={renameMutation.isPending}
              aria-invalid={Boolean(renameError)} aria-describedby={renameError ? 'note-type-rename-error' : undefined}
              onChange={(event) => { setRenameValue(event.target.value); setRenameError(null) }} />
            {renameError && <p id="note-type-rename-error" role="alert" className="text-xs text-destructive">{renameError}</p>}
            <DialogFooter><Button type="button" variant="outline" disabled={renameMutation.isPending} onClick={() => setRenameOpen(false)}>{t('fields.add_card.cancel')}</Button>
              <Button type="submit" disabled={renameMutation.isPending}>{t('setup.rename_save')}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <DeleteNoteTypeDialog
        noteType={detailQuery.data ? { id: detailQuery.data.id, name: detailQuery.data.name } : null}
        isOpen={deleteNoteTypeOpen}
        onClose={() => setDeleteNoteTypeOpen(false)}
        isAdmin={isAdmin}
        purgeNoteType={purgeNoteType}
        onPurgeChange={setPurgeNoteType}
        onConfirmDelete={() => {
          if (noteTypeId) {
            deleteNoteTypeMutation.mutate({ id: noteTypeId, purge: purgeNoteType })
          }
        }}
        isDeleting={deleteNoteTypeMutation.isPending}
      />
    </NoteTypeSetupShell>
  )
}
