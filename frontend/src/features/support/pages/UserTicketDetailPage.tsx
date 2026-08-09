import { useState } from 'react'
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  ExternalLink,
  Image as ImageIcon,
  MessageSquare,
  RefreshCw,
  Send,
  User as UserIcon,
  XCircle,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { TicketItem } from '@/features/admin/pages/AdminTicketsPage'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

const STATUS_MAP: Record<string, { label: string; badge: string; icon: any }> = {
  open: { label: 'Chờ xử lý', badge: 'bg-amber-500 text-white', icon: Clock },
  in_progress: { label: 'Đang xử lý', badge: 'bg-blue-600 text-white', icon: RefreshCw },
  resolved: { label: 'Đã giải quyết', badge: 'bg-emerald-600 text-white', icon: CheckCircle2 },
  rejected: { label: 'Từ chối', badge: 'bg-rose-600 text-white', icon: XCircle },
  closed: { label: 'Đã đóng', badge: 'bg-gray-500 text-white', icon: XCircle },
}

export function UserTicketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [userReplyMsg, setUserReplyMsg] = useState('')
  const [previewImage, setPreviewImage] = useState<string | null>(null)

  const queryKey = ['user', 'ticket-detail', id] as const

  const detailQuery = useQuery({
    queryKey,
    queryFn: () => appApi.get<{ item: TicketItem }>(`/tickets/${id}`),
    enabled: Boolean(id),
  })

  // User reply mutation
  const userReplyMutation = useMutation({
    mutationFn: (payload: { ticketId: string; message: string }) =>
      appApi.mutate(`/tickets/${payload.ticketId}/replies`, 'POST', { message: payload.message }),
    onSuccess: () => {
      toast.success('Đã gửi phản hồi thành công!')
      setUserReplyMsg('')
      void queryClient.invalidateQueries({ queryKey })
      void queryClient.invalidateQueries({ queryKey: ['user', 'my-tickets'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.message || 'Gửi phản hồi thất bại.')
    },
  })

  if (detailQuery.isLoading) {
    return <PageLoading label="Đang tải chi tiết ticket..." />
  }

  if (detailQuery.isError || !detailQuery.data?.item) {
    return (
      <Page className="py-8">
        <PageError error={detailQuery.error || new Error('Không tìm thấy ticket.')} />
        <div className="pt-4 text-center">
          <Button variant="outline" onClick={() => navigate('/tickets')} className="rounded-full">
            <ArrowLeft className="mr-1.5 size-4" /> Quay lại danh sách Ticket
          </Button>
        </div>
      </Page>
    )
  }

  const ticket = detailQuery.data.item
  const statusInfo = STATUS_MAP[ticket.status] || STATUS_MAP.open
  const StatusIcon = statusInfo.icon

  return (
    <Page className="max-w-4xl mx-auto space-y-6 py-4 pb-16">
      {/* Navigation Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/tickets')}
          className="rounded-full text-xs font-semibold gap-1.5 text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Quay lại danh sách Ticket
        </Button>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold text-primary px-3 py-1 bg-primary/10 rounded-full">
            {ticket.ticket_code}
          </span>
          <Badge className={`px-3 py-1 text-xs gap-1.5 rounded-full ${statusInfo.badge}`}>
            <StatusIcon className="size-3.5" /> {statusInfo.label}
          </Badge>
        </div>
      </div>

      {/* Hero Issue Card */}
      <Card className="shadow-xs border-border/60">
        <CardHeader className="space-y-3 pb-3 border-b border-border/40">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
              <span>Báo cáo ngày: {new Date(ticket.created_at).toLocaleString('vi-VN')}</span>
            </div>
            <CardTitle className="text-xl sm:text-2xl font-bold text-foreground">
              {ticket.title}
            </CardTitle>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5 font-medium text-foreground bg-muted/40 px-3 py-1 rounded-full border">
              <UserIcon className="size-3.5 text-primary" /> {ticket.sender_name || 'Khách'} ({ticket.user_email || 'Không email'})
            </span>

            {ticket.screen_url && (
              <a
                href={ticket.screen_url}
                target="_blank"
                rel="noreferrer"
                className="text-primary hover:underline flex items-center gap-1.5 font-semibold bg-primary/10 px-3 py-1 rounded-full"
              >
                <ExternalLink className="size-3.5" /> Màn hình báo lỗi: {ticket.screen_name || ticket.screen_url}
              </a>
            )}
          </div>
        </CardHeader>

        <CardContent className="pt-5 space-y-5">
          {/* Main Description */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Mô tả chi tiết sự cố:</h4>
            <div className="p-4 rounded-xl border bg-muted/20 text-sm leading-relaxed whitespace-pre-wrap font-sans text-foreground">
              {ticket.description}
            </div>
          </div>

          {/* Reproduce Steps */}
          {ticket.reproduce_steps && (
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Các bước tái hiện lỗi:</h4>
              <div className="p-4 rounded-xl border bg-amber-50/40 border-amber-200/60 text-xs font-mono text-amber-950 leading-relaxed whitespace-pre-wrap">
                {ticket.reproduce_steps}
              </div>
            </div>
          )}

          {/* Attached Screenshots */}
          {ticket.attachment_urls && ticket.attachment_urls.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                <ImageIcon className="size-3.5 text-primary" /> Ảnh chụp màn hình đính kèm ({ticket.attachment_urls.length}):
              </h4>
              <div className="flex flex-wrap gap-3 pt-1">
                {ticket.attachment_urls.map((url, idx) => (
                  <div
                    key={idx}
                    className="relative group border rounded-xl overflow-hidden shadow-xs cursor-pointer hover:ring-2 hover:ring-primary transition-all bg-muted/30"
                    onClick={() => setPreviewImage(url)}
                  >
                    <img src={url} alt={`Screenshot ${idx + 1}`} className="size-28 object-cover" />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition-opacity text-xs font-medium">
                      Nhấp để phóng to
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Conversation Thread Section */}
      <Card className="shadow-xs border-border/60">
        <CardHeader className="pb-3 border-b border-border/40">
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <MessageSquare className="size-4 text-primary" />
            <span>Lịch sử trao đổi & Phản hồi ({ticket.replies?.length || 0})</span>
          </CardTitle>
        </CardHeader>

        <CardContent className="pt-6 space-y-6">
          {(!ticket.replies || ticket.replies.length === 0) ? (
            <div className="p-6 text-center text-xs text-muted-foreground bg-muted/20 rounded-xl border">
              Ticket đang được chuyển tới Quản trị viên. Bạn sẽ nhận được câu trả lời tại đây ngay khi có phản hồi.
            </div>
          ) : (
            <div className="space-y-4">
              {ticket.replies.map((reply) => (
                <div
                  key={reply.id}
                  className={`p-4 rounded-xl border space-y-2 ${
                    reply.is_admin_reply
                      ? 'bg-blue-50/50 border-blue-200 text-blue-950 ml-4 shadow-2xs'
                      : 'bg-muted/30 border-border/60 mr-4'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className={`font-bold ${reply.is_admin_reply ? 'text-blue-700' : 'text-foreground'}`}>
                      {reply.sender_name} {reply.is_admin_reply && '(Quản trị viên)'}
                    </span>
                    <span className="text-[11px] text-muted-foreground font-mono">
                      {reply.created_at ? new Date(reply.created_at).toLocaleString('vi-VN') : ''}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed whitespace-pre-wrap">{reply.message}</p>
                </div>
              ))}
            </div>
          )}

          {/* Reply Form */}
          <div className="space-y-3 pt-4 border-t border-border/40">
            <Label className="text-xs font-bold text-foreground">Gửi thêm phản hồi cho Quản trị viên:</Label>
            <Textarea
              placeholder="Nhập thông tin bổ sung hoặc câu hỏi phản hồi của bạn..."
              value={userReplyMsg}
              onChange={(e) => setUserReplyMsg(e.target.value)}
              className="min-h-24 text-xs rounded-xl"
            />
            <div className="flex justify-end">
              <Button
                size="sm"
                className="rounded-full text-xs font-bold px-6 gap-1.5 shadow-xs"
                onClick={() =>
                  userReplyMutation.mutate({
                    ticketId: ticket.id,
                    message: userReplyMsg.trim(),
                  })
                }
                disabled={userReplyMutation.isPending || !userReplyMsg.trim()}
              >
                <Send className="size-3.5" /> Gửi phản hồi
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Lightbox Image Preview Modal */}
      <Dialog open={Boolean(previewImage)} onOpenChange={(open) => !open && setPreviewImage(null)}>
        <DialogContent className="max-w-4xl p-2 bg-black/95 border-none flex flex-col items-center justify-center">
          {previewImage && (
            <img src={previewImage} alt="Full Screenshot Preview" className="max-h-[85vh] object-contain rounded-lg" />
          )}
        </DialogContent>
      </Dialog>
    </Page>
  )
}
