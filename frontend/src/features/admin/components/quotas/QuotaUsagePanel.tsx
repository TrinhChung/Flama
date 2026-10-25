import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState } from '@/shared/components/PageState'
import type { QuotaPolicy, QuotaRankingRow, QuotaUnit, QuotaUsage } from '../../types/quotas'
import {
  QUOTA_KIND_META,
  QUOTA_SOURCE_LABELS,
  formatQuotaAmount,
  formatQuotaLimit,
  quotaUsagePercent,
  quotaUserLabel,
} from './quotaFormat'

function RankingTable({
  rows,
  unit,
  onSelectUser,
  emptyLabel,
}: {
  rows: QuotaRankingRow[]
  unit: QuotaUnit
  onSelectUser: (userId: number) => void
  emptyLabel: string
}) {
  if (rows.length === 0) {
    return <p className="py-4 text-center text-xs text-muted-foreground">{emptyLabel}</p>
  }
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Người dùng</TableHead>
            <TableHead className="text-right">Đã dùng</TableHead>
            <TableHead className="hidden text-right sm:table-cell">Hạn mức</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const percent = row.effective ? quotaUsagePercent(row.used, row.effective.limit_value) : null
            return (
              <TableRow key={row.user.id}>
                <TableCell className="max-w-[12rem]">
                  <button
                    type="button"
                    className="block max-w-full truncate text-left text-sm font-medium hover:underline"
                    onClick={() => onSelectUser(row.user.id)}
                    disabled={row.user.missing}
                  >
                    {quotaUserLabel(row.user)}
                  </button>
                  {row.user.email && <span className="block truncate text-xs text-muted-foreground">{row.user.email}</span>}
                </TableCell>
                <TableCell className="text-right align-top">
                  <span className="text-sm font-semibold tabular-nums">{formatQuotaAmount(row.used, unit)}</span>
                  {percent !== null && <Progress value={percent} className="mt-1 h-1.5" />}
                </TableCell>
                <TableCell className="hidden text-right align-top text-xs text-muted-foreground sm:table-cell">
                  {row.effective ? (
                    <>
                      {formatQuotaLimit(row.effective.limit_value, unit, row.effective.period)}
                      <span className="block">{QUOTA_SOURCE_LABELS[row.effective.source]}</span>
                    </>
                  ) : (
                    '—'
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

export function QuotaUsagePanel({
  policy,
  usage,
  onSelectUser,
}: {
  policy: QuotaPolicy
  usage: QuotaUsage
  onSelectUser: (userId: number) => void
}) {
  const meta = QUOTA_KIND_META[policy.kind]
  const Icon = meta.icon
  const hasData = usage.total > 0 || usage.top.length > 0

  return (
    <Card data-testid={`quota-usage-${policy.kind}`}>
      <CardHeader className="space-y-1">
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="size-4 text-primary" />
          {meta.label}
        </CardTitle>
        <CardDescription>
          Tổng: <span className="font-semibold text-foreground">{formatQuotaAmount(usage.total, policy.unit)}</span>
          {' · '}kỳ {usage.period_token}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasData ? (
          <EmptyState title="Chưa có lượt sử dụng" description="Chưa ai dùng loại quota này trong kỳ đang xem." />
        ) : (
          <>
            <div className="space-y-2">
              <p className="text-sm font-medium">Dùng nhiều nhất</p>
              <RankingTable
                rows={usage.top}
                unit={policy.unit}
                onSelectUser={onSelectUser}
                emptyLabel="Chưa có dữ liệu."
              />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">
                {policy.enforce ? 'Đã bị chặn khi vượt hạn mức' : 'Vượt hạn mức (lẽ ra đã bị chặn)'}
              </p>
              <p className="text-xs text-muted-foreground">
                Tổng lượng của các request vượt hạn mức đang cấu hình. Dùng số này để chỉnh hạn mức trước khi bật chặn.
              </p>
              <RankingTable
                rows={usage.over}
                unit={policy.unit}
                onSelectUser={onSelectUser}
                emptyLabel="Không ai vượt hạn mức trong kỳ này."
              />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
