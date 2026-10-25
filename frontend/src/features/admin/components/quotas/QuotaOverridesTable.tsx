import { Edit3, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState } from '@/shared/components/PageState'
import { useDeleteUserQuota } from '../../api/quotasApi'
import type { QuotaOverride } from '../../types/quotas'
import {
  QUOTA_KIND_META,
  formatLocalDate,
  formatQuotaAmount,
  formatQuotaLimit,
  quotaUserLabel,
} from './quotaFormat'

export function QuotaOverridesTable({
  overrides,
  onEditUser,
}: {
  overrides: QuotaOverride[]
  onEditUser: (userId: number) => void
}) {
  const deleteMutation = useDeleteUserQuota()

  if (overrides.length === 0) {
    return (
      <EmptyState
        title="Chưa có quota riêng"
        description="Mọi người dùng đang theo hạn mức mặc định của vai trò. Bấm “Thêm quota riêng” để nâng hạn mức cho một người."
      />
    )
  }

  const remove = (row: QuotaOverride) => {
    deleteMutation.mutate(
      { userId: row.user_id, kind: row.kind },
      {
        onSuccess: (data) => toast.success(data.message || 'Đã xoá quota riêng.'),
        onError: (error: Error) => toast.error(error.message || 'Không thể xoá quota riêng.'),
      },
    )
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Người dùng</TableHead>
            <TableHead>Loại</TableHead>
            <TableHead>Hạn mức</TableHead>
            <TableHead className="text-right">Đã dùng kỳ này</TableHead>
            <TableHead>Hết hạn</TableHead>
            <TableHead className="hidden xl:table-cell">Ghi chú</TableHead>
            <TableHead className="text-right">Hành động</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {overrides.map((row) => (
            <TableRow key={`${row.user_id}-${row.kind}`} className={row.is_active ? undefined : 'opacity-60'}>
              <TableCell className="max-w-[12rem]">
                <span className="block truncate font-medium">{quotaUserLabel(row.user)}</span>
                {row.user?.email && <span className="block truncate text-xs text-muted-foreground">{row.user.email}</span>}
              </TableCell>
              <TableCell className="whitespace-nowrap text-sm">{QUOTA_KIND_META[row.kind].short}</TableCell>
              <TableCell className="whitespace-nowrap text-sm">
                {formatQuotaLimit(row.limit_value, row.unit, row.effective_period)}
              </TableCell>
              <TableCell className="text-right text-sm tabular-nums">
                {formatQuotaAmount(row.used ?? 0, row.unit)}
              </TableCell>
              <TableCell className="whitespace-nowrap text-sm">
                {row.is_active ? (
                  formatLocalDate(row.expires_on)
                ) : (
                  <Badge variant="outline">Đã hết hạn {formatLocalDate(row.expires_on)}</Badge>
                )}
              </TableCell>
              <TableCell className="hidden max-w-[14rem] truncate text-xs text-muted-foreground xl:table-cell">
                {row.note || '—'}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1.5">
                  <Button variant="outline" size="sm" className="gap-1" onClick={() => onEditUser(row.user_id)}>
                    <Edit3 className="size-3.5" /> Sửa
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-1 text-destructive"
                    disabled={deleteMutation.isPending}
                    onClick={() => remove(row)}
                    aria-label={`Xoá quota ${row.kind} của ${quotaUserLabel(row.user)}`}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
