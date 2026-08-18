import { UsersRound } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { RetentionCohortItem } from '../../types/analytics'

type CohortRetentionTableProps = {
  cohorts: RetentionCohortItem[]
}

function getRetentionCellColor(rate: number, cohortSize: number): string {
  if (cohortSize === 0) return 'text-muted-foreground/40 bg-transparent'
  if (rate >= 50) return 'bg-emerald-600/25 text-emerald-700 dark:text-emerald-300 font-bold'
  if (rate >= 35) return 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-semibold'
  if (rate >= 20) return 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-medium'
  if (rate >= 10) return 'bg-amber-500/15 text-amber-600 dark:text-amber-400 font-medium'
  if (rate > 0) return 'bg-rose-500/10 text-rose-600 dark:text-rose-400 font-medium'
  return 'text-muted-foreground/60 bg-muted/20'
}

export function CohortRetentionTable({ cohorts }: CohortRetentionTableProps) {
  return (
    <Card className="border-border/80 bg-card shadow-xs">
      <CardHeader className="flex flex-col gap-1 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <UsersRound className="size-4 text-emerald-500" />
            Ma trận Giữ chân Học viên theo Nhóm (Cohort Retention)
          </CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">
            Tỷ lệ học viên quay lại ôn tập thẻ sau 1 ngày (D1), 7 ngày (D7), 14 ngày (D14) và 30 ngày (D30).
          </p>
        </div>
      </CardHeader>

      <CardContent className="pt-1">
        <div className="rounded-lg border border-border/80 overflow-hidden">
          <Table>
            <TableHeader className="bg-muted/40 text-xs">
              <TableRow>
                <TableHead className="font-semibold text-foreground">Nhóm đăng ký (Cohort)</TableHead>
                <TableHead className="font-semibold text-foreground text-center">Quy mô (Users)</TableHead>
                <TableHead className="font-semibold text-foreground text-center">D1 (Ngày 1)</TableHead>
                <TableHead className="font-semibold text-foreground text-center">D7 (1 tuần)</TableHead>
                <TableHead className="font-semibold text-foreground text-center">D14 (2 tuần)</TableHead>
                <TableHead className="font-semibold text-foreground text-center">D30 (1 tháng)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="text-xs">
              {cohorts.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                    Chưa có đủ dữ liệu chu kỳ để tạo ma trận giữ chân.
                  </TableCell>
                </TableRow>
              ) : (
                cohorts.map((row, idx) => (
                  <TableRow key={idx} className="hover:bg-muted/30">
                    <TableCell className="font-medium text-foreground py-2.5">
                      {row.cohort}
                    </TableCell>
                    <TableCell className="text-center font-medium text-foreground py-2.5">
                      {row.cohort_size.toLocaleString()}
                    </TableCell>
                    <TableCell className={`text-center py-2.5 rounded-sm ${getRetentionCellColor(row.d1_rate, row.cohort_size)}`}>
                      {row.cohort_size > 0 ? `${row.d1_rate}%` : '-'}
                      {row.cohort_size > 0 ? (
                        <span className="block text-[10px] opacity-75">({row.d1_retained})</span>
                      ) : null}
                    </TableCell>
                    <TableCell className={`text-center py-2.5 rounded-sm ${getRetentionCellColor(row.d7_rate, row.cohort_size)}`}>
                      {row.cohort_size > 0 ? `${row.d7_rate}%` : '-'}
                      {row.cohort_size > 0 ? (
                        <span className="block text-[10px] opacity-75">({row.d7_retained})</span>
                      ) : null}
                    </TableCell>
                    <TableCell className={`text-center py-2.5 rounded-sm ${getRetentionCellColor(row.d14_rate, row.cohort_size)}`}>
                      {row.cohort_size > 0 ? `${row.d14_rate}%` : '-'}
                      {row.cohort_size > 0 ? (
                        <span className="block text-[10px] opacity-75">({row.d14_retained})</span>
                      ) : null}
                    </TableCell>
                    <TableCell className={`text-center py-2.5 rounded-sm ${getRetentionCellColor(row.d30_rate, row.cohort_size)}`}>
                      {row.cohort_size > 0 ? `${row.d30_rate}%` : '-'}
                      {row.cohort_size > 0 ? (
                        <span className="block text-[10px] opacity-75">({row.d30_retained})</span>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
