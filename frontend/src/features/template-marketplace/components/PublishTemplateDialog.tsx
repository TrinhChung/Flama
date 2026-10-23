import { ArrowLeft, Ban, Globe, Info, Loader2, Palette, Store } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { TemplateListingFields } from '@/entities/card-template'
import { useTemplateListingForm } from '../hooks/useTemplateListingForm'
import { usePublishTemplateSelection, useTemplatePublishPicker } from '../hooks/useTemplatePublishPicker'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { PageError } from '@/shared/components/PageState'
import { SearchInput } from '@/shared/ui'


type PublishTemplateDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Preselected template; without it the dialog first asks which authored template to list. */
  templateId?: string
  /** Called after the dialog saved description/category on the template itself. */
  onTemplateChanged?: () => void
}

export function PublishTemplateDialog({ open, onOpenChange, templateId, onTemplateChanged }: PublishTemplateDialogProps) {
  const { t } = useTranslation('marketplace')
  const [selectedId, setSelectedId] = usePublishTemplateSelection(open, templateId)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90svh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Store className="size-4 text-primary" />{t('templates.publish.title')}</DialogTitle>
          <DialogDescription>{t('templates.publish.description')}</DialogDescription>
        </DialogHeader>
        {selectedId ? (
          <ListingForm
            key={selectedId}
            templateId={selectedId}
            onBack={templateId ? undefined : () => setSelectedId('')}
            onDone={() => onOpenChange(false)}
            onTemplateChanged={onTemplateChanged}
          />
        ) : (
          <TemplatePicker onSelect={setSelectedId} />
        )}
      </DialogContent>
    </Dialog>
  )
}

function TemplatePicker({ onSelect }: { onSelect: (id: string) => void }) {
  const { t } = useTranslation('marketplace')
  const { search, setSearch, library } = useTemplatePublishPicker()
  const items = library.data?.items ?? []
  return (
    <div className="space-y-3">
      <Label className="text-xs font-semibold">{t('templates.publish.pick_label')}</Label>
      <SearchInput size="sm" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('templates.publish.pick_search')} aria-label={t('templates.publish.pick_search')} />
      {library.error ? <PageError error={library.error} /> : null}
      <div className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
        {library.isPending ? (
          <p className="flex items-center gap-2 p-3 text-xs text-muted-foreground"><Loader2 className="size-3.5 animate-spin" />{t('templates.loading')}</p>
        ) : items.length ? items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            className="flex w-full items-center gap-3 rounded-xl border border-border/80 bg-muted/20 p-3 text-left transition-colors hover:border-primary/50 hover:bg-primary/5 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
          >
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><Palette className="size-4" /></span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-foreground">{item.name}</span>
              <span className="block truncate text-[11px] text-muted-foreground">{item.primary_category || t('templates.publish.no_category')}</span>
            </span>
          </button>
        )) : (
          <div className="rounded-xl border border-dashed p-4 text-center text-xs text-muted-foreground space-y-2">
            <p>{t('templates.publish.pick_empty')}</p>
            <Button variant="outline" size="sm" asChild className="rounded-lg text-xs"><Link to="/card-templates">{t('templates.publish.open_library')}</Link></Button>
          </div>
        )}
      </div>
      <p className="flex items-start gap-1.5 text-[11px] text-muted-foreground"><Info className="mt-0.5 size-3 shrink-0" />{t('templates.publish.pick_rule')}</p>
    </div>
  )
}

function ListingForm({ templateId, onBack, onDone, onTemplateChanged }: {
  templateId: string
  onBack?: () => void
  onDone: () => void
  onTemplateChanged?: () => void
}) {
  const { t } = useTranslation('marketplace')
  const { listingQuery, templateQuery, listing, template, description, setDescription, category, setCategory, pricing, setPricing, price, setPrice, formError, mutation, submit } = useTemplateListingForm(templateId, onDone, onTemplateChanged)

  if (listingQuery.error || templateQuery.error) return <PageError error={listingQuery.error || templateQuery.error} />
  if (!listing || !template) {
    return <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />{t('templates.loading')}</p>
  }

  const isListed = listing.marketplace_status === 'published'
  const backButton = onBack ? (
    <Button type="button" variant="ghost" size="sm" onClick={onBack} className="h-7 px-2 text-xs"><ArrowLeft className="mr-1 size-3.5" />{t('templates.publish.pick_other')}</Button>
  ) : null

  if (!listing.can_publish) {
    return (
      <div className="space-y-4">
        {backButton}
        <div role="alert" className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
          <Ban className="mt-0.5 size-4 shrink-0 text-amber-600" />
          <div className="space-y-1">
            <p className="font-semibold text-foreground">{template.name}</p>
            <p className="text-muted-foreground">{listing.block_code === 'MARKET_TEMPLATE_REPUBLISH_FORBIDDEN' ? t('templates.publish.blocked_market_copy') : listing.block_reason}</p>
          </div>
        </div>
        {isListed ? (
          <Button variant="outline" className="w-full rounded-xl" disabled={mutation.isPending} onClick={() => mutation.mutate('private')}>{t('templates.publish.btn_unlist')}</Button>
        ) : null}
      </div>
    )
  }


  return (
    <form className="space-y-4" noValidate onSubmit={(event) => { event.preventDefault(); submit() }}>
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-foreground">{template.name}</p>
          <p className="text-[11px] text-muted-foreground">
            {isListed ? t('templates.publish.status_listed', { count: listing.install_count }) : t('templates.publish.status_private')}
          </p>
        </div>
        {backButton}
      </div>

      <TemplateListingFields description={description} category={category} pricing={pricing} price={price} disabled={mutation.isPending} setDescription={setDescription} setCategory={setCategory} setPricing={setPricing} setPrice={setPrice} />

      {listing.has_unpublished_changes ? (
        <p className="flex items-start gap-1.5 rounded-lg bg-muted/50 p-2.5 text-[11px] text-muted-foreground"><Info className="mt-0.5 size-3 shrink-0" />{t('templates.publish.release_note')}</p>
      ) : null}
      <p className="flex items-start gap-1.5 text-[11px] text-muted-foreground"><Info className="mt-0.5 size-3 shrink-0" />{t('templates.publish.buyer_rule')}</p>
      {formError ? <p role="alert" className="text-xs font-medium text-destructive">{formError}</p> : null}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        {isListed ? (
          <Button type="button" variant="outline" className="rounded-xl" disabled={mutation.isPending} onClick={() => mutation.mutate('private')}>{t('templates.publish.btn_unlist')}</Button>
        ) : null}
        <Button type="submit" className="rounded-xl font-bold" disabled={mutation.isPending}>
          {mutation.isPending ? <Loader2 className="mr-1.5 size-4 animate-spin" /> : <Globe className="mr-1.5 size-4" />}
          {isListed ? t('templates.publish.btn_update') : t('templates.publish.btn_publish')}
        </Button>
      </div>
    </form>
  )
}
