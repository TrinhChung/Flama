import {
  AlertCircle,
  ArrowRight,
  Clock,
  CreditCard,
  HeartHandshake,
  LoaderCircle,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface SupportDonationFormProps {
  amount: number
  setAmount: (val: number) => void
  suggested: number[]
  minAmount: number
  maxAmount: number
  anonymous: boolean
  setAnonymous: (val: boolean) => void
  authenticated: boolean
  isPending: boolean
  error: Error | null
  onSubmit: () => void
}

export function SupportDonationForm({
  amount,
  setAmount,
  suggested,
  minAmount,
  maxAmount,
  anonymous,
  setAnonymous,
  authenticated,
  isPending,
  error,
  onSubmit,
}: SupportDonationFormProps) {
  const { t } = useTranslation('support')

  return (
    <Card className="border-primary/20 bg-card/90 shadow-xl backdrop-blur-md rounded-2xl sm:rounded-3xl overflow-hidden">
      <div className="h-1 bg-gradient-to-r from-primary via-orange-500 to-amber-500" />
      <CardHeader className="p-4 sm:p-6 pb-2 sm:pb-4">
        <div className="flex items-center gap-2.5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <HeartHandshake className="size-5" />
          </span>
          <div>
            <CardTitle className="text-lg sm:text-xl">
              {t('donation.online_card.title')}
            </CardTitle>
            <CardDescription className="text-xs">
              {t('donation.online_card.description')}
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-4 sm:p-6 pt-0 space-y-5 sm:space-y-6">
        {error ? (
          <Alert variant="destructive">
            <AlertCircle className="size-4" />
            <AlertTitle>{t('toast.checkout_failed')}</AlertTitle>
            <AlertDescription>{error.message}</AlertDescription>
          </Alert>
        ) : null}

        {/* Amount Input */}
        <div className="space-y-2">
          <Label htmlFor="donation-amount" className="text-xs sm:text-sm">
            {t('donation.online_card.amount_label')}
          </Label>
          <div className="relative">
            <Input
              id="donation-amount"
              type="text"
              inputMode="numeric"
              placeholder="0"
              value={amount ? amount.toLocaleString('vi-VN') : ''}
              onChange={(e) => {
                const raw = e.target.value.replace(/\D/g, '')
                const val = raw ? parseInt(raw, 10) : 0
                setAmount(val)
              }}
              className="h-11 sm:h-12 text-base sm:text-lg font-bold pr-14 sm:pr-16 border-primary/30 focus-visible:ring-primary"
            />
            <span className="absolute right-3.5 sm:right-4 top-1/2 -translate-y-1/2 text-xs font-bold text-muted-foreground">
              VND
            </span>
          </div>
          <p className="text-[11px] sm:text-xs text-muted-foreground">
            {t('donation.online_card.limit_hint', {
              min: minAmount.toLocaleString('vi-VN'),
              max: maxAmount.toLocaleString('vi-VN'),
            })}
          </p>
        </div>

        {/* Preset Amount Pills */}
        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">
            {t('donation.online_card.presets_label')}
          </Label>
          <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
            {suggested.map((preset) => (
              <Button
                key={preset}
                type="button"
                variant={amount === preset ? 'default' : 'outline'}
                size="sm"
                className={`rounded-full font-semibold transition-all text-xs px-2.5 sm:px-3 h-8 sm:h-9 justify-center ${
                  amount === preset
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'hover:border-primary/50'
                }`}
                onClick={() => setAmount(preset)}
              >
                <span className="truncate">{preset.toLocaleString('vi-VN')} VND</span>
              </Button>
            ))}
          </div>
        </div>

        {/* Anonymous Checkbox */}
        {authenticated ? (
          <div className="flex items-start space-x-3 rounded-2xl border bg-muted/30 p-3 sm:p-3.5">
            <Checkbox
              id="anonymous"
              checked={anonymous}
              onCheckedChange={(checked) => setAnonymous(Boolean(checked))}
              className="mt-0.5"
            />
            <div className="grid gap-1 leading-none">
              <Label htmlFor="anonymous" className="text-xs font-semibold cursor-pointer">
                {t('donation.online_card.anonymous_label')}
              </Label>
              <p className="text-[11px] text-muted-foreground leading-normal">
                {t('donation.online_card.anonymous_desc')}
              </p>
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-3 sm:p-3.5 text-xs text-amber-800 dark:text-amber-300">
            <p className="font-semibold">{t('donation.online_card.guest_warning_title')}</p>
            <p className="mt-0.5 text-[11px] opacity-90">
              {t('donation.online_card.guest_warning_desc')}{' '}
              <Link to="/login" className="underline font-bold">
                {t('donation.online_card.guest_login_link')}
              </Link>{' '}
              {t('donation.online_card.guest_login_after')}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="space-y-3 pt-2">
          <Button
            type="button"
            size="lg"
            className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 text-primary-foreground shadow-md shadow-primary/25 hover:opacity-95 transition-all hover:shadow-lg text-xs sm:text-sm h-11 sm:h-12 px-3 sm:px-4"
            disabled={isPending || !amount || amount < minAmount}
            onClick={onSubmit}
          >
            {isPending ? (
              <LoaderCircle className="size-5 animate-spin" />
            ) : (
              <span className="flex items-center justify-center gap-1.5 min-w-0 max-w-full">
                <CreditCard className="size-4 sm:size-5 shrink-0" />
                <span className="truncate">
                  {t('donation.online_card.pay_button', {
                    amount: amount > 0 ? `${amount.toLocaleString('vi-VN')} VND` : '',
                  })}
                </span>
                <ArrowRight className="size-3.5 sm:size-4 shrink-0" />
              </span>
            )}
          </Button>

          {authenticated ? (
            <Button
              variant="ghost"
              size="sm"
              asChild
              className="w-full text-xs text-muted-foreground h-9"
            >
              <Link to="/orders?product_type=support_donation">
                <Clock className="size-3.5 mr-1.5" />
                {t('donation.online_card.view_history')}
              </Link>
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
