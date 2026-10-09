import { Check, Copy, Heart, QrCode } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { SupportDonation } from '../types'

interface SupportManualTransferProps {
  support: SupportDonation
  copiedField: string | null
  onCopy: (text: string, fieldName: string) => void
}

export function SupportManualTransfer({
  support,
  copiedField,
  onCopy,
}: SupportManualTransferProps) {
  const { t } = useTranslation('support')

  return (
    <div className="space-y-6">
      <Card className="border-border/80 shadow-lg rounded-2xl sm:rounded-3xl">
        <CardHeader className="p-4 sm:p-6 pb-2 sm:pb-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <QrCode className="size-5" />
            </span>
            <div>
              <CardTitle className="text-base sm:text-lg">
                {t('donation.manual_card.title')}
              </CardTitle>
              <CardDescription className="text-xs">
                {t('donation.manual_card.description')}
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-4 sm:p-6 pt-0 space-y-4 sm:space-y-5">
          {/* QR Image Preview */}
          {support.qr_image_url ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border bg-muted/20 p-3 sm:p-4">
              <img
                src={support.qr_image_url}
                alt={t('donation.manual_card.qr_alt', 'Mã QR chuyển khoản')}
                className="max-h-48 sm:max-h-56 max-w-full rounded-xl border bg-white p-2 shadow-sm object-contain"
              />
              <p className="mt-2 text-[11px] text-muted-foreground">
                {t('donation.manual_card.qr_hint')}
              </p>
            </div>
          ) : null}

          {/* Account Details with Copy Buttons */}
          <div className="space-y-3">
            {support.account_name ? (
              <div className="rounded-2xl border bg-muted/40 p-3 sm:p-3.5 space-y-1">
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                  {t('donation.manual_card.account_name')}
                </span>
                <div className="flex items-center justify-between gap-2 min-w-0">
                  <span className="font-semibold text-xs sm:text-sm truncate min-w-0">
                    {support.account_name}
                  </span>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    className="shrink-0"
                    onClick={() =>
                      onCopy(support.account_name, t('donation.manual_card.account_name'))
                    }
                  >
                    {copiedField === t('donation.manual_card.account_name') ? (
                      <Check className="size-4 text-emerald-600" />
                    ) : (
                      <Copy className="size-4 text-muted-foreground" />
                    )}
                  </Button>
                </div>
              </div>
            ) : null}

            {support.account_number ? (
              <div className="rounded-2xl border bg-muted/40 p-3 sm:p-3.5 space-y-1">
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                  {t('donation.manual_card.account_number')}
                </span>
                <div className="flex items-center justify-between gap-2 min-w-0">
                  <span className="font-mono font-bold text-sm sm:text-base text-primary truncate min-w-0">
                    {support.account_number}
                  </span>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    className="shrink-0"
                    onClick={() =>
                      onCopy(
                        support.account_number,
                        t('donation.manual_card.account_number')
                      )
                    }
                  >
                    {copiedField === t('donation.manual_card.account_number') ? (
                      <Check className="size-4 text-emerald-600" />
                    ) : (
                      <Copy className="size-4 text-muted-foreground" />
                    )}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* Thank You Note */}
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-card to-card shadow-md rounded-2xl sm:rounded-3xl">
        <CardContent className="p-4 sm:p-6 flex items-start gap-3 sm:gap-4">
          <span className="flex size-9 sm:size-10 shrink-0 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-500">
            <Heart className="size-4 sm:size-5 fill-rose-500" />
          </span>
          <div className="space-y-1 min-w-0">
            <h3 className="font-bold text-xs sm:text-sm">
              {t('donation.manual_card.thank_you_title')}
            </h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {support.thank_you_message || t('donation.manual_card.default_thank_you')}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
