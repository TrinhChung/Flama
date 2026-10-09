import { Clock, ExternalLink, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { PageLoading } from '@/shared/components/PageState'

interface OrderDetailDialogProps {
  selectedOrderId: string | null
  onClose: () => void
  orderDetail: any
  isLoading: boolean
  isSyncing: boolean
  onSync: (orderId: string) => void
}

export function OrderDetailDialog({
  selectedOrderId,
  onClose,
  orderDetail,
  isLoading,
  isSyncing,
  onSync,
}: OrderDetailDialogProps) {
  const { t } = useTranslation('orders')

  return (
    <Dialog open={selectedOrderId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('detail.title')}</DialogTitle>
          <DialogDescription>
            {t('detail.code_description', {
              code: orderDetail?.merchant_order_code || selectedOrderId || '',
            })}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <PageLoading label={t('detail_loading')} />
        ) : orderDetail ? (
          <div className="space-y-4 text-sm py-2">
            <div className="grid grid-cols-2 gap-3 border-b pb-3 text-xs">
              <div>
                <span className="text-muted-foreground uppercase text-[10px] font-bold">
                  {t('detail.transaction_code')}
                </span>
                <p className="font-mono font-semibold text-foreground mt-0.5">
                  {orderDetail.merchant_order_code || orderDetail.id}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground uppercase text-[10px] font-bold">
                  {t('detail.status')}
                </span>
                <div className="mt-0.5">
                  <Badge variant="outline">
                    {orderDetail.status_display?.label || orderDetail.status}
                  </Badge>
                </div>
              </div>
              <div>
                <span className="text-muted-foreground uppercase text-[10px] font-bold">
                  {t('detail.total_payment')}
                </span>
                <p className="font-bold text-primary text-sm mt-0.5">
                  {orderDetail.total_amount_minor
                    ? `${orderDetail.total_amount_minor.toLocaleString('vi-VN')} ${orderDetail.currency_code || 'VND'}`
                    : '—'}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground uppercase text-[10px] font-bold">
                  {t('detail.grant_status')}
                </span>
                <div className="mt-0.5">
                  <Badge variant="secondary">
                    {orderDetail.grant_status_display?.label ||
                      orderDetail.grant_status ||
                      t('detail.completed')}
                  </Badge>
                </div>
              </div>
            </div>

            {orderDetail.items && orderDetail.items.length > 0 && (
              <div>
                <p className="font-bold text-xs uppercase text-muted-foreground mb-2">
                  {t('detail.items_in_order')}
                </p>
                <div className="space-y-1.5 bg-muted/40 p-3 rounded-xl text-xs">
                  {orderDetail.items.map((it: any, i: number) => (
                    <div key={i} className="flex justify-between items-center">
                      <span className="font-medium text-foreground">
                        {it.title_snapshot || it.title || it.name}
                      </span>
                      <span className="font-semibold text-primary">
                        {it.unit_amount_minor
                          ? `${it.unit_amount_minor.toLocaleString('vi-VN')} VND`
                          : t('detail.free')}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {orderDetail.status === 'pending_payment' &&
              orderDetail.active_attempt?.checkout_url && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-amber-700 dark:text-amber-300">
                    <Clock className="size-4 shrink-0 animate-pulse" />
                    <span>{t('detail.pending_payment_banner')}</span>
                  </div>
                  <Button size="sm" asChild className="h-7 text-xs font-bold rounded-lg shrink-0">
                    <a
                      href={orderDetail.active_attempt.checkout_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ExternalLink className="size-3 mr-1" /> {t('detail.pay_now')}
                    </a>
                  </Button>
                </div>
              )}
          </div>
        ) : null}

        <DialogFooter className="flex gap-2">
          {selectedOrderId && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onSync(selectedOrderId)}
              disabled={isSyncing}
            >
              <RefreshCw
                className={`size-3.5 mr-1.5 ${isSyncing ? 'animate-spin' : ''}`}
              />
              {t('detail.recheck_status')}
            </Button>
          )}
          <Button variant="default" size="sm" onClick={onClose}>
            {t('detail.close')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
