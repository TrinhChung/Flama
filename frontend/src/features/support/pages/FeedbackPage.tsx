import { useState } from 'react'
import {
  Bug,
  Check,
  Code2,
  Copy,
  Globe,
  Heart,
  Lightbulb,
  Link as LinkIcon,
  Mail,
  MessageSquareHeart,
  RefreshCw,
  Send,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Page } from '@/shared/components/Page'

type FeedbackCategory = 'bug' | 'feature' | 'ui' | 'other'

const CONTACT_EMAIL = 'chungtrinh2k2@gmail.com'

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

  // Exact or prefix match in ROUTE_NAME_MAP
  const lowerPath = pathname.toLowerCase()
  for (const [route, title] of Object.entries(ROUTE_NAME_MAP)) {
    if (lowerPath === route.toLowerCase() || lowerPath.startsWith(route.toLowerCase())) {
      return title
    }
  }

  // Clean fallback formatter: /settings/yomitan -> Settings > Yomitan
  const segments = pathname.replace(/^\/+|\/+$/g, '').split('/')
  if (!segments[0]) return 'Trang chủ (Dashboard)'

  return segments
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(' > ')
}

export function FeedbackPage() {
  const [copied, setCopied] = useState<string | null>(null)
  const [category, setCategory] = useState<FeedbackCategory>('bug')
  const [urlPath, setUrlPath] = useState(window.location.href)
  const [description, setDescription] = useState('')
  const [reproduceSteps, setReproduceSteps] = useState('')
  const [senderInfo, setSenderInfo] = useState('')

  const resolvedScreenName = resolveScreenName(urlPath)

  const copyEmail = async () => {
    await navigator.clipboard.writeText(CONTACT_EMAIL)
    setCopied('email')
    window.setTimeout(() => setCopied(null), 1800)
    toast.success('Đã sao chép email chungtrinh2k2@gmail.com!')
  }

  const fillCurrentUrl = () => {
    setUrlPath(window.location.href)
    toast.success('Đã lấy đường dẫn URL hiện tại!')
  }

  const categoryLabel = {
    bug: 'Báo lỗi hệ thống (Bug Report)',
    feature: 'Đề xuất Ý tưởng mới',
    ui: 'Góp ý Giao diện & Trải nghiệm',
    other: 'Ý kiến đóng góp khác',
  }[category]

  // Live generated formatted template text
  const generatedTemplateText = `=== PHẢN HỒI / BÁO LỖI ỨNG DỤNG FLAMA ===
• Chủ đề: ${categoryLabel}
• Tên màn hình (Tự động nhận diện): ${resolvedScreenName}
• Đường dẫn URL: ${urlPath.trim() || '(Chưa nhập)'}
• Người gửi: ${senderInfo.trim() || '(Khách vô danh)'}

[MÔ TẢ CHI TIẾT]
${description.trim() || '(Chưa nhập nội dung mô tả)'}

${reproduceSteps.trim() ? `[CÁC BƯỚC TÁI HIỆN LỖI]\n${reproduceSteps.trim()}\n` : ''}=========================================
Gửi tới: ${CONTACT_EMAIL}`

  const mailSubject = encodeURIComponent(
    `[Flama ${category.toUpperCase()}] ${resolvedScreenName !== '(Vui lòng nhập URL để tự động nhận diện)' ? `${resolvedScreenName} - ` : ''}${description.trim().slice(0, 40) || 'Góp ý ứng dụng'}`
  )
  const mailBody = encodeURIComponent(generatedTemplateText)
  const mailtoUrl = `mailto:${CONTACT_EMAIL}?subject=${mailSubject}&body=${mailBody}`

  const copyGeneratedContent = async () => {
    if (!description.trim() && !urlPath.trim()) {
      toast.error('Vui lòng nhập URL hoặc nội dung mô tả trước khi sao chép!')
      return
    }
    await navigator.clipboard.writeText(generatedTemplateText)
    setCopied('generated')
    window.setTimeout(() => setCopied(null), 1800)
    toast.success('Đã sao chép nội dung đã tạo vào bộ nhớ tạm!')
  }

  const resetForm = () => {
    setUrlPath(window.location.href)
    setDescription('')
    setReproduceSteps('')
    setSenderInfo('')
    toast.info('Đã xóa form về mặc định.')
  }

  return (
    <Page className="max-w-4xl mx-auto space-y-10 py-4 pb-16">
      {/* Seamless Hero Header */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="px-3 py-1 text-xs gap-1.5 font-medium rounded-full bg-primary/10 text-primary border-none">
            <Heart className="size-3.5 fill-current text-primary" /> Lắng nghe & Đồng hành
          </Badge>
        </div>

        <div className="space-y-2">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground flex items-center gap-3">
            <MessageSquareHeart className="size-9 text-primary shrink-0" />
            <span>Góp ý & Báo lỗi</span>
          </h1>
          <p className="text-base text-muted-foreground leading-relaxed max-w-2xl">
            Chỉ cần dán đường dẫn URL, hệ thống sẽ tự động nhận diện tên màn hình và tạo nội dung báo cáo chuẩn để bạn gửi về{' '}
            <button
              onClick={copyEmail}
              className="inline-flex items-center gap-1 font-semibold font-mono text-primary hover:underline cursor-pointer"
              title="Nhấp để sao chép email"
            >
              <Mail className="size-3.5" />
              {CONTACT_EMAIL}
            </button>.
          </p>
        </div>

        {/* Quick Email Action Bar */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          <div className="flex items-center gap-2 px-4 py-2 rounded-full border bg-muted/40 text-sm font-mono font-medium">
            <Mail className="size-4 text-muted-foreground" />
            <span>{CONTACT_EMAIL}</span>
          </div>
          <Button size="sm" variant="outline" className="rounded-full px-4" onClick={copyEmail}>
            {copied === 'email' ? <Check className="mr-1.5 size-3.5 text-green-600" /> : <Copy className="mr-1.5 size-3.5" />}
            {copied === 'email' ? 'Đã chép' : 'Sao chép Email'}
          </Button>
          <a href={mailtoUrl} target="_blank" rel="noreferrer">
            <Button size="sm" className="rounded-full px-4 font-semibold shadow-xs">
              <Send className="mr-1.5 size-3.5" /> Mở Mail gửi ngay
            </Button>
          </a>
        </div>
      </div>

      <hr className="border-border/60" />

      {/* Seamless Box-Free Form */}
      <div className="space-y-6">
        {/* Category Pills */}
        <div className="space-y-3">
          <Label className="text-sm font-semibold text-foreground">1. Chọn chủ đề</Label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setCategory('bug')}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                category === 'bug'
                  ? 'bg-red-500 text-white shadow-xs'
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
                  ? 'bg-amber-500 text-white shadow-xs'
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
                  ? 'bg-sky-500 text-white shadow-xs'
                  : 'bg-muted/60 hover:bg-muted text-muted-foreground'
              }`}
            >
              <Sparkles className="size-4" /> Giao diện (UI/UX)
            </button>

            <button
              type="button"
              onClick={() => setCategory('other')}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                category === 'other'
                  ? 'bg-purple-500 text-white shadow-xs'
                  : 'bg-muted/60 hover:bg-muted text-muted-foreground'
              }`}
            >
              <Heart className="size-4" /> Khác
            </button>
          </div>
        </div>

        {/* URL Input with Auto-Detected Screen Name Badge */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="url-path" className="text-sm font-semibold flex items-center gap-1.5">
              <Globe className="size-4 text-primary" /> 2. Đường dẫn URL
            </Label>
            <button
              type="button"
              onClick={fillCurrentUrl}
              className="text-xs text-primary hover:underline font-medium flex items-center gap-1 cursor-pointer"
            >
              <LinkIcon className="size-3.5" /> Lấy URL hiện tại
            </button>
          </div>
          <Input
            id="url-path"
            placeholder="Dán URL trang bị lỗi (ví dụ: http://localhost:4789/settings/yomitan)..."
            value={urlPath}
            onChange={(e) => setUrlPath(e.target.value)}
            className="h-11 rounded-xl bg-background border-border/80 font-mono text-xs"
          />

          {/* Display Auto-Resolved Screen Name Badge */}
          <div className="flex items-center gap-2 pt-1 text-xs text-muted-foreground">
            <span>Tên màn hình tự động nhận diện:</span>
            <Badge variant="outline" className="text-xs font-semibold text-primary border-primary/30 bg-primary/5">
              {resolvedScreenName}
            </Badge>
          </div>
        </div>

        {/* Description */}
        <div className="space-y-2">
          <Label htmlFor="bug-description" className="text-sm font-semibold text-foreground">
            3. Mô tả chi tiết lỗi / ý tưởng
          </Label>
          <Textarea
            id="bug-description"
            rows={4}
            placeholder="Chia sẻ suy nghĩ, mô tả lỗi hoặc chi tiết ý tưởng của bạn tại đây..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="rounded-xl bg-background border-border/80 leading-relaxed resize-y"
          />
        </div>

        {/* Reproduce Steps */}
        <div className="space-y-2">
          <Label htmlFor="reproduce-steps" className="text-sm font-semibold text-muted-foreground">
            4. Các bước tái hiện lỗi (Tùy chọn)
          </Label>
          <Textarea
            id="reproduce-steps"
            rows={2}
            placeholder="Bước 1: Mở trang x... Bước 2: Bấm vào nút y..."
            value={reproduceSteps}
            onChange={(e) => setReproduceSteps(e.target.value)}
            className="rounded-xl bg-background border-border/80 leading-relaxed text-xs"
          />
        </div>

        {/* Sender Info */}
        <div className="space-y-2">
          <Label htmlFor="sender-info" className="text-sm font-semibold text-muted-foreground">
            5. Tên hoặc email của bạn (Tùy chọn)
          </Label>
          <Input
            id="sender-info"
            placeholder="Tên của bạn hoặc thông tin liên hệ..."
            value={senderInfo}
            onChange={(e) => setSenderInfo(e.target.value)}
            className="h-11 rounded-xl bg-background border-border/80"
          />
        </div>

        <div className="flex justify-end pt-1">
          <Button type="button" variant="ghost" size="sm" onClick={resetForm} className="text-xs text-muted-foreground">
            <RefreshCw className="mr-1.5 size-3.5" /> Làm mới form
          </Button>
        </div>
      </div>

      <hr className="border-border/60" />

      {/* Live Generated Content Area */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label className="text-base font-bold flex items-center gap-2">
            <Code2 className="size-5 text-primary" /> Nội dung tạo tự động để sao chép
          </Label>
          <Badge variant="outline" className="text-xs text-muted-foreground">
            Tự động cập nhật
          </Badge>
        </div>

        <pre className="text-xs sm:text-sm font-mono whitespace-pre-wrap leading-relaxed break-all bg-muted/40 p-4 sm:p-5 rounded-2xl border border-border/80 max-h-[320px] overflow-y-auto text-foreground select-all">
          {generatedTemplateText}
        </pre>

        <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
          <Button type="button" variant="outline" className="rounded-full px-5 font-medium" onClick={copyGeneratedContent}>
            {copied === 'generated' ? <Check className="mr-2 size-4 text-green-600" /> : <Copy className="mr-2 size-4" />}
            {copied === 'generated' ? 'Đã sao chép nội dung!' : 'Sao chép nội dung này'}
          </Button>

          <a href={mailtoUrl} target="_blank" rel="noreferrer">
            <Button type="button" size="lg" className="rounded-full px-6 font-bold shadow-xs">
              <Send className="mr-2 size-4" /> Mở Mail gửi ngay
            </Button>
          </a>
        </div>
      </div>

      <hr className="border-border/60" />

      {/* Appreciation Footer Note */}
      <div className="flex items-center gap-3 text-xs text-muted-foreground leading-relaxed">
        <Heart className="size-4 text-rose-500 shrink-0 fill-rose-500/20" />
        <span>
          Mọi đóng góp và phản hồi từ bạn gửi về <strong className="text-foreground font-mono">{CONTACT_EMAIL}</strong> đều được tác giả trân trọng sâu sắc. Chân thành cảm ơn sự đóng góp của bạn!
        </span>
      </div>
    </Page>
  )
}
