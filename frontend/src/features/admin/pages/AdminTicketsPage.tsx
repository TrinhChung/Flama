import { useState } from 'react'
import {
  Bug,
  CheckCircle2,
  Clock,
  ExternalLink,
  Eye,
  Image as ImageIcon,
  Lightbulb,
  MessageSquare,
  Palette,
  RefreshCw,
  Search,
  Ticket,
  User as UserIcon,
  XCircle,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Page, PageHeader, StatCard } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

export type TicketItem = {
  id: string
  ticket_code: string
  user_id: number | null
  user_email?: string
  sender_name?: string
  category: 'bug' | 'feature' | 'ui' | 'other'
  title: string
  description: string
  reproduce_steps?: string
  screen_url?: string
  screen_name?: string
  attachment_urls: string[]
  status: 'open' | 'in_progress' | 'resolved' | 'closed' | 'rejected'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  admin_notes?: string
  created_at: string
  updated_at: string
  resolved_at?: string
  replies_count?: number
  replies?: ReplyItem[]
}

export type ReplyItem = {
  id: string
  ticket_id: string
  user_id: number | null
  is_admin_reply: boolean
  sender_name?: string
  message: string
  attachment_urls: string[]
  created_at: string
}

type AdminTicketsResponse = {
  items: TicketItem[]
  total: number
  page: number
  per_page: number
  stats: {
    total: number
    open: number
    in_progress: number
    resolved: number
    closed: number
    rejected: number
  }
}

