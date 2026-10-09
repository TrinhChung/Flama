import { Info } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { useTranslation } from 'react-i18next'

export interface OrderDetailLine {
  key: string
  label: string
  type: string
  value?: string | null
  value_minor?: number
  currency_code?: string
}

interface PaymentResultDetailsProps {
  totalAmountMinor?: number
  currencyCode?: string
  nextAction?: string
  isPaid: boolean
  orderDetailLines?: OrderDetailLine[]
}

export function PaymentResultDetails({
  totalAmountMinor,
  currencyCode,
  nextAction,
  isPaid,
  orderDetailLines,
}: PaymentResultDetailsProps) {
  const { t, i18n } = useTranslation('marketplace')
  const numberLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <div className="space-y-5">
      {/* Amount Hero */}
      {totalAmountMinor !== undefined ? (
        <div className="rounded-2xl border bg-muted/30 p-4 text-center">
          <span className="text-xs text-muted-foreground uppercase font-bold tracking-wider">
            {t('payment_result.total_amount_label', 'Tổng số tiền thanh toán')}
          </span>
          <div className="text-2xl sm:text-3xl font-black text-primary mt-0.5 tabular-nums">
            {totalAmountMinor.toLocaleString(numberLocale)} {currencyCode || 'VND'}
          </div>
        </div>
      ) : null}

      {/* Next Action / Guidance Alert */}
      {nextAction ? (
        <Alert className={isPaid ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-primary/20 bg-primary/5'}>
          <Info className="size-4 text-primary shrink-0" />
          <AlertTitle className="text-xs sm:text-sm font-bold">
            {t('payment_result.next_action_title', 'Hướng dẫn tiếp theo')}
          </AlertTitle>
          <AlertDescription className="text-xs text-muted-foreground leading-relaxed">
            {nextAction}
          </AlertDescription>
        </Alert>
      ) : null}

      {/* Order Details List */}
      {orderDetailLines && orderDetailLines.length > 0 ? (
        <div className="rounded-2xl border border-border/80 bg-card p-4 space-y-2.5 shadow-2xs">
          <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
            {t('payment_result.details_title', 'Chi tiết phiên giao dịch')}
          </h4>
          <div className="divide-y divide-border/60 text-xs">
            {orderDetailLines.map((line) => (
              <div key={line.key} className="flex items-center justify-between py-2 gap-3">
                <span className="text-muted-foreground">{line.label}</span>
                <span className="font-semibold text-foreground text-right truncate max-w-[65%]">
                  {line.type === 'amount_minor' && line.value_minor !== undefined
                    ? `${line.value_minor.toLocaleString(numberLocale)} ${line.currency_code || 'VND'}`
                    : line.value || '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
