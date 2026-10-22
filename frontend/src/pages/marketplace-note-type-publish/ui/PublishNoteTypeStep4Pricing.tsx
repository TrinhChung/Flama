import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCreditCard, faGift } from '@fortawesome/free-solid-svg-icons'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface PublishNoteTypeStep4PricingProps {
  pricingMode: 'free' | 'paid'
  priceAmountMinor: number
  version: string
  title: string
  taxonomySubject: string
  effectiveCategory: string
  availableSubjects: any[]
  fieldErrors: Record<string, string>
  setPricingMode: (mode: 'free' | 'paid') => void
  setPriceAmountMinor: (val: number) => void
  setVersion: (val: string) => void
  clearFieldError: (name: string) => void
}

function FieldErrorMessage({ error }: { error?: string }) {
  if (!error) return null
  return (
    <p className="text-xs font-semibold text-destructive mt-1.5 flex items-center gap-1.5 animate-in fade-in">
      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
      <span>{error}</span>
    </p>
  )
}

export function PublishNoteTypeStep4Pricing({
  pricingMode,
  priceAmountMinor,
  version,
  title,
  taxonomySubject,
  effectiveCategory,
  availableSubjects,
  fieldErrors,
  setPricingMode,
  setPriceAmountMinor,
  setVersion,
  clearFieldError,
}: PublishNoteTypeStep4PricingProps) {
  const { t } = useTranslation('marketplace')

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      <p className="text-xs leading-relaxed text-muted-foreground">{t('bundle.publish.discount_hint')}</p>
      {/* Pricing Selector Cards */}
      <div className="space-y-2">
        <Label className="text-xs font-semibold">
          {t('publish_deck.step4.section_title', { defaultValue: 'Mô hình phân phối & Giá bán' })}
        </Label>
        <div className="grid grid-cols-2 gap-3">
          <div
            onClick={() => setPricingMode('free')}
            className={`p-4 rounded-xl border cursor-pointer transition-all text-center select-none ${
              pricingMode === 'free'
                ? 'border-primary bg-primary/5 text-foreground font-bold ring-1 ring-primary/30 shadow-2xs'
                : 'border-border/80 bg-card hover:bg-muted/40 text-muted-foreground'
            }`}
          >
            <div className="flex items-center justify-center mb-1.5 text-muted-foreground">
              <FontAwesomeIcon icon={faGift} className="size-4" />
            </div>
            <div className="font-bold text-sm sm:text-base">
              {t('publish_deck.step4.mode_free_title', { defaultValue: 'Miễn phí (Free)' })}
            </div>
            <div className="text-xs opacity-80 mt-0.5">
              {t('publish_deck.step4.mode_free_desc', { defaultValue: 'Chia sẻ tự do tới mọi người' })}
            </div>
          </div>

          <div
            onClick={() => setPricingMode('paid')}
            className={`p-4 rounded-xl border cursor-pointer transition-all text-center select-none ${
              pricingMode === 'paid'
                ? 'border-primary bg-primary/5 text-foreground font-bold ring-1 ring-primary/30 shadow-2xs'
                : 'border-border/80 bg-card hover:bg-muted/40 text-muted-foreground'
            }`}
          >
            <div className="flex items-center justify-center mb-1.5 text-muted-foreground">
              <FontAwesomeIcon icon={faCreditCard} className="size-4" />
            </div>
            <div className="font-bold text-sm sm:text-base">
              {t('publish_deck.step4.mode_paid_title', { defaultValue: 'Có phí (Paid)' })}
            </div>
            <div className="text-xs opacity-80 mt-0.5">
              {t('publish_deck.step4.mode_paid_desc', { defaultValue: 'Bán qua cổng payOS' })}
            </div>
          </div>
        </div>

        {pricingMode === 'paid' && (
          <div className="space-y-1.5 animate-in fade-in duration-200">
            <Label htmlFor="nt-price" className="text-xs font-semibold">
              {t('publish_deck.step4.price_label', { defaultValue: 'Giá bán niêm yết (VNĐ)' })} <span className="text-destructive">*</span>
            </Label>
            <div className="relative">
              <Input
                id="nt-price"
                type="number"
                min="1000"
                step="1000"
                value={priceAmountMinor || ''}
                onChange={(e) => {
                  setPriceAmountMinor(Number(e.target.value))
                  clearFieldError('priceAmountMinor')
                }}
                className={`h-11 sm:h-10 text-sm rounded-xl pr-14 font-mono font-semibold ${
                  fieldErrors.priceAmountMinor ? 'border-destructive bg-destructive/5' : ''
                }`}
              />
              <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground font-bold">
                VND
              </span>
            </div>
            <FieldErrorMessage error={fieldErrors.priceAmountMinor} />
          </div>
        )}
      </div>

      {/* Version */}
      <div className="space-y-1.5">
        <Label htmlFor="nt-version" className="text-xs font-semibold">
          {t('publish_deck.step4.version_label', { defaultValue: 'Phiên bản phát hành' })}
        </Label>
        <Input
          id="nt-version"
          value={version}
          onChange={(e) => setVersion(e.target.value)}
          className="h-10 text-xs sm:text-sm rounded-xl font-mono"
        />
      </div>

      {/* Summary Checklist before Submit */}
      <div className="p-4 rounded-xl border border-border/80 bg-muted/30 space-y-2.5 text-xs">
        <div className="font-bold text-foreground flex items-center gap-1.5">
          <CheckCircle2 className="w-4 h-4 text-muted-foreground" />
          <span>{t('publish_deck.step4.summary_box_title', { defaultValue: 'Tóm tắt thông tin xuất bản NoteType:' })}</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-muted-foreground">
          <div>
            {t('publish_deck.summary_title', { defaultValue: 'Tiêu đề:' })}{' '}
            <strong className="text-foreground">{title || t('publish_deck.summary_not_set', { defaultValue: 'Chưa đặt' })}</strong>
          </div>
          <div>
            {t('publish_deck.summary_subject', { defaultValue: 'Môn học:' })}{' '}
            <strong className="text-foreground">
              {availableSubjects.find((s) => s.id === taxonomySubject)?.label || taxonomySubject}
            </strong>
          </div>
          <div>
            Danh mục: <strong className="text-foreground">{effectiveCategory}</strong>
          </div>
          <div>
            {t('publish_deck.summary_model', { defaultValue: 'Mô hình:' })}{' '}
            <strong className="text-foreground">
              {pricingMode === 'paid' ? `${priceAmountMinor.toLocaleString('vi-VN')} đ` : t('card.free', { defaultValue: 'Miễn phí' })}
            </strong>
          </div>
        </div>
      </div>
    </div>
  )
}