const CATEGORY_MAP: Record<string, { label: string; icon: any; color: string }> = {
  bug: { label: 'Báo lỗi', icon: Bug, color: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-200/50' },
  feature: { label: 'Ý tưởng mới', icon: Lightbulb, color: 'bg-muted text-foreground border-border/80' },
  ui: { label: 'Giao diện', icon: Palette, color: 'bg-muted text-foreground border-border/80' },
  other: { label: 'Khác', icon: MessageSquare, color: 'bg-muted text-foreground border-border/80' },
}

const STATUS_MAP: Record<string, { label: string; badge: string; icon: any }> = {
  open: { label: 'Chờ xử lý', badge: 'bg-amber-500 text-white', icon: Clock },
  in_progress: { label: 'Đang xử lý', badge: 'bg-blue-600 text-white', icon: RefreshCw },
  resolved: { label: 'Đã giải quyết', badge: 'bg-emerald-600 text-white', icon: CheckCircle2 },
  rejected: { label: 'Từ chối', badge: 'bg-rose-600 text-white', icon: XCircle },
  closed: { label: 'Đã đóng', badge: 'bg-gray-500 text-white', icon: XCircle },
}

const PRIORITY_MAP: Record<string, { label: string; color: string }> = {
  low: { label: 'Thấp', color: 'text-slate-500 bg-slate-100' },
  medium: { label: 'Vừa', color: 'text-blue-700 bg-blue-50' },
  high: { label: 'Cao', color: 'text-amber-700 bg-amber-50 font-semibold' },
  urgent: { label: 'Khẩn cấp', color: 'text-red-700 bg-red-50 font-extrabold animate-pulse' },
}

export function AdminTicketsPage() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [priorityFilter, setPriorityFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState<string>('')

  const queryKey = ['admin', 'tickets', statusFilter, categoryFilter, priorityFilter, searchQuery] as const

  const query = useQuery({
    queryKey,
    queryFn: () => {
      const params: Record<string, string> = {}
      if (statusFilter) params.status = statusFilter
      if (categoryFilter) params.category = categoryFilter
      if (priorityFilter) params.priority = priorityFilter
      if (searchQuery) params.q = searchQuery
      return appApi.get<AdminTicketsResponse>('/admin/tickets', params)
    },
  })

  if (query.isLoading) {
    return <PageLoading label="Đang tải danh sách ticket..." />
  }

  if (query.isError) {
    return <PageError error={query.error} />
  }

  const { items = [], stats = { total: 0, open: 0, in_progress: 0, resolved: 0, closed: 0, rejected: 0 } } =
    query.data || {}

  return (
    <Page className="space-y-8 py-4 pb-16">
      <PageHeader
        title="Quản lý Ticket & Báo lỗi"
        description="Theo dõi các yêu cầu hỗ trợ, phân loại bug, cập nhật trạng thái và phản hồi người dùng."
      />

      {/* Stats Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard
          label="Tổng số Ticket"
          value={stats.total}
          tone="default"
        />
        <StatCard
          label="Chờ xử lý"
          value={stats.open}
          hint="Yêu cầu mới chưa xử lý"
          tone="warning"
        />
        <StatCard
          label="Đang xử lý"
          value={stats.in_progress}
          hint="Đang kiểm tra & sửa lỗi"
          tone="primary"
        />
        <StatCard
          label="Đã giải quyết"
          value={stats.resolved}
          hint="Hoàn tất trả lời"
          tone="success"
        />
      </div>

      {/* Filter & Search Bar */}
      <Card className="shadow-xs border-border/60">
        <CardContent className="pt-6 space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
              <Input
                placeholder="Tìm mã ticket, tiêu đề, người gửi..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 rounded-lg"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <NativeSelect
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-36 rounded-lg text-xs"
              >
                <NativeSelectOption value="">Tất cả Trạng thái</NativeSelectOption>
                <NativeSelectOption value="open">Chờ xử lý (Open)</NativeSelectOption>
                <NativeSelectOption value="in_progress">Đang xử lý</NativeSelectOption>
                <NativeSelectOption value="resolved">Đã giải quyết</NativeSelectOption>
                <NativeSelectOption value="rejected">Từ chối</NativeSelectOption>
                <NativeSelectOption value="closed">Đã đóng</NativeSelectOption>
              </NativeSelect>

              <NativeSelect
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="w-36 rounded-lg text-xs"
              >
                <NativeSelectOption value="">Tất cả Loại lỗi</NativeSelectOption>
                <NativeSelectOption value="bug">Báo lỗi (Bug)</NativeSelectOption>
                <NativeSelectOption value="feature">Ý tưởng mới</NativeSelectOption>
                <NativeSelectOption value="ui">Giao diện (UI)</NativeSelectOption>
                <NativeSelectOption value="other">Khác</NativeSelectOption>
              </NativeSelect>

              <NativeSelect
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="w-36 rounded-lg text-xs"
              >
                <NativeSelectOption value="">Tất cả Ưu tiên</NativeSelectOption>
                <NativeSelectOption value="urgent">Khẩn cấp</NativeSelectOption>
                <NativeSelectOption value="high">Cao</NativeSelectOption>
                <NativeSelectOption value="medium">Vừa</NativeSelectOption>
                <NativeSelectOption value="low">Thấp</NativeSelectOption>
              </NativeSelect>

              {(statusFilter || categoryFilter || priorityFilter || searchQuery) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setStatusFilter('')
                    setCategoryFilter('')
                    setPriorityFilter('')
                    setSearchQuery('')
                  }}
                  className="text-xs text-muted-foreground"
                >
                  Xóa bộ lọc
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tickets List Table */}
      <Card className="shadow-xs border-border/60">
        <CardHeader className="pb-3 border-b border-border/40">
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <Ticket className="size-4 text-primary" />
            <span>Danh sách Ticket báo cáo ({items.length})</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {items.length === 0 ? (
            <EmptyState
              title="Không tìm thấy ticket nào"
              description="Chưa có báo cáo lỗi nào phù hợp với bộ lọc hiện tại."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b bg-muted/30 text-muted-foreground font-semibold">
                    <th className="py-3 px-4">Mã Ticket</th>
                    <th className="py-3 px-4">Tiêu đề & Người gửi</th>
                    <th className="py-3 px-4">Màn hình bị lỗi</th>
                    <th className="py-3 px-4">Trạng thái</th>
                    <th className="py-3 px-4">Mức ưu tiên</th>
                    <th className="py-3 px-4">Ngày tạo</th>
                    <th className="py-3 px-4 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {items.map((t) => {
                    const catInfo = CATEGORY_MAP[t.category] || CATEGORY_MAP.other
                    const statusInfo = STATUS_MAP[t.status] || STATUS_MAP.open
                    const priorityInfo = PRIORITY_MAP[t.priority] || PRIORITY_MAP.medium
                    const CatIcon = catInfo.icon
                    const StatusIcon = statusInfo.icon

                    return (
                      <tr
                        key={t.id}
                        className="hover:bg-muted/20 transition-colors cursor-pointer"
                        onClick={() => navigate(`/admin/tickets/${t.id}`)}
                      >
                        <td className="py-3 px-4 font-mono font-bold text-primary">
                          {t.ticket_code}
                        </td>

                        <td className="py-3 px-4 space-y-1">
                          <div className="font-semibold text-foreground flex items-center gap-2">
                            <span>{t.title}</span>
                            {t.attachment_urls && t.attachment_urls.length > 0 && (
                              <Badge variant="outline" className="px-1.5 py-0 text-[10px] gap-1 text-blue-600 bg-blue-50 border-blue-200">
                                <ImageIcon className="size-3" /> {t.attachment_urls.length} ảnh
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                            <span className={`px-2 py-0.5 rounded-full border text-[10px] font-medium flex items-center gap-1 ${catInfo.color}`}>
                              <CatIcon className="size-3" /> {catInfo.label}
                            </span>
                            <span>•</span>
                            <span className="flex items-center gap-1 font-medium">
                              <UserIcon className="size-3 text-muted-foreground" />
                              {t.sender_name || 'Khách'} ({t.user_email || 'Không có email'})
                            </span>
                          </div>
                        </td>

                        <td className="py-3 px-4 max-w-[180px]">
                          {t.screen_url ? (
                            <a
                              href={t.screen_url}
                              target="_blank"
                              rel="noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-primary hover:underline font-medium truncate flex items-center gap-1"
                              title={t.screen_url}
                            >
                              <span>{t.screen_name || t.screen_url}</span>
                              <ExternalLink className="size-3 shrink-0" />
                            </a>
                          ) : (
                            <span className="text-muted-foreground font-mono text-[11px]">-</span>
                          )}
                        </td>

                        <td className="py-3 px-4">
                          <Badge className={`px-2.5 py-1 text-[10px] gap-1 rounded-full ${statusInfo.badge}`}>
                            <StatusIcon className="size-3" /> {statusInfo.label}
                          </Badge>
                        </td>

                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded-md text-[10px] font-medium ${priorityInfo.color}`}>
                            {priorityInfo.label}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-muted-foreground font-mono text-[11px]">
                          {t.created_at ? new Date(t.created_at).toLocaleString('vi-VN') : '-'}
                        </td>

                        <td className="py-3 px-4 text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            className="rounded-full text-xs gap-1.5"
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate(`/admin/tickets/${t.id}`)
                            }}
                          >
                            <Eye className="size-3.5" /> Xem & Trả lời
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </Page>
  )
}
