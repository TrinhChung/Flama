import { Award, Clock, Flame } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { TopLearner } from '../../types/analytics'

type TopLearnersTableProps = {
  learners: TopLearner[]
}

function formatRelativeTime(isoStr: string | null): string {
  if (!isoStr) return 'Chưa ghi nhận'
  try {
    const d = new Date(isoStr)
    return d.toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return isoStr
  }
}

export function TopLearnersTable({ learners }: TopLearnersTableProps) {
  return (
    <Card className="border-border/80 bg-card shadow-xs">
      <CardHeader className="flex flex-col gap-1 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Award className="size-4 text-amber-500" />
            Top Học viên Tích cực nhất (Leaderboard)
          </CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">
            Những người dùng dành nhiều thời gian học tập và có lượt ôn tập thẻ cao nhất trong kỳ.
          </p>
        </div>
      </CardHeader>

      <CardContent className="pt-1">
        <div className="rounded-lg border border-border/80 overflow-hidden">
          <Table>
            <TableHeader className="bg-muted/40 text-xs">
              <TableRow>
                <TableHead className="w-12 text-center font-semibold text-foreground">Hạng</TableHead>
                <TableHead className="font-semibold text-foreground">Học viên</TableHead>
                <TableHead className="font-semibold text-foreground text-right">Lượt ôn thẻ</TableHead>
                <TableHead className="font-semibold text-foreground text-right">Thời gian học</TableHead>
                <TableHead className="font-semibold text-foreground text-right">Hoạt động gần nhất</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="text-xs">
              {learners.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                    Chưa có dữ liệu lượt học trong khoảng thời gian này.
                  </TableCell>
                </TableRow>
              ) : (
                learners.map((learner, idx) => {
                  const rank = idx + 1
                  return (
                    <TableRow key={learner.user_id} className="hover:bg-muted/30">
                      <TableCell className="text-center font-bold">
                        {rank === 1 ? (
                          <span className="inline-flex size-6 items-center justify-center rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400">
                            🥇
                          </span>
                        ) : rank === 2 ? (
                          <span className="inline-flex size-6 items-center justify-center rounded-full bg-slate-300/40 text-slate-700 dark:text-slate-200">
                            🥈
                          </span>
                        ) : rank === 3 ? (
                          <span className="inline-flex size-6 items-center justify-center rounded-full bg-amber-700/20 text-amber-700 dark:text-amber-300">
                            🥉
                          </span>
                        ) : (
                          <span className="text-muted-foreground">{rank}</span>
                        )}
                      </TableCell>
                      <TableCell className="font-medium text-foreground">
                        <div className="font-semibold">{learner.username}</div>
                        <div className="text-[11px] text-muted-foreground">{learner.email}</div>
                      </TableCell>
                      <TableCell className="text-right font-medium text-foreground">
                        <span className="inline-flex items-center gap-1">
                          <Flame className="size-3 text-orange-500" />
                          {learner.reviews_count.toLocaleString()} thẻ
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-semibold text-foreground">
                        <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
                          <Clock className="size-3" />
                          {learner.total_study_minutes} phút
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        {formatRelativeTime(learner.last_active_at)}
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
