import {
  BadgePercent,
  Coins,
  Info,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
} from '@/components/ui/card'
import type { ProfileWallet } from '../types/profile'

export function ProfileWalletCard({
  wallet,
}: {
  wallet: ProfileWallet
}) {
  const isCreatorDiscount =
    wallet.platform_fee_percent < 10.0 || wallet.is_custom_fee

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Main Available Balance */}
        <Card className="relative overflow-hidden border-primary/30 bg-gradient-to-br from-primary/10 via-amber-500/5 to-background shadow-xs">
          <div className="absolute -top-6 -right-6 size-24 rounded-full bg-primary/10 blur-xl" />
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground">
                Số dư khả dụng
              </span>
              <span className="flex size-8 items-center justify-center rounded-full bg-primary/15 text-primary">
                <Wallet className="size-4" />
              </span>
            </div>
            <div className="mt-3">
              <div className="text-2xl font-bold tracking-tight text-foreground">
                {wallet.balance_amount_display}
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                Tích lũy an toàn trong ví Flama
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Total Lifetime Earnings */}
        <Card className="border-border/60 bg-muted/20 shadow-xs">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground">
                Tổng thu nhập nhận được
              </span>
              <span className="flex size-8 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                <TrendingUp className="size-4" />
              </span>
            </div>
            <div className="mt-3">
              <div className="text-2xl font-bold tracking-tight text-foreground">
                {wallet.earnings.total_net_display}
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                Từ {wallet.earnings.total_sales_count} lượt tải trả phí
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Platform Fee Rate */}
        <Card className="border-border/60 bg-muted/20 shadow-xs">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground">
                Phí nền tảng áp dụng
              </span>
              <span className="flex size-8 items-center justify-center rounded-full bg-orange-500/15 text-orange-600 dark:text-orange-400">
                <BadgePercent className="size-4" />
              </span>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <div className="text-2xl font-bold tracking-tight text-foreground">
                {wallet.platform_fee_percent}%
              </div>
              {isCreatorDiscount ? (
                <Badge className="bg-primary/15 text-primary border-primary/30 text-[10px]">
                  Ưu đãi
                </Badge>
              ) : null}
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {wallet.is_custom_fee
                ? 'Tỷ lệ riêng biệt do Admin thiết lập'
                : 'Áp dụng tự động theo vai trò tài khoản'}
            </p>
          </CardContent>
        </Card>

        {/* Total Gross Revenue */}
        <Card className="border-border/60 bg-muted/20 shadow-xs">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground">
                Doanh số gộp
              </span>
              <span className="flex size-8 items-center justify-center rounded-full bg-blue-500/15 text-blue-600 dark:text-blue-400">
                <Coins className="size-4" />
              </span>
            </div>
            <div className="mt-3">
              <div className="text-2xl font-bold tracking-tight text-foreground">
                {wallet.earnings.total_gross_display}
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                Phí nền tảng đã trích: {wallet.earnings.total_platform_fee_display}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Payout Notice Banner */}
      <Alert className="border-amber-500/30 bg-amber-500/5 text-foreground">
        <Info className="size-4 text-amber-600 dark:text-amber-400" />
        <AlertTitle className="text-xs font-bold text-amber-700 dark:text-amber-300">
          Chính sách quản lý số dư và rút tiền
        </AlertTitle>
        <AlertDescription className="text-xs text-muted-foreground">
          {wallet.payout_status_message} Khi có người dùng mua bộ thẻ của bạn qua PayOS, tiền thực nhận (sau khi trừ {wallet.platform_fee_percent}% phí nền tảng) sẽ được cộng ngay lập tức vào số dư này.
        </AlertDescription>
      </Alert>
    </div>
  )
}
