import { ArrowRight, BookOpen, ExternalLink, Heart, RefreshCw, ShoppingBag } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useTranslation } from 'react-i18next'

interface OrderItem {
  id?: string | null
  product_type: string
  product_ref_id: string
  title_snapshot?: string | null
  unit_amount_minor?: number
  line_total_amount_minor?: number
}

interface PaymentResultActionsProps {
  isPaid: boolean
  isPending: boolean
  isDeck: boolean
  isNoteType: boolean
  isDonation: boolean
  firstItem?: OrderItem
  checkoutUrl?: string | null
  isManualReconciling: boolean
  isFetching: boolean
  onManualReconcile: () => void
}

export function PaymentResultActions({
  isPaid,
  isPending,
  isDeck,
  isNoteType,
  isDonation,
  firstItem,
  checkoutUrl,
  isManualReconciling,
  isFetching,
  onManualReconcile,
}: PaymentResultActionsProps) {
  const { t } = useTranslation('marketplace')

  return (
    <div className="flex flex-col sm:flex-row gap-3 pt-2">
      {isPaid ? (
        <>
          {isDeck && firstItem?.product_ref_id ? (
            <Button asChild size="lg" className="flex-1 font-bold rounded-xl shadow-md">
              <Link to={`/marketplace/decks/${firstItem.product_ref_id}`}>
                <BookOpen className="size-4 mr-1.5" />
                {t('payment_result.btn_goto_deck', 'Đến bộ thẻ vừa mua')}
              </Link>
            </Button>
          ) : isNoteType && firstItem?.product_ref_id ? (
            <Button asChild size="lg" className="flex-1 font-bold rounded-xl shadow-md">
              <Link to={`/marketplace/note-types/${firstItem.product_ref_id}`}>
                <BookOpen className="size-4 mr-1.5" />
                {t('payment_result.btn_goto_notetype', 'Đến loại thẻ vừa mua')}
              </Link>
            </Button>
          ) : isDonation ? (
            <Button asChild size="lg" className="flex-1 font-bold rounded-xl shadow-md bg-gradient-to-r from-emerald-600 to-teal-600 text-white">
              <Link to="/support">
                <Heart className="size-4 mr-1.5 fill-current" />
                {t('payment_result.btn_goto_support', 'Quay lại trang Ủng hộ')}
              </Link>
            </Button>
          ) : (
            <Button asChild size="lg" className="flex-1 font-bold rounded-xl shadow-md">
              <Link to="/orders">
                <ShoppingBag className="size-4 mr-1.5" />
                {t('payment_result.btn_goto_orders', 'Xem đơn hàng của tôi')}
              </Link>
            </Button>
          )}

          <Button variant="outline" size="lg" asChild className="rounded-xl">
            <Link to="/marketplace/decks">
              {t('payment_result.btn_explore_market', 'Khám phá Marketplace')}
            </Link>
          </Button>
        </>
      ) : isPending ? (
        <>
          {checkoutUrl ? (
            <Button asChild size="lg" className="flex-1 font-bold rounded-xl bg-gradient-to-r from-primary to-orange-500 shadow-md">
              <a href={checkoutUrl} target="_blank" rel="noreferrer">
                <ExternalLink className="size-4 mr-1.5" />
                {t('payment_result.btn_reopen_checkout', 'Mở lại trang thanh toán')}
              </a>
            </Button>
          ) : null}

          <Button
            variant="outline"
            size="lg"
            className="rounded-xl font-semibold"
            onClick={onManualReconcile}
            disabled={isManualReconciling || isFetching}
          >
            <RefreshCw className={`size-4 mr-1.5 ${isManualReconciling || isFetching ? 'animate-spin' : ''}`} />
            {t('payment_result.btn_recheck', 'Kiểm tra lại trạng thái')}
          </Button>
        </>
      ) : (
        <>
          {firstItem?.product_type === 'deck_marketplace_item' ? (
            <Button asChild size="lg" className="flex-1 font-bold rounded-xl">
              <Link to={`/marketplace/decks/${firstItem.product_ref_id}`}>
                <ArrowRight className="size-4 mr-1.5" />
                {t('payment_result.btn_retry_new', 'Thử tạo đơn mới')}
              </Link>
            </Button>
          ) : isDonation ? (
            <Button asChild size="lg" className="flex-1 font-bold rounded-xl">
              <Link to="/support">
                <Heart className="size-4 mr-1.5" />
                {t('payment_result.btn_retry_support', 'Thử ủng hộ lại')}
              </Link>
            </Button>
          ) : (
            <Button asChild size="lg" className="flex-1 font-bold rounded-xl">
              <Link to="/marketplace/decks">
                {t('payment_result.btn_back_market', 'Quay lại Marketplace')}
              </Link>
            </Button>
          )}
          <Button variant="outline" size="lg" asChild className="rounded-xl">
            <Link to="/orders">
              {t('payment_result.btn_orders_history_short', 'Lịch sử đơn hàng')}
            </Link>
          </Button>
        </>
      )}
    </div>
  )
}
