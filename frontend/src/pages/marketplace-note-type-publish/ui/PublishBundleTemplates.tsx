import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { TemplateListingFields, type TemplateListingDraft } from '@/entities/card-template'
import { PageError } from '@/shared/components/PageState'
import type { PublishTemplateOption } from '../api/publishNoteTypeApi'

type Props = {
  options: PublishTemplateOption[]
  query: { isPending: boolean; error: Error | null }
  listingDraft: (item: PublishTemplateOption) => TemplateListingDraft
  updateListingDraft: (item: PublishTemplateOption, patch: Partial<TemplateListingDraft>) => void
  fieldErrors: Record<string, string>
  disabled: boolean
  bundleAmount: number
}

export function PublishBundleTemplates({ options, query, listingDraft, updateListingDraft, fieldErrors, disabled, bundleAmount }: Props) {
  const { t, i18n } = useTranslation('marketplace')
  const money = (value: number) => `${value.toLocaleString(i18n.language === 'en' ? 'en-US' : 'vi-VN')} đ`
  const foreignAmount = options.filter((item) => !item.is_owned && item.pricing_mode === 'paid').reduce((sum, item) => sum + item.price_amount_minor, 0)
  return (
    <section className="space-y-4" aria-label={t('bundle.publish.templates_title')}>
      <div className="space-y-1">
        <h2 className="text-sm font-bold">{t('bundle.publish.templates_title')}</h2>
        <p className="text-xs leading-relaxed text-muted-foreground">{t('bundle.publish.references_hint')}</p>
      </div>
      {query.error ? <PageError error={query.error} /> : null}
      {query.isPending ? <p className="text-xs text-muted-foreground">{t('templates.loading')}</p> : null}
      {options.map((item) => {
        const draft = listingDraft(item)
        const editable = item.is_owned && item.requires_publication
        return (
          <article key={item.template_id} className="space-y-3 rounded-xl border border-border/80 bg-muted/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold">{item.name}</h3>
                <p className="text-xs text-muted-foreground">{t('card.author')}: <Link className="font-medium hover:text-primary" to={`/profile/${encodeURIComponent(item.author.username)}`}>{item.author.username}</Link></p>
              </div>
              <span className="text-xs font-semibold text-primary">{editable ? t('bundle.publish.publish_together') : t('bundle.publish.original_listing')}</span>
            </div>
            {editable ? (
              <TemplateListingFields
                prefix={`bundle-template-${item.template_id}`}
                description={draft.description} category={draft.primary_category} pricing={draft.pricing_mode}
                price={draft.price_amount_minor ? String(draft.price_amount_minor) : ''} disabled={disabled}
                setDescription={(description) => updateListingDraft(item, { description })}
                setCategory={(primary_category) => updateListingDraft(item, { primary_category })}
                setPricing={(pricing_mode) => updateListingDraft(item, { pricing_mode })}
                setPrice={(price) => updateListingDraft(item, { price_amount_minor: Number(price) })}
              />
            ) : (
              <div className="space-y-1 text-xs text-muted-foreground">
                <p>{item.description}</p>
                <p>{item.pricing_mode === 'paid' ? money(item.price_amount_minor) : t('card.free')} · {item.is_owned ? t('bundle.publish.in_own_bundle') : t('bundle.publish.foreign_price_fixed')}</p>
                <Link className="font-semibold text-primary hover:underline" to={`/marketplace/templates/${encodeURIComponent(item.source_template_id)}`}>{t('bundle.publish.view_original')}</Link>
              </div>
            )}
            {fieldErrors[`template:${item.template_id}`] ? <p role="alert" className="text-xs font-medium text-destructive">{fieldErrors[`template:${item.template_id}`]}</p> : null}
          </article>
        )
      })}
      {fieldErrors.templateListings ? <p role="alert" className="text-xs text-destructive">{fieldErrors.templateListings}</p> : null}
      <div className="space-y-2 rounded-xl border border-primary/20 bg-primary/5 p-4 text-xs">
        <div className="flex justify-between gap-3"><span>{t('bundle.own_portion')}</span><strong>{money(bundleAmount)}</strong></div>
        <div className="flex justify-between gap-3"><span>{t('bundle.foreign_portion')}</span><strong>{money(foreignAmount)}</strong></div>
        <div className="flex justify-between gap-3 border-t border-border/60 pt-2 font-bold"><span>{t('bundle.publish.total_before_entitlements')}</span><span>{money(bundleAmount + foreignAmount)}</span></div>
        <p className="leading-relaxed text-muted-foreground">{t('bundle.no_repeat_charge')}</p>
      </div>
    </section>
  )
}
