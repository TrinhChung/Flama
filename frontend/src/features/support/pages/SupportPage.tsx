import { useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  Check,
  Clock,
  Copy,
  CreditCard,
  ExternalLink,
  Flame,
  Heart,
  HeartHandshake,
  LoaderCircle,
  QrCode,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
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

type CheckoutDetails = {
  provider?: string
  checkout_url?: string | null
  payment_link_id?: string | null
  provider_order_code?: string | null
  bank_bin?: string | null
  account_no?: string | null
  account_name?: string | null
  qr_code?: string | null
  provider_status?: string | null
  amount_minor?: number
  currency_code?: string
  payment_reference?: string | null
  merchant_order_code?: string
  expires_at?: string | null
  provider_metadata?: Record<string, any>
}

type CheckoutResult = {
  checkout_mode?: string
  created?: boolean
  payment_required?: boolean
  checkout_url?: string
  payment_link_id?: string
  provider_order_code?: string
  checkout?: CheckoutDetails
  order?: any
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
  const queryClient = useQueryClient()
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
        return appApi.get<DonationStatusResult>('/support-donation/status', {
          payment_order_id: paymentOrderId,
        })
      }
      if (supportProviderOrderCode) {
        return appApi.get<DonationStatusResult>('/support-donation/status', {
          support_provider_order_code: supportProviderOrderCode,
        })
      }
      return null
    },
    enabled: Boolean(paymentOrderId || supportProviderOrderCode),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status) return false
      return status === 'pending_payment' || status === 'pending' ? 4000 : false
    },
  })

  const query = useQuery({
    queryKey: ['support-donation'],
    queryFn: () => appApi.get<SupportDonation>('/support-donation'),
  })

  const [amount, setAmount] = useState<number>(100000)
  const [anonymous, setAnonymous] = useState<boolean>(false)
  const [copiedField, setCopiedField] = useState<string | null>(null)
  const [activeCheckout, setActiveCheckout] = useState<CheckoutResult | null>(null)
  const [isCheckoutModalOpen, setIsCheckoutModalOpen] = useState<boolean>(false)

  const checkoutMutation = useMutation({
    mutationFn: (payload: { amount_minor: number; anonymous: boolean }) =>
      appApi.mutate<CheckoutResult>('/support-donation/checkout', 'POST', {
        amount_minor: payload.amount_minor,
        anonymous: payload.anonymous,
        return_url: window.location.href,
        cancel_url: window.location.href,
      }),
    onSuccess: (result) => {
      if (result.checkout || result.checkout_url) {
        setActiveCheckout(result)
        setIsCheckoutModalOpen(true)
        toast.success('Đã tạo phiên thanh toán! Quét mã QR để hoàn tất.')
      } else {
        toast.error(result.message || 'Không thể khởi tạo thanh toán.')
      }
    },
    onError: (error: Error) => {
      toast.error('Lỗi khởi tạo thanh toán', { description: error.message })
    },
  })

  const modalOrderCode =
    activeCheckout?.provider_order_code || activeCheckout?.checkout?.provider_order_code
  const modalOrderId = activeCheckout?.order?.id

  const modalStatusQuery = useQuery({
    queryKey: ['support-modal-status', modalOrderCode, modalOrderId],
    queryFn: async () => {
      if (modalOrderId) {
        return appApi.get<DonationStatusResult>('/support-donation/status', {
          payment_order_id: modalOrderId,
        })
      }
      if (modalOrderCode) {
        return appApi.get<DonationStatusResult>('/support-donation/status', {
          support_provider_order_code: modalOrderCode,
        })
      }
      return null
    },
    enabled: Boolean(isCheckoutModalOpen && (modalOrderId || modalOrderCode)),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'paid') {
        void queryClient.invalidateQueries({ queryKey: ['support-donation-status'] })
        return false
      }
      return 3000
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
                {(donationStatusQuery.data.status === 'pending_payment' || donationStatusQuery.data.status === 'pending') ? (
                  <div className="pt-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-7 px-2.5 text-xs text-muted-foreground hover:text-foreground"
                      disabled={donationStatusQuery.isFetching}
                      onClick={() => donationStatusQuery.refetch()}
                    >
                      <RefreshCw className={`size-3 mr-1.5 ${donationStatusQuery.isFetching ? 'animate-spin' : ''}`} />
                      Kiểm tra lại
                    </Button>
                  </div>
                ) : null}
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
                  <CardTitle className="text-lg sm:text-xl">Ủng hộ trực tuyến (QR Code / Ngân hàng)</CardTitle>
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
                      <span className="truncate">Thanh toán {amount > 0 ? `${amount.toLocaleString('vi-VN')} VND` : ''} qua mã QR</span>
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

      {/* Interactive PayOS Payment Modal (Thẻ & Modal Thanh toán Trực tiếp) */}
      <Dialog open={isCheckoutModalOpen} onOpenChange={setIsCheckoutModalOpen}>
        <DialogContent className="sm:max-w-md p-0 overflow-hidden border-primary/20 shadow-2xl rounded-2xl sm:rounded-3xl">
          {/* Header with gradient */}
          <div className="bg-gradient-to-r from-primary via-orange-500 to-amber-500 p-4 sm:p-5 text-primary-foreground">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex size-8 items-center justify-center rounded-lg bg-white/20 backdrop-blur-sm">
                  <CreditCard className="size-4 text-white" />
                </span>
                <div>
                  <DialogTitle className="text-base sm:text-lg font-bold text-white leading-tight">
                    Thanh toán Ủng hộ Flama
                  </DialogTitle>
                  <DialogDescription className="text-xs text-white/80">
                    Cổng thanh toán tự động VietQR / Napas247
                  </DialogDescription>
                </div>
              </div>
              <Badge variant="secondary" className="bg-white/20 text-white border-0 text-[11px] font-semibold">
                <ShieldCheck className="size-3 mr-1" /> An toàn
              </Badge>
            </div>
          </div>

          <div className="p-4 sm:p-6 space-y-4 max-h-[80vh] overflow-y-auto">
            {modalStatusQuery.data?.status === 'paid' ? (
              /* Success Celebration View */
              <div className="py-6 flex flex-col items-center text-center space-y-4">
                <div className="relative">
                  <div className="absolute -inset-2 bg-emerald-500/20 rounded-full blur-xl animate-pulse" />
                  <span className="relative flex size-20 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/30 shadow-inner">
                    <Heart className="size-10 fill-emerald-500 text-emerald-500 animate-bounce" />
                  </span>
                </div>
                <div className="space-y-1.5">
                  <Badge variant="outline" className="border-emerald-500/30 text-emerald-700 bg-emerald-500/10 text-xs px-2.5 py-0.5 font-bold">
                    GIAO DỊCH THÀNH CÔNG
                  </Badge>
                  <h3 className="text-lg sm:text-xl font-black text-foreground">
                    Cảm ơn bạn đã ủng hộ Flama! 🎉
                  </h3>
                  <p className="text-xs sm:text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
                    Hệ thống đã nhận được số tiền đóng góp và tự động cập nhật vào cơ sở dữ liệu.
                  </p>
                </div>

                <div className="w-full rounded-2xl border bg-muted/30 p-4 space-y-2 text-xs">
                  <div className="flex justify-between items-center border-b pb-2">
                    <span className="text-muted-foreground">Số tiền ủng hộ:</span>
                    <span className="font-bold text-primary text-base">
                      {(modalStatusQuery.data?.total_amount_minor || activeCheckout?.checkout?.amount_minor || amount).toLocaleString('vi-VN')} VND
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Mã đơn hàng:</span>
                    <span className="font-mono font-semibold">
                      #{modalStatusQuery.data?.merchant_order_code || activeCheckout?.checkout?.merchant_order_code || '—'}
                    </span>
                  </div>
                </div>

                <Button
                  className="w-full font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20"
                  onClick={() => {
                    setIsCheckoutModalOpen(false)
                    void donationStatusQuery.refetch()
                  }}
                >
                  Hoàn tất
                </Button>
              </div>
            ) : (
              /* QR Code & Transfer Instructions View */
              <>
                {/* Amount Banner */}
                <div className="flex items-center justify-between rounded-xl bg-primary/10 border border-primary/20 p-3">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-muted-foreground">Số tiền cần chuyển</span>
                    <p className="text-lg font-black text-primary leading-tight">
                      {(activeCheckout?.checkout?.amount_minor || amount).toLocaleString('vi-VN')} VND
                    </p>
                  </div>
                  {activeCheckout?.checkout?.merchant_order_code && (
                    <span className="font-mono text-xs text-muted-foreground">
                      #{activeCheckout.checkout.merchant_order_code}
                    </span>
                  )}
                </div>

                {/* QR Code Container */}
                <div className="flex flex-col items-center justify-center rounded-2xl border bg-card p-3 shadow-inner">
                  {(() => {
                    const ch = activeCheckout?.checkout
                    let qrSrc = support.qr_image_url
                    if (ch?.qr_code && (ch.qr_code.startsWith('http') || ch.qr_code.startsWith('data:'))) {
                      qrSrc = ch.qr_code
                    } else if (ch?.bank_bin && ch?.account_no) {
                      const ref = ch.payment_reference || ''
                      const accName = ch.account_name || support.account_name || ''
                      const amt = ch.amount_minor || amount
                      qrSrc = `https://img.vietqr.io/image/${ch.bank_bin}-${ch.account_no}-compact2.png?amount=${amt}&addInfo=${encodeURIComponent(ref)}&accountName=${encodeURIComponent(accName)}`
                    }
                    return qrSrc ? (
                      <div className="relative group">
                        <img
                          src={qrSrc}
                          alt="Mã VietQR thanh toán"
                          className="size-52 sm:size-60 rounded-xl border bg-white p-2 shadow-sm object-contain mx-auto"
                        />
                      </div>
                    ) : (
                      <div className="size-52 flex items-center justify-center text-muted-foreground text-xs">
                        Đang tạo mã QR...
                      </div>
                    )
                  })()}
                  <p className="mt-2 text-[11px] text-muted-foreground flex items-center gap-1">
                    <QrCode className="size-3.5" /> Quét nhanh bằng bất kỳ ứng dụng Ngân hàng nào
                  </p>
                </div>

                {/* Account Details with Copy Buttons */}
                <div className="space-y-2 text-xs">
                  {/* Bank Account */}
                  <div className="flex items-center justify-between rounded-xl border bg-muted/40 p-2.5">
                    <div>
                      <span className="text-[10px] text-muted-foreground font-semibold uppercase block">Số tài khoản</span>
                      <span className="font-mono font-bold text-sm text-foreground">
                        {activeCheckout?.checkout?.account_no || support.account_number}
                      </span>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      onClick={() => handleCopy(activeCheckout?.checkout?.account_no || support.account_number, 'Số tài khoản')}
                    >
                      {copiedField === 'Số tài khoản' ? (
                        <Check className="size-3.5 text-emerald-600 mr-1" />
                      ) : (
                        <Copy className="size-3.5 text-muted-foreground mr-1" />
                      )}
                      Sao chép
                    </Button>
                  </div>

                  {/* Transfer Reference / Content */}
                  {activeCheckout?.checkout?.payment_reference && (
                    <div className="flex items-center justify-between rounded-xl border-2 border-primary/30 bg-primary/5 p-2.5">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] text-primary font-bold uppercase">Nội dung chuyển khoản</span>
                          <Badge variant="destructive" className="h-4 px-1 text-[9px]">Bắt buộc</Badge>
                        </div>
                        <span className="font-mono font-bold text-sm text-primary tracking-wide">
                          {activeCheckout.checkout.payment_reference}
                        </span>
                      </div>
                      <Button
                        size="sm"
                        variant="default"
                        className="h-7 px-2.5 text-xs font-bold"
                        onClick={() => handleCopy(activeCheckout.checkout?.payment_reference || '', 'Nội dung CK')}
                      >
                        {copiedField === 'Nội dung CK' ? (
                          <Check className="size-3.5 text-white mr-1" />
                        ) : (
                          <Copy className="size-3.5 text-white mr-1" />
                        )}
                        Sao chép
                      </Button>
                    </div>
                  )}

                  {/* Account Name */}
                  <div className="flex items-center justify-between rounded-xl border bg-muted/40 p-2.5">
                    <div>
                      <span className="text-[10px] text-muted-foreground font-semibold uppercase block">Chủ tài khoản</span>
                      <span className="font-semibold text-xs text-foreground">
                        {activeCheckout?.checkout?.account_name || support.account_name}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Real-time Status Card with Pulse */}
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="relative flex size-3">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full size-3 bg-amber-500"></span>
                    </span>
                    <div className="text-xs text-amber-800 dark:text-amber-300">
                      <p className="font-semibold leading-none">Đang chờ bạn thanh toán...</p>
                      <p className="text-[11px] opacity-80 mt-0.5">Tự động nhận diện sau khi chuyển tiền</p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 px-2 text-[11px] gap-1"
                    disabled={modalStatusQuery.isFetching}
                    onClick={() => modalStatusQuery.refetch()}
                  >
                    <RefreshCw className={`size-3 ${modalStatusQuery.isFetching ? 'animate-spin' : ''}`} />
                    Kiểm tra
                  </Button>
                </div>

                {/* Footer Buttons */}
                <div className="space-y-2 pt-2">
                  {(activeCheckout?.checkout_url || activeCheckout?.checkout?.checkout_url) && (
                    <Button
                      variant="outline"
                      size="sm"
                      asChild
                      className="w-full text-xs text-muted-foreground hover:text-foreground h-9"
                    >
                      <a
                        href={activeCheckout.checkout_url || activeCheckout.checkout?.checkout_url || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-center gap-1.5"
                      >
                        <span>Mở cổng thanh toán PayOS riêng</span>
                        <ExternalLink className="size-3.5" />
                      </a>
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-xs text-muted-foreground h-8"
                    onClick={() => setIsCheckoutModalOpen(false)}
                  >
                    Đóng cửa sổ
                  </Button>
                </div>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </Page>
  )
}
