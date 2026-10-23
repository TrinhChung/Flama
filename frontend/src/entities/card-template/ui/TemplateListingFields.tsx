import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { TEMPLATE_MARKET_CATEGORIES, TEMPLATE_MIN_PRICE } from '../model/listing'

export type TemplateListingFieldsProps = {
  prefix?: string
  description: string
  category: string
  pricing: 'free' | 'paid'
  price: string
  disabled?: boolean
  setDescription: (value: string) => void
  setCategory: (value: string) => void
  setPricing: (value: 'free' | 'paid') => void
  setPrice: (value: string) => void
}

export function TemplateListingFields({ prefix = 'market-template', description, category, pricing, price, disabled, setDescription, setCategory, setPricing, setPrice }: TemplateListingFieldsProps) {
  const { t } = useTranslation('marketplace')
  return <>
      <div className="space-y-1.5">
        <Label htmlFor={`${prefix}-description`} className="text-xs font-semibold">{t('templates.publish.description_label')} <span className="text-destructive">*</span></Label>
        <Textarea id={`${prefix}-description`} value={description} maxLength={1000} rows={3} onChange={(event) => setDescription(event.target.value)} placeholder={t('templates.publish.description_placeholder')} disabled={disabled} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${prefix}-category`} className="text-xs font-semibold">{t('templates.publish.category_label')} <span className="text-destructive">*</span></Label>
        <Input id={`${prefix}-category`} list={`${prefix}-categories`} value={category} maxLength={120} onChange={(event) => setCategory(event.target.value)} placeholder={t('templates.publish.category_placeholder')} disabled={disabled} />
        <datalist id={`${prefix}-categories`}>{TEMPLATE_MARKET_CATEGORIES.map((name) => <option key={name} value={name} />)}</datalist>
        <div className="flex flex-wrap gap-1.5 pt-1">
          {TEMPLATE_MARKET_CATEGORIES.map((name) => (
            <button key={name} type="button" onClick={() => setCategory(name)} disabled={disabled}
              className={cn('rounded-md border px-2 py-0.5 text-[11px] font-medium transition-colors', category === name ? 'border-primary bg-primary/10 text-primary' : 'border-border/70 text-muted-foreground hover:bg-muted')}>
              {name}
            </button>
          ))}
        </div>
      </div>

      <fieldset className="space-y-2" disabled={disabled}>
        <legend className="text-xs font-semibold">{t('templates.publish.pricing_label')}</legend>
        <div className="grid grid-cols-2 gap-2">
          {(['free', 'paid'] as const).map((mode) => (
            <label key={mode} className={cn('flex cursor-pointer flex-col gap-0.5 rounded-xl border p-3 text-sm transition-colors', pricing === mode ? 'border-primary bg-primary/5' : 'hover:bg-muted')}>
              <span className="flex items-center gap-2 font-semibold">
                <input type="radio" name={`${prefix}-pricing`} value={mode} checked={pricing === mode} onChange={() => setPricing(mode)} />
                {mode === 'free' ? t('card.free', { defaultValue: 'Miễn phí' }) : t('templates.publish.paid')}
              </span>
              <span className="text-[11px] text-muted-foreground">{mode === 'free' ? t('templates.publish.free_hint') : t('templates.publish.paid_hint')}</span>
            </label>
          ))}
        </div>
        {pricing === 'paid' ? (
          <div className="space-y-1.5">
            <Label htmlFor={`${prefix}-price`} className="text-xs font-semibold">{t('templates.publish.price_label')} <span className="text-destructive">*</span></Label>
            <Input id={`${prefix}-price`} type="number" inputMode="numeric" min={TEMPLATE_MIN_PRICE} step={1000} value={price} onChange={(event) => setPrice(event.target.value)} placeholder="20000" />
          </div>
        ) : null}
      </fieldset>

  </>
}
