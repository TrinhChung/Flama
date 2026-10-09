import { AlertCircle, Clock, Heart, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { DonationStatusResult } from '../types'

interface SupportStatusBannerProps {
  data: DonationStatusResult
  isFetching: boolean
  onRefetch: () => void
}

export function SupportStatusBanner({
  data,
  isFetching,
  onRefetch,
}: SupportStatusBannerProps) {
  const { t } = useTranslation('support')
  const isPaid = data.status === 'paid'
  const isPending = data.status === 'pending_payment' || data.status === 'pending'

  return (
    <Card
      className={`overflow-hidden border shadow-lg rounded-2xl ${
        isPaid
          ? 'border-emerald-500/30 bg-emerald-500/5'
          : isPending
            ? 'border-amber-500/30 bg-amber-500/5'
            : 'border-destructive/30 bg-destructive/5'
      }`}
    >
      <CardContent className="p-4 sm:p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5">
            {isPaid ? (
              <span className="flex size-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600">
                <Heart className="size-5 fill-emerald-500" />
              </span>
            ) : isPending ? (
              <span className="flex size-10 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600">
                <Clock className="size-5 animate-pulse" />
              </span>
            ) : (
              <span className="flex size-10 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
                <AlertCircle className="size-5" />
              </span>
            )}
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={
                  isPaid
                    ? 'border-emerald-500/30 text-emerald-700 bg-emerald-500/10'
                    : 'border-amber-500/30 text-amber-700 bg-amber-500/10'
                }
              >
                {data.status_display?.label || data.status}
              </Badge>
              {data.merchant_order_code ? (
                <span className="font-mono text-xs text-muted-foreground font-semibold">
                  #{data.merchant_order_code}
                </span>
              ) : null}
            </div>
            <h4 className="font-bold text-foreground sm:text-base">
              {data.headline ||
                data.status_display?.headline ||
                t('donation.status_banner.headline_default')}
            </h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {data.message || data.status_display?.description}
            </p>
            {isPending ? (
              <div className="pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 px-2.5 text-xs text-muted-foreground hover:text-foreground"
                  disabled={isFetching}
                  onClick={onRefetch}
                >
                  <RefreshCw
                    className={`size-3 mr-1.5 ${isFetching ? 'animate-spin' : ''}`}
                  />
                  {t('donation.status_banner.recheck')}
                </Button>
              </div>
            ) : null}
          </div>
        </div>

        {data.total_amount_minor ? (
          <div className="text-right shrink-0">
            <span className="text-xs text-muted-foreground uppercase font-semibold">
              {t('donation.status_banner.amount_label')}
            </span>
            <p className="text-lg sm:text-xl font-black text-primary">
              {data.total_amount_minor.toLocaleString('vi-VN')}{' '}
              {data.currency_code || 'VND'}
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
