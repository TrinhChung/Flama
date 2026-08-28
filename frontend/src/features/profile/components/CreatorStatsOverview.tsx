import {
  BookOpen,
  DownloadCloud,
  GitPullRequest,
  Star,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import type { CreatorStats } from '../types/profile'

export function CreatorStatsOverview({ stats }: { stats: CreatorStats }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Card className="border-border/60 bg-card/60 shadow-xs">
        <CardContent className="p-4">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-medium">Học liệu đã tạo</span>
            <BookOpen className="size-4 text-primary" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-foreground">
            {stats.created_decks_count}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Bộ thẻ xuất bản công khai
          </p>
        </CardContent>
      </Card>

      <Card className="border-border/60 bg-card/60 shadow-xs">
        <CardContent className="p-4">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-medium">Lượt người cài đặt</span>
            <DownloadCloud className="size-4 text-blue-500" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-foreground">
            {stats.total_installs_count.toLocaleString('vi-VN')}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Tổng lượt tải các bộ thẻ
          </p>
        </CardContent>
      </Card>

      <Card className="border-border/60 bg-card/60 shadow-xs">
        <CardContent className="p-4">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-medium">Đánh giá trung bình</span>
            <Star className="size-4 fill-amber-400 text-amber-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-2xl font-extrabold text-foreground">
              {stats.rating_avg > 0 ? stats.rating_avg.toFixed(1) : '—'}
            </span>
            {stats.rating_count > 0 ? (
              <span className="text-xs text-muted-foreground font-normal">
                ({stats.rating_count} đánh giá)
              </span>
            ) : null}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Uy tín chất lượng nội dung
          </p>
        </CardContent>
      </Card>

      <Card className="border-border/60 bg-card/60 shadow-xs">
        <CardContent className="p-4">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-medium">Đóng góp cộng đồng</span>
            <GitPullRequest className="size-4 text-emerald-500" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-foreground">
            {stats.contributions_merged_count}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Change request được duyệt
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
