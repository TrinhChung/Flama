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
import { Link } from 'react-router-dom'
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

export function SupportPage() {
  const { data: bootstrap } = useBootstrap()
  const authenticated = Boolean(bootstrap?.user)

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
    <Page className="space-y-10">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-3xl border border-primary/20 bg-gradient-to-br from-card via-card to-primary/5 p-6 md:p-10 shadow-xl">
        <div className="pointer-events-none absolute -right-10 -top-10 size-60 rounded-full bg-primary/10 blur-3xl" />

        <div className="relative z-10 max-w-3xl space-y-4">
          <Badge className="border-primary/20 bg-primary/10 text-primary" variant="secondary">
            <Flame className="size-3.5 fill-primary mr-1" />
            Support Flama Platform
          </Badge>
          <PageHeader
            title={support.title || 'Ủng hộ duy trì hệ thống'}
            description={support.description || 'Sự đóng góp của bạn tiếp thêm động lực để duy trì và phát triển cộng đồng.'}
          />
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-12">
        {/* Left Column: Interactive Online PayOS Donation Form */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="border-primary/20 bg-card/90 shadow-xl backdrop-blur-md rounded-3xl overflow-hidden">
            <div className="h-1 bg-gradient-to-r from-primary via-orange-500 to-amber-500" />
            <CardHeader>
              <div className="flex items-center gap-2">
                <span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <HeartHandshake className="size-5" />
                </span>
                <div>
                  <CardTitle className="text-xl">Ủng hộ qua PayOS</CardTitle>
                  <CardDescription className="text-xs">
                    Thanh toán online an toàn qua mã QR Ngân hàng / Napas247
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-6">
              {checkoutMutation.error ? (
                <Alert variant="destructive">
                  <AlertCircle className="size-4" />
                  <AlertTitle>Không thể tạo thanh toán</AlertTitle>
                  <AlertDescription>{checkoutMutation.error.message}</AlertDescription>
                </Alert>
              ) : null}

              {/* Amount Input */}
              <div className="space-y-2">
                <Label htmlFor="donation-amount">Số tiền ủng hộ (VND)</Label>
                <div className="relative">
                  <Input
                    id="donation-amount"
                    type="number"
                    min={minAmount}
                    max={maxAmount}
                    step={1000}
                    value={amount || ''}
                    onChange={(e) => setAmount(Number(e.target.value))}
                    className="h-12 text-lg font-bold pr-16 border-primary/30 focus-visible:ring-primary"
                  />
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-xs font-bold text-muted-foreground">
                    VND
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Từ {minAmount.toLocaleString('vi-VN')} VND tới {maxAmount.toLocaleString('vi-VN')} VND
                </p>
              </div>

              {/* Preset Amount Pills */}
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">Mức gợi ý nhanh:</Label>
                <div className="flex flex-wrap gap-2">
                  {suggested.map((preset) => (
                    <Button
                      key={preset}
                      type="button"
                      variant={amount === preset ? 'default' : 'outline'}
                      size="sm"
                      className={`rounded-full font-semibold transition-all ${
                        amount === preset
                          ? 'bg-gradient-to-r from-primary to-orange-500 text-primary-foreground shadow-sm'
                          : 'hover:border-primary/50'
                      }`}
                      onClick={() => setAmount(preset)}
                    >
                      <Sparkles className="size-3 mr-1" />
                      {preset.toLocaleString('vi-VN')} VND
                    </Button>
                  ))}
                </div>
              </div>

              {/* Anonymous Checkbox */}
              {authenticated ? (
                <div className="flex items-start space-x-3 rounded-2xl border bg-muted/30 p-3.5">
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
                <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-3.5 text-xs text-amber-800 dark:text-amber-300">
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
                  className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 text-primary-foreground shadow-md shadow-primary/25 hover:opacity-95 transition-all hover:shadow-lg"
                  disabled={checkoutMutation.isPending || !amount || amount < minAmount}
                  onClick={() =>
                    checkoutMutation.mutate({ amount_minor: amount, anonymous })
                  }
                >
                  {checkoutMutation.isPending ? (
                    <LoaderCircle className="size-5 animate-spin" />
                  ) : (
                    <>
                      <CreditCard className="size-5 mr-2" />
                      Thanh toán {amount > 0 ? `${amount.toLocaleString('vi-VN')} VND` : ''} qua PayOS
                      <ArrowRight className="size-4 ml-1.5" />
                    </>
                  )}
                </Button>

                {authenticated ? (
                  <Button variant="ghost" size="sm" asChild className="w-full text-xs text-muted-foreground">
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
          <Card className="border-border/80 shadow-lg rounded-3xl">
            <CardHeader>
              <div className="flex items-center gap-2">
                <span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <QrCode className="size-5" />
                </span>
                <div>
                  <CardTitle className="text-lg">Chuyển khoản thủ công</CardTitle>
                  <CardDescription className="text-xs">
                    Quét mã QR hoặc copy thông tin tài khoản bên dưới
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-5">
              {/* QR Image Preview */}
              {support.qr_image_url ? (
                <div className="flex flex-col items-center justify-center rounded-2xl border bg-muted/20 p-4">
                  <img
                    src={support.qr_image_url}
                    alt="Mã QR chuyển khoản"
                    className="max-h-56 max-w-full rounded-xl border bg-white p-2 shadow-sm object-contain"
                  />
                  <p className="mt-2 text-[11px] text-muted-foreground">Quét QR bằng app Ngân hàng</p>
                </div>
              ) : null}

              {/* Account Details with Copy Buttons */}
              <div className="space-y-3">
                {support.account_name ? (
                  <div className="rounded-2xl border bg-muted/40 p-3.5 space-y-1">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                      Chủ tài khoản
                    </span>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm">{support.account_name}</span>
                      <Button
                        size="icon-sm"
                        variant="ghost"
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
                  <div className="rounded-2xl border bg-muted/40 p-3.5 space-y-1">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                      Số tài khoản
                    </span>
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-base text-primary">
                        {support.account_number}
                      </span>
                      <Button
                        size="icon-sm"
                        variant="ghost"
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
          <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-card to-card shadow-md rounded-3xl">
            <CardContent className="p-6 flex items-start gap-4">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-500">
                <Heart className="size-5 fill-rose-500" />
              </span>
              <div className="space-y-1">
                <h3 className="font-bold text-sm">Lời cảm ơn từ Flama</h3>
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
