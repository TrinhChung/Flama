import { useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  Check,
  Clock,
  Copy,
  CreditCard,
  Flame,
  Heart,
  HeartHandshake,
  LoaderCircle,
  QrCode,
  Sparkles,
} from 'lucide-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useBootstrap } from '@/shared/api/bootstrap'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

type SupportDonation = {
  configured: boolean
  title: string
  description: string
  account_name: string
  account_number: string
  thank_you_message: string
  qr_image_url: string | null
  limits: {
    min_amount_minor: number
    max_amount_minor: number
    suggested_amounts: number[]
  }
}

type CheckoutResult = {
  checkout_url?: string
  payment_link_id?: string
  error?: string
  message?: string
}

type DonationStatusResult = {
  id?: string | null
  merchant_order_code?: string
  status: string
  status_display?: {
    code: string
    tone: string
    label: string
    headline: string
    description: string
  }
  total_amount_minor?: number
  currency_code?: string
  headline?: string
  message?: string
}

export function SupportPage() {
  const [searchParams] = useSearchParams()
  const { data: bootstrap } = useBootstrap()
  const authenticated = Boolean(bootstrap?.user)

  const paymentOrderId = (
    searchParams.get('payment_order_id') ||
    searchParams.get('order_id') ||
    ''
  ).trim()

  const supportProviderOrderCode = (
    searchParams.get('support_provider_order_code') ||
    searchParams.get('orderCode') ||
    searchParams.get('order_code') ||
    ''
  ).trim()

  const donationStatusQuery = useQuery({
    queryKey: ['support-donation-status', paymentOrderId, supportProviderOrderCode],
    queryFn: async () => {
      if (paymentOrderId) {
        return appApi.get<DonationStatusResult>(`/api/payments/orders/${paymentOrderId}`)
      }
      if (supportProviderOrderCode) {
        return appApi.get<DonationStatusResult>('/api/support-donation/status', {
          support_provider_order_code: supportProviderOrderCode,
        })
      }
      return null
    },
    enabled: Boolean(paymentOrderId || supportProviderOrderCode),
  })

  const query = useQuery({
    queryKey: ['support-donation'],
    queryFn: () => appApi.get<SupportDonation>('/support-donation'),
  })

  const [amount, setAmount] = useState<number>(100000)
  const [anonymous, setAnonymous] = useState<boolean>(false)
  const [copiedField, setCopiedField] = useState<string | null>(null)

  const checkoutMutation = useMutation({
    mutationFn: (payload: { amount_minor: number; anonymous: boolean }) =>
      appApi.mutate<CheckoutResult>('/support-donation/checkout', 'POST', {
        amount_minor: payload.amount_minor,
        anonymous: payload.anonymous,
        return_url: window.location.href,
        cancel_url: window.location.href,
      }),
    onSuccess: (result) => {
      if (result.checkout_url) {
        toast.success('Đang chuyển hướng tới cổng thanh toán PayOS…')
        window.location.href = result.checkout_url
      } else {
        toast.error(result.message || 'Không thể khởi tạo thanh toán.')
      }
    },
    onError: (error: Error) => {
      toast.error('Lỗi khởi tạo thanh toán', { description: error.message })
    },
  })

  const handleCopy = (text: string, fieldName: string) => {
    void navigator.clipboard.writeText(text)
    setCopiedField(fieldName)
    toast.success(`Đã sao chép ${fieldName}`)
    setTimeout(() => setCopiedField(null), 2000)
  }

  if (query.isPending) return <PageLoading label="Đang tải trang ủng hộ…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  const support = query.data
  const minAmount = support.limits.min_amount_minor || 10000
  const maxAmount = support.limits.max_amount_minor || 50000000
  const suggested = support.limits.suggested_amounts.length
    ? support.limits.suggested_amounts
    : [20000, 50000, 100000, 200000, 500000]

  return (
    <Page className="space-y-6 sm:space-y-10 px-3 sm:px-6">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-2xl sm:rounded-3xl border border-primary/20 bg-gradient-to-br from-card via-card to-primary/5 p-4 sm:p-6 md:p-10 shadow-xl">
        <div className="pointer-events-none absolute -right-10 -top-10 size-40 sm:size-60 rounded-full bg-primary/10 blur-3xl" />

        <div className="relative z-10 max-w-3xl space-y-3 sm:space-y-4">
          <Badge className="border-primary/20 bg-primary/10 text-primary text-xs" variant="secondary">
            <Flame className="size-3.5 fill-primary mr-1" />
            Support Flama Platform
          </Badge>
          <PageHeader
            title={support.title || 'Ủng hộ duy trì hệ thống'}
            description={support.description || 'Sự đóng góp của bạn tiếp thêm động lực để duy trì và phát triển cộng đồng.'}
          />
        </div>
      </div>

      {/* Donation Status Banner when returning from PayOS */}
      {donationStatusQuery.data ? (
        <Card
          className={`overflow-hidden border shadow-lg rounded-2xl ${
            donationStatusQuery.data.status === 'paid'
              ? 'border-emerald-500/30 bg-emerald-500/5'
              : donationStatusQuery.data.status === 'pending_payment' || donationStatusQuery.data.status === 'pending'
                ? 'border-amber-500/30 bg-amber-500/5'
                : 'border-destructive/30 bg-destructive/5'
          }`}
        >
          <CardContent className="p-4 sm:p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5">
                {donationStatusQuery.data.status === 'paid' ? (
                  <span className="flex size-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600">
                    <Heart className="size-5 fill-emerald-500" />
                  </span>
                ) : donationStatusQuery.data.status === 'pending_payment' || donationStatusQuery.data.status === 'pending' ? (
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
                      donationStatusQuery.data.status === 'paid'
                        ? 'border-emerald-500/30 text-emerald-700 bg-emerald-500/10'
                        : 'border-amber-500/30 text-amber-700 bg-amber-500/10'
                    }
                  >
                    {donationStatusQuery.data.status_display?.label || donationStatusQuery.data.status}
                  </Badge>
                  {donationStatusQuery.data.merchant_order_code ? (
                    <span className="font-mono text-xs text-muted-foreground font-semibold">
                      #{donationStatusQuery.data.merchant_order_code}
                    </span>
                  ) : null}
                </div>
                <h4 className="font-bold text-foreground sm:text-base">
                  {donationStatusQuery.data.headline || donationStatusQuery.data.status_display?.headline || 'Kết quả giao dịch ủng hộ'}
                </h4>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {donationStatusQuery.data.message || donationStatusQuery.data.status_display?.description}
                </p>
              </div>
            </div>

            {donationStatusQuery.data.total_amount_minor ? (
              <div className="text-right shrink-0">
                <span className="text-xs text-muted-foreground uppercase font-semibold">Số tiền</span>
                <p className="text-lg sm:text-xl font-black text-primary">
                  {donationStatusQuery.data.total_amount_minor.toLocaleString('vi-VN')} {donationStatusQuery.data.currency_code || 'VND'}
                </p>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 sm:gap-8 lg:grid-cols-12">
        {/* Left Column: Interactive Online PayOS Donation Form */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="border-primary/20 bg-card/90 shadow-xl backdrop-blur-md rounded-2xl sm:rounded-3xl overflow-hidden">
            <div className="h-1 bg-gradient-to-r from-primary via-orange-500 to-amber-500" />
            <CardHeader className="p-4 sm:p-6 pb-2 sm:pb-4">
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <HeartHandshake className="size-5" />
                </span>
                <div>
                  <CardTitle className="text-lg sm:text-xl">Ủng hộ qua PayOS</CardTitle>
                  <CardDescription className="text-xs">
                    Thanh toán online an toàn qua mã QR Ngân hàng / Napas247
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-4 sm:p-6 pt-0 space-y-5 sm:space-y-6">
              {checkoutMutation.error ? (
                <Alert variant="destructive">
                  <AlertCircle className="size-4" />
                  <AlertTitle>Không thể tạo thanh toán</AlertTitle>
                  <AlertDescription>{checkoutMutation.error.message}</AlertDescription>
                </Alert>
              ) : null}

              {/* Amount Input */}
              <div className="space-y-2">
                <Label htmlFor="donation-amount" className="text-xs sm:text-sm">Số tiền ủng hộ (VND)</Label>
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
                  Từ {minAmount.toLocaleString('vi-VN')} VND tới {maxAmount.toLocaleString('vi-VN')} VND
                </p>
              </div>

              {/* Preset Amount Pills */}
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">Mức gợi ý nhanh:</Label>
                <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
                  {suggested.map((preset) => (
                    <Button
                      key={preset}
                      type="button"
                      variant={amount === preset ? 'default' : 'outline'}
                      size="sm"
                      className={`rounded-full font-semibold transition-all text-xs px-2.5 sm:px-3 h-8 sm:h-9 justify-center ${
                        amount === preset
                          ? 'bg-gradient-to-r from-primary to-orange-500 text-primary-foreground shadow-sm'
                          : 'hover:border-primary/50'
                      }`}
                      onClick={() => setAmount(preset)}
                    >
                      <Sparkles className="size-3 mr-1 shrink-0" />
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
                      Ủng hộ ở chế độ ẩn danh
                    </Label>
                    <p className="text-[11px] text-muted-foreground leading-normal">
                      Không hiển thị thông tin lần đóng góp này trong lịch sử công khai.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-3 sm:p-3.5 text-xs text-amber-800 dark:text-amber-300">
                  <p className="font-semibold">Bạn đang ở chế độ ẩn danh</p>
                  <p className="mt-0.5 text-[11px] opacity-90">
                    Để lưu lại lịch sử đóng góp vào tài khoản, hãy{' '}
                    <Link to="/login" className="underline font-bold">
                      Đăng nhập
                    </Link>{' '}
                    trước khi thanh toán.
                  </p>
                </div>
              )}

              {/* Action Buttons */}
              <div className="space-y-3 pt-2">
                <Button
                  type="button"
                  size="lg"
                  className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 text-primary-foreground shadow-md shadow-primary/25 hover:opacity-95 transition-all hover:shadow-lg text-xs sm:text-sm h-11 sm:h-12 px-3 sm:px-4"
                  disabled={checkoutMutation.isPending || !amount || amount < minAmount}
                  onClick={() =>
                    checkoutMutation.mutate({ amount_minor: amount, anonymous })
                  }
                >
                  {checkoutMutation.isPending ? (
                    <LoaderCircle className="size-5 animate-spin" />
                  ) : (
                    <span className="flex items-center justify-center gap-1.5 min-w-0 max-w-full">
                      <CreditCard className="size-4 sm:size-5 shrink-0" />
                      <span className="truncate">Thanh toán {amount > 0 ? `${amount.toLocaleString('vi-VN')} VND` : ''} qua PayOS</span>
                      <ArrowRight className="size-3.5 sm:size-4 shrink-0" />
                    </span>
                  )}
                </Button>

                {authenticated ? (
                  <Button variant="ghost" size="sm" asChild className="w-full text-xs text-muted-foreground h-9">
                    <Link to="/orders?product_type=support_donation">
                      <Clock className="size-3.5 mr-1.5" />
                      Xem lịch sử donate của tôi
                    </Link>
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Manual Bank Transfer & QR Code */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="border-border/80 shadow-lg rounded-2xl sm:rounded-3xl">
            <CardHeader className="p-4 sm:p-6 pb-2 sm:pb-4">
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <QrCode className="size-5" />
                </span>
                <div>
                  <CardTitle className="text-base sm:text-lg">Chuyển khoản thủ công</CardTitle>
                  <CardDescription className="text-xs">
                    Quét mã QR hoặc copy thông tin tài khoản bên dưới
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
                    alt="Mã QR chuyển khoản"
                    className="max-h-48 sm:max-h-56 max-w-full rounded-xl border bg-white p-2 shadow-sm object-contain"
                  />
                  <p className="mt-2 text-[11px] text-muted-foreground">Quét QR bằng app Ngân hàng</p>
                </div>
              ) : null}

              {/* Account Details with Copy Buttons */}
              <div className="space-y-3">
                {support.account_name ? (
                  <div className="rounded-2xl border bg-muted/40 p-3 sm:p-3.5 space-y-1">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                      Chủ tài khoản
                    </span>
                    <div className="flex items-center justify-between gap-2 min-w-0">
                      <span className="font-semibold text-xs sm:text-sm truncate min-w-0">{support.account_name}</span>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        className="shrink-0"
                        onClick={() => handleCopy(support.account_name, 'Tên tài khoản')}
                      >
                        {copiedField === 'Tên tài khoản' ? (
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
                      Số tài khoản
                    </span>
                    <div className="flex items-center justify-between gap-2 min-w-0">
                      <span className="font-mono font-bold text-sm sm:text-base text-primary truncate min-w-0">
                        {support.account_number}
                      </span>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        className="shrink-0"
                        onClick={() => handleCopy(support.account_number, 'Số tài khoản')}
                      >
                        {copiedField === 'Số tài khoản' ? (
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
                <h3 className="font-bold text-xs sm:text-sm">Lời cảm ơn từ Flama</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {support.thank_you_message || 'Cảm ơn bạn đã luôn ủng hộ và đồng hành cùng sự phát triển của Flama!'}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  )
}
