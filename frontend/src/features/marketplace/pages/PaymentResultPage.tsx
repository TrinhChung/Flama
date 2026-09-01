import { useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  ExternalLink,
  Heart,
  Info,
  RefreshCw,
  ShoppingBag,
  XCircle,
} from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Page } from '@/shared/components/Page'
import { PageLoading } from '@/shared/components/PageState'

type OrderDetailLine = {
  key: string
  label: string
  type: string
  value?: string | null
  value_minor?: number
  currency_code?: string
}

type OrderItem = {
  id?: string | null
  product_type: string
  product_ref_id: string
  title_snapshot?: string | null
  unit_amount_minor?: number
  line_total_amount_minor?: number
}

type OrderResult = {
  id?: string | null
  merchant_order_code?: string
  status: string
  status_display?: {
    code: string
    tone: 'success' | 'warning' | 'danger' | 'info' | 'secondary'
    label: string
    headline: string
    description: string
  }
  grant_status?: string
  grant_status_display?: {
    code: string
    label: string
    description: string
  }
  total_amount_minor?: number
  currency_code?: string
  paid_at?: string | null
  created_at?: string | null
  message?: string
  headline?: string
  next_action?: string
  instructions?: string[]
  order_detail_lines?: OrderDetailLine[]
  items?: OrderItem[]
  is_support_donation?: boolean
  active_attempt?: {
    status?: string
    checkout_url?: string | null
    expires_at?: string | null
  } | null
}

