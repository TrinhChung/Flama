import { CheckCircle2, GitMerge, GitPullRequest } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import type { ContributionItem } from '../types/profile'

export function ContributionsTab({
  contributions,
}: {
  contributions: ContributionItem[]
}) {
  if (!contributions || contributions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border/80 p-12 text-center">
        <GitPullRequest className="size-10 text-muted-foreground/40 mb-3" />
        <p className="text-sm font-semibold text-foreground">
          Chưa có đóng góp nào được ghi nhận
        </p>
        <p className="text-xs text-muted-foreground mt-1 max-w-sm">
          Các đóng góp sửa đổi thẻ hoặc cải tiến nội dung đã được hợp nhất (merged) sẽ xuất hiện tại đây.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {contributions.map((cr) => (
        <Card
          key={cr.id}
          className="border-border/60 bg-card transition hover:border-border"
        >
          <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                <GitMerge className="size-4" />
              </div>
              <div className="space-y-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-xs font-bold text-foreground truncate">
                    {cr.title}
                  </h4>
                  <Badge className="bg-emerald-500/15 text-emerald-700 border-emerald-500/30 text-[10px] font-semibold dark:text-emerald-400">
                    <CheckCircle2 className="mr-1 size-3" />
                    Đã hợp nhất
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  Bộ thẻ:{' '}
                  {cr.deck_item_id ? (
                    <Link
                      to={`/marketplace/decks/${cr.deck_item_id}`}
                      className="font-medium text-foreground hover:underline"
                    >
                      {cr.deck_title}
                    </Link>
                  ) : (
                    <span className="font-medium text-foreground">{cr.deck_title}</span>
                  )}
                </p>
                {cr.description ? (
                  <p className="text-xs text-muted-foreground/80 line-clamp-1 italic">
                    "{cr.description}"
                  </p>
                ) : null}
              </div>
            </div>

            {cr.merged_at ? (
              <span className="text-[11px] text-muted-foreground shrink-0 self-start sm:self-center">
                {new Date(cr.merged_at).toLocaleDateString('vi-VN', {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
            ) : null}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
