import '@/shared/config/i18n'
import { useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  cardTemplateQueryKeys, fetchLibraryTemplate, fetchTemplateApplications, fetchTemplateLibrary,
  type TemplateApplication, type TemplateLibraryParams,
} from '@/entities/card-template'
import { SearchInput } from '@/shared/ui'
import { ApplyTemplateForm } from './ApplyTemplateWizard'

export type AttachTemplateDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  noteTypeId: string
  onApplied?: (application: TemplateApplication) => void
}

function useAttachTemplateSelection(noteTypeId: string) {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [composing, setComposing] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mapping, setMapping] = useState(false)
  const [occurrence, setOccurrence] = useState('compat')
  useEffect(() => {
    if (composing) return
    const timer = setTimeout(() => setQuery(search.trim()), 250)
    return () => clearTimeout(timer)
  }, [search, composing])
  const params = useMemo<TemplateLibraryParams>(() => ({ compact: true, page_size: 24, ...(query ? { q: query } : {}) }), [query])
  const library = useInfiniteQuery({
    queryKey: [...cardTemplateQueryKeys.library(params), 'infinite'],
    initialPageParam: 1,
    queryFn: ({ signal, pageParam }) => fetchTemplateLibrary({ ...params, page: pageParam }, signal),
    getNextPageParam: (last) => last.pagination?.has_more ? last.pagination.page + 1 : undefined,
  })
  const detail = useQuery({
    queryKey: cardTemplateQueryKeys.libraryDetail(selectedId ?? ''),
    queryFn: ({ signal }) => fetchLibraryTemplate(selectedId!, signal),
    enabled: Boolean(selectedId),
  })
  const applications = useQuery({
    queryKey: cardTemplateQueryKeys.applications(noteTypeId, true),
    queryFn: ({ signal }) => fetchTemplateApplications(noteTypeId, true, signal),
  })
  const existing = applications.data?.items.filter((application) => application.status_code === 'ACTIVE' && application.template_id === selectedId) ?? []
  return {
    search, setSearch, setComposing, selectedId, setSelectedId, mapping, setMapping,
    occurrence, setOccurrence, library, detail, applications, existing,
    libraryItems: library.data?.pages.flatMap((page) => page.items) ?? [],
  }
}

