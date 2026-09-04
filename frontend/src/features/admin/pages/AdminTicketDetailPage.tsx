import { useState } from 'react'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  ExternalLink,
  Filter,
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
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
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

const PRIORITY_MAP: Record<string, { label: string; color: string }> = {
  low: { label: 'Thấp', color: 'text-slate-500 bg-slate-100' },
  medium: { label: 'Vừa', color: 'text-blue-700 bg-blue-50' },
  high: { label: 'Cao', color: 'text-amber-700 bg-amber-50 font-semibold' },
  urgent: { label: 'Khẩn cấp', color: 'text-red-700 bg-red-50 font-extrabold animate-pulse' },
}

export function AdminTicketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [replyMessage, setReplyMessage] = useState('')
  const [adminNotes, setAdminNotes] = useState('')
  const [previewImage, setPreviewImage] = useState<string | null>(null)
  const [isNotesInitialized, setIsNotesInitialized] = useState(false)

  const queryKey = ['admin', 'ticket-detail', id] as const

  const detailQuery = useQuery({
    queryKey,
    queryFn: () => appApi.get<{ item: TicketItem }>(`/tickets/${id}`),
    enabled: Boolean(id),
  })

  const currentDetail = detailQuery.data?.item

  if (currentDetail && !isNotesInitialized) {
    setAdminNotes(currentDetail.admin_notes || '')
    setIsNotesInitialized(true)
  }

  // Update Status / Priority / Notes Mutation
  const updateMutation = useMutation({
    mutationFn: (payload: { ticketId: string; status?: string; priority?: string; admin_notes?: string }) =>
      appApi.mutate<{ item: TicketItem }>(`/admin/tickets/${payload.ticketId}`, 'PATCH', {
        status: payload.status,
        priority: payload.priority,
        admin_notes: payload.admin_notes,
      }),
    onSuccess: () => {
      toast.success('Đã cập nhật trạng thái ticket thành công!')
      void queryClient.invalidateQueries({ queryKey })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'tickets'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.message || 'Cập nhật thất bại.')
    },
  })

  // Send Admin Reply Mutation
  const replyMutation = useMutation({
    mutationFn: (payload: { ticketId: string; message: string; new_status?: string }) =>
      appApi.mutate(`/tickets/${payload.ticketId}/replies`, 'POST', {
        message: payload.message,
        new_status: payload.new_status,
      }),
    onSuccess: () => {
      toast.success('Đã gửi câu trả lời cho người dùng!')
      setReplyMessage('')
      void queryClient.invalidateQueries({ queryKey })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'tickets'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.message || 'Gửi phản hồi thất bại.')
    },
  })

  const handleSendReply = (markResolved = false) => {
    if (!id || !replyMessage.trim()) {
      toast.error('Vui lòng nhập nội dung phản hồi!')
      return
    }
    replyMutation.mutate({
      ticketId: id,
      message: replyMessage.trim(),
      new_status: markResolved ? 'resolved' : undefined,
    })
  }

  const handleSaveNotes = () => {
    if (!id) return
    updateMutation.mutate({
      ticketId: id,
      admin_notes: adminNotes,
    })
  }

  if (detailQuery.isLoading) {
    return <PageLoading label="Đang tải chi tiết ticket..." />
  }

  if (detailQuery.isError || !currentDetail) {
    return (
      <Page className="py-8">
        <PageError error={detailQuery.error || new Error('Không tìm thấy ticket.')} />
        <div className="pt-4 text-center">
          <Button variant="outline" onClick={() => navigate('/admin/tickets')} className="rounded-full">
            <ArrowLeft className="mr-1.5 size-4" /> Quay lại Quản lý Ticket Admin
          </Button>
        </div>
      </Page>
    )
  }

  const statusInfo = STATUS_MAP[currentDetail.status] || STATUS_MAP.open
  const priorityInfo = PRIORITY_MAP[currentDetail.priority] || PRIORITY_MAP.medium
  const StatusIcon = statusInfo.icon

  return (
    <Page className="space-y-6 py-4 pb-16">
      {/* Navigation Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/admin/tickets')}
          className="rounded-full text-xs font-semibold gap-1.5 text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Quay lại Quản lý Ticket Admin
        </Button>

        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-extrabold text-primary px-3 py-1 bg-primary/10 rounded-full">
            {currentDetail.ticket_code}
          </span>
          <Badge className={`px-3 py-1 text-xs gap-1.5 rounded-full ${statusInfo.badge}`}>
            <StatusIcon className="size-3.5" /> {statusInfo.label}
          </Badge>
          <span className={`px-2.5 py-1 rounded-md text-xs font-semibold ${priorityInfo.color}`}>
            Độ ưu tiên: {priorityInfo.label}
          </span>
        </div>
      </div>

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Issue details & Conversation */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="shadow-xs border-border/60">
            <CardHeader className="space-y-3 pb-3 border-b border-border/40">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span className="font-mono">Ngày tạo: {new Date(currentDetail.created_at).toLocaleString('vi-VN')}</span>
              </div>
              <CardTitle className="text-xl sm:text-2xl font-bold text-foreground">
                {currentDetail.title}
              </CardTitle>
              <div className="flex flex-wrap items-center gap-4 text-xs">
                <span className="flex items-center gap-1.5 font-medium text-foreground bg-muted/40 px-3 py-1 rounded-full border">
                  <UserIcon className="size-3.5 text-primary" /> {currentDetail.sender_name || 'Khách'} ({currentDetail.user_email || 'Không email'})
                </span>

                {currentDetail.screen_url && (
                  <a
                    href={currentDetail.screen_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary hover:underline flex items-center gap-1.5 font-semibold bg-primary/10 px-3 py-1 rounded-full"
                  >
                    <ExternalLink className="size-3.5" /> Mở màn hình lỗi: {currentDetail.screen_name || currentDetail.screen_url}
                  </a>
                )}
              </div>
            </CardHeader>

            <CardContent className="pt-5 space-y-5">
              {/* Description */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Nội dung báo cáo chi tiết:</h4>
                <div className="p-4 rounded-xl border bg-muted/20 text-sm leading-relaxed whitespace-pre-wrap font-sans text-foreground">
                  {currentDetail.description}
                </div>
              </div>

              {/* Reproduce Steps */}
              {currentDetail.reproduce_steps && (
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Các bước tái hiện lỗi:</h4>
                  <div className="p-4 rounded-xl border bg-amber-50/40 border-amber-200/60 text-xs font-mono text-amber-950 leading-relaxed whitespace-pre-wrap">
                    {currentDetail.reproduce_steps}
                  </div>
                </div>
              )}

              {/* Screenshots */}
              {currentDetail.attachment_urls && currentDetail.attachment_urls.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                    <ImageIcon className="size-3.5 text-primary" /> Ảnh đính kèm ({currentDetail.attachment_urls.length}):
                  </h4>
                  <div className="flex flex-wrap gap-3 pt-1">
                    {currentDetail.attachment_urls.map((url, idx) => (
                      <div
                        key={idx}
                        className="relative group border rounded-xl overflow-hidden shadow-xs cursor-pointer hover:ring-2 hover:ring-primary transition-all bg-muted/30"
                        onClick={() => setPreviewImage(url)}
                      >
                        <img src={url} alt={`Attachment ${idx + 1}`} className="size-28 object-cover" />
                        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition-opacity text-xs font-medium">
                          Phóng to
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Conversation Thread & Admin Reply */}
          <Card className="shadow-xs border-border/60">
            <CardHeader className="pb-3 border-b border-border/40">
              <CardTitle className="text-base font-bold flex items-center gap-2">
                <MessageSquare className="size-4 text-primary" />
                <span>Lịch sử trao đổi với Người dùng ({currentDetail.replies?.length || 0})</span>
              </CardTitle>
            </CardHeader>

            <CardContent className="pt-6 space-y-6">
              {(!currentDetail.replies || currentDetail.replies.length === 0) ? (
                <div className="p-6 text-center text-xs text-muted-foreground bg-muted/20 rounded-xl border">
                  Chưa có phản hồi nào. Hãy viết câu trả lời đầu tiên gửi người dùng bên dưới.
                </div>
              ) : (
                <div className="space-y-4">
                  {currentDetail.replies.map((reply) => (
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
                          {reply.sender_name} {reply.is_admin_reply && '(Admin)'}
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
                <Label className="text-xs font-bold text-foreground">Trả lời người dùng:</Label>
                <Textarea
                  placeholder="Nhập nội dung giải đáp, nguyên nhân sự cố hoặc hướng dẫn xử lý gửi tới người dùng..."
                  value={replyMessage}
                  onChange={(e) => setReplyMessage(e.target.value)}
                  className="min-h-28 text-xs rounded-xl"
                />

                <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full text-xs gap-1.5 border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                    onClick={() => handleSendReply(true)}
                    disabled={replyMutation.isPending}
                  >
                    <CheckCircle2 className="size-3.5" /> Gửi & Đánh dấu Đã giải quyết
                  </Button>

                  <Button
                    size="sm"
                    className="rounded-full text-xs font-bold px-6 gap-1.5 shadow-xs"
                    onClick={() => handleSendReply(false)}
                    disabled={replyMutation.isPending}
                  >
                    <Send className="size-3.5" /> Gửi phản hồi
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Sidebar: Admin Controls & Internal Notes */}
        <div className="space-y-6">
          <Card className="shadow-xs border-border/60">
            <CardHeader className="pb-3 border-b border-border/40">
              <CardTitle className="text-sm font-bold flex items-center gap-2">
                <Filter className="size-4 text-primary" />
                <span>Cấu hình Trạng thái & Ưu tiên</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-5 space-y-4">
              <div className="space-y-2">
                <Label className="text-xs font-bold">Trạng thái ticket:</Label>
                <NativeSelect
                  value={currentDetail.status}
                  onChange={(e) => updateMutation.mutate({ ticketId: currentDetail.id, status: e.target.value })}
                  className="text-xs h-9 rounded-xl"
                >
                  <NativeSelectOption value="open">Chờ xử lý (Open)</NativeSelectOption>
                  <NativeSelectOption value="in_progress">Đang xử lý (In Progress)</NativeSelectOption>
                  <NativeSelectOption value="resolved">Đã giải quyết (Resolved)</NativeSelectOption>
                  <NativeSelectOption value="rejected">Từ chối (Rejected)</NativeSelectOption>
                  <NativeSelectOption value="closed">Đã đóng (Closed)</NativeSelectOption>
                </NativeSelect>
              </div>

              <div className="space-y-2">
                <Label className="text-xs font-bold">Mức độ ưu tiên:</Label>
                <NativeSelect
                  value={currentDetail.priority}
                  onChange={(e) => updateMutation.mutate({ ticketId: currentDetail.id, priority: e.target.value })}
                  className="text-xs h-9 rounded-xl"
                >
                  <NativeSelectOption value="low">Thấp</NativeSelectOption>
                  <NativeSelectOption value="medium">Vừa</NativeSelectOption>
                  <NativeSelectOption value="high">Cao</NativeSelectOption>
                  <NativeSelectOption value="urgent">Khẩn cấp</NativeSelectOption>
                </NativeSelect>
              </div>
            </CardContent>
          </Card>

          {/* Internal Admin Notes */}
          <Card className="shadow-xs border-border/60">
            <CardHeader className="pb-3 border-b border-border/40">
              <CardTitle className="text-sm font-bold flex items-center gap-2">
                <AlertCircle className="size-4 text-amber-600" />
                <span>Ghi chú nội bộ Admin</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-5 space-y-3">
              <p className="text-[11px] text-muted-foreground">
                Ghi chú kỹ thuật hoặc phân công nhiệm vụ (Người dùng không nhìn thấy).
              </p>
              <Textarea
                placeholder="Ghi chú kỹ thuật, nguyên nhân lỗi..."
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                className="text-xs min-h-28 rounded-xl font-mono bg-amber-50/20"
              />
              <Button
                size="sm"
                variant="outline"
                className="w-full text-xs font-semibold rounded-xl"
                onClick={handleSaveNotes}
                disabled={updateMutation.isPending}
              >
                Lưu ghi chú nội bộ
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Lightbox Modal */}
      <Dialog open={Boolean(previewImage)} onOpenChange={(open) => !open && setPreviewImage(null)}>
        <DialogContent className="max-w-4xl sm:max-w-4xl p-2 bg-black/95 border-none flex flex-col items-center justify-center">
          {previewImage && (
            <img src={previewImage} alt="Full Screenshot Preview" className="max-h-[85vh] object-contain rounded-lg" />
          )}
        </DialogContent>
      </Dialog>
    </Page>
  )
}
