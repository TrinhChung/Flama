import { useState } from 'react'
import {
  Eye,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Page, PageHeader, SectionCard, StatCard } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

export type PaymentOrderRow = {
  id: string
  merchant_order_code: string
  title?: string
  status_label: string
  status?: string
  total_amount_display: string
  created_at?: string
  user_email?: string
}

export type PaymentTransactionRow = {
  id: string
  order_id?: string
  merchant_order_code?: string
  status: string
  status_label?: string
  amount_display: string
  provider_code?: string
  created_at?: string
}

export type PaymentOrdersResponse = {
  items: PaymentOrderRow[]
  total: number
  page: number
  per_page: number
  pages: number
}

export type PaymentTransactionsResponse = {
  items: PaymentTransactionRow[]
  total: number
  page: number
  per_page: number
  pages: number
}

type PaymentCard = {
  label: string
  value: string
  tone: string
  hint: string
}

type PaymentDashboard = {
  cards: PaymentCard[]
  recent_orders: Array<{
    id: string
    merchant_order_code: string
    title: string
    status_label: string
    total_amount_display: string
  }>
}
function AdminHeader({
  title,
  description,
}: {
  title: string
  description?: string
}) {
  return (
    <div className="space-y-3">
      <Badge variant="destructive" className="gap-1 font-semibold">
        <ShieldCheck className="size-3.5" /> Admin
      </Badge>
      <PageHeader title={title} description={description} />
    </div>
  )
}