export function PaymentResultPage() {
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()

  const paymentOrderId = (
    searchParams.get('payment_order_id') ||
    searchParams.get('order_id') ||
    searchParams.get('id') ||
    ''
  ).trim()

  const supportProviderOrderCode = (
    searchParams.get('support_provider_order_code') ||
    searchParams.get('orderCode') ||
    searchParams.get('order_code') ||
    ''
  ).trim()

  const isAnonymousDonation =
    searchParams.get('support_checkout_mode') === 'anonymous' ||
    (Boolean(supportProviderOrderCode) && !paymentOrderId)

  const [isManualReconciling, setIsManualReconciling] = useState(false)

  // Query order detail / reconciliation
  const query = useQuery({
    queryKey: [
      'payment-result',
      paymentOrderId,
      supportProviderOrderCode,
      isAnonymousDonation,
    ],
    queryFn: async () => {
      if (paymentOrderId) {
        return appApi.get<OrderResult>(`/api/payments/orders/${paymentOrderId}`)
      }
      if (supportProviderOrderCode) {
        return appApi.get<OrderResult>('/api/support-donation/status', {
          support_provider_order_code: supportProviderOrderCode,
        })
      }
      throw new Error('Không tìm thấy thông tin đơn hàng hoặc mã giao dịch hợp lệ.')
    },
    enabled: Boolean(paymentOrderId || supportProviderOrderCode),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'pending_payment' || status === 'created' || status === 'pending') {
        return 4000 // Tự động thăm dò nếu đơn đang pending
      }
      return false
    },
  })

  const handleManualReconcile = async () => {
    setIsManualReconciling(true)
    try {
      await query.refetch()
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: ['marketplace'] })
      toast.success('Đã cập nhật trạng thái thanh toán mới nhất!')
    } catch (err: any) {
      toast.error('Lỗi khi kiểm tra lại trạng thái', {
        description: err?.message || 'Vui lòng thử lại sau ít phút.',
      })
    } finally {
      setIsManualReconciling(false)
    }
  }

  if (query.isPending) {
    return (
      <Page>
        <PageLoading label="Đang kiểm tra kết quả thanh toán…" />
      </Page>
    )
  }

  if (query.error || !query.data) {
    return (
      <Page className="max-w-2xl mx-auto py-8">
        <Card className="border-destructive/30 shadow-lg rounded-2xl">
          <CardHeader className="text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive mb-2">
              <AlertCircle className="size-6" />
            </div>
            <CardTitle className="text-xl">Không thể tải thông tin thanh toán</CardTitle>
            <CardDescription>
              {query.error?.message || 'Mã đơn hàng không hợp lệ hoặc phiên thanh toán đã kết thúc.'}
            </CardDescription>
          </CardHeader>
          <CardFooter className="flex justify-center gap-3">
            <Button variant="outline" asChild>
              <Link to="/orders">Xem lịch sử đơn hàng</Link>
            </Button>
            <Button asChild>
              <Link to="/marketplace/decks">Quay lại Marketplace</Link>
            </Button>
          </CardFooter>
        </Card>
      </Page>
    )
  }

  const order = query.data
  const status = order.status?.toLowerCase() || 'pending_payment'
  const isPaid = status === 'paid'
  const isPending = status === 'pending_payment' || status === 'created'
  const isUnderReview = status === 'under_review'

  const firstItem = order.items?.[0]
  const isDeck = firstItem?.product_type === 'deck_marketplace_item'
  const isNoteType = firstItem?.product_type === 'note_type'
  const isDonation = order.is_support_donation || firstItem?.product_type === 'support_donation'

  return (
    <Page className="max-w-3xl mx-auto space-y-6 px-3 sm:px-6 py-4 sm:py-8">
      <AmbientBackground intensity="subtle" />

      {/* Main Status Header Card */}
      <Card
        className={`overflow-hidden border shadow-xl rounded-2xl sm:rounded-3xl transition-all ${
          isPaid
            ? 'border-emerald-500/30 bg-gradient-to-br from-card via-card to-emerald-500/5'
            : isPending
              ? 'border-amber-500/30 bg-gradient-to-br from-card via-card to-amber-500/5'
              : isUnderReview
                ? 'border-orange-500/30 bg-gradient-to-br from-card via-card to-orange-500/5'
                : 'border-destructive/30 bg-gradient-to-br from-card via-card to-destructive/5'
        }`}
      >
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
                {order.status_display?.label || order.status}
              </Badge>
              {order.merchant_order_code ? (
                <span className="font-mono text-xs text-muted-foreground font-semibold">
                  #{order.merchant_order_code}
                </span>
              ) : null}
            </div>

            <CardTitle className="text-xl sm:text-2xl font-black text-foreground pt-1">
              {order.headline || order.status_display?.headline || 'Kết quả giao dịch'}
            </CardTitle>
            <CardDescription className="text-xs sm:text-sm max-w-lg mx-auto leading-relaxed">
              {order.message || order.status_display?.description}
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="p-6 pt-0 space-y-5">
          {/* Amount Hero */}
          {order.total_amount_minor !== undefined ? (
            <div className="rounded-2xl border bg-muted/30 p-4 text-center">
              <span className="text-xs text-muted-foreground uppercase font-bold tracking-wider">
                Tổng số tiền thanh toán
              </span>
              <div className="text-2xl sm:text-3xl font-black text-primary mt-0.5 tabular-nums">
                {order.total_amount_minor.toLocaleString('vi-VN')} {order.currency_code || 'VND'}
              </div>
            </div>
          ) : null}

          {/* Next Action / Guidance Alert */}
          {order.next_action ? (
            <Alert className={isPaid ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-primary/20 bg-primary/5'}>
              <Info className="size-4 text-primary shrink-0" />
              <AlertTitle className="text-xs sm:text-sm font-bold">Hướng dẫn tiếp theo</AlertTitle>
              <AlertDescription className="text-xs text-muted-foreground leading-relaxed">
                {order.next_action}
              </AlertDescription>
            </Alert>
          ) : null}

          {/* Order Details List */}
          {order.order_detail_lines && order.order_detail_lines.length > 0 ? (
            <div className="rounded-2xl border border-border/80 bg-card p-4 space-y-2.5 shadow-2xs">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                Chi tiết phiên giao dịch
              </h4>
              <div className="divide-y divide-border/60 text-xs">
                {order.order_detail_lines.map((line) => (
                  <div key={line.key} className="flex items-center justify-between py-2 gap-3">
                    <span className="text-muted-foreground">{line.label}</span>
                    <span className="font-semibold text-foreground text-right truncate max-w-[65%]">
                      {line.type === 'amount_minor' && line.value_minor !== undefined
                        ? `${line.value_minor.toLocaleString('vi-VN')} ${line.currency_code || 'VND'}`
                        : line.value || '—'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            {isPaid ? (
              <>
                {isDeck && firstItem?.product_ref_id ? (
                  <Button asChild size="lg" className="flex-1 font-bold rounded-xl shadow-md">
                    <Link to={`/marketplace/decks/${firstItem.product_ref_id}`}>
                      <BookOpen className="size-4 mr-1.5" /> Đến bộ thẻ vừa mua
                    </Link>
                  </Button>
                ) : isNoteType && firstItem?.product_ref_id ? (
                  <Button asChild size="lg" className="flex-1 font-bold rounded-xl shadow-md">
                    <Link to={`/marketplace/note-types/${firstItem.product_ref_id}`}>
                      <BookOpen className="size-4 mr-1.5" /> Đến loại thẻ vừa mua
                    </Link>
                  </Button>
                ) : isDonation ? (
                  <Button asChild size="lg" className="flex-1 font-bold rounded-xl shadow-md bg-gradient-to-r from-emerald-600 to-teal-600 text-white">
                    <Link to="/support">
                      <Heart className="size-4 mr-1.5 fill-current" /> Quay lại trang Ủng hộ
                    </Link>
                  </Button>
                ) : (
                  <Button asChild size="lg" className="flex-1 font-bold rounded-xl shadow-md">
                    <Link to="/orders">
                      <ShoppingBag className="size-4 mr-1.5" /> Xem đơn hàng của tôi
                    </Link>
                  </Button>
                )}

                <Button variant="outline" size="lg" asChild className="rounded-xl">
                  <Link to="/marketplace/decks">Khám phá Marketplace</Link>
                </Button>
              </>
            ) : isPending ? (
              <>
                {order.active_attempt?.checkout_url ? (
                  <Button asChild size="lg" className="flex-1 font-bold rounded-xl bg-gradient-to-r from-primary to-orange-500 shadow-md">
                    <a href={order.active_attempt.checkout_url} target="_blank" rel="noreferrer">
                      <ExternalLink className="size-4 mr-1.5" /> Mở lại trang thanh toán
                    </a>
                  </Button>
                ) : null}

                <Button
                  variant="outline"
                  size="lg"
                  className="rounded-xl font-semibold"
                  onClick={handleManualReconcile}
                  disabled={isManualReconciling || query.isFetching}
                >
                  <RefreshCw className={`size-4 mr-1.5 ${isManualReconciling || query.isFetching ? 'animate-spin' : ''}`} />
                  Kiểm tra lại trạng thái
                </Button>
              </>
            ) : (
              <>
                {firstItem?.product_type === 'deck_marketplace_item' ? (
                  <Button asChild size="lg" className="flex-1 font-bold rounded-xl">
                    <Link to={`/marketplace/decks/${firstItem.product_ref_id}`}>
                      <ArrowRight className="size-4 mr-1.5" /> Thử tạo đơn mới
                    </Link>
                  </Button>
                ) : isDonation ? (
                  <Button asChild size="lg" className="flex-1 font-bold rounded-xl">
                    <Link to="/support">
                      <Heart className="size-4 mr-1.5" /> Thử ủng hộ lại
                    </Link>
                  </Button>
                ) : (
                  <Button asChild size="lg" className="flex-1 font-bold rounded-xl">
                    <Link to="/marketplace/decks">Quay lại Marketplace</Link>
                  </Button>
                )}
                <Button variant="outline" size="lg" asChild className="rounded-xl">
                  <Link to="/orders">Lịch sử đơn hàng</Link>
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </Page>
  )
}
