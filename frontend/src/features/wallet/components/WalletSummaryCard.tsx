import { useTranslation } from 'react-i18next'
import {
  BadgePercent,
  Coins,
  PackageCheck,
  Percent,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { WalletSummary } from '../types/wallet'

export function WalletSummaryCard({ wallet }: { wallet: WalletSummary }) {
  const { t } = useTranslation('wallet')
  const { earnings } = wallet

  return (
    <div className="space-y-4">
      {/* Primary Balance Card */}
      <Card className="relative overflow-hidden border-primary/20 bg-gradient-to-br from-primary/10 via-background to-amber-500/5 shadow-md">
        <div className="absolute top-0 right-0 h-40 w-80 bg-radial from-primary/15 via-orange-500/5 to-transparent blur-3xl" />
        <CardContent className="p-6 md:p-8">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                <Wallet className="size-4 text-primary" />
                <span>{t('summary.available_balance')}</span>
              </div>
              <div className="flex flex-wrap items-baseline gap-3">
                <span className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl md:text-5xl">
                  {wallet.balance_amount_display}
                </span>
                <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary text-xs font-medium">
                  {wallet.currency_code}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('summary.balance_explanation')}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-background/80 px-4 py-2.5 shadow-xs backdrop-blur-sm">
                <BadgePercent className="size-4 text-amber-500" />
                <div className="text-xs">
                  <p className="font-semibold text-foreground">
                    {t('summary.platform_fee_label', { percent: wallet.platform_fee_percent })}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    {wallet.is_custom_fee ? t('summary.custom_fee_tier') : t('summary.standard_fee_tier')}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4 Stat Breakdown Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-border/60 bg-card/60 shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              {t('summary.total_gross_title')}
            </CardTitle>
            <Coins className="size-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-foreground">
              {earnings.total_gross_display}
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {t('summary.total_gross_description')}
            </p>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              {t('summary.net_earnings_title')}
            </CardTitle>
            <TrendingUp className="size-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
              {earnings.total_net_display}
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {t('summary.net_earnings_description')}
            </p>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              {t('summary.service_fee_title')}
            </CardTitle>
            <Percent className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-muted-foreground">
              {earnings.total_platform_fee_display}
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {t('summary.service_fee_description')}
            </p>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              {t('summary.sales_count_title')}
            </CardTitle>
            <PackageCheck className="size-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-foreground">
              {earnings.total_sales_count}
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {t('summary.sales_count_description')}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
