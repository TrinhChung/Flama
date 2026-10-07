import { AlertCircle, CheckCircle2, Clock, Heart, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useTranslation } from 'react-i18next'

interface OrderResultStatusProps {
  status: string
  isPaid: boolean
  isPending: boolean
  isUnderReview: boolean
  isDonation: boolean
  merchantOrderCode?: string
  headline?: string
  statusDisplay?: {
    label: string
    headline: string
    description: string
  }
  message?: string
}

export function PaymentResultStatusCard({
  status,
  isPaid,
  isPending,
  isUnderReview,
  isDonation,
  merchantOrderCode,
  headline,
  statusDisplay,
  message,
}: OrderResultStatusProps) {
  const { t } = useTranslation('marketplace')

  return (
    <>
      <div
        className={`h-1.5 w-full ${
          isPaid
            ? 'bg-gradient-to-r from-emerald-500 to-teal-500'
            : isPending
              ? 'bg-gradient-to-r from-amber-500 to-orange-500'
              : isUnderReview
                ? 'bg-gradient-to-r from-orange-500 to-amber-500'
                : 'bg-destructive'
        }`}
      />

      <CardHeader className="text-center p-6 sm:p-8 pb-4 sm:pb-6 space-y-3">
        <div className="mx-auto flex size-14 sm:size-16 items-center justify-center rounded-2xl shadow-sm transition-transform animate-in zoom-in-75">
          {isPaid ? (
            <span className="flex size-14 sm:size-16 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              {isDonation ? (
                <Heart className="size-8 sm:size-9 fill-emerald-500 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <CheckCircle2 className="size-8 sm:size-9" />
              )}
            </span>
          ) : isPending ? (
            <span className="flex size-14 sm:size-16 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <Clock className="size-8 sm:size-9 animate-pulse" />
            </span>
          ) : isUnderReview ? (
            <span className="flex size-14 sm:size-16 items-center justify-center rounded-2xl bg-orange-500/10 text-orange-600 dark:text-orange-400">
              <AlertCircle className="size-8 sm:size-9" />
            </span>
          ) : (
            <span className="flex size-14 sm:size-16 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
              <XCircle className="size-8 sm:size-9" />
            </span>
          )}
        </div>

        <div className="space-y-1">
          <div className="flex items-center justify-center gap-2">
            <Badge
              variant="outline"
              className={`text-xs font-bold px-3 py-0.5 rounded-full ${
                isPaid
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                  : isPending
                    ? 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300'
                    : isUnderReview
                      ? 'border-orange-500/40 bg-orange-500/10 text-orange-700 dark:text-orange-300'
                      : 'border-destructive/40 bg-destructive/10 text-destructive'
              }`}
            >
              {statusDisplay?.label || status}
            </Badge>
            {merchantOrderCode ? (
              <span className="font-mono text-xs text-muted-foreground font-semibold">
                #{merchantOrderCode}
              </span>
            ) : null}
          </div>

          <CardTitle className="text-xl sm:text-2xl font-black text-foreground pt-1">
            {headline || statusDisplay?.headline || t('payment_result.title', 'Kết quả giao dịch')}
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm max-w-lg mx-auto leading-relaxed">
            {message || statusDisplay?.description}
          </CardDescription>
        </div>
      </CardHeader>
    </>
  )
}
