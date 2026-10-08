import { Eye, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Page, PageHeader } from '@/shared/components/Page'
import {
  EmptyState,
  PageError,
  PageLoading,
} from '@/shared/components/PageState'
import { OrderDetailDialog } from '../components/OrderDetailDialog'
import { useOrders } from '../hooks/useOrders'

function badgeVariant(tone: string) {
  if (tone === 'danger') return 'destructive' as const
  if (tone === 'success') return 'secondary' as const
  return 'outline' as const
}

export function OrdersPage() {
  const { t } = useTranslation('orders')
  const {
    ordersQuery,
    selectedOrderId,
    setSelectedOrderId,
    orderDetailQuery,
    syncingOrderId,
    handleSyncOrder,
  } = useOrders()

  if (ordersQuery.isPending) return <PageLoading label={t('loading')} />
  if (ordersQuery.error) {
    return (
      <Page>
        <PageError error={ordersQuery.error} />
      </Page>
    )
  }

  return (
    <Page>
      <PageHeader
        title={t('title')}
        description={t('description')}
      />
      {!ordersQuery.data.items.length ? (
        <EmptyState
          title={t('empty.title')}
          description={t('empty.description')}
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <Table className="min-w-190">
              <TableHeader>
                <TableRow>
                  <TableHead>{t('table.order_code')}</TableHead>
                  <TableHead>{t('table.item')}</TableHead>
                  <TableHead>{t('table.date')}</TableHead>
                  <TableHead>{t('table.amount')}</TableHead>
                  <TableHead>{t('table.status')}</TableHead>
                  <TableHead className="text-right">{t('table.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ordersQuery.data.items.map((order) => {
                  const isPending =
                    order.status === 'pending_payment' || order.status === 'created'
                  return (
                    <TableRow key={order.id}>
                      <TableCell className="font-mono text-xs font-semibold">
                        {order.merchant_order_code || order.id}
                      </TableCell>
                      <TableCell className="font-medium">{order.title}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {order.created_at_display}
                      </TableCell>
                      <TableCell className="font-semibold text-sm">
                        {order.total_amount_display}
                      </TableCell>
                      <TableCell>
                        <Badge variant={badgeVariant(order.status_tone)}>
                          {order.status_label || order.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {isPending ? (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-8 text-xs font-semibold"
                              onClick={(e) => handleSyncOrder(order.id, e)}
                              disabled={syncingOrderId === order.id}
                            >
                              <RefreshCw
                                className={`size-3 mr-1 ${syncingOrderId === order.id ? 'animate-spin' : ''}`}
                              />
                              {t('actions.check')}
                            </Button>
                          ) : null}

                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 text-xs"
                            onClick={() => setSelectedOrderId(order.id)}
                          >
                            <Eye className="size-3.5 mr-1" /> {t('actions.details')}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
          <div className="border-t px-4 py-3 text-sm text-muted-foreground">
            {t('table.total_count', { count: ordersQuery.data.total })}
          </div>
        </Card>
      )}

      <OrderDetailDialog
        selectedOrderId={selectedOrderId}
        onClose={() => setSelectedOrderId(null)}
        orderDetail={orderDetailQuery.data}
        isLoading={orderDetailQuery.isPending}
        isSyncing={syncingOrderId === selectedOrderId}
        onSync={handleSyncOrder}
      />
    </Page>
  )
}
