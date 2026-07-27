import { useQuery } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
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

type OrderRow = {
  id: string
  merchant_order_code: string
  title: string
  total_amount_display: string
  status: string
  status_label: string
  status_tone: string
  created_at_display: string
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
  const query = useQuery({
    queryKey: ['orders'],
    queryFn: () => appApi.get<OrdersResponse>('/orders'),
  })

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
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.map((order) => (
                  <TableRow key={order.id}>
                    <TableCell className="font-mono text-xs">
                      {order.merchant_order_code || order.id}
                    </TableCell>
                    <TableCell className="font-medium">{order.title}</TableCell>
                    <TableCell>{order.created_at_display}</TableCell>
                    <TableCell>{order.total_amount_display}</TableCell>
                    <TableCell>
                      <Badge variant={badgeVariant(order.status_tone)}>
                        {order.status_label || order.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="border-t px-4 py-3 text-sm text-muted-foreground">
            Tổng cộng {query.data.total} đơn hàng
          </div>
        </Card>
      )}
    </Page>
  )
}
