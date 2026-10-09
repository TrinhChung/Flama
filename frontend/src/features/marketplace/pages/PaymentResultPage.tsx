import { useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
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
import { PaymentResultStatusCard } from '../components/payment/PaymentResultStatusCard'
import { PaymentResultDetails, type OrderDetailLine } from '../components/payment/PaymentResultDetails'
import { PaymentResultActions } from '../components/payment/PaymentResultActions'

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
  const { t } = useTranslation('marketplace')
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
      throw new Error(
        t('payment_result.error_default_desc', 'Không tìm thấy thông tin đơn hàng hoặc mã giao dịch hợp lệ.')
      )
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
      toast.success(
        t('payment_result.toast_status_updated', 'Đã cập nhật trạng thái thanh toán mới nhất!')
      )
    } catch (err: any) {
      toast.error(
        t('payment_result.toast_error_recheck', 'Lỗi khi kiểm tra lại trạng thái'),
        {
          description:
            err?.message ||
            t('payment_result.toast_error_recheck_desc', 'Vui lòng thử lại sau ít phút.'),
        }
      )
    } finally {
      setIsManualReconciling(false)
    }
  }

  if (query.isPending) {
    return (
      <Page>
        <PageLoading
          label={t('payment_result.loading_label', 'Đang kiểm tra kết quả thanh toán…')}
        />
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
            <CardTitle className="text-xl">
              {t('payment_result.error_title', 'Không thể tải thông tin thanh toán')}
            </CardTitle>
            <CardDescription>
              {query.error?.message ||
                t(
                  'payment_result.error_default_desc',
                  'Mã đơn hàng không hợp lệ hoặc phiên thanh toán đã kết thúc.'
                )}
            </CardDescription>
          </CardHeader>
          <CardFooter className="flex justify-center gap-3">
            <Button variant="outline" asChild>
              <Link to="/orders">
                {t('payment_result.btn_orders_history', 'Xem lịch sử đơn hàng')}
              </Link>
            </Button>
            <Button asChild>
              <Link to="/marketplace/decks">
                {t('payment_result.btn_back_market', 'Quay lại Marketplace')}
              </Link>
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
        <PaymentResultStatusCard
          status={status}
          isPaid={isPaid}
          isPending={isPending}
          isUnderReview={isUnderReview}
          isDonation={isDonation}
          merchantOrderCode={order.merchant_order_code}
          headline={order.headline}
          statusDisplay={order.status_display}
          message={order.message}
        />

        <CardContent className="p-6 pt-0 space-y-5">
          <PaymentResultDetails
            totalAmountMinor={order.total_amount_minor}
            currencyCode={order.currency_code}
            nextAction={order.next_action}
            isPaid={isPaid}
            orderDetailLines={order.order_detail_lines}
          />

          <PaymentResultActions
            isPaid={isPaid}
            isPending={isPending}
            isDeck={isDeck}
            isNoteType={isNoteType}
            isDonation={isDonation}
            firstItem={firstItem}
            checkoutUrl={order.active_attempt?.checkout_url}
            isManualReconciling={isManualReconciling}
            isFetching={query.isFetching}
            onManualReconcile={handleManualReconcile}
          />
        </CardContent>
      </Card>
    </Page>
  )
}
