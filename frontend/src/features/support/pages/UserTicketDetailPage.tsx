import { useState } from 'react'
import {
  ArrowLeft,
  Bug,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  Image as ImageIcon,
  Lightbulb,
  Loader2,
  MessageSquare,
  Palette,
  RefreshCw,
  Send,
  Shield,
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
  open: { label: 'Chờ xử lý', badge: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-300/40', icon: Clock },
  in_progress: { label: 'Đang xử lý', badge: 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border border-blue-300/40', icon: RefreshCw },
  resolved: { label: 'Đã giải quyết', badge: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-300/40', icon: CheckCircle2 },
  rejected: { label: 'Từ chối', badge: 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border border-rose-300/40', icon: XCircle },
  closed: { label: 'Đã đóng', badge: 'bg-slate-500/15 text-slate-700 dark:text-slate-400 border border-slate-300/40', icon: XCircle },
}

const CATEGORY_MAP: Record<string, { label: string; icon: any; color: string }> = {
  bug: { label: 'Báo lỗi (Bug)', icon: Bug, color: 'text-rose-500' },
  feature: { label: 'Ý tưởng mới', icon: Lightbulb, color: 'text-amber-500' },
  ui: { label: 'Giao diện (UI/UX)', icon: Palette, color: 'text-purple-500' },
  other: { label: 'Chủ đề khác', icon: MessageSquare, color: 'text-blue-500' },
}

export function UserTicketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [userReplyMsg, setUserReplyMsg] = useState('')
  const [previewImage, setPreviewImage] = useState<string | null>(null)
  const [copiedCode, setCopiedCode] = useState(false)

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

  const handleSendReply = () => {
    if (!id || !userReplyMsg.trim()) return
    userReplyMutation.mutate({
      ticketId: id,
      message: userReplyMsg.trim(),
    })
  }

  // Ctrl+Enter shortcut to send reply
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSendReply()
    }
  }

  const handleCopyTicketCode = (code: string) => {
    navigator.clipboard.writeText(code)
    setCopiedCode(true)
    toast.success(`Đã sao chép mã ticket [${code}]`)
    setTimeout(() => setCopiedCode(false), 2000)
  }

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
  const catInfo = CATEGORY_MAP[ticket.category] || CATEGORY_MAP.other
  const CatIcon = catInfo.icon

  return (
    <Page className="max-w-4xl mx-auto space-y-6 py-4 pb-20">
      {/* Navigation Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/tickets')}
          className="rounded-full text-xs font-bold gap-1.5 text-muted-foreground hover:text-foreground hover:bg-muted"
        >
          <ArrowLeft className="size-4" /> Quay lại danh sách Ticket
        </Button>

        <div className="flex items-center gap-2">
          {/* Ticket Code */}
          <div className="flex items-center gap-1 font-mono font-bold text-xs px-3 py-1 bg-primary/10 text-primary rounded-full">
            <span>{ticket.ticket_code}</span>
            <button
              type="button"
              onClick={() => handleCopyTicketCode(ticket.ticket_code)}
              className="p-0.5 hover:bg-primary/20 rounded text-primary transition-colors cursor-pointer"
              title="Sao chép mã"
            >
              {copiedCode ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
            </button>
          </div>

          <Badge className={`px-3 py-1 text-xs gap-1.5 rounded-full font-semibold ${statusInfo.badge}`}>
            <StatusIcon className="size-3.5" /> {statusInfo.label}
          </Badge>
        </div>
      </div>

      {/* Main Issue Card */}
      <Card className="shadow-xs border-border/60 rounded-2xl">
        <CardHeader className="space-y-3 pb-4 border-b border-border/40">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline" className="px-2.5 py-0.5 text-[11px] gap-1 font-medium rounded-full border-border/80">
                <CatIcon className={`size-3 ${catInfo.color}`} /> {catInfo.label}
              </Badge>
              <span>•</span>
              <span className="font-mono">
                Báo cáo ngày {new Date(ticket.created_at).toLocaleString('vi-VN')}
              </span>
            </div>

            <CardTitle className="text-xl sm:text-2xl font-extrabold text-foreground leading-snug">
              {ticket.title}
            </CardTitle>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs pt-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground bg-muted/40 px-3 py-1 rounded-full border border-border/60">
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

        <CardContent className="pt-5 space-y-6">
          {/* Main Description */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
              Nội dung mô tả chi tiết:
            </h4>
            <div className="p-4 rounded-xl border border-border/80 bg-card text-sm leading-relaxed whitespace-pre-wrap font-sans text-foreground shadow-2xs">
              {ticket.description}
            </div>
          </div>

          {/* Reproduce Steps */}
          {ticket.reproduce_steps && (
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                Các bước tái hiện lỗi:
              </h4>
              <div className="p-4 rounded-xl border border-border/80 bg-card text-xs font-mono text-foreground leading-relaxed whitespace-pre-wrap shadow-2xs">
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
              <div className="flex flex-wrap gap-3.5 pt-1">
                {ticket.attachment_urls.map((url, idx) => (
                  <div
                    key={idx}
                    className="relative group size-28 rounded-xl border border-border/80 overflow-hidden shadow-2xs cursor-pointer hover:ring-2 hover:ring-primary transition-all bg-card"
                    onClick={() => setPreviewImage(url)}
                  >
                    <img src={url} alt={`Screenshot ${idx + 1}`} className="size-full object-cover" />
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition-opacity text-xs font-medium">
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
      <Card className="shadow-2xs border-border/80 bg-card rounded-xl">
        <CardHeader className="pb-3 border-b border-border/40">
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <MessageSquare className="size-4 text-primary" />
            <span>Lịch sử trao đổi & Phản hồi ({ticket.replies?.length || 0})</span>
          </CardTitle>
        </CardHeader>

        <CardContent className="pt-6 space-y-6">
          {(!ticket.replies || ticket.replies.length === 0) ? (
            <div className="p-8 text-center space-y-2 bg-card rounded-xl border border-border/80 shadow-2xs">
              <Clock className="size-8 text-amber-500 mx-auto" />
              <p className="text-sm font-semibold text-foreground">Ticket đang được xử lý</p>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                Yêu cầu của bạn đã được tiếp nhận. Đội ngũ Quản trị viên sẽ gửi câu trả lời tại đây trong thời gian sớm nhất.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {ticket.replies.map((reply) => (
                <div
                  key={reply.id}
                  className={`p-4 rounded-xl border space-y-2.5 transition-all shadow-2xs ${
                    reply.is_admin_reply
                      ? 'bg-blue-500/10 border-blue-400/40 text-foreground ml-3 sm:ml-6'
                      : 'bg-card border-border/80 mr-3 sm:mr-6'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 font-bold">
                      {reply.is_admin_reply ? (
                        <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400 font-extrabold">
                          <Shield className="size-3.5" /> {reply.sender_name || 'Quản trị viên'} (Admin)
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-foreground">
                          <UserIcon className="size-3.5 text-muted-foreground" /> {reply.sender_name || 'Bạn'}
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] text-muted-foreground font-mono">
                      {reply.created_at ? new Date(reply.created_at).toLocaleString('vi-VN') : ''}
                    </span>
                  </div>
                  <p className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap">{reply.message}</p>
                </div>
              ))}
            </div>
          )}

          {/* Reply Form */}
          <div className="space-y-3 pt-4 border-t border-border/40">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-bold text-foreground">Gửi thêm phản hồi cho Quản trị viên:</Label>
              <span className="text-[11px] text-muted-foreground">
                <kbd className="px-1 py-0.5 text-[10px] font-mono bg-card rounded border border-border/80">Ctrl</kbd> + <kbd className="px-1 py-0.5 text-[10px] font-mono bg-card rounded border border-border/80">Enter</kbd> để gửi
              </span>
            </div>

            <Textarea
              placeholder="Nhập thông tin bổ sung hoặc câu hỏi phản hồi của bạn..."
              value={userReplyMsg}
              onChange={(e) => setUserReplyMsg(e.target.value)}
              onKeyDown={handleKeyDown}
              className="bg-card border-border/80 min-h-24 text-xs sm:text-sm rounded-xl p-3 shadow-2xs text-foreground"
            />

            <div className="flex justify-end">
              <Button
                size="sm"
                className="rounded-full text-xs font-bold px-7 gap-2 shadow-xs"
                onClick={handleSendReply}
                disabled={userReplyMutation.isPending || !userReplyMsg.trim()}
              >
                {userReplyMutation.isPending ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" /> Đang gửi...
                  </>
                ) : (
                  <>
                    <Send className="size-3.5" /> Gửi phản hồi
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Lightbox Image Preview Modal */}
      <Dialog open={Boolean(previewImage)} onOpenChange={(open) => !open && setPreviewImage(null)}>
        <DialogContent className="max-w-4xl sm:max-w-4xl p-2 bg-black/95 border-none flex flex-col items-center justify-center">
          {previewImage && (
            <img src={previewImage} alt="Full Screenshot Preview" className="max-h-[85vh] object-contain rounded-xl" />
          )}
        </DialogContent>
      </Dialog>
    </Page>
  )
}
