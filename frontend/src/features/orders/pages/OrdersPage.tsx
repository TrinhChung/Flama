import { useState } from 'react'
import {
  Clock,
  ExternalLink,
  Eye,
  RefreshCw,
} from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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

type OrderRow = {
  id: string
  merchant_order_code: string
  title: string
  total_amount_display: string
  status: string
  status_label: string
  status_tone: string
  grant_status?: string
  grant_status_label?: string
  created_at_display: string
  serialized?: any
}

type OrdersResponse = {
  items: OrderRow[]
  total: number
}

function badgeVariant(tone: string) {
  if (tone === 'danger') return 'destructive' as const
  if (tone === 'success') return 'secondary' as const
  return 'outline' as const
}

export function OrdersPage() {
  const queryClient = useQueryClient()
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)
  const [syncingOrderId, setSyncingOrderId] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['orders'],
    queryFn: () => appApi.get<OrdersResponse>('/orders'),
  })

  const orderDetailQuery = useQuery({
    queryKey: ['order-detail', selectedOrderId],
    queryFn: () => appApi.get<any>(`/api/payments/orders/${selectedOrderId}`),
    enabled: Boolean(selectedOrderId),
  })

  const handleSyncOrder = async (orderId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    setSyncingOrderId(orderId)
    try {
      await appApi.get(`/api/payments/orders/${orderId}`)
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: ['order-detail', orderId] })
      toast.success('Đã cập nhật và đối soát đơn hàng từ PayOS!')
    } catch (err: any) {
      toast.error('Không thể cập nhật trạng thái', {
        description: err?.message || 'Vui lòng thử lại sau.',
      })
    } finally {
      setSyncingOrderId(null)
    }
  }

  if (query.isPending) return <PageLoading label="Đang tải đơn hàng…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page>
      <PageHeader
        title="Lịch sử đơn hàng"
        description="Theo dõi giao dịch marketplace và quyền truy cập học liệu."
      />
      {!query.data.items.length ? (
        <EmptyState
          title="Chưa có đơn hàng"
          description="Các giao dịch marketplace của bạn sẽ xuất hiện tại đây."
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <Table className="min-w-190">
              <TableHeader>
                <TableRow>
                  <TableHead>Mã đơn</TableHead>
                  <TableHead>Học liệu</TableHead>
                  <TableHead>Thời gian</TableHead>
                  <TableHead>Giá trị</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead className="text-right">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.map((order) => {
                  const isPending = order.status === 'pending_payment' || order.status === 'created'
                  return (
                    <TableRow key={order.id}>
                      <TableCell className="font-mono text-xs font-semibold">
                        {order.merchant_order_code || order.id}
                      </TableCell>
                      <TableCell className="font-medium">{order.title}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{order.created_at_display}</TableCell>
                      <TableCell className="font-semibold text-sm">{order.total_amount_display}</TableCell>
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
                              Đối soát
                            </Button>
                          ) : null}

                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 text-xs"
                            onClick={() => setSelectedOrderId(order.id)}
                          >
                            <Eye className="size-3.5 mr-1" /> Chi tiết
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
            Tổng cộng {query.data.total} đơn hàng
          </div>
        </Card>
      )}

      {/* Order Detail Modal */}
      <Dialog open={selectedOrderId !== null} onOpenChange={(open) => !open && setSelectedOrderId(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Chi tiết Đơn hàng</DialogTitle>
            <DialogDescription>
              Mã đơn hàng: #{orderDetailQuery.data?.merchant_order_code || selectedOrderId}
            </DialogDescription>
          </DialogHeader>

          {orderDetailQuery.isPending ? (
            <PageLoading label="Đang tải chi tiết đơn hàng…" />
          ) : orderDetailQuery.data ? (
            <div className="space-y-4 text-sm py-2">
              <div className="grid grid-cols-2 gap-3 border-b pb-3 text-xs">
                <div>
                  <span className="text-muted-foreground uppercase text-[10px] font-bold">Mã giao dịch</span>
                  <p className="font-mono font-semibold text-foreground mt-0.5">
                    {orderDetailQuery.data.merchant_order_code || orderDetailQuery.data.id}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground uppercase text-[10px] font-bold">Trạng thái</span>
                  <div className="mt-0.5">
                    <Badge variant="outline">
                      {orderDetailQuery.data.status_display?.label || orderDetailQuery.data.status}
                    </Badge>
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground uppercase text-[10px] font-bold">Tổng thanh toán</span>
                  <p className="font-bold text-primary text-sm mt-0.5">
                    {orderDetailQuery.data.total_amount_minor
                      ? `${orderDetailQuery.data.total_amount_minor.toLocaleString('vi-VN')} ${orderDetailQuery.data.currency_code || 'VND'}`
                      : '—'}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground uppercase text-[10px] font-bold">Cấp quyền</span>
                  <div className="mt-0.5">
                    <Badge variant="secondary">
                      {orderDetailQuery.data.grant_status_display?.label || orderDetailQuery.data.grant_status || 'Hoàn tất'}
                    </Badge>
                  </div>
                </div>
              </div>

              {orderDetailQuery.data.items && orderDetailQuery.data.items.length > 0 && (
                <div>
                  <p className="font-bold text-xs uppercase text-muted-foreground mb-2">Học liệu trong đơn:</p>
                  <div className="space-y-1.5 bg-muted/40 p-3 rounded-xl text-xs">
                    {orderDetailQuery.data.items.map((it: any, i: number) => (
                      <div key={i} className="flex justify-between items-center">
                        <span className="font-medium text-foreground">{it.title_snapshot || it.title || it.name}</span>
                        <span className="font-semibold text-primary">
                          {it.unit_amount_minor
                            ? `${it.unit_amount_minor.toLocaleString('vi-VN')} VND`
                            : 'Miễn phí'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {orderDetailQuery.data.status === 'pending_payment' && orderDetailQuery.data.active_attempt?.checkout_url && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-amber-700 dark:text-amber-300">
                    <Clock className="size-4 shrink-0 animate-pulse" />
                    <span>Đơn hàng đang chờ thanh toán qua PayOS</span>
                  </div>
                  <Button size="sm" asChild className="h-7 text-xs font-bold rounded-lg shrink-0">
                    <a href={orderDetailQuery.data.active_attempt.checkout_url} target="_blank" rel="noreferrer">
                      <ExternalLink className="size-3 mr-1" /> Mở PayOS
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
                onClick={() => handleSyncOrder(selectedOrderId)}
                disabled={syncingOrderId === selectedOrderId}
              >
                <RefreshCw className={`size-3.5 mr-1.5 ${syncingOrderId === selectedOrderId ? 'animate-spin' : ''}`} />
                Kiểm tra lại với PayOS
              </Button>
            )}
            <Button variant="default" size="sm" onClick={() => setSelectedOrderId(null)}>
              Đóng
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  )
}

