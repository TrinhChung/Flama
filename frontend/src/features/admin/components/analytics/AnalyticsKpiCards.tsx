import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BookOpen,
  Clock,
  CreditCard,
  Layers,
  Users,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import type { AnalyticsOverviewResponse } from '../../types/analytics'

type AnalyticsKpiCardsProps = {
  data: AnalyticsOverviewResponse
}

function DeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null || delta === undefined) return null
  const isPositive = delta > 0
  const isNeutral = delta === 0

  if (isNeutral) {
    return (
      <span className="inline-flex items-center gap-0.5 rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
        0%
      </span>
    )
  }

  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-medium ${
        isPositive
          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
          : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
      }`}
    >
      {isPositive ? (
        <ArrowUpRight className="size-3" />
      ) : (
        <ArrowDownRight className="size-3" />
      )}
      {Math.abs(delta)}%
    </span>
  )
}

export function AnalyticsKpiCards({ data }: AnalyticsKpiCardsProps) {
  const { totals, period_metrics, deltas } = data

  const cards = [
    {
      title: 'Thời gian học TB / User',
      value: `${period_metrics.avg_study_minutes_per_active_user} phút`,
      subtext: `Tổng ${period_metrics.total_duration_hours} giờ học hệ thống`,
      delta: deltas.avg_study_time_delta_pct,
      icon: Clock,
      color: 'text-amber-500 bg-amber-500/10',
    },
    {
      title: 'Người dùng tích cực (DAU / MAU)',
      value: `${totals.dau.toLocaleString()} DAU`,
      subtext: `MAU: ${totals.mau.toLocaleString()} · Gắn kết: ${totals.stickiness_ratio}%`,
      delta: deltas.active_users_delta_pct,
      icon: Activity,
      color: 'text-orange-500 bg-orange-500/10',
    },
    {
      title: 'Lượt ôn tập thẻ',
      value: `${period_metrics.total_reviews.toLocaleString()} lượt`,
      subtext: `Tỷ lệ nhớ thành công: ${period_metrics.retention_pass_rate}%`,
      delta: deltas.total_reviews_delta_pct,
      icon: Layers,
      color: 'text-blue-500 bg-blue-500/10',
    },
    {
      title: 'Người dùng đăng ký mới',
      value: `+${period_metrics.new_users.toLocaleString()}`,
      subtext: `Tổng ${totals.users.toLocaleString()} tài khoản hoạt động`,
      delta: deltas.new_users_delta_pct,
      icon: Users,
      color: 'text-emerald-500 bg-emerald-500/10',
    },
    {
      title: 'Doanh thu thanh toán (GMV)',
      value: `${period_metrics.revenue_minor.toLocaleString('vi-VN')} ₫`,
      subtext: `${period_metrics.paid_orders} đơn hàng thanh toán thành công`,
      delta: deltas.revenue_delta_pct,
      icon: CreditCard,
      color: 'text-indigo-500 bg-indigo-500/10',
    },
    {
      title: 'Học liệu & Thẻ mới tạo',
      value: `+${period_metrics.new_cards.toLocaleString()} thẻ`,
      subtext: `Tổng ${totals.decks} bộ thẻ · ${totals.notes} ghi chú`,
      delta: null,
      icon: BookOpen,
      color: 'text-purple-500 bg-purple-500/10',
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {cards.map((item, idx) => {
        const Icon = item.icon
        return (
          <Card key={idx} className="relative overflow-hidden border-border/80 bg-card shadow-xs transition-all hover:shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-muted-foreground truncate" title={item.title}>
                  {item.title}
                </span>
                <div className={`flex size-7 shrink-0 items-center justify-center rounded-lg ${item.color}`}>
                  <Icon className="size-4" />
                </div>
              </div>

              <div className="mt-3 flex items-baseline justify-between gap-2">
                <div className="text-xl font-bold tracking-tight text-foreground">{item.value}</div>
                <DeltaBadge delta={item.delta} />
              </div>

              <p className="mt-1 text-[11px] text-muted-foreground truncate" title={item.subtext}>
                {item.subtext}
              </p>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
