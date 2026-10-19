import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Ban, Globe, Info, Loader2, Palette, Store } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import {
  cardTemplateQueryKeys,
  fetchLibraryTemplate,
  fetchTemplateLibrary,
  updateLibraryTemplate,
  type TemplateWriteBody,
} from '@/entities/card-template'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { PageError } from '@/shared/components/PageState'
import { SearchInput } from '@/shared/ui'
import { fetchTemplateListing, templateMarketQueryKeys, updateTemplateListing } from '../api/templateMarketApi'
import type { MarketTemplatePricing, TemplateListingStatus } from '../model/types'
import { TEMPLATE_MARKET_CATEGORIES } from '../lib/categories'

const MIN_PRICE = 1000

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
  const [selectedId, setSelectedId] = useState(templateId ?? '')
  useEffect(() => {
    if (open) setSelectedId(templateId ?? '')
  }, [open, templateId])
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
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [search])
  // "mine" excludes received copies: those can never be listed again.
  const params = useMemo(() => ({ group: 'mine' as const, compact: true, page_size: 50, ...(query ? { q: query } : {}) }), [query])
  const library = useQuery({
    queryKey: [...cardTemplateQueryKeys.library(params), 'publish-picker'],
    queryFn: ({ signal }) => fetchTemplateLibrary(params, signal),
  })
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
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const listingQuery = useQuery({
    queryKey: templateMarketQueryKeys.listing(templateId),
    queryFn: ({ signal }) => fetchTemplateListing(templateId, signal),
  })
  const templateQuery = useQuery({
    queryKey: cardTemplateQueryKeys.libraryDetail(templateId),
    queryFn: ({ signal }) => fetchLibraryTemplate(templateId, signal),
  })
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('')
  const [pricing, setPricing] = useState<MarketTemplatePricing>('free')
  const [price, setPrice] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const initialized = useRef(false)
  const listing = listingQuery.data
  const template = templateQuery.data
  useEffect(() => {
    if (initialized.current || !listing || !template) return
    initialized.current = true
    setDescription(template.description || '')
    setCategory(template.primary_category || '')
    setPricing(listing.pricing_mode)
    setPrice(listing.pricing_mode === 'paid' ? String(listing.price_amount_minor) : '')
  }, [listing, template])

  const mutation = useMutation({
    mutationFn: async (status: TemplateListingStatus) => {
      let templateChanged = false
      if (status === 'published' && template) {
        const metadata: TemplateWriteBody = {}
        if (description.trim() !== (template.description || '')) metadata.description = description.trim()
        if (category.trim() !== (template.primary_category || '')) metadata.primary_category = category.trim() || null
        if (Object.keys(metadata).length) {
          await updateLibraryTemplate(templateId, metadata)
          templateChanged = true
        }
      }
      const body = status === 'published'
        ? { marketplace_status: status, pricing_mode: pricing, price_amount_minor: pricing === 'paid' ? Number(price) : 0 }
        : { marketplace_status: status }
      return { listing: await updateTemplateListing(templateId, body), templateChanged }
    },
    onSuccess: ({ listing: saved, templateChanged }) => {
      queryClient.setQueryData(templateMarketQueryKeys.listing(templateId), saved)
      void queryClient.invalidateQueries({ queryKey: templateMarketQueryKeys.all })
      void queryClient.invalidateQueries({ queryKey: ['card-template'] })
      if (templateChanged) onTemplateChanged?.()
      if (saved.marketplace_status === 'published') {
        toast.success(t('templates.publish.toast_published'), {
          action: { label: t('templates.publish.view_on_market'), onClick: () => navigate(`/marketplace/templates/${encodeURIComponent(templateId)}`) },
        })
      } else {
        toast.success(t('templates.publish.toast_unlisted'))
      }
      onDone()
    },
    onError: (error: Error) => setFormError(error.message),
  })

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

  const submit = () => {
    setFormError(null)
    if (!description.trim()) return setFormError(t('templates.publish.error_description'))
    if (!category.trim()) return setFormError(t('templates.publish.error_category'))
    if (pricing === 'paid' && (!Number.isInteger(Number(price)) || Number(price) < MIN_PRICE)) {
      return setFormError(t('templates.publish.error_price', { min: MIN_PRICE.toLocaleString('vi-VN') }))
    }
    mutation.mutate('published')
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

      <div className="space-y-1.5">
        <Label htmlFor="market-template-description" className="text-xs font-semibold">{t('templates.publish.description_label')} <span className="text-destructive">*</span></Label>
        <Textarea id="market-template-description" value={description} maxLength={1000} rows={3} onChange={(event) => setDescription(event.target.value)} placeholder={t('templates.publish.description_placeholder')} disabled={mutation.isPending} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="market-template-category" className="text-xs font-semibold">{t('templates.publish.category_label')} <span className="text-destructive">*</span></Label>
        <Input id="market-template-category" list="market-template-categories" value={category} maxLength={120} onChange={(event) => setCategory(event.target.value)} placeholder={t('templates.publish.category_placeholder')} disabled={mutation.isPending} />
        <datalist id="market-template-categories">{TEMPLATE_MARKET_CATEGORIES.map((name) => <option key={name} value={name} />)}</datalist>
        <div className="flex flex-wrap gap-1.5 pt-1">
          {TEMPLATE_MARKET_CATEGORIES.map((name) => (
            <button key={name} type="button" onClick={() => setCategory(name)} disabled={mutation.isPending}
              className={cn('rounded-md border px-2 py-0.5 text-[11px] font-medium transition-colors', category === name ? 'border-primary bg-primary/10 text-primary' : 'border-border/70 text-muted-foreground hover:bg-muted')}>
              {name}
            </button>
          ))}
        </div>
      </div>

      <fieldset className="space-y-2" disabled={mutation.isPending}>
        <legend className="text-xs font-semibold">{t('templates.publish.pricing_label')}</legend>
        <div className="grid grid-cols-2 gap-2">
          {(['free', 'paid'] as const).map((mode) => (
            <label key={mode} className={cn('flex cursor-pointer flex-col gap-0.5 rounded-xl border p-3 text-sm transition-colors', pricing === mode ? 'border-primary bg-primary/5' : 'hover:bg-muted')}>
              <span className="flex items-center gap-2 font-semibold">
                <input type="radio" name="market-template-pricing" value={mode} checked={pricing === mode} onChange={() => setPricing(mode)} />
                {mode === 'free' ? t('card.free', { defaultValue: 'Miễn phí' }) : t('templates.publish.paid')}
              </span>
              <span className="text-[11px] text-muted-foreground">{mode === 'free' ? t('templates.publish.free_hint') : t('templates.publish.paid_hint')}</span>
            </label>
          ))}
        </div>
        {pricing === 'paid' ? (
          <div className="space-y-1.5">
            <Label htmlFor="market-template-price" className="text-xs font-semibold">{t('templates.publish.price_label')} <span className="text-destructive">*</span></Label>
            <Input id="market-template-price" type="number" inputMode="numeric" min={MIN_PRICE} step={1000} value={price} onChange={(event) => setPrice(event.target.value)} placeholder="20000" />
          </div>
        ) : null}
      </fieldset>

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
