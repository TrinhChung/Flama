import { useState } from 'react'
import {
  Eye,
  RefreshCw,
  Search,
  ShieldCheck,
  CheckCircle2,
  Clock,
  XCircle,
  AlertTriangle,
  RotateCcw,
  Copy,
  Check,
  SlidersHorizontal,
  ArrowUpDown,
  FileText,
  CreditCard,
  X,
  Filter
} from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
  item_count?: number
  total_amount_minor?: number
  total_amount_display: string
  status: string
  status_label: string
  status_tone?: string
  payment_status?: string
  payment_status_label?: string
  grant_status?: string
  grant_status_label?: string
  provider_code?: string
  created_at?: string
  created_at_display?: string
  paid_at?: string
  paid_at_display?: string
  buyer?: {
    user_id?: number
    username?: string
    display_name?: string
    email?: string
  }
  user_email?: string
  serialized?: any
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
  created_at_display?: string
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
    status: string
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

function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(text)
    setCopied(true)
    toast.success(`Đã copy: ${text}`)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 p-1 hover:bg-slate-200/80 rounded transition-colors text-slate-400 hover:text-slate-700"
      title={label}
    >
      {copied ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
    </button>
  )
}

function renderStatusBadge(status: string = '', label?: string) {
  const s = status.toLowerCase()
  const displayLabel = label || status || 'Không rõ'

  if (s === 'paid' || s === 'confirmed' || s === 'completed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 className="size-3 text-emerald-600" />
        <span>{displayLabel}</span>
      </span>
    )
  }
  if (s === 'pending_payment' || s === 'pending' || s === 'created') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        <Clock className="size-3 text-amber-600 animate-pulse" />
        <span>{displayLabel}</span>
      </span>
    )
  }
  if (s === 'under_review' || s === 'manual_review') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
        <AlertTriangle className="size-3 text-indigo-600" />
        <span>{displayLabel}</span>
      </span>
    )
  }
  if (s === 'canceled' || s === 'cancelled') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
        <XCircle className="size-3 text-rose-600" />
        <span>{displayLabel}</span>
      </span>
    )
  }
  if (s === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
        <AlertTriangle className="size-3 text-red-600" />
        <span>{displayLabel}</span>
      </span>
    )
  }
  if (s === 'expired') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
        <Clock className="size-3 text-slate-500" />
        <span>{displayLabel}</span>
      </span>
    )
  }
  if (s === 'refunded') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
        <RotateCcw className="size-3 text-purple-600" />
        <span>{displayLabel}</span>
      </span>
    )
  }
  return (
    <Badge variant="outline" className="text-xs">
      {displayLabel}
    </Badge>
  )
}

const ORDER_STATUS_FILTERS = [
  { value: 'all', label: 'Tất cả trạng thái' },
  { value: 'paid', label: 'Đã thanh toán', dot: 'bg-emerald-500' },
  { value: 'pending_payment', label: 'Chờ thanh toán', dot: 'bg-amber-500' },
  { value: 'under_review', label: 'Cần kiểm tra', dot: 'bg-indigo-500' },
  { value: 'canceled', label: 'Đã hủy', dot: 'bg-rose-500' },
  { value: 'refunded', label: 'Hoàn tiền', dot: 'bg-purple-500' },
]

const TX_STATUS_FILTERS = [
  { value: 'all', label: 'Tất cả trạng thái' },
  { value: 'confirmed', label: 'Đã xác nhận', dot: 'bg-emerald-500' },
  { value: 'pending', label: 'Đang chờ', dot: 'bg-amber-500' },
  { value: 'manual_review', label: 'Chờ duyệt', dot: 'bg-indigo-500' },
  { value: 'canceled', label: 'Đã hủy', dot: 'bg-rose-500' },
  { value: 'failed', label: 'Thất bại', dot: 'bg-red-500' },
]

const SORT_OPTIONS = [
  { value: 'created_desc', label: 'Mới nhất trước' },
  { value: 'created_asc', label: 'Cũ nhất trước' },
  { value: 'amount_desc', label: 'Số tiền: Cao → Thấp' },
  { value: 'amount_asc', label: 'Số tiền: Thấp → Cao' },
]