function AttachTemplateContent({ noteTypeId, onOpenChange, onApplied, onPendingChange }: Omit<AttachTemplateDialogProps, 'open'> & {
  onPendingChange: (pending: boolean) => void
}) {
  const { t } = useTranslation('template_mapping')
  const { t: legacyT } = useTranslation('card_templates')
  const { t: commonT } = useTranslation('common')
  const state = useAttachTemplateSelection(noteTypeId)
  if (state.mapping && state.detail.data) return <ApplyTemplateForm
    key={`${state.detail.data.id}:${state.occurrence}`}
    template={state.detail.data} initialNoteTypeId={noteTypeId} initialOccurrenceKey={state.occurrence}
    onOpenChange={onOpenChange} onApplied={onApplied} onPendingChange={onPendingChange}
    onBack={() => state.setMapping(false)} submitLabel={t('attach_save')} />
  const canContinue = state.detail.isSuccess && state.applications.isSuccess && !state.detail.data.archived_at
  return <>
    <DialogHeader>
      <DialogTitle>{t('select_template')}</DialogTitle>
      <DialogDescription>{t('select_template_description')}</DialogDescription>
    </DialogHeader>
    <SearchInput aria-label={t('search_templates')} placeholder={t('search_templates')} value={state.search}
      onChange={(event) => state.setSearch(event.target.value)} onCompositionStart={() => state.setComposing(true)}
      onCompositionEnd={(event) => { state.setSearch(event.currentTarget.value); state.setComposing(false) }} />
    {state.library.isPending && <p role="status" className="text-sm text-muted-foreground">{legacyT('library.loading')}</p>}
    {state.library.isError && <Alert variant="destructive"><AlertDescription>{state.library.error.message}
      <Button variant="outline" size="sm" onClick={() => void state.library.refetch()}>{t('retry')}</Button>
    </AlertDescription></Alert>}
    {state.library.data && <div className="max-h-64 space-y-2 overflow-y-auto" aria-label={t('select_template')}>
      {state.libraryItems.filter((template) => !template.archived_at).map((template) => <button
        key={template.id} type="button" aria-pressed={state.selectedId === template.id}
        className={`flex w-full items-center justify-between gap-3 rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${state.selectedId === template.id ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/50'}`}
        onClick={() => { state.setSelectedId(template.id); state.setOccurrence('compat') }}>
        <span className="min-w-0 space-y-1">
          <span className="block break-words font-medium">{template.name}</span>
          <span className="block text-xs text-muted-foreground">{template.primary_category || (template.origin === 'market_copy' ? legacyT('library.badge_received') : legacyT('library.badge_mine'))}</span>
        </span>
        <Badge variant="secondary" className="shrink-0">{t('input_count', { count: template.input_schema.length })}</Badge>
      </button>)}
      {!state.libraryItems.some((template) => !template.archived_at) && <p className="py-6 text-center text-sm text-muted-foreground">{t('no_templates')}</p>}
      {state.library.hasNextPage && <Button variant="outline" disabled={state.library.isFetchingNextPage} onClick={() => void state.library.fetchNextPage()}>{commonT(state.library.isFetchingNextPage ? 'pagination_loading' : 'pagination_load_more')}</Button>}
    </div>}
    {state.selectedId && state.detail.isPending && <p role="status" className="text-muted-foreground">{legacyT('detail.loading')}</p>}
    {state.detail.isError && <Alert variant="destructive"><AlertDescription>{state.detail.error.message}
      <Button variant="outline" size="sm" onClick={() => void state.detail.refetch()}>{t('retry')}</Button>
    </AlertDescription></Alert>}
    {state.applications.isError && <Alert variant="destructive"><AlertDescription>{state.applications.error.message}
      <Button variant="outline" size="sm" onClick={() => void state.applications.refetch()}>{t('retry')}</Button>
    </AlertDescription></Alert>}
    {state.existing.length > 0 && <div className="space-y-2 rounded-xl border border-border bg-muted/30 p-3">
      <p className="text-sm text-muted-foreground">{t('existing')}</p>
      {state.existing.map((application) => <Button key={application.id} variant="outline" className="h-auto w-full justify-start whitespace-normal text-left" asChild>
        <Link to={`/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates/${encodeURIComponent(application.id)}`} onClick={() => onOpenChange(false)}>
          {t('open_existing')}: {application.display_name || application.template.name}
        </Link>
      </Button>)}
    </div>}
    {state.detail.data?.archived_at && <p className="text-sm text-muted-foreground">{legacyT('apply_wizard.unarchive_warning')}</p>}
    <DialogFooter>
      <Button variant="outline" asChild><Link to="/card-templates" onClick={() => onOpenChange(false)}>{t('open_library')}</Link></Button>
      <Button variant="outline" onClick={() => onOpenChange(false)}>{t('cancel')}</Button>
      <Button disabled={!canContinue} onClick={() => {
        state.setOccurrence(state.existing.length ? crypto.randomUUID() : 'compat')
        state.setMapping(true)
      }}>{state.existing.length ? t('attach_again') : t('next')}</Button>
    </DialogFooter>
  </>
}

export function AttachTemplateDialog({ open, ...props }: AttachTemplateDialogProps) {
  const [pending, setPending] = useState(false)
  useEffect(() => { if (!open) setPending(false) }, [open])
  return <Dialog open={open} onOpenChange={(nextOpen) => { if (!pending) props.onOpenChange(nextOpen) }}>
    {open && <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-2xl" showCloseButton={!pending}
      onEscapeKeyDown={(event) => { if (pending) event.preventDefault() }} onPointerDownOutside={(event) => { if (pending) event.preventDefault() }}>
      <AttachTemplateContent key={props.noteTypeId} {...props} onPendingChange={setPending} />
    </DialogContent>}
  </Dialog>
}
