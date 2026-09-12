import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Bug,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  Eye,
  Image as ImageIcon,
  Info,
  Lightbulb,
  Link as LinkIcon,
  Loader2,
  MessageSquare,
  MessageSquareHeart,
  Palette,
  Plus,
  RefreshCw,
  Search,
  Send,
  Ticket,
  Trash2,
  Upload,
  XCircle,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import type { TicketItem } from '@/features/admin/pages/AdminTicketsPage'
import { Page } from '@/shared/components/Page'
import { EmptyState } from '@/shared/components/PageState'
import { compressImage, MAX_IMAGE_UPLOAD_BYTES } from '@/lib/imageCompression'

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
  '/tickets': 'Danh sách Ticket hỗ trợ',
  '/admin/users': 'Admin - Quản lý người dùng',
  '/admin/permissions': 'Admin - Phân quyền',
  '/admin/payments': 'Admin - Quản lý thanh toán',
  '/admin/tts': 'Admin - TTS Provider',
  '/admin/image-library': 'Admin - Thư viện ảnh',
  '/admin/support': 'Admin - Cấu hình Ủng hộ',
}

const COMMON_SCREEN_PRESETS = [
  { label: 'Học Flashcard', url: '/study' },
  { label: 'Duyệt từ vựng', url: '/browse' },
  { label: 'Quản lý loại thẻ', url: '/note-types' },
  { label: 'Marketplace', url: '/marketplace/decks' },
  { label: 'Trang chủ', url: '/dashboard' },
]

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
  open: { label: 'Chờ xử lý', badge: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-300/40', icon: Clock },
  in_progress: { label: 'Đang xử lý', badge: 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border border-blue-300/40', icon: RefreshCw },
  resolved: { label: 'Đã giải quyết', badge: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-300/40', icon: CheckCircle2 },
  rejected: { label: 'Từ chối', badge: 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border border-rose-300/40', icon: XCircle },
  closed: { label: 'Đã đóng', badge: 'bg-slate-500/15 text-slate-700 dark:text-slate-400 border border-slate-300/40', icon: XCircle },
}

const CATEGORIES: {
  key: FeedbackCategory
  title: string
  subtitle: string
  icon: any
  color: string
  activeBorder: string
  activeBg: string
  placeholderTitle: string
  placeholderDesc: string
}[] = [
  {
    key: 'bug',
    title: 'Báo lỗi (Bug)',
    subtitle: 'Nút đơ, lỗi hiển thị, âm thanh',
    icon: Bug,
    color: 'text-rose-500',
    activeBorder: 'border-rose-500/80 ring-1 ring-rose-500/40',
    activeBg: 'bg-rose-500/10 text-foreground',
    placeholderTitle: 'Ví dụ: Nút Bắt đầu học trên màn hình /study bị đơ',
    placeholderDesc: 'Mô tả cụ thể sự cố bạn gặp phải, màn hình nào, thông báo lỗi nếu có...',
  },
  {
    key: 'feature',
    title: 'Ý tưởng mới',
    subtitle: 'Đề xuất tính năng & công cụ',
    icon: Lightbulb,
    color: 'text-amber-500',
    activeBorder: 'border-amber-500/80 ring-1 ring-amber-500/40',
    activeBg: 'bg-amber-500/10 text-foreground',
    placeholderTitle: 'Ví dụ: Thêm chế độ ôn tập theo bảng chữ cái Katakana',
    placeholderDesc: 'Mô tả tính năng bạn muốn và cách tính năng này giúp ích cho việc học...',
  },
  {
    key: 'ui',
    title: 'Giao diện (UI/UX)',
    subtitle: 'Bố cục, phông chữ, màu sắc',
    icon: Palette,
    color: 'text-purple-500',
    activeBorder: 'border-purple-500/80 ring-1 ring-purple-500/40',
    activeBg: 'bg-purple-500/10 text-foreground',
    placeholderTitle: 'Ví dụ: Tăng kích thước phông chữ kanji trên điện thoại',
    placeholderDesc: 'Mô tả phần giao diện cần cải thiện và gợi ý điều chỉnh của bạn...',
  },
  {
    key: 'other',
    title: 'Chủ đề khác',
    subtitle: 'Tài khoản, từ vựng, hỗ trợ chung',
    icon: MessageSquare,
    color: 'text-blue-500',
    activeBorder: 'border-blue-500/80 ring-1 ring-blue-500/40',
    activeBg: 'bg-blue-500/10 text-foreground',
    placeholderTitle: 'Ví dụ: Đóng góp ý kiến về nội dung bộ thẻ từ vựng N2',
    placeholderDesc: 'Nội dung phản hồi hoặc câu hỏi chi tiết của bạn...',
  },
]

function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString)
    const now = new Date()
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000)

    if (diffSec < 60) return 'Vừa xong'
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} phút trước`
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} giờ trước`
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)} ngày trước`
    return date.toLocaleDateString('vi-VN')
  } catch {
    return isoString
  }
}

export function FeedbackPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const isMyTicketsRoute = location.pathname === '/tickets' || searchParams.get('tab') === 'my-tickets'
  const queryClient = useQueryClient()

  const [activeTab, setActiveTab] = useState<'create' | 'my-tickets'>(isMyTicketsRoute ? 'my-tickets' : 'create')
  const [category, setCategory] = useState<FeedbackCategory>('bug')
  const [urlPath, setUrlPath] = useState(window.location.href)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [reproduceSteps, setReproduceSteps] = useState('')
  const [attachedUrls, setAttachedUrls] = useState<string[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [previewImage, setPreviewImage] = useState<string | null>(null)
  const [copiedTicketCode, setCopiedTicketCode] = useState<string | null>(null)

  // My tickets filter & search
  const [ticketSearch, setTicketSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')

  const fileInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (location.pathname === '/tickets' || searchParams.get('tab') === 'my-tickets') {
      setActiveTab('my-tickets')
    }
  }, [location.pathname, searchParams])

  const resolvedScreenName = resolveScreenName(urlPath)
  const activeCategoryConfig = CATEGORIES.find((c) => c.key === category) || CATEGORIES[0]

  // My tickets query
  const myTicketsQuery = useQuery({
    queryKey: ['user', 'my-tickets'],
    queryFn: () => appApi.get<{ items: TicketItem[] }>('/tickets/my'),
    enabled: activeTab === 'my-tickets',
  })

  // Upload image handler
  const uploadImageFile = useCallback(async (file: File) => {
    if (!file.type.startsWith('image/')) {
      toast.error('Chỉ chấp nhận tập tin hình ảnh (PNG, JPG, WEBP, GIF)!')
      return
    }

    setIsUploading(true)
    try {
      let fileToSend: File = file
      try {
        const compressed = await compressImage(file, {
          maxDimension: 1600,
          quality: 0.85,
        })
        fileToSend = compressed.file
      } catch {
        // Fall back to original file if compression fails
      }

      if (fileToSend.size > MAX_IMAGE_UPLOAD_BYTES) {
        toast.error('Dung lượng ảnh vượt quá 2MB. Vui lòng chọn ảnh nhỏ hơn.')
        return
      }

      const formData = new FormData()
      formData.append('file', fileToSend)
      const res = await appApi.mutateFormData<{ url: string }>('/tickets/upload-image', 'POST', formData)
      if (res.url) {
        setAttachedUrls((prev) => {
          if (prev.length >= 5) {
            toast.error('Đã đạt tối đa 5 ảnh đính kèm!')
            return prev
          }
          return [...prev, res.url]
        })
        toast.success('Đã tải lên ảnh chụp màn hình!')
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.message || err?.message || 'Không thể tải ảnh lên.')
    } finally {
      setIsUploading(false)
    }
  }, [])

  // Global Clipboard Paste Handler (Ctrl+V)
  useEffect(() => {
    if (activeTab !== 'create') return

    const handlePaste = (e: ClipboardEvent) => {
      const clipboardItems = e.clipboardData?.items
      if (!clipboardItems) return

      for (let i = 0; i < clipboardItems.length; i++) {
        const item = clipboardItems[i]
        if (item.type.startsWith('image/')) {
          const blob = item.getAsFile()
          if (blob) {
            e.preventDefault()
            toast.info('Đang tải lên ảnh từ Clipboard...')
            void uploadImageFile(blob)
            break
          }
        }
      }
    }

    window.addEventListener('paste', handlePaste)
    return () => {
      window.removeEventListener('paste', handlePaste)
    }
  }, [activeTab, uploadImageFile])

  // Drag & drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (!files || files.length === 0) return
    Array.from(files).forEach((file) => {
      void uploadImageFile(file)
    })
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
      toast.success(`Đã gửi ticket [${ticketCode}] thành công! Đội ngũ Flama sẽ hỗ trợ bạn sớm nhất.`)
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
      void uploadImageFile(file)
    })
    e.target.value = ''
  }

  const handleSubmitTicket = (e: React.FormEvent) => {
    e.preventDefault()
    if (!description.trim()) {
      toast.error('Vui lòng nhập nội dung mô tả chi tiết!')
      return
    }

    const autoTitle =
      title.trim() ||
      `[${activeCategoryConfig.title}] ${resolvedScreenName !== '(Vui lòng nhập URL để tự động nhận diện)' ? resolvedScreenName : 'Flama'}`

    createTicketMutation.mutate({
      category,
      title: autoTitle,
      description: description.trim(),
      reproduce_steps: category === 'bug' && reproduceSteps.trim() ? reproduceSteps.trim() : undefined,
      screen_url: urlPath.trim() || undefined,
      screen_name: resolvedScreenName !== '(Vui lòng nhập URL để tự động nhận diện)' ? resolvedScreenName : undefined,
      attachment_urls: attachedUrls,
    })
  }

  const fillCurrentUrl = () => {
    setUrlPath(window.location.href)
    toast.success('Đã lấy đường dẫn URL hiện tại!')
  }

  const handleCopyCode = (e: React.MouseEvent, code: string) => {
    e.stopPropagation()
    navigator.clipboard.writeText(code)
    setCopiedTicketCode(code)
    toast.success(`Đã sao chép mã ticket [${code}]`)
    setTimeout(() => {
      setCopiedTicketCode((prev) => (prev === code ? null : prev))
    }, 2000)
  }

  // Filtered tickets in My Tickets tab
  const filteredTickets = useMemo(() => {
    const items = myTicketsQuery.data?.items || []
    return items.filter((ticket) => {
      if (ticketSearch.trim()) {
        const query = ticketSearch.toLowerCase()
        const matchCode = ticket.ticket_code?.toLowerCase().includes(query)
        const matchTitle = ticket.title?.toLowerCase().includes(query)
        const matchDesc = ticket.description?.toLowerCase().includes(query)
        if (!matchCode && !matchTitle && !matchDesc) return false
      }
      if (statusFilter !== 'all' && ticket.status !== statusFilter) {
        return false
      }
      if (categoryFilter !== 'all' && ticket.category !== categoryFilter) {
        return false
      }
      return true
    })
  }, [myTicketsQuery.data?.items, ticketSearch, statusFilter, categoryFilter])

  return (
    <Page className="max-w-4xl mx-auto space-y-6 py-4 pb-20">
      {/* Hero Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="px-3 py-1 text-xs font-semibold rounded-full bg-card border-border/80 text-foreground"
          >
            Hỗ trợ & Tiếp nhận phản hồi
          </Badge>
        </div>

        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground flex items-center gap-2.5">
          <MessageSquareHeart className="size-7 text-primary shrink-0" />
          <span>Góp ý & Báo lỗi Hệ thống</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-2xl">
          Gửi báo cáo lỗi, đề xuất tính năng mới hoặc đóng góp ý kiến giao diện để đội ngũ Flama cải thiện hệ thống.
        </p>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center justify-between border-b pb-3">
        <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as any)}>
          <TabsList className="bg-card p-1 rounded-full border border-border/80 shadow-2xs">
            <TabsTrigger
              value="create"
              className="rounded-full text-xs font-bold gap-2 px-5 py-2 transition-all data-[state=active]:!bg-orange-500 data-[state=active]:!text-white data-[state=active]:!border-transparent data-[state=active]:shadow-sm hover:text-foreground cursor-pointer"
            >
              <Plus className="size-3.5" /> Gửi phản hồi mới
            </TabsTrigger>

            <TabsTrigger
              value="my-tickets"
              className="rounded-full text-xs font-bold gap-2 px-5 py-2 transition-all data-[state=active]:!bg-orange-500 data-[state=active]:!text-white data-[state=active]:!border-transparent data-[state=active]:shadow-sm hover:text-foreground cursor-pointer"
            >
              <Ticket className="size-3.5" /> Ticket của tôi
              {myTicketsQuery.data?.items && myTicketsQuery.data.items.length > 0 && (
                <span
                  className={`ml-1 px-1.5 py-0.5 text-[10px] font-bold rounded-full transition-colors ${
                    activeTab === 'my-tickets'
                      ? 'bg-white/25 text-white'
                      : 'bg-orange-500/15 text-orange-600 dark:text-orange-400'
                  }`}
                >
                  {myTicketsQuery.data.items.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Tab Content 1: Create Ticket */}
      {activeTab === 'create' && (
        <form onSubmit={handleSubmitTicket} className="space-y-6">
          {/* 1. Compact Category Selection Grid */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs sm:text-sm font-bold text-foreground flex items-center gap-1.5">
                <span className="flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-xs font-bold">1</span>
                <span>Chủ đề phản hồi</span>
              </Label>
              <span className="text-[11px] text-muted-foreground">Chọn 1 chủ đề</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {CATEGORIES.map((cat) => {
                const IconComp = cat.icon
                const isSelected = category === cat.key

                return (
                  <button
                    key={cat.key}
                    type="button"
                    onClick={() => setCategory(cat.key)}
                    className={`flex items-center gap-2.5 p-3 rounded-xl border text-left transition-all cursor-pointer select-none ${
                      isSelected
                        ? `${cat.activeBorder} ${cat.activeBg} shadow-xs font-bold`
                        : 'bg-card border-border/80 text-foreground hover:bg-muted/40 hover:border-border font-medium shadow-2xs'
                    }`}
                  >
                    <div className={`p-1.5 rounded-lg shrink-0 ${isSelected ? 'bg-background/80' : 'bg-muted/50'}`}>
                      <IconComp className={`size-4 ${cat.color}`} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-bold truncate text-foreground">{cat.title}</div>
                      <div className="text-[10px] text-muted-foreground truncate hidden sm:block">{cat.subtitle}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* 2. Screen URL Auto Detection */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs sm:text-sm font-bold text-foreground flex items-center gap-1.5">
                <span className="flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-xs font-bold">2</span>
                <LinkIcon className="size-3.5 text-primary" />
                <span>Màn hình xảy ra vấn đề (URL)</span>
              </Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={fillCurrentUrl}
                className="rounded-full text-xs h-7 gap-1 px-3 bg-card border-border/80 hover:bg-muted font-medium"
              >
                <RefreshCw className="size-3 text-primary" /> Lấy URL hiện tại
              </Button>
            </div>

            <div className="space-y-2">
              <Input
                placeholder="Dán URL màn hình (Ví dụ: http://localhost:5173/study)"
                value={urlPath}
                onChange={(e) => setUrlPath(e.target.value)}
                className="bg-card border-border/80 font-mono text-xs h-10 shadow-2xs rounded-xl text-foreground"
              />

              {/* Quick Pick Presets */}
              <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                <span className="text-[11px] text-muted-foreground mr-1">Gợi ý nhanh:</span>
                {COMMON_SCREEN_PRESETS.map((preset) => (
                  <button
                    key={preset.url}
                    type="button"
                    onClick={() => setUrlPath(preset.url)}
                    className="text-[11px] px-2.5 py-1 rounded-lg border border-border/80 bg-card hover:bg-muted text-foreground font-medium transition-colors cursor-pointer shadow-2xs"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>

              {/* Recognized Screen Info Banner */}
              <div className="text-xs text-muted-foreground flex items-center gap-2 bg-card p-3 rounded-xl border border-border/80 shadow-2xs">
                <Info className="size-4 text-primary shrink-0" />
                <span>
                  Tên màn hình nhận diện:{' '}
                  <strong className="text-foreground font-semibold">
                    {resolvedScreenName}
                  </strong>
                </span>
              </div>
            </div>
          </div>

          {/* 3. Title & Description */}
          <div className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs sm:text-sm font-bold text-foreground flex items-center gap-1.5">
                  <span className="flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-xs font-bold">3</span>
                  <span>Tiêu đề tóm tắt</span>
                </Label>
                <span className="text-[11px] text-muted-foreground">Tùy chọn</span>
              </div>
              <Input
                placeholder={activeCategoryConfig.placeholderTitle}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                className="bg-card border-border/80 text-xs sm:text-sm h-10 shadow-2xs rounded-xl text-foreground"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs sm:text-sm font-bold text-foreground flex items-center gap-1.5">
                  <span className="flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-xs font-bold">4</span>
                  <span>Nội dung chi tiết <strong className="text-rose-500">*</strong></span>
                </Label>
                <span className="text-[11px] text-muted-foreground font-mono">
                  {description.length}/2000 ký tự
                </span>
              </div>
              <Textarea
                placeholder={activeCategoryConfig.placeholderDesc}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={2000}
                className="bg-card border-border/80 min-h-32 rounded-xl text-xs sm:text-sm leading-relaxed p-3.5 shadow-2xs text-foreground"
                required
              />
            </div>

            {/* Reproduce steps (Specific to Bug category) */}
            {category === 'bug' && (
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <span>Các bước tái hiện lỗi</span>
                  </Label>
                  <span className="text-[11px] text-muted-foreground">Tùy chọn</span>
                </div>
                <Textarea
                  placeholder="1. Mở trang Duyệt từ vựng&#10;2. Chọn bộ thẻ N3&#10;3. Bấm nút Bắt đầu học và nút không phản hồi..."
                  value={reproduceSteps}
                  onChange={(e) => setReproduceSteps(e.target.value)}
                  className="bg-card border-border/80 min-h-24 rounded-xl text-xs font-mono p-3 leading-relaxed shadow-2xs text-foreground"
                />
              </div>
            )}
          </div>

          {/* 4. Screenshot Uploader & Drag-and-Drop */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs sm:text-sm font-bold text-foreground flex items-center gap-1.5">
                <span className="flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-xs font-bold">
                  {category === 'bug' ? '5' : '5'}
                </span>
                <ImageIcon className="size-4 text-primary" />
                <span>Ảnh chụp màn hình ({attachedUrls.length}/5 ảnh)</span>
              </Label>
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-card rounded border border-border/80">Ctrl</kbd>
                <span>+</span>
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-card rounded border border-border/80">V</kbd>
                <span>để dán ảnh</span>
              </span>
            </div>

            {/* Dropzone & Preview Grid */}
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                {/* Uploaded Thumbnails */}
                {attachedUrls.map((url, idx) => (
                  <div
                    key={idx}
                    className="relative group size-20 rounded-xl border border-border/80 overflow-hidden shadow-2xs bg-card transition-all hover:ring-2 hover:ring-primary/60"
                  >
                    <img src={url} alt={`Screenshot ${idx + 1}`} className="size-full object-cover" />
                    
                    {/* Action Overlay */}
                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                      <button
                        type="button"
                        onClick={() => setPreviewImage(url)}
                        className="p-1 rounded-full bg-white/20 hover:bg-white/40 text-white transition-colors cursor-pointer"
                        title="Xem ảnh lớn"
                      >
                        <Eye className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setAttachedUrls((prev) => prev.filter((_, i) => i !== idx))}
                        className="p-1 rounded-full bg-rose-600/80 hover:bg-rose-600 text-white transition-colors cursor-pointer"
                        title="Xóa ảnh"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </div>
                ))}

                {/* Upload Action Tile */}
                {attachedUrls.length < 5 && (
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`flex flex-col items-center justify-center size-20 rounded-xl border-2 border-dashed transition-all cursor-pointer select-none ${
                      isDragging
                        ? 'border-primary bg-primary/10 scale-105'
                        : 'border-border/80 hover:border-primary bg-card hover:bg-muted/40 shadow-2xs'
                    }`}
                  >
                    {isUploading ? (
                      <Loader2 className="size-5 animate-spin text-primary" />
                    ) : (
                      <>
                        <Upload className="size-4 text-muted-foreground mb-1" />
                        <span className="text-[10px] text-muted-foreground font-semibold">Tải ảnh</span>
                      </>
                    )}
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={handleFileChange}
                      className="hidden"
                      disabled={isUploading}
                    />
                  </div>
                )}
              </div>

              <p className="text-[11px] text-muted-foreground">
                Hỗ trợ PNG, JPG, WEBP (tối đa 2MB). Bạn có thể chụp màn hình và bấm <strong>Ctrl+V</strong> để dán trực tiếp.
              </p>
            </div>
          </div>

          {/* Submit Action */}
          <div className="pt-4 border-t flex flex-wrap items-center justify-between gap-4">
            <div className="text-xs text-muted-foreground flex items-center gap-1.5">
              <CheckCircle2 className="size-4 text-emerald-600" />
              <span>Ticket sẽ được gửi trực tiếp tới đội ngũ phát triển</span>
            </div>

            <Button
              type="submit"
              size="lg"
              className="rounded-full px-8 font-bold shadow-md gap-2 text-sm"
              disabled={createTicketMutation.isPending || isUploading || !description.trim()}
            >
              {createTicketMutation.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" /> Đang gửi Ticket...
                </>
              ) : (
                <>
                  <Send className="size-4" /> Gửi phản hồi ngay
                </>
              )}
            </Button>
          </div>
        </form>
      )}

      {/* Tab Content 2: My Tickets */}
      {activeTab === 'my-tickets' && (
        <div className="space-y-4">
          {/* Search & Filter Bar */}
          <Card className="shadow-2xs border-border/80 bg-card rounded-xl">
            <CardContent className="p-3.5 flex flex-wrap items-center gap-3">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
                <Input
                  placeholder="Tìm mã ticket, tiêu đề, nội dung..."
                  value={ticketSearch}
                  onChange={(e) => setTicketSearch(e.target.value)}
                  className="pl-9 bg-card border-border/80 rounded-xl text-xs h-9 shadow-2xs text-foreground"
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <NativeSelect
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-36 rounded-xl text-xs h-9 bg-card border-border/80 text-foreground shadow-2xs"
                >
                  <NativeSelectOption value="all">Tất cả Trạng thái</NativeSelectOption>
                  <NativeSelectOption value="open">Chờ xử lý</NativeSelectOption>
                  <NativeSelectOption value="in_progress">Đang xử lý</NativeSelectOption>
                  <NativeSelectOption value="resolved">Đã giải quyết</NativeSelectOption>
                  <NativeSelectOption value="closed">Đã đóng</NativeSelectOption>
                  <NativeSelectOption value="rejected">Từ chối</NativeSelectOption>
                </NativeSelect>

                <NativeSelect
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="w-36 rounded-xl text-xs h-9 bg-card border-border/80 text-foreground shadow-2xs"
                >
                  <NativeSelectOption value="all">Tất cả Chủ đề</NativeSelectOption>
                  <NativeSelectOption value="bug">Báo lỗi (Bug)</NativeSelectOption>
                  <NativeSelectOption value="feature">Ý tưởng mới</NativeSelectOption>
                  <NativeSelectOption value="ui">Giao diện (UI)</NativeSelectOption>
                  <NativeSelectOption value="other">Khác</NativeSelectOption>
                </NativeSelect>

                {(ticketSearch || statusFilter !== 'all' || categoryFilter !== 'all') && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setTicketSearch('')
                      setStatusFilter('all')
                      setCategoryFilter('all')
                    }}
                    className="text-xs text-muted-foreground h-9 px-3"
                  >
                    Xóa bộ lọc
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* List or Loading / Empty */}
          {myTicketsQuery.isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((n) => (
                <Card key={n} className="p-4 border-border/80 bg-card rounded-xl shadow-2xs">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Skeleton className="h-5 w-24 rounded-full" />
                      <Skeleton className="h-5 w-48 rounded-lg" />
                    </div>
                    <Skeleton className="h-4 w-full rounded-md" />
                    <div className="flex gap-3 pt-1">
                      <Skeleton className="h-4 w-32 rounded-md" />
                      <Skeleton className="h-4 w-24 rounded-md" />
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : !myTicketsQuery.data?.items || myTicketsQuery.data.items.length === 0 ? (
            <EmptyState
              title="Bạn chưa gửi ticket nào"
              description="Hãy dùng form 'Gửi phản hồi mới' để gửi thông tin cho đội ngũ phát triển khi gặp bất kỳ sự cố hay có ý tưởng mới."
              action={
                <Button size="sm" onClick={() => setActiveTab('create')} className="rounded-full font-bold px-6">
                  <Plus className="mr-1.5 size-4" /> Tạo ticket đầu tiên
                </Button>
              }
            />
          ) : filteredTickets.length === 0 ? (
            <EmptyState
              title="Không tìm thấy ticket phù hợp"
              description="Không có báo cáo nào trùng khớp với bộ lọc tìm kiếm hiện tại của bạn."
              action={
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setTicketSearch('')
                    setStatusFilter('all')
                    setCategoryFilter('all')
                  }}
                  className="rounded-full text-xs"
                >
                  Xóa bộ lọc tìm kiếm
                </Button>
              }
            />
          ) : (
            <div className="space-y-3">
              {filteredTickets.map((t) => {
                const statusInfo = STATUS_MAP[t.status] || STATUS_MAP.open
                const StatusIcon = statusInfo.icon
                const catCfg = CATEGORIES.find((c) => c.key === t.category) || CATEGORIES[3]
                const CatIcon = catCfg.icon
                const isCopied = copiedTicketCode === t.ticket_code

                return (
                  <Card
                    key={t.id}
                    className="shadow-2xs hover:shadow-md hover:border-primary/60 transition-all cursor-pointer border-border/80 bg-card rounded-xl group"
                    onClick={() => navigate(`/tickets/${t.id}`)}
                  >
                    <CardContent className="p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4">
                      <div className="space-y-2 max-w-xl">
                        <div className="flex flex-wrap items-center gap-2">
                          {/* Ticket Code with Copy Button */}
                          <div className="flex items-center gap-1 font-mono font-bold text-xs px-2.5 py-0.5 bg-primary/10 text-primary rounded-full">
                            <span>{t.ticket_code}</span>
                            <button
                              type="button"
                              onClick={(e) => handleCopyCode(e, t.ticket_code)}
                              className="p-0.5 hover:bg-primary/20 rounded text-primary transition-colors cursor-pointer"
                              title="Sao chép mã ticket"
                            >
                              {isCopied ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
                            </button>
                          </div>

                          {/* Category Badge */}
                          <Badge variant="outline" className="px-2 py-0.5 text-[11px] gap-1 font-medium rounded-full bg-card border-border/80 text-foreground">
                            <CatIcon className={`size-3 ${catCfg.color}`} /> {catCfg.title}
                          </Badge>

                          {/* Replies Count Badge */}
                          {t.replies_count && t.replies_count > 0 ? (
                            <Badge className="px-2 py-0.5 text-[10px] gap-1 rounded-full bg-blue-600 text-white font-bold">
                              <MessageSquare className="size-3" /> {t.replies_count} phản hồi
                            </Badge>
                          ) : null}
                        </div>

                        {/* Title */}
                        <h3 className="font-bold text-sm sm:text-base text-foreground group-hover:text-primary transition-colors">
                          {t.title}
                        </h3>

                        {/* Description snippet */}
                        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                          {t.description}
                        </p>

                        {/* Metadata Row */}
                        <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground pt-0.5">
                          {t.screen_name && (
                            <span className="flex items-center gap-1 font-medium text-foreground">
                              <ExternalLink className="size-3 text-primary" /> {t.screen_name}
                            </span>
                          )}
                          <span>•</span>
                          <span title={new Date(t.created_at).toLocaleString('vi-VN')}>
                            Gửi {formatRelativeTime(t.created_at)}
                          </span>
                          {t.attachment_urls && t.attachment_urls.length > 0 && (
                            <>
                              <span>•</span>
                              <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400 font-medium">
                                <ImageIcon className="size-3" /> {t.attachment_urls.length} ảnh
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Right Status & Action */}
                      <div className="flex items-center gap-3">
                        <Badge className={`px-3 py-1 text-xs gap-1.5 rounded-full font-semibold ${statusInfo.badge}`}>
                          <StatusIcon className="size-3.5" /> {statusInfo.label}
                        </Badge>
                        <Button size="sm" variant="ghost" className="rounded-full px-3 text-xs gap-1 group-hover:bg-primary group-hover:text-primary-foreground transition-all">
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

      {/* Lightbox Image Preview Modal */}
      <Dialog open={Boolean(previewImage)} onOpenChange={(open) => !open && setPreviewImage(null)}>
        <DialogContent className="max-w-4xl sm:max-w-4xl p-2 bg-black/95 border-none flex flex-col items-center justify-center">
          {previewImage && (
            <img src={previewImage} alt="Screenshot Preview" className="max-h-[85vh] object-contain rounded-xl" />
          )}
        </DialogContent>
      </Dialog>
    </Page>
  )
}