export function AdminPaymentsPage() {
  const [activeTab, setActiveTab] = useState<'orders' | 'transactions' | 'dashboard'>('orders')
  const queryClient = useQueryClient()

  // Sync state
  const [syncingOrderId, setSyncingOrderId] = useState<string | null>(null)

  // Manual status update modal state
  const [statusUpdateTarget, setStatusUpdateTarget] = useState<PaymentOrderRow | null>(null)
  const [targetNewStatus, setTargetNewStatus] = useState<string>('paid')
  const [statusUpdateNote, setStatusUpdateNote] = useState<string>('')
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false)

  // Orders filters & pagination
  const [ordersPage, setOrdersPage] = useState(1)
  const [ordersSearch, setOrdersSearch] = useState('')
  const [ordersStatus, setOrdersStatus] = useState('all')
  const [ordersSort, setOrdersSort] = useState('created_desc')
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)

  // Transactions filters & pagination
  const [txPage, setTxPage] = useState(1)
  const [txSearch, setTxSearch] = useState('')
  const [txStatus, setTxStatus] = useState('all')
  const [txSort, setTxSort] = useState('created_desc')
  const [selectedTxId, setSelectedTxId] = useState<string | null>(null)

  // 1. Sync handler (Call PayOS API)
  const handleSyncOrder = async (orderId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    setSyncingOrderId(orderId)
    try {
      await appApi.mutate(`/admin/payments/orders/${orderId}/sync`, 'POST')
      void queryClient.invalidateQueries({ queryKey: ['admin', 'payments-orders'] })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'payments-dashboard'] })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'payments-order-detail', orderId] })
      toast.success('Đã đồng bộ trạng thái đơn hàng từ PayOS thành công!')
    } catch (err: any) {
      toast.error('Không thể đồng bộ với PayOS', {
        description: err?.message || 'Vui lòng kiểm tra lại kết nối hoặc khóa API.',
      })
    } finally {
      setSyncingOrderId(null)
    }
  }

  // 2. Manual status update handler
  const handleConfirmStatusUpdate = async () => {
    if (!statusUpdateTarget) return
    setIsUpdatingStatus(true)
    try {
      await appApi.mutate(`/admin/payments/orders/${statusUpdateTarget.id}/status`, 'PATCH', {
        status: targetNewStatus,
        note: statusUpdateNote,
      })
      toast.success(`Đã cập nhật trạng thái đơn hàng sang '${targetNewStatus}'!`)
      void queryClient.invalidateQueries({ queryKey: ['admin', 'payments-orders'] })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'payments-dashboard'] })
      if (selectedOrderId) {
        void queryClient.invalidateQueries({ queryKey: ['admin', 'payments-order-detail', selectedOrderId] })
      }
      setStatusUpdateTarget(null)
      setStatusUpdateNote('')
    } catch (err: any) {
      toast.error('Lỗi khi cập nhật trạng thái', {
        description: err?.message || 'Vui lòng kiểm tra lại.',
      })
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  // Dashboard Query
  const dashQuery = useQuery({
    queryKey: ['admin', 'payments-dashboard'],
    queryFn: () => appApi.get<PaymentDashboard>('/admin/payments'),
    enabled: activeTab === 'dashboard',
  })

  // Orders Query
  const ordersQuery = useQuery({
    queryKey: ['admin', 'payments-orders', ordersSearch, ordersStatus, ordersSort, ordersPage],
    queryFn: () =>
      appApi.get<PaymentOrdersResponse>('/admin/payments/orders', {
        q: ordersSearch,
        order_status: ordersStatus,
        sort: ordersSort,
        page: ordersPage,
        per_page: 20,
      }),
    enabled: activeTab === 'orders',
  })

  // Order Detail Query
  const orderDetailQuery = useQuery({
    queryKey: ['admin', 'payments-order-detail', selectedOrderId],
    queryFn: () => appApi.get<any>(`/admin/payments/orders/${selectedOrderId}`),
    enabled: Boolean(selectedOrderId),
  })

  const orderDetail = orderDetailQuery.data
    ? {
        ...orderDetailQuery.data,
        status: orderDetailQuery.data.status || orderDetailQuery.data.serialized?.status,
        status_label: orderDetailQuery.data.status_label || orderDetailQuery.data.serialized?.status_label,
        total_amount_display:
          orderDetailQuery.data.total_amount_display || orderDetailQuery.data.serialized?.total_amount_display,
        created_at_display:
          orderDetailQuery.data.created_at_display || orderDetailQuery.data.serialized?.created_at_display,
      }
    : null

  // Transactions Query
  const txQuery = useQuery({
    queryKey: ['admin', 'payments-transactions', txSearch, txStatus, txSort, txPage],
    queryFn: () =>
      appApi.get<PaymentTransactionsResponse>('/admin/payments/transactions', {
        q: txSearch,
        status: txStatus,
        sort: txSort,
        page: txPage,
        per_page: 20,
      }),
    enabled: activeTab === 'transactions',
  })

  // Transaction Detail Query
  const txDetailQuery = useQuery({
    queryKey: ['admin', 'payments-tx-detail', selectedTxId],
    queryFn: () => appApi.get<any>(`/admin/payments/transactions/${selectedTxId}`),
    enabled: Boolean(selectedTxId),
  })

  return (
    <Page size="wide">
      <AdminHeader
        title="Quản lý Thanh toán & Đơn hàng"
        description="Tra cứu danh sách giao dịch, đối soát PayOS và cập nhật trạng thái đơn hàng."
      />

      {/* Main Tab Switcher */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
        <TabsList className="w-full justify-start sm:w-auto">
          <TabsTrigger value="orders" className="gap-1.5 font-semibold">
            <FileText className="size-4" />
            <span>Danh sách Đơn hàng</span>
          </TabsTrigger>
          <TabsTrigger value="transactions" className="gap-1.5 font-semibold">
            <CreditCard className="size-4" />
            <span>Lịch sử Giao dịch</span>
          </TabsTrigger>
          <TabsTrigger value="dashboard" className="gap-1.5 font-semibold">
            <span>Tổng quan Tài chính</span>
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {/* ========================================================================= */}
      {/* TAB 1: DANH SÁCH ĐƠN HÀNG (ORDERS) - TRỌNG TÂM QUẢN LÝ & CẬP NHẬT TRẠNG THÁI */}
      {/* ========================================================================= */}
      {activeTab === 'orders' && (
        <div className="space-y-4">
          
          {/* Filter Bar: Status Pills + Search + Sort */}
          <Card className="shadow-xs border-slate-200">
            <CardContent className="p-3.5 sm:p-4 space-y-3">
              
              {/* Row 1: Status Filter Pills */}
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs font-bold text-slate-500 mr-1.5 flex items-center gap-1">
                  <Filter className="size-3.5" /> Lọc trạng thái:
                </span>
                {ORDER_STATUS_FILTERS.map((f) => {
                  const isActive = ordersStatus === f.value
                  return (
                    <button
                      key={f.value}
                      onClick={() => {
                        setOrdersStatus(f.value)
                        setOrdersPage(1)
                      }}
                      className={`px-3 py-1 rounded-full text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                        isActive
                          ? 'bg-slate-900 text-white border-slate-900 shadow-xs'
                          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100 hover:text-slate-900'
                      }`}
                    >
                      {f.dot && <span className={`size-2 rounded-full ${f.dot}`} />}
                      <span>{f.label}</span>
                    </button>
                  )
                })}
              </div>

              {/* Row 2: Search Box + Sort Selector + Refresh Button */}
              <div className="flex flex-col sm:flex-row items-center gap-2.5 pt-1 border-t border-slate-100">
                <div className="relative flex-1 w-full">
                  <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    className="pl-9 pr-8 h-9 text-xs"
                    placeholder="Tìm theo mã đơn hàng, mã merchant, email hoặc tên khách..."
                    value={ordersSearch}
                    onChange={(e) => {
                      setOrdersSearch(e.target.value)
                      setOrdersPage(1)
                    }}
                  />
                  {ordersSearch && (
                    <button
                      onClick={() => {
                        setOrdersSearch('')
                        setOrdersPage(1)
                      }}
                      className="absolute top-1/2 right-2.5 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      <X className="size-3.5" />
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto shrink-0 justify-end">
                  {/* Sort dropdown */}
                  <div className="flex items-center gap-1 bg-slate-50 border border-slate-200 rounded-lg px-2 h-9 text-xs">
                    <ArrowUpDown className="size-3.5 text-slate-500" />
                    <select
                      value={ordersSort}
                      onChange={(e) => {
                        setOrdersSort(e.target.value)
                        setOrdersPage(1)
                      }}
                      className="bg-transparent border-none text-xs font-semibold text-slate-700 focus:outline-none cursor-pointer"
                    >
                      {SORT_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    className="h-9 px-3 text-xs gap-1.5"
                    title="Tải lại danh sách đơn hàng"
                    onClick={() => ordersQuery.refetch()}
                    disabled={ordersQuery.isFetching}
                  >
                    <RefreshCw className={`size-3.5 ${ordersQuery.isFetching ? 'animate-spin' : ''}`} />
                    <span className="hidden sm:inline">Làm mới</span>
                  </Button>
                </div>
              </div>

            </CardContent>
          </Card>

          {/* Table Container */}
          {ordersQuery.isPending ? (
            <PageLoading label="Đang tải danh sách đơn hàng…" />
          ) : ordersQuery.error ? (
            <PageError error={ordersQuery.error} />
          ) : !ordersQuery.data.items.length ? (
            <EmptyState
              title="Không tìm thấy đơn hàng nào"
              description="Không có đơn hàng nào khớp với điều kiện lọc hoặc từ khóa tìm kiếm."
            />
          ) : (
            <Card className="shadow-xs overflow-hidden border-slate-200">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50/80">
                    <TableHead className="w-[190px]">Mã đơn hàng</TableHead>
                    <TableHead className="w-[200px]">Khách hàng</TableHead>
                    <TableHead>Nội dung học liệu</TableHead>
                    <TableHead className="w-[130px]">Số tiền</TableHead>
                    <TableHead className="w-[140px]">Thời gian</TableHead>
                    <TableHead className="w-[140px]">Trạng thái</TableHead>
                    <TableHead className="text-right w-[170px]">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ordersQuery.data.items.map((order) => {
                    const isSyncing = syncingOrderId === order.id
                    const buyerName = order.buyer?.display_name || order.buyer?.username || order.buyer?.email || order.user_email || 'Khách vãng lai'
                    const buyerEmail = order.buyer?.email || order.user_email || ''

                    return (
                      <TableRow key={order.id} className="hover:bg-slate-50/70 transition-colors">
                        
                        {/* Order code */}
                        <TableCell>
                          <div className="flex items-center space-x-1">
                            <span className="font-mono font-bold text-xs text-slate-800" title={order.id}>
                              {order.merchant_order_code || order.id.slice(0, 12)}
                            </span>
                            <CopyButton text={order.merchant_order_code || order.id} label="Copy mã đơn" />
                          </div>
                          {order.merchant_order_code && order.merchant_order_code !== order.id && (
                            <p className="font-mono text-[10px] text-slate-400 truncate max-w-[150px]" title={order.id}>
                              ID: {order.id.slice(0, 8)}...
                            </p>
                          )}
                        </TableCell>

                        {/* Customer */}
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="font-semibold text-xs text-slate-800 truncate max-w-[180px]" title={buyerName}>
                              {buyerName}
                            </span>
                            {buyerEmail && buyerEmail !== buyerName && (
                              <span className="text-[11px] text-slate-400 font-mono truncate max-w-[180px]" title={buyerEmail}>
                                {buyerEmail}
                              </span>
                            )}
                          </div>
                        </TableCell>

                        {/* Items / Title */}
                        <TableCell>
                          <p className="font-medium text-xs text-slate-700 max-w-[260px] truncate" title={order.title}>
                            {order.title || 'Học liệu Marketplace'}
                          </p>
                          {order.item_count && order.item_count > 1 && (
                            <span className="text-[10px] text-slate-400 font-medium">
                              ({order.item_count} món hàng)
                            </span>
                          )}
                        </TableCell>

                        {/* Amount */}
                        <TableCell>
                          <span className="font-extrabold text-xs text-emerald-700">
                            {order.total_amount_display}
                          </span>
                        </TableCell>

                        {/* Date */}
                        <TableCell>
                          <span className="text-[11px] text-slate-600 block">
                            {order.created_at_display || (order.created_at ? new Date(order.created_at).toLocaleString('vi-VN') : '—')}
                          </span>
                        </TableCell>

                        {/* Status */}
                        <TableCell>
                          {renderStatusBadge(order.status, order.status_label)}
                        </TableCell>

                        {/* Actions */}
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            
                            {/* Fast Sync from PayOS Button */}
                            <Button
                              size="sm"
                              variant="outline"
                              className={`h-7 px-2 text-xs gap-1 font-semibold ${
                                order.status === 'pending_payment'
                                  ? 'bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100'
                                  : 'text-slate-700 hover:bg-slate-100'
                              }`}
                              title="Đồng bộ trạng thái trực tiếp từ PayOS"
                              disabled={isSyncing}
                              onClick={(e) => handleSyncOrder(order.id, e)}
                            >
                              <RefreshCw className={`size-3.5 ${isSyncing ? 'animate-spin text-primary' : ''}`} />
                              <span className="hidden xl:inline">{isSyncing ? 'Đang kiểm tra...' : 'Đồng bộ'}</span>
                            </Button>

                            {/* Manual Status Override Dropdown */}
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 px-2 text-xs gap-1 text-slate-700"
                                  title="Cập nhật trạng thái thủ công"
                                >
                                  <SlidersHorizontal className="size-3.5" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-48 text-xs">
                                <div className="px-2 py-1.5 text-[11px] font-bold text-slate-400 uppercase">
                                  Đổi trạng thái đơn
                                </div>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  onClick={() => {
                                    setStatusUpdateTarget(order)
                                    setTargetNewStatus('paid')
                                    setStatusUpdateNote('Xác nhận thanh toán thủ công (chuyển khoản ngoài / duyệt tay)')
                                  }}
                                  className="gap-2 text-emerald-700 font-semibold cursor-pointer"
                                >
                                  <CheckCircle2 className="size-3.5 text-emerald-600" />
                                  <span>Duyệt đã thu tiền (Paid)</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => {
                                    setStatusUpdateTarget(order)
                                    setTargetNewStatus('canceled')
                                    setStatusUpdateNote('Hủy đơn hàng theo yêu cầu khách / hết hạn')
                                  }}
                                  className="gap-2 text-rose-700 cursor-pointer"
                                >
                                  <XCircle className="size-3.5 text-rose-600" />
                                  <span>Hủy đơn hàng (Canceled)</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => {
                                    setStatusUpdateTarget(order)
                                    setTargetNewStatus('under_review')
                                    setStatusUpdateNote('Chuyển sang kiểm tra do phát sinh tra soát')
                                  }}
                                  className="gap-2 text-indigo-700 cursor-pointer"
                                >
                                  <AlertTriangle className="size-3.5 text-indigo-600" />
                                  <span>Chờ kiểm tra (Review)</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => {
                                    setStatusUpdateTarget(order)
                                    setTargetNewStatus('refunded')
                                    setStatusUpdateNote('Đã hoàn trả tiền cho khách hàng')
                                  }}
                                  className="gap-2 text-purple-700 cursor-pointer"
                                >
                                  <RotateCcw className="size-3.5 text-purple-600" />
                                  <span>Hoàn tiền (Refunded)</span>
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>

                            {/* View Detail Button */}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 px-2 text-xs text-blue-600 hover:text-blue-800"
                              onClick={() => setSelectedOrderId(order.id)}
                              title="Xem chi tiết đơn hàng"
                            >
                              <Eye className="size-3.5" />
                            </Button>

                          </div>
                        </TableCell>

                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>

              {/* Pagination */}
              {ordersQuery.data.pages > 1 && (
                <div className="flex items-center justify-between border-t p-3 text-xs bg-slate-50/50">
                  <span className="text-slate-500">
                    Hiển thị trang <strong>{ordersPage}</strong> trên tổng số <strong>{ordersQuery.data.pages}</strong> ({ordersQuery.data.total} đơn hàng)
                  </span>
                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2.5 text-xs"
                      disabled={ordersPage <= 1}
                      onClick={() => setOrdersPage((p) => Math.max(p - 1, 1))}
                    >
                      Trước
                    </Button>
                    <span className="px-2 font-bold text-slate-700">{ordersPage}</span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2.5 text-xs"
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

      {/* ========================================================================= */}
      {/* TAB 2: LỊCH SỬ GIAO DỊCH (TRANSACTIONS) */}
      {/* ========================================================================= */}
      {activeTab === 'transactions' && (
        <div className="space-y-4">
          
          <Card className="shadow-xs border-slate-200">
            <CardContent className="p-3.5 sm:p-4 space-y-3">
              
              {/* Status Filter Pills for Transactions */}
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs font-bold text-slate-500 mr-1.5 flex items-center gap-1">
                  <Filter className="size-3.5" /> Lọc trạng thái:
                </span>
                {TX_STATUS_FILTERS.map((f) => {
                  const isActive = txStatus === f.value
                  return (
                    <button
                      key={f.value}
                      onClick={() => {
                        setTxStatus(f.value)
                        setTxPage(1)
                      }}
                      className={`px-3 py-1 rounded-full text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                        isActive
                          ? 'bg-slate-900 text-white border-slate-900 shadow-xs'
                          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100 hover:text-slate-900'
                      }`}
                    >
                      {f.dot && <span className={`size-2 rounded-full ${f.dot}`} />}
                      <span>{f.label}</span>
                    </button>
                  )
                })}
              </div>

              {/* Search Box + Sort Selector */}
              <div className="flex flex-col sm:flex-row items-center gap-2.5 pt-1 border-t border-slate-100">
                <div className="relative flex-1 w-full">
                  <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    className="pl-9 pr-8 h-9 text-xs"
                    placeholder="Tìm theo mã giao dịch (Attempt ID), mã đơn hàng..."
                    value={txSearch}
                    onChange={(e) => {
                      setTxSearch(e.target.value)
                      setTxPage(1)
                    }}
                  />
                  {txSearch && (
                    <button
                      onClick={() => {
                        setTxSearch('')
                        setTxPage(1)
                      }}
                      className="absolute top-1/2 right-2.5 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      <X className="size-3.5" />
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto shrink-0 justify-end">
                  <div className="flex items-center gap-1 bg-slate-50 border border-slate-200 rounded-lg px-2 h-9 text-xs">
                    <ArrowUpDown className="size-3.5 text-slate-500" />
                    <select
                      value={txSort}
                      onChange={(e) => {
                        setTxSort(e.target.value)
                        setTxPage(1)
                      }}
                      className="bg-transparent border-none text-xs font-semibold text-slate-700 focus:outline-none cursor-pointer"
                    >
                      {SORT_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    className="h-9 px-3 text-xs gap-1.5"
                    title="Tải lại danh sách giao dịch"
                    onClick={() => txQuery.refetch()}
                    disabled={txQuery.isFetching}
                  >
                    <RefreshCw className={`size-3.5 ${txQuery.isFetching ? 'animate-spin' : ''}`} />
                    <span className="hidden sm:inline">Làm mới</span>
                  </Button>
                </div>
              </div>

            </CardContent>
          </Card>

          {txQuery.isPending ? (
            <PageLoading label="Đang tải lịch sử giao dịch…" />
          ) : txQuery.error ? (
            <PageError error={txQuery.error} />
          ) : !txQuery.data.items.length ? (
            <EmptyState title="Không tìm thấy giao dịch nào" description="Thử đổi từ khóa hoặc bộ lọc trạng thái." />
          ) : (
            <Card className="shadow-xs overflow-hidden border-slate-200">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50/80">
                    <TableHead className="w-[200px]">Mã Attempt ID</TableHead>
                    <TableHead className="w-[180px]">Mã Đơn hàng liên kết</TableHead>
                    <TableHead className="w-[110px]">Cổng xử lý</TableHead>
                    <TableHead className="w-[130px]">Số tiền</TableHead>
                    <TableHead className="w-[140px]">Thời gian</TableHead>
                    <TableHead className="w-[130px]">Trạng thái</TableHead>
                    <TableHead className="text-right w-[100px]">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {txQuery.data.items.map((tx) => (
                    <TableRow key={tx.id} className="hover:bg-slate-50/70 transition-colors">
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          <span className="font-mono text-xs font-bold text-slate-800 truncate max-w-[150px]" title={tx.id}>
                            {tx.id}
                          </span>
                          <CopyButton text={tx.id} label="Copy mã giao dịch" />
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-xs text-slate-600 truncate block max-w-[160px]" title={tx.order_id || '—'}>
                          {tx.merchant_order_code || tx.order_id || '—'}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-100 text-slate-700 uppercase">
                          {tx.provider_code || 'PayOS'}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="font-extrabold text-xs text-emerald-700">{tx.amount_display}</span>
                      </TableCell>
                      <TableCell>
                        <span className="text-[11px] text-slate-600 block">
                          {tx.created_at_display || (tx.created_at ? new Date(tx.created_at).toLocaleString('vi-VN') : '—')}
                        </span>
                      </TableCell>
                      <TableCell>
                        {renderStatusBadge(tx.status, tx.status_label)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2 text-xs text-blue-600 hover:text-blue-800"
                          onClick={() => setSelectedTxId(tx.id)}
                        >
                          <Eye className="size-3.5 mr-1" /> Chi tiết
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {txQuery.data.pages > 1 && (
                <div className="flex items-center justify-between border-t p-3 text-xs bg-slate-50/50">
                  <span className="text-slate-500">
                    Trang <strong>{txPage}</strong> / {txQuery.data.pages} ({txQuery.data.total} giao dịch)
                  </span>
                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2.5 text-xs"
                      disabled={txPage <= 1}
                      onClick={() => setTxPage((p) => Math.max(p - 1, 1))}
                    >
                      Trước
                    </Button>
                    <span className="px-2 font-bold text-slate-700">{txPage}</span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2.5 text-xs"
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

      {/* ========================================================================= */}
      {/* TAB 3: TỔNG QUAN TÀI CHÍNH (DASHBOARD) */}
      {/* ========================================================================= */}
      {activeTab === 'dashboard' && (
        <>
          {dashQuery.isPending ? (
            <PageLoading label="Đang tải Dashboard thanh toán…" />
          ) : dashQuery.error ? (
            <PageError error={dashQuery.error} />
          ) : (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">Chỉ số tài chính & giao dịch</h3>
                  <p className="text-xs text-muted-foreground">Thống kê doanh thu và đơn hàng thời gian thực</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs gap-1.5"
                  onClick={() => dashQuery.refetch()}
                  disabled={dashQuery.isFetching}
                >
                  <RefreshCw className={`size-3.5 ${dashQuery.isFetching ? 'animate-spin' : ''}`} />
                  Làm mới dữ liệu
                </Button>
              </div>

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

              <SectionCard title="Đơn hàng phát sinh gần đây">
                {!dashQuery.data.recent_orders.length ? (
                  <p className="text-sm text-muted-foreground">Chưa có giao dịch trong kỳ.</p>
                ) : (
                  <div className="space-y-3">
                    {dashQuery.data.recent_orders.map((order) => (
                      <div
                        key={order.id}
                        className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3 last:border-0 last:pb-0"
                      >
                        <div className="space-y-0.5">
                          <p className="font-semibold text-xs text-slate-800">{order.title}</p>
                          <div className="flex items-center space-x-1 font-mono text-[11px] text-slate-500">
                            <span>{order.merchant_order_code}</span>
                            <CopyButton text={order.merchant_order_code} />
                          </div>
                        </div>
                        <div className="text-right flex items-center space-x-3">
                          <div>
                            <p className="font-extrabold text-xs text-emerald-700">{order.total_amount_display}</p>
                          </div>
                          {renderStatusBadge(order.status, order.status_label)}
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs text-blue-600"
                            onClick={() => {
                              setSelectedOrderId(order.id)
                              setActiveTab('orders')
                            }}
                          >
                            <Eye className="size-3.5" />
                          </Button>
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

      {/* ========================================================================= */}
      {/* DIALOG 1: ORDER DETAIL MODAL */}
      {/* ========================================================================= */}
      <Dialog open={selectedOrderId !== null} onOpenChange={(open) => !open && setSelectedOrderId(null)}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle className="text-base flex items-center justify-between pr-6">
              <span>Chi tiết Đơn hàng #{selectedOrderId?.slice(0, 10)}</span>
              {orderDetail && renderStatusBadge(orderDetail.status, orderDetail.status_label)}
            </DialogTitle>
            <DialogDescription className="font-mono text-xs">
              Mã đầy đủ: {selectedOrderId}
            </DialogDescription>
          </DialogHeader>

          {orderDetailQuery.isPending ? (
            <PageLoading label="Đang tải chi tiết đơn hàng…" />
          ) : orderDetail ? (
            <div className="space-y-4 text-xs py-1">
              
              {/* Summary Grid */}
              <div className="grid grid-cols-2 gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200/80">
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold">Mã Merchant</p>
                  <div className="flex items-center space-x-1">
                    <p className="font-mono font-bold text-slate-800">
                      {orderDetail.merchant_order_code || '—'}
                    </p>
                    {orderDetail.merchant_order_code && (
                      <CopyButton text={orderDetail.merchant_order_code} />
                    )}
                  </div>
                </div>

                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold">Tổng tiền thanh toán</p>
                  <p className="font-extrabold text-sm text-emerald-700">
                    {orderDetail.total_amount_display || `${orderDetail.amount || 0} VND`}
                  </p>
                </div>

                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold">Khách hàng</p>
                  <p className="font-semibold text-slate-800">
                    {orderDetail.buyer?.display_name ||
                      orderDetail.buyer?.username ||
                      orderDetail.user_email ||
                      'Khách vãng lai'}
                  </p>
                  {orderDetail.buyer?.email && (
                    <p className="text-[10px] text-slate-400 font-mono">
                      {orderDetail.buyer.email}
                    </p>
                  )}
                </div>

                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold">Thời gian tạo</p>
                  <p className="text-slate-700">
                    {orderDetail.created_at_display ||
                      (orderDetail.created_at ? new Date(orderDetail.created_at).toLocaleString('vi-VN') : '—')}
                  </p>
                </div>
              </div>

              {/* Items Purchased */}
              {orderDetail.item_rows && orderDetail.item_rows.length > 0 && (
                <div>
                  <p className="font-bold text-slate-700 mb-1.5 flex items-center gap-1">
                    <FileText className="size-3.5 text-blue-600" />
                    Học liệu trong đơn:
                  </p>
                  <div className="space-y-1.5 bg-slate-50/70 p-2.5 rounded-xl border border-slate-200/70 text-xs">
                    {orderDetail.item_rows.map((it: any, i: number) => (
                      <div key={i} className="flex justify-between items-center py-1 border-b border-slate-200/60 last:border-none">
                        <span className="font-medium text-slate-800">{it.title_snapshot || it.title || it.name}</span>
                        <span className="font-bold text-emerald-700">{it.price_display || `${it.price || 0} VND`}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Payment Attempts */}
              {orderDetail.attempt_rows && orderDetail.attempt_rows.length > 0 && (
                <div>
                  <p className="font-bold text-slate-700 mb-1.5 flex items-center gap-1">
                    <CreditCard className="size-3.5 text-amber-600" />
                    Lịch sử lượt thanh toán (Attempts):
                  </p>
                  <div className="space-y-1.5 bg-slate-50/70 p-2.5 rounded-xl border border-slate-200/70 text-xs">
                    {orderDetail.attempt_rows.map((att: any, i: number) => (
                      <div key={i} className="flex justify-between items-center py-1 border-b border-slate-200/60 last:border-none">
                        <div>
                          <span className="font-mono text-[11px] text-slate-700 block">#{att.id?.slice(0, 10)}</span>
                          <span className="text-[10px] text-slate-400 uppercase">{att.provider_code || 'PayOS'}</span>
                        </div>
                        <div className="text-right">
                          {renderStatusBadge(att.status, att.status_label)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            </div>
          ) : null}

          <DialogFooter className="gap-2 sm:gap-0 justify-between sm:justify-between w-full border-t pt-3">
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-1.5 text-xs bg-amber-50 text-amber-900 border-amber-200 hover:bg-amber-100 font-semibold"
                disabled={syncingOrderId === selectedOrderId}
                onClick={() => selectedOrderId && handleSyncOrder(selectedOrderId)}
              >
                <RefreshCw className={`size-3.5 ${syncingOrderId === selectedOrderId ? 'animate-spin' : ''}`} />
                <span>Đồng bộ PayOS</span>
              </Button>

              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-1.5 text-xs font-semibold text-slate-700"
                onClick={() => {
                  if (orderDetail) {
                    setStatusUpdateTarget(orderDetail)
                    setTargetNewStatus(orderDetail.status === 'paid' ? 'canceled' : 'paid')
                  }
                }}
              >
                <SlidersHorizontal className="size-3.5" />
                <span>Đổi trạng thái</span>
              </Button>
            </div>

            <Button variant="secondary" size="sm" onClick={() => setSelectedOrderId(null)}>
              Đóng
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ========================================================================= */}
      {/* DIALOG 2: MANUAL STATUS UPDATE MODAL (CẬP NHẬT TRẠNG THÁI THỦ CÔNG) */}
      {/* ========================================================================= */}
      <Dialog
        open={statusUpdateTarget !== null}
        onOpenChange={(open) => !open && setStatusUpdateTarget(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base flex items-center gap-2">
              <SlidersHorizontal className="size-4 text-blue-600" />
              <span>Cập nhật trạng thái đơn hàng</span>
            </DialogTitle>
            <DialogDescription className="text-xs">
              Mã đơn: <strong>{statusUpdateTarget?.merchant_order_code || statusUpdateTarget?.id}</strong>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3.5 py-2 text-xs">
            <div>
              <label className="font-bold text-slate-700 block mb-1">Trạng thái mới:</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setTargetNewStatus('paid')}
                  className={`p-2.5 rounded-xl border text-left transition-all ${
                    targetNewStatus === 'paid'
                      ? 'bg-emerald-50 border-emerald-500 text-emerald-800 font-bold shadow-2xs ring-1 ring-emerald-500'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="size-4 text-emerald-600" />
                    <span>Đã thanh toán (Paid)</span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-1 font-normal">
                    Tự động cấp quyền học liệu ngay
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setTargetNewStatus('canceled')}
                  className={`p-2.5 rounded-xl border text-left transition-all ${
                    targetNewStatus === 'canceled'
                      ? 'bg-rose-50 border-rose-500 text-rose-800 font-bold shadow-2xs ring-1 ring-rose-500'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <XCircle className="size-4 text-rose-600" />
                    <span>Đã hủy (Canceled)</span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-1 font-normal">
                    Đóng đơn hàng, không cấp quyền
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setTargetNewStatus('under_review')}
                  className={`p-2.5 rounded-xl border text-left transition-all ${
                    targetNewStatus === 'under_review'
                      ? 'bg-indigo-50 border-indigo-500 text-indigo-800 font-bold shadow-2xs ring-1 ring-indigo-500'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <AlertTriangle className="size-4 text-indigo-600" />
                    <span>Cần kiểm tra (Review)</span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-1 font-normal">
                    Tạm giữ đơn chờ đối soát
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setTargetNewStatus('refunded')}
                  className={`p-2.5 rounded-xl border text-left transition-all ${
                    targetNewStatus === 'refunded'
                      ? 'bg-purple-50 border-purple-500 text-purple-800 font-bold shadow-2xs ring-1 ring-purple-500'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <RotateCcw className="size-4 text-purple-600" />
                    <span>Hoàn tiền (Refunded)</span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-1 font-normal">
                    Đã hoàn trả số tiền cho khách
                  </p>
                </button>
              </div>
            </div>

            <div>
              <label className="font-bold text-slate-700 block mb-1">Ghi chú xử lý của Admin:</label>
              <Input
                placeholder="VD: Khách chuyển khoản trực tiếp qua ngân hàng, duyệt theo phiếu đối soát..."
                value={statusUpdateNote}
                onChange={(e) => setStatusUpdateNote(e.target.value)}
                className="text-xs h-9"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setStatusUpdateTarget(null)}
              disabled={isUpdatingStatus}
            >
              Hủy bỏ
            </Button>
            <Button
              size="sm"
              onClick={handleConfirmStatusUpdate}
              disabled={isUpdatingStatus}
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold"
            >
              {isUpdatingStatus ? 'Đang cập nhật...' : 'Xác nhận cập nhật'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ========================================================================= */}
      {/* DIALOG 3: TRANSACTION DETAIL MODAL */}
      {/* ========================================================================= */}
      <Dialog open={selectedTxId !== null} onOpenChange={(open) => !open && setSelectedTxId(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-base flex items-center justify-between pr-6">
              <span>Chi tiết Giao dịch #{selectedTxId?.slice(0, 10)}</span>
              {txDetailQuery.data && renderStatusBadge(txDetailQuery.data.status, txDetailQuery.data.status_label)}
            </DialogTitle>
            <DialogDescription className="font-mono text-xs">
              Mã Attempt ID: {selectedTxId}
            </DialogDescription>
          </DialogHeader>

          {txDetailQuery.isPending ? (
            <PageLoading label="Đang tải chi tiết giao dịch…" />
          ) : txDetailQuery.data ? (
            <div className="space-y-4 text-xs py-1">
              <div className="grid grid-cols-2 gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200/80">
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold">Mã Đơn hàng</p>
                  <div className="flex items-center space-x-1">
                    <p className="font-mono font-bold text-slate-800">
                      {txDetailQuery.data.order_id || '—'}
                    </p>
                    {txDetailQuery.data.order_id && <CopyButton text={txDetailQuery.data.order_id} />}
                  </div>
                </div>

                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold">Số tiền giao dịch</p>
                  <p className="font-extrabold text-sm text-emerald-700">
                    {txDetailQuery.data.amount_display || `${txDetailQuery.data.amount || 0} VND`}
                  </p>
                </div>

                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold">Cổng thanh toán</p>
                  <p className="font-bold uppercase text-slate-700">{txDetailQuery.data.provider_code || 'PayOS'}</p>
                </div>

                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold">Thời gian ghi nhận</p>
                  <p className="text-slate-700">
                    {txDetailQuery.data.created_at_display ||
                      (txDetailQuery.data.created_at ? new Date(txDetailQuery.data.created_at).toLocaleString('vi-VN') : '—')}
                  </p>
                </div>
              </div>

              {txDetailQuery.data.raw_response && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <p className="font-bold text-slate-700">Dữ liệu gốc từ Cổng (Raw Payload):</p>
                    <CopyButton text={JSON.stringify(txDetailQuery.data.raw_response, null, 2)} label="Copy JSON" />
                  </div>
                  <pre className="bg-slate-950 text-slate-100 p-3 rounded-xl text-[10px] font-mono overflow-x-auto max-h-48 border border-slate-800">
                    {JSON.stringify(txDetailQuery.data.raw_response, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setSelectedTxId(null)}>
              Đóng
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </Page>
  )
}
