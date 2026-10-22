import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { NoteTypePricingBreakdown } from '../model/types'

export function NoteTypeBundlePrice({ pricing }: { pricing: NoteTypePricingBreakdown }) {
  const { t, i18n } = useTranslation('marketplace')
  const money = (value: number) => value === 0 ? t('card.free') : `${value.toLocaleString(i18n.language === 'en' ? 'en-US' : 'vi-VN')} đ`
  return (
    <Card className="border-border shadow-xs rounded-2xl">
      <CardHeader className="p-4 sm:p-5 pb-3"><CardTitle className="text-base font-bold">{t('bundle.price_title')}</CardTitle></CardHeader>
      <CardContent className="p-4 sm:p-5 pt-0 space-y-3 text-xs">
        {pricing.available === false ? <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 p-3 font-medium text-destructive">{t('bundle.unavailable')}</p> : null}
        <div className="flex justify-between gap-3"><span className="font-semibold">{t('bundle.own_portion')}</span><strong>{money(pricing.bundle_amount_minor)}</strong></div>
        <p className="text-muted-foreground">{t('bundle.own_portion_hint')}</p>
        <ul className="space-y-2">
          {pricing.templates.map((template) => (
            <li key={template.template_id} className="flex items-start justify-between gap-3 rounded-xl border border-border/60 bg-muted/20 p-3">
              <div className="min-w-0 space-y-1">
                <Link className="block truncate font-semibold hover:text-primary" to={`/marketplace/templates/${encodeURIComponent(template.template_id)}`}>{template.name}</Link>
                <p className="text-muted-foreground">{t('card.author')}: {template.author.username}</p>
                <p className="text-muted-foreground">{template.already_entitled ? t('bundle.already_entitled') : template.is_owned_by_author ? t('bundle.included') : template.pricing_mode === 'free' ? t('card.free') : t('bundle.original_price')}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className="font-semibold">{template.is_owned_by_author ? t('bundle.included_short') : money(template.charge_amount_minor)}</p>
                {template.pricing_mode === 'paid' ? <p className="mt-1 text-[11px] text-muted-foreground">{t('bundle.list_price')}: {money(template.price_amount_minor)}</p> : null}
              </div>
            </li>
          ))}
        </ul>
        <div className="flex justify-between gap-3 border-t border-border/60 pt-3 text-sm font-bold"><span>{t('bundle.total_due')}</span><span>{money(pricing.total_amount_minor)}</span></div>
        <p className="leading-relaxed text-muted-foreground">{t('bundle.no_repeat_charge')}</p>
      </CardContent>
    </Card>
  )
}
