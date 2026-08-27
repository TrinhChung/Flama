import { useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Clock,
  History,
  User,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { EmptyState, PageLoading } from '@/shared/components/PageState'
import { profileApi } from '../api/profileApi'

export function ProfileTransactionsTable() {
  const [page, setPage] = useState(1)
  const perPage = 10

  const { data, isPending, error } = useQuery({
    queryKey: ['profile-transactions', page],
    queryFn: () => profileApi.listTransactions({ page, per_page: perPage }),
  })

  return (
    <Card className="border-border/60 shadow-xs">
      <CardHeader className="border-b border-border/60 p-5">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <History className="size-4 text-primary" />
              Lịch sử biến động số dư & Doanh thu
            </CardTitle>
            <CardDescription className="text-xs">
              Chi tiết các khoản cộng tiền khi người dùng khác tải/mua bộ thẻ của bạn.
            </CardDescription>
          </div>
          {data ? (
            <Badge variant="outline" className="self-start text-xs font-normal">
              Tổng {data.total} giao dịch
            </Badge>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {isPending ? (
          <div className="py-12">
            <PageLoading label="Đang tải lịch sử giao dịch…" />
          </div>
        ) : error ? (
          <div className="p-8 text-center text-sm text-destructive">
            Không thể tải lịch sử giao dịch. Vui lòng thử lại sau.
          </div>
        ) : !data.items || data.items.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="Chưa có giao dịch nào"
              description="Khi có người dùng mua bộ thẻ bạn chia sẻ trên Marketplace, các giao dịch và khoản tiền cộng vào ví sẽ hiển thị tại đây."
            />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30">
                    <TableHead className="w-[180px] text-xs">Thời gian</TableHead>
                    <TableHead className="text-xs">Nội dung & Học liệu</TableHead>
                    <TableHead className="text-xs">Người mua</TableHead>
                    <TableHead className="text-xs">Mã đơn hàng</TableHead>
                    <TableHead className="text-right text-xs">Giá bán</TableHead>
                    <TableHead className="text-right text-xs">Phí nền tảng</TableHead>
                    <TableHead className="text-right text-xs">Thực nhận</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((tx) => (
                    <TableRow key={tx.id} className="hover:bg-muted/20">
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <Clock className="size-3.5 text-muted-foreground/70" />
                          {tx.created_at
                            ? new Date(tx.created_at).toLocaleString('vi-VN', {
                                dateStyle: 'short',
                                timeStyle: 'short',
                              })
                            : '—'}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-0.5">
                          <p className="text-xs font-semibold text-foreground">
                            {tx.description || tx.transaction_type_label}
                          </p>
                          <span className="inline-block rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                            {tx.transaction_type_label}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        <div className="flex items-center gap-1.5">
                          <User className="size-3.5" />
                          <span>{tx.buyer_username}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs font-mono text-muted-foreground">
                        {tx.merchant_order_code ? (
                          <span className="rounded bg-muted px-1.5 py-0.5">
                            #{tx.merchant_order_code}
                          </span>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell className="text-right text-xs font-medium text-muted-foreground">
                        {tx.gross_amount_display}
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">
                        <span className="text-amber-600 dark:text-amber-400">
                          -{tx.platform_fee_amount_display}
                        </span>
                        <span className="ml-1 text-[10px] text-muted-foreground/70">
                          ({tx.platform_fee_percent}%)
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-xs font-bold text-emerald-600 dark:text-emerald-400">
                        {tx.net_amount_display}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Pagination Controls */}
            {data.pages > 1 ? (
              <div className="flex items-center justify-between border-t border-border/60 p-4">
                <p className="text-xs text-muted-foreground">
                  Trang {data.page} / {data.pages} (Tổng {data.total} giao dịch)
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="h-8 gap-1 text-xs"
                  >
                    <ChevronLeft className="size-3.5" />
                    Trước
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                    disabled={page >= data.pages}
                    className="h-8 gap-1 text-xs"
                  >
                    Sau
                    <ChevronRight className="size-3.5" />
                  </Button>
                </div>
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  )
}