export function AdminPaymentsPage() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'orders' | 'transactions'>('dashboard')
  
  // Dashboard query
  const dashQuery = useQuery({
    queryKey: ['admin', 'payments-dashboard'],
    queryFn: () => appApi.get<PaymentDashboard>('/admin/payments'),
    enabled: activeTab === 'dashboard',
  })

  // Orders state & query
  const [ordersPage, setOrdersPage] = useState(1)
  const [ordersSearch, setOrdersSearch] = useState('')
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)
  
  const ordersQuery = useQuery({
    queryKey: ['admin', 'payments-orders', ordersSearch, ordersPage],
    queryFn: () =>
      appApi.get<PaymentOrdersResponse>('/admin/payments/orders', {
        q: ordersSearch,
        page: ordersPage,
        per_page: 20,
      }),
    enabled: activeTab === 'orders',
  })

  const orderDetailQuery = useQuery({
    queryKey: ['admin', 'payments-order-detail', selectedOrderId],
    queryFn: () => appApi.get<any>(`/admin/payments/orders/${selectedOrderId}`),
    enabled: Boolean(selectedOrderId),
  })

  // Transactions state & query
  const [txPage, setTxPage] = useState(1)
  const [txSearch, setTxSearch] = useState('')
  const [selectedTxId, setSelectedTxId] = useState<string | null>(null)

  const txQuery = useQuery({
    queryKey: ['admin', 'payments-transactions', txSearch, txPage],
    queryFn: () =>
      appApi.get<PaymentTransactionsResponse>('/admin/payments/transactions', {
        q: txSearch,
        page: txPage,
        per_page: 20,
      }),
    enabled: activeTab === 'transactions',
  })

  const txDetailQuery = useQuery({
    queryKey: ['admin', 'payments-tx-detail', selectedTxId],
    queryFn: () => appApi.get<any>(`/admin/payments/transactions/${selectedTxId}`),
    enabled: Boolean(selectedTxId),
  })

  return (
    <Page>
      <AdminHeader
        title="Quản lý Thanh toán & Đơn hàng"
        description="Tổng quan giao dịch, danh sách đơn hàng payOS và lịch sử giao dịch."
      />

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
        <TabsList className="w-full justify-start sm:w-auto">
          <TabsTrigger value="dashboard">Dashboard Tổng quan</TabsTrigger>
          <TabsTrigger value="orders">Danh sách Đơn hàng</TabsTrigger>
          <TabsTrigger value="transactions">Lịch sử Giao dịch</TabsTrigger>
        </TabsList>
      </Tabs>

      {activeTab === 'dashboard' && (
        <>
          {dashQuery.isPending ? (
            <PageLoading label="Đang tải Dashboard thanh toán…" />
          ) : dashQuery.error ? (
            <PageError error={dashQuery.error} />
          ) : (
            <div className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {dashQuery.data.cards.map((item) => (
                  <StatCard
                    key={item.label}
                    label={item.label}
                    value={item.value}
                    hint={item.hint}
                    tone={
                      item.tone === 'success'
                        ? 'success'
                        : item.tone === 'warning' || item.tone === 'danger'
                          ? 'warning'
                          : item.tone === 'primary'
                            ? 'primary'
                            : 'default'
                    }
                  />
                ))}
              </div>

              <SectionCard title="Đơn hàng gần đây">
                {!dashQuery.data.recent_orders.length ? (
                  <p className="text-sm text-muted-foreground">Chưa có giao dịch trong kỳ.</p>
                ) : (
                  <div className="space-y-3">
                    {dashQuery.data.recent_orders.map((order) => (
                      <div
                        key={order.id}
                        className="flex flex-wrap items-center justify-between gap-3 border-b pb-3 last:border-0 last:pb-0"
                      >
                        <div>
                          <p className="font-medium">{order.title}</p>
                          <p className="font-mono text-xs text-muted-foreground">
                            {order.merchant_order_code}
                          </p>
                        </div>
                        <div className="text-right text-sm">
                          <p className="font-semibold">{order.total_amount_display}</p>
                          <p className="text-muted-foreground text-xs">{order.status_label}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            </div>
          )}
        </>
      )}

      {activeTab === 'orders' && (
        <div className="space-y-4">
          <Card className="shadow-xs">
            <CardContent className="p-4 flex gap-3">
              <div className="relative flex-1">
                <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="pl-9"
                  placeholder="Tìm theo mã đơn hàng, tiêu đề..."
                  value={ordersSearch}
                  onChange={(e) => {
                    setOrdersSearch(e.target.value)
                    setOrdersPage(1)
                  }}
                />
              </div>
            </CardContent>
          </Card>

          {ordersQuery.isPending ? (
            <PageLoading label="Đang tải danh sách đơn hàng…" />
          ) : ordersQuery.error ? (
            <PageError error={ordersQuery.error} />
          ) : !ordersQuery.data.items.length ? (
            <EmptyState title="Không tìm thấy đơn hàng nào" description="Thử đổi từ khóa tìm kiếm." />
          ) : (
            <Card className="shadow-xs overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40">
                    <TableHead>Mã đơn hàng</TableHead>
                    <TableHead>Nội dung</TableHead>
                    <TableHead>Số tiền</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead className="text-right">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ordersQuery.data.items.map((order) => (
                    <TableRow key={order.id}>
                      <TableCell className="font-mono text-xs font-bold">
                        {order.merchant_order_code || order.id}
                      </TableCell>
                      <TableCell>{order.title || 'Học liệu Marketplace'}</TableCell>
                      <TableCell className="font-semibold text-sm">
                        {order.total_amount_display}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{order.status_label || order.status}</Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSelectedOrderId(order.id)}
                        >
                          <Eye className="mr-1 size-3.5" /> Chi tiết
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {ordersQuery.data.pages > 1 && (
                <div className="flex items-center justify-between border-t p-3 text-xs">
                  <span>Trang {ordersPage} / {ordersQuery.data.pages}</span>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={ordersPage <= 1}
                      onClick={() => setOrdersPage((p) => Math.max(p - 1, 1))}
                    >
                      Trước
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={ordersPage >= ordersQuery.data.pages}
                      onClick={() => setOrdersPage((p) => Math.min(p + 1, ordersQuery.data.pages))}
                    >
                      Sau
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>
      )}

      {activeTab === 'transactions' && (
        <div className="space-y-4">
          <Card className="shadow-xs">
            <CardContent className="p-4 flex gap-3">
              <div className="relative flex-1">
                <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="pl-9"
                  placeholder="Tìm theo mã giao dịch..."
                  value={txSearch}
                  onChange={(e) => {
                    setTxSearch(e.target.value)
                    setTxPage(1)
                  }}
                />
              </div>
            </CardContent>
          </Card>

          {txQuery.isPending ? (
            <PageLoading label="Đang tải lịch sử giao dịch…" />
          ) : txQuery.error ? (
            <PageError error={txQuery.error} />
          ) : !txQuery.data.items.length ? (
            <EmptyState title="Không tìm thấy giao dịch nào" description="Thử đổi từ khóa tìm kiếm." />
          ) : (
            <Card className="shadow-xs overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40">
                    <TableHead>Mã Attempt ID</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Số tiền</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead className="text-right">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {txQuery.data.items.map((tx) => (
                    <TableRow key={tx.id}>
                      <TableCell className="font-mono text-xs font-bold">{tx.id}</TableCell>
                      <TableCell className="uppercase text-xs">{tx.provider_code || 'PayOS'}</TableCell>
                      <TableCell className="font-semibold text-sm">{tx.amount_display}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{tx.status_label || tx.status}</Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSelectedTxId(tx.id)}
                        >
                          <Eye className="mr-1 size-3.5" /> Chi tiết
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {txQuery.data.pages > 1 && (
                <div className="flex items-center justify-between border-t p-3 text-xs">
                  <span>Trang {txPage} / {txQuery.data.pages}</span>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={txPage <= 1}
                      onClick={() => setTxPage((p) => Math.max(p - 1, 1))}
                    >
                      Trước
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={txPage >= txQuery.data.pages}
                      onClick={() => setTxPage((p) => Math.min(p + 1, txQuery.data.pages))}
                    >
                      Sau
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>
      )}

      {/* Order Detail Modal */}
      <Dialog open={selectedOrderId !== null} onOpenChange={(open) => !open && setSelectedOrderId(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Chi tiết Đơn hàng</DialogTitle>
            <DialogDescription>Mã đơn hàng: #{selectedOrderId}</DialogDescription>
          </DialogHeader>
          {orderDetailQuery.isPending ? (
            <PageLoading label="Đang tải chi tiết đơn hàng…" />
          ) : orderDetailQuery.data ? (
            <div className="space-y-4 text-sm py-2">
              <div className="grid grid-cols-2 gap-2 border-b pb-3">
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Mã Merchant</p>
                  <p className="font-mono font-semibold">
                    {orderDetailQuery.data.merchant_order_code || orderDetailQuery.data.order_code || '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Trạng thái</p>
                  <Badge variant="outline">
                    {orderDetailQuery.data.status_label || orderDetailQuery.data.status}
                  </Badge>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Tổng tiền</p>
                  <p className="font-bold text-emerald-600">
                    {orderDetailQuery.data.total_amount_display || `${orderDetailQuery.data.amount || 0} VND`}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Khách hàng</p>
                  <p className="font-medium">{orderDetailQuery.data.user_name || orderDetailQuery.data.user_email || 'Khách'}</p>
                </div>
              </div>
              {orderDetailQuery.data.items && (
                <div>
                  <p className="font-semibold mb-2">Học liệu mua:</p>
                  <div className="space-y-1 bg-muted/40 p-2.5 rounded-md text-xs">
                    {orderDetailQuery.data.items.map((it: any, i: number) => (
                      <div key={i} className="flex justify-between">
                        <span>{it.title || it.name}</span>
                        <span className="font-semibold">{it.price_display || `${it.price || 0} VND`}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedOrderId(null)}>
              Đóng
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Transaction Detail Modal */}
      <Dialog open={selectedTxId !== null} onOpenChange={(open) => !open && setSelectedTxId(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Chi tiết Giao dịch</DialogTitle>
            <DialogDescription>Attempt ID: #{selectedTxId}</DialogDescription>
          </DialogHeader>
          {txDetailQuery.isPending ? (
            <PageLoading label="Đang tải chi tiết giao dịch…" />
          ) : txDetailQuery.data ? (
            <div className="space-y-4 text-sm py-2">
              <div className="grid grid-cols-2 gap-2 border-b pb-3">
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Mã Đơn hàng</p>
                  <p className="font-mono font-semibold">
                    {txDetailQuery.data.order_id || '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Trạng thái</p>
                  <Badge variant="outline">
                    {txDetailQuery.data.status_label || txDetailQuery.data.status}
                  </Badge>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Số tiền</p>
                  <p className="font-bold text-emerald-600">
                    {txDetailQuery.data.amount_display || `${txDetailQuery.data.amount || 0} VND`}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Cổng thanh toán</p>
                  <p className="font-medium uppercase">{txDetailQuery.data.provider_code || 'PayOS'}</p>
                </div>
              </div>
              {txDetailQuery.data.raw_response && (
                <div>
                  <p className="font-semibold mb-1 text-xs">Raw Provider Payload:</p>
                  <pre className="bg-slate-950 text-slate-100 p-2.5 rounded-md text-[11px] font-mono overflow-x-auto max-h-48">
                    {JSON.stringify(txDetailQuery.data.raw_response, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedTxId(null)}>
              Đóng
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  )
}


