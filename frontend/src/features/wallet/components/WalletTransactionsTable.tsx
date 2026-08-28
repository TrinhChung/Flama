import { useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  History,
  Receipt,
  User,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { walletApi } from '../api/walletApi'

export function WalletTransactionsTable() {
  const [page, setPage] = useState(1)
  const [filterType, setFilterType] = useState<string | undefined>(undefined)

  const { data, isPending, error } = useQuery({
    queryKey: ['wallet-transactions', page, filterType],
    queryFn: () =>
      walletApi.getTransactions({
        page,
        per_page: 10,
        type: filterType,
      }),
  })

  const formatDate = (isoString: string | null) => {
    if (!isoString) return '—'
    return new Date(isoString).toLocaleString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <Card className="border-border/60 shadow-xs">
      <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between pb-4">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-base font-bold">
            <History className="size-4 text-primary" />
            Lịch sử giao dịch số dư
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Bảng kê chi tiết từng lượt mua học liệu và tiền thực nhận vào ví
          </p>
        </div>

        {/* Filter buttons */}
        <div className="flex items-center gap-1.5 self-start sm:self-center">
          <Button
            variant={filterType === undefined ? 'default' : 'outline'}
            size="sm"
            onClick={() => {
              setFilterType(undefined)
              setPage(1)
            }}
            className="h-7 text-xs font-semibold"
          >
            Tất cả
          </Button>
          <Button
            variant={filterType === 'deck_sale' ? 'default' : 'outline'}
            size="sm"
            onClick={() => {
              setFilterType('deck_sale')
              setPage(1)
            }}
            className="h-7 text-xs font-semibold"
          >
            Doanh thu Deck
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {isPending ? (
          <div className="py-12 text-center text-xs text-muted-foreground">
            Đang tải dữ liệu lịch sử giao dịch…
          </div>
        ) : error ? (
          <div className="py-8 text-center text-xs text-destructive">
            Không thể tải lịch sử giao dịch. Vui lòng thử lại.
          </div>
        ) : !data.items || data.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Receipt className="size-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm font-semibold text-foreground">
              Chưa có giao dịch nào
            </p>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
              Khi có người học mua bộ thẻ hoặc học liệu của bạn trên Marketplace, các khoản doanh thu sẽ được hiển thị tại đây.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg border border-border/60 overflow-hidden">
              <Table>
                <TableHeader className="bg-muted/40">
                  <TableRow>
                    <TableHead className="text-xs font-semibold">Thời gian</TableHead>
                    <TableHead className="text-xs font-semibold">Nội dung</TableHead>
                    <TableHead className="text-xs font-semibold">Người mua</TableHead>
                    <TableHead className="text-xs font-semibold text-right">Giá bán</TableHead>
                    <TableHead className="text-xs font-semibold text-right">Phí sàn</TableHead>
                    <TableHead className="text-xs font-semibold text-right">Thực nhận</TableHead>
                    <TableHead className="text-xs font-semibold text-right">Số dư sau GD</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((tx) => (
                    <TableRow key={tx.id} className="hover:bg-muted/30 transition-colors">
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatDate(tx.created_at)}
                      </TableCell>
                      <TableCell className="text-xs font-medium">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-foreground">{tx.description}</span>
                          {tx.merchant_order_code ? (
                            <span className="text-[11px] font-mono text-muted-foreground">
                              Mã đơn: #{tx.merchant_order_code}
                            </span>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <User className="size-3 text-muted-foreground/70" />
                          {tx.buyer_username}
                        </span>
                      </TableCell>
                      <TableCell className="text-xs text-right font-medium text-foreground">
                        {tx.gross_amount_display}
                      </TableCell>
                      <TableCell className="text-xs text-right text-muted-foreground">
                        -{tx.platform_fee_amount_display}{' '}
                        <span className="text-[10px] text-muted-foreground/80">
                          ({tx.platform_fee_percent}%)
                        </span>
                      </TableCell>
                      <TableCell className="text-xs text-right font-bold text-emerald-600 dark:text-emerald-400">
                        {tx.net_amount_display}
                      </TableCell>
                      <TableCell className="text-xs text-right font-semibold text-foreground">
                        {tx.balance_after_display}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Pagination Controls */}
            {data.pages > 1 ? (
              <div className="flex items-center justify-between pt-2">
                <p className="text-xs text-muted-foreground">
                  Trang {data.page} / {data.pages} (Tổng {data.total} giao dịch)
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="h-8 gap-1 text-xs"
                  >
                    <ChevronLeft className="size-3.5" />
                    Trang trước
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= data.pages}
                    onClick={() => setPage((p) => p + 1)}
                    className="h-8 gap-1 text-xs"
                  >
                    Trang sau
                    <ChevronRight className="size-3.5" />
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
