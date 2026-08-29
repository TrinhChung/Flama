import { useState } from 'react'
import {
  Bug,
  CheckCircle2,
  Clock,
  ExternalLink,
  Eye,
  Heart,
  Image as ImageIcon,
  Lightbulb,
  Link as LinkIcon,
  Loader2,
  MessageSquare,
  MessageSquareHeart,
  Palette,
  Plus,
  RefreshCw,
  Send,
  Ticket,
  Upload,
  X,
  XCircle,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import type { TicketItem } from '@/features/admin/pages/AdminTicketsPage'
import { Page } from '@/shared/components/Page'
import { EmptyState } from '@/shared/components/PageState'

type FeedbackCategory = 'bug' | 'feature' | 'ui' | 'other'

const ROUTE_NAME_MAP: Record<string, string> = {
  '/dashboard': 'Trang chủ / Tổng quan',
  '/statistics': 'Thống kê học tập',
  '/browse': 'Duyệt từ vựng & Thẻ ghi nhớ',
  '/study': 'Màn hình Học Flashcard',
  '/note-types': 'Quản lý Loại thẻ',
  '/installed-decks': 'Bộ thẻ đã cài',
  '/import': 'Import thẻ',
  '/marketplace/decks/publish': 'Đăng bộ thẻ',
  '/marketplace/decks': 'Kho bộ thẻ (Marketplace)',
  '/marketplace/note-types/publish': 'Đăng loại thẻ',
  '/marketplace/note-types': 'Kho loại thẻ',
  '/orders': 'Danh sách đơn hàng',
  '/settings/yomitan': 'Cài đặt Kết nối Yomitan',
  '/settings/mcp-tokens': 'MCP Access Tokens',
  '/feedback': 'Góp ý & Báo lỗi',
  '/admin/users': 'Admin - Quản lý người dùng',
  '/admin/permissions': 'Admin - Phân quyền',
  '/admin/payments': 'Admin - Quản lý thanh toán',
  '/admin/tts': 'Admin - TTS Provider',
  '/admin/image-library': 'Admin - Thư viện ảnh',
  '/admin/support': 'Admin - Cấu hình Ủng hộ',
}

function resolveScreenName(urlInput: string): string {
  const trimmed = urlInput.trim()
  if (!trimmed) return '(Vui lòng nhập URL để tự động nhận diện)'

  let pathname = trimmed
  try {
    if (trimmed.includes('://')) {
      pathname = new URL(trimmed).pathname
    } else {
      pathname = trimmed.split('?')[0].split('#')[0]
    }
  } catch {
    pathname = trimmed
  }

  const lowerPath = pathname.toLowerCase()
  for (const [route, title] of Object.entries(ROUTE_NAME_MAP)) {
    if (lowerPath === route.toLowerCase() || lowerPath.startsWith(route.toLowerCase())) {
      return title
    }
  }

  const segments = pathname.replace(/^\/+|\/+$/g, '').split('/')
  if (!segments[0]) return 'Trang chủ (Dashboard)'

  return segments
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(' > ')
}

const STATUS_MAP: Record<string, { label: string; badge: string; icon: any }> = {
  open: { label: 'Chờ xử lý', badge: 'bg-amber-500 text-white', icon: Clock },
  in_progress: { label: 'Đang xử lý', badge: 'bg-blue-600 text-white', icon: RefreshCw },
  resolved: { label: 'Đã giải quyết', badge: 'bg-emerald-600 text-white', icon: CheckCircle2 },
  rejected: { label: 'Từ chối', badge: 'bg-rose-600 text-white', icon: XCircle },
  closed: { label: 'Đã đóng', badge: 'bg-gray-500 text-white', icon: XCircle },
}

export function FeedbackPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'create' | 'my-tickets'>('create')
  const [category, setCategory] = useState<FeedbackCategory>('bug')
  const [urlPath, setUrlPath] = useState(window.location.href)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [reproduceSteps, setReproduceSteps] = useState('')
  const [attachedUrls, setAttachedUrls] = useState<string[]>([])
  const [isUploading, setIsUploading] = useState(false)

  const resolvedScreenName = resolveScreenName(urlPath)

  // My tickets query
  const myTicketsQuery = useQuery({
    queryKey: ['user', 'my-tickets'],
    queryFn: () => appApi.get<{ items: TicketItem[] }>('/tickets/my'),
    enabled: activeTab === 'my-tickets',
  })

  // Upload image mutation
  const uploadImage = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    setIsUploading(true)
    try {
      const res = await appApi.mutateFormData<{ url: string }>('/tickets/upload-image', 'POST', formData)
      if (res.url) {
        setAttachedUrls((prev) => [...prev, res.url])
        toast.success('Đã tải lên ảnh chụp màn hình!')
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.message || 'Không thể tải ảnh lên.')
    } finally {
      setIsUploading(false)
    }
  }

  // Create Ticket mutation
  const createTicketMutation = useMutation({
    mutationFn: (payload: {
      category: string
      title: string
      description: string
      reproduce_steps?: string
      screen_url?: string
      screen_name?: string
      attachment_urls?: string[]
    }) => appApi.mutate<{ item: TicketItem }>('/tickets', 'POST', payload),
    onSuccess: (data) => {
      const ticketCode = data.item?.ticket_code || 'Mới'
      toast.success(`Đã gửi ticket báo lỗi [${ticketCode}] thành công! Đội ngũ sẽ hỗ trợ bạn sớm nhất.`)
      // Reset form
      setTitle('')
      setDescription('')
      setReproduceSteps('')
      setAttachedUrls([])
      setActiveTab('my-tickets')
      void queryClient.invalidateQueries({ queryKey: ['user', 'my-tickets'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.message || 'Gửi báo cáo lỗi thất bại.')
    },
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    Array.from(files).forEach((file) => {
      void uploadImage(file)
    })
    e.target.value = ''
  }

  const handleSubmitTicket = (e: React.FormEvent) => {
    e.preventDefault()
    if (!description.trim()) {
      toast.error('Vui lòng nhập nội dung mô tả chi tiết lỗi!')
      return
    }

    const autoTitle = title.trim() || `[Báo lỗi] ${resolvedScreenName !== '(Vui lòng nhập URL để tự động nhận diện)' ? resolvedScreenName : 'Ứng dụng Flama'}`

    createTicketMutation.mutate({
      category,
      title: autoTitle,
      description: description.trim(),
      reproduce_steps: reproduceSteps.trim() || undefined,
      screen_url: urlPath.trim() || undefined,
      screen_name: resolvedScreenName !== '(Vui lòng nhập URL để tự động nhận diện)' ? resolvedScreenName : undefined,
      attachment_urls: attachedUrls,
    })
  }

  const fillCurrentUrl = () => {
    setUrlPath(window.location.href)
    toast.success('Đã lấy đường dẫn URL hiện tại!')
  }

  return (
    <Page className="max-w-4xl mx-auto space-y-8 py-4 pb-16">
      {/* Hero Header */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="px-3 py-1 text-xs gap-1.5 font-medium rounded-full bg-primary/10 text-primary border-none">
            <Heart className="size-3.5 fill-current text-primary" /> Lắng nghe & Hỗ trợ trực tiếp
          </Badge>
        </div>

        <div className="space-y-2">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground flex items-center gap-3">
            <MessageSquareHeart className="size-9 text-primary shrink-0" />
            <span>Góp ý & Báo lỗi System</span>
          </h1>
          <p className="text-base text-muted-foreground leading-relaxed max-w-2xl">
            Tạo ticket hỗ trợ trực tiếp trong ứng dụng để gửi ảnh chụp màn hình, đường dẫn lỗi và theo dõi phản hồi từ Quản trị viên mà không cần mở Email!
          </p>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center justify-between border-b pb-2">
        <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as any)}>
          <TabsList className="bg-muted/50 p-1 rounded-full">
            <TabsTrigger value="create" className="rounded-full text-xs font-semibold gap-1.5 px-4">
              <Plus className="size-3.5" /> Gửi báo cáo lỗi mới
            </TabsTrigger>

            <TabsTrigger value="my-tickets" className="rounded-full text-xs font-semibold gap-1.5 px-4">
              <Ticket className="size-3.5" /> Ticket của tôi
              {myTicketsQuery.data?.items && myTicketsQuery.data.items.length > 0 && (
                <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px] rounded-full">
                  {myTicketsQuery.data.items.length}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Tab Content 1: Create Ticket */}
      {activeTab === 'create' && (
        <form onSubmit={handleSubmitTicket} className="space-y-6">
          {/* Category Pills */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold text-foreground">1. Chọn chủ đề báo cáo</Label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setCategory('bug')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                  category === 'bug'
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'bg-muted/60 hover:bg-muted text-muted-foreground'
                }`}
              >
                <Bug className="size-4" /> Báo lỗi (Bug)
              </button>

              <button
                type="button"
                onClick={() => setCategory('feature')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                  category === 'feature'
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'bg-muted/60 hover:bg-muted text-muted-foreground'
                }`}
              >
                <Lightbulb className="size-4" /> Ý tưởng mới
              </button>

              <button
                type="button"
                onClick={() => setCategory('ui')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                  category === 'ui'
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'bg-muted/60 hover:bg-muted text-muted-foreground'
                }`}
              >
                <Palette className="size-4" /> Giao diện (UI/UX)
              </button>

              <button
                type="button"
                onClick={() => setCategory('other')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                  category === 'other'
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'bg-muted/60 hover:bg-muted text-muted-foreground'
                }`}
              >
                <MessageSquare className="size-4" /> Khác
              </button>
            </div>
          </div>

          {/* Screen URL Auto Detect */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-semibold text-foreground flex items-center gap-2">
                <LinkIcon className="size-4 text-primary" /> 2. Đường dẫn màn hình xảy ra lỗi
              </Label>
              <Button type="button" variant="outline" size="sm" onClick={fillCurrentUrl} className="rounded-full text-xs h-7">
                <RefreshCw className="mr-1 size-3" /> Lấy URL hiện tại
              </Button>
            </div>
            <Input
              placeholder="Dán URL màn hình (Ví dụ: http://localhost:5173/study)"
              value={urlPath}
              onChange={(e) => setUrlPath(e.target.value)}
              className="rounded-xl font-mono text-xs"
            />
            <div className="text-xs text-muted-foreground flex items-center gap-1.5 bg-muted/30 p-2.5 rounded-xl border border-border/80">
              <Info className="size-3.5 text-muted-foreground shrink-0" />
              <span>Tên màn hình nhận diện: <strong className="text-foreground font-semibold">{resolvedScreenName}</strong></span>
            </div>
          </div>

          {/* Title & Description */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm font-semibold text-foreground">3. Tiêu đề tóm tắt lỗi (Không bắt buộc)</Label>
              <Input
                placeholder="Ví dụ: Nút Bắt đầu học trên màn hình /study bị đơ"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="rounded-xl text-xs"
              />
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-semibold text-foreground">4. Mô tả chi tiết vấn đề (*)</Label>
              <Textarea
                placeholder="Vui lòng mô tả những gì xảy ra, thông báo lỗi nếu có..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="min-h-28 rounded-xl text-xs"
                required
              />
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-semibold text-foreground">5. Các bước tái hiện lỗi (Tùy chọn)</Label>
              <Textarea
                placeholder="1. Mở trang Duyệt từ vựng&#10;2. Bấm vào bộ thẻ N3&#10;3. Nút học không phản hồi..."
                value={reproduceSteps}
                onChange={(e) => setReproduceSteps(e.target.value)}
                className="min-h-20 rounded-xl text-xs font-mono"
              />
            </div>
          </div>

          {/* Screenshots Uploader */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold text-foreground flex items-center gap-2">
              <ImageIcon className="size-4 text-primary" /> 6. Đính kèm ảnh chụp màn hình (Screenshots)
            </Label>

            <div className="flex flex-wrap items-center gap-3">
              {attachedUrls.map((url, idx) => (
                <div key={idx} className="relative group border rounded-xl overflow-hidden shadow-xs bg-muted/40">
                  <img src={url} alt={`Screenshot ${idx + 1}`} className="size-20 object-cover" />
                  <button
                    type="button"
                    onClick={() => setAttachedUrls((prev) => prev.filter((_, i) => i !== idx))}
                    className="absolute top-1 right-1 p-1 bg-black/70 hover:bg-red-600 text-white rounded-full transition-colors"
                    title="Xóa ảnh"
                  >
                    <X className="size-3" />
                  </button>
                </div>
              ))}

              <label className="flex flex-col items-center justify-center size-20 rounded-xl border-2 border-dashed border-border/80 hover:border-primary bg-muted/20 hover:bg-muted/40 cursor-pointer transition-all">
                {isUploading ? (
                  <Loader2 className="size-5 animate-spin text-primary" />
                ) : (
                  <>
                    <Upload className="size-5 text-muted-foreground" />
                    <span className="text-[10px] text-muted-foreground font-medium pt-1">Thêm ảnh</span>
                  </>
                )}
                <input type="file" accept="image/*" multiple onChange={handleFileChange} className="hidden" disabled={isUploading} />
              </label>
            </div>
          </div>

          {/* Submit Action */}
          <div className="pt-4 flex items-center justify-end gap-3">
            <Button
              type="submit"
              size="lg"
              className="rounded-full px-8 font-bold shadow-md gap-2 text-sm"
              disabled={createTicketMutation.isPending || isUploading}
            >
              {createTicketMutation.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" /> Đang gửi Ticket...
                </>
              ) : (
                <>
                  <Send className="size-4" /> Gửi báo cáo lỗi ngay
                </>
              )}
            </Button>
          </div>
        </form>
      )}

      {/* Tab Content 2: My Tickets */}
      {activeTab === 'my-tickets' && (
        <div className="space-y-4">
          {myTicketsQuery.isLoading ? (
            <div className="py-12 text-center text-muted-foreground">Đang tải các ticket của bạn...</div>
          ) : !myTicketsQuery.data?.items || myTicketsQuery.data.items.length === 0 ? (
            <EmptyState
              title="Bạn chưa gửi ticket báo lỗi nào"
              description="Hãy dùng form 'Gửi báo cáo lỗi mới' để phản hồi với đội ngũ phát triển khi gặp sự cố."
              action={
                <Button size="sm" onClick={() => setActiveTab('create')} className="rounded-full">
                  <Plus className="mr-1 size-3.5" /> Tạo ticket đầu tiên
                </Button>
              }
            />
          ) : (
            <div className="space-y-3">
              {myTicketsQuery.data.items.map((t) => {
                const statusInfo = STATUS_MAP[t.status] || STATUS_MAP.open
                const StatusIcon = statusInfo.icon

                return (
                  <Card
                    key={t.id}
                    className="shadow-xs hover:shadow-md hover:border-primary/50 transition-all cursor-pointer border-border/60"
                    onClick={() => navigate(`/tickets/${t.id}`)}
                  >
                    <CardContent className="p-5 flex flex-wrap items-center justify-between gap-4">
                      <div className="space-y-1.5 max-w-xl">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-xs px-2.5 py-0.5 bg-primary/10 text-primary rounded-full">
                            {t.ticket_code}
                          </span>
                          <h3 className="font-bold text-base text-foreground hover:text-primary transition-colors">
                            {t.title}
                          </h3>
                        </div>

                        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                          {t.description}
                        </p>

                        <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground pt-1">
                          {t.screen_name && (
                            <span className="flex items-center gap-1 font-medium text-foreground">
                              <ExternalLink className="size-3 text-primary" /> {t.screen_name}
                            </span>
                          )}
                          <span>•</span>
                          <span>Ngày gửi: {new Date(t.created_at).toLocaleString('vi-VN')}</span>
                          {t.attachment_urls && t.attachment_urls.length > 0 && (
                            <>
                              <span>•</span>
                              <span className="flex items-center gap-1 text-blue-600 font-medium">
                                <ImageIcon className="size-3" /> {t.attachment_urls.length} ảnh
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <Badge className={`px-3 py-1 text-xs gap-1.5 rounded-full ${statusInfo.badge}`}>
                          <StatusIcon className="size-3.5" /> {statusInfo.label}
                        </Badge>
                        <Button size="sm" variant="ghost" className="rounded-full px-3 text-xs gap-1">
                          <Eye className="size-3.5" /> Xem chi tiết
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}
        </div>
      )}
    </Page>
  )
}
