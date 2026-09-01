import { useState } from 'react'
import {
  AudioLines,
  Check,
  Copy,
  ExternalLink,
  HelpCircle,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'

export function TtsKeyGuidePage() {
  const [copiedKeyUrl, setCopiedKeyUrl] = useState(false)

  const voicevoxApiUrl = 'https://su-shiki.com/api/'

  const handleCopyUrl = (url: string) => {
    void navigator.clipboard.writeText(url)
    setCopiedKeyUrl(true)
    toast.success('Đã sao chép đường dẫn lấy API Key!')
    setTimeout(() => setCopiedKeyUrl(false), 2000)
  }

  return (
    <Page className="max-w-5xl space-y-8">
      <PageHeader
        title="Hướng dẫn lấy API Key tạo âm thanh (TTS)"
        description="Chi tiết các bước đăng ký và lấy API Key cho VoiceVox, OpenAI, Google TTS và ElevenLabs để tạo phát âm chuẩn cho từ vựng và flashcard trên Flama."
        actions={
          <Button asChild variant="outline" className="gap-2">
            <Link to="/browse">
              <AudioLines className="size-4 text-primary" />
              <span>Đến trang Duyệt thẻ</span>
            </Link>
          </Button>
        }
      />

      {/* Overview Alert */}
      <Alert className="border-border/80 bg-muted/30">
        <AudioLines className="size-5 text-foreground/80" />
        <AlertTitle className="text-base font-bold text-foreground">
          Tại sao bạn nên dùng API Key cá nhân?
        </AlertTitle>
        <AlertDescription className="mt-1 text-xs text-muted-foreground leading-relaxed">
          Flama hỗ trợ kết nối trực tiếp các công cụ tổng hợp giọng nói (Text-to-Speech) nổi tiếng.
          Sử dụng API Key cá nhân giúp quá trình tạo audio diễn ra <strong>nhanh chóng</strong>,{' '}
          <strong>không bị giới hạn băng thông chung</strong> và đảm bảo bạn toàn quyền quản lý chất lượng giọng đọc.
        </AlertDescription>
      </Alert>

      {/* Main Guide Step: VoiceVox (Default & Primary) */}
      <Card className="border-2 border-primary/30 shadow-md">
        <CardHeader className="bg-gradient-to-r from-primary/10 via-amber-500/10 to-transparent pb-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground font-black text-lg shadow-sm">
                1
              </div>
              <div>
                <CardTitle className="text-xl font-bold flex items-center gap-2">
                  <span>VoiceVox (TTS Quest API)</span>
                  <Badge variant="default" className="bg-primary text-primary-foreground text-[10px]">
                    Miễn phí & Mặc định
                  </Badge>
                </CardTitle>
                <CardDescription className="text-xs">
                  Giọng đọc tiếng Nhật tự nhiên chuẩn như người bản xứ (Shikikoin Metan, Kasukabe Tsumugi, Namine Ritsu...)
                </CardDescription>
              </div>
            </div>
            <a
              href={voicevoxApiUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground shadow-xs transition hover:opacity-90"
            >
              <span>Mở trang lấy Key</span>
              <ExternalLink className="size-3.5" />
            </a>
          </div>
        </CardHeader>
        <CardContent className="space-y-6 pt-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-md bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary shrink-0">
                  Bước 1
                </span>
                <h4 className="font-semibold text-sm">Truy cập Su-Shiki API</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Nhấn vào liên kết bên dưới hoặc truy cập trực tiếp website cấp key miễn phí:
              </p>
              <div className="flex items-center gap-1.5 pt-1">
                <code className="rounded bg-muted px-2 py-1 text-[11px] font-mono text-foreground truncate max-w-[200px]">
                  {voicevoxApiUrl}
                </code>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 shrink-0"
                  onClick={() => handleCopyUrl(voicevoxApiUrl)}
                  title="Sao chép liên kết"
                >
                  {copiedKeyUrl ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
                </Button>
              </div>
            </div>

            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-md bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary shrink-0">
                  Bước 2
                </span>
                <h4 className="font-semibold text-sm">Tạo &amp; Sao chép API Key</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Trên giao diện Su-Shiki, nhấn nút <strong>Generate Key</strong> (hoặc điền thông tin nếu có).
                Sau đó sao chép chuỗi mã API Key được cấp.
              </p>
            </div>

            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-md bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary shrink-0">
                  Bước 3
                </span>
                <h4 className="font-semibold text-sm">Dán vào Flama</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Mở ứng dụng Flama, vào màn hình <strong>Duyệt thẻ (Browse)</strong> &gt; Chọn thẻ &gt; Nhấn{' '}
                <strong>Tạo âm thanh VoiceVox (TTS)</strong> &gt; Dán Key vào ô <strong>VoiceVox API Key</strong>.
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-900 dark:text-amber-200 space-y-1">
            <div className="font-bold flex items-center gap-1.5">
              <Zap className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>Lưu ý về hạn ngạch điểm (Points) của VoiceVox:</span>
            </div>
            <p className="leading-relaxed">
              Mỗi lượt phát hoặc tạo file âm thanh VoiceVox sẽ tiêu tốn một số lượng điểm (Points) nhất định từ key của bạn.
              Nếu bạn hết điểm, bạn có thể chờ điểm tự phục hồi hoặc tạo một API key mới tại trang Su-Shiki API.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Additional Providers Grid */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
          <AudioLines className="size-5 text-primary" />
          <span>Các dịch vụ âm thanh AI khác</span>
        </h3>

        <div className="grid gap-6 md:grid-cols-3">
          {/* OpenAI TTS */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Badge variant="outline" className="text-[10px]">AI Voice</Badge>
                <a
                  href="https://platform.openai.com/api-keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline flex items-center gap-1 font-semibold"
                >
                  <span>Lấy key OpenAI</span>
                  <ExternalLink className="size-3" />
                </a>
              </div>
              <CardTitle className="text-base font-bold mt-2">OpenAI TTS</CardTitle>
              <CardDescription className="text-xs">
                Giọng đọc chuẩn AI chất lượng cao (Alloy, Echo, Fable, Onyx, Nova, Shimmer).
              </CardDescription>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 pt-0">
              <ol className="list-decimal pl-4 space-y-1.5">
                <li>Đăng nhập tài khoản tại <strong>platform.openai.com</strong>.</li>
                <li>Vào mục <strong>API Keys</strong> &gt; Chọn <strong>Create new secret key</strong>.</li>
                <li>Sao chép chuỗi Key bắt đầu bằng <code>sk-...</code> và lưu an toàn.</li>
              </ol>
            </CardContent>
          </Card>

          {/* ElevenLabs */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Badge variant="outline" className="text-[10px]">Realistic Voice</Badge>
                <a
                  href="https://elevenlabs.io"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline flex items-center gap-1 font-semibold"
                >
                  <span>Lấy key ElevenLabs</span>
                  <ExternalLink className="size-3" />
                </a>
              </div>
              <CardTitle className="text-base font-bold mt-2">ElevenLabs</CardTitle>
              <CardDescription className="text-xs">
                Giọng đọc AI cảm xúc nhất thế giới với khả năng tùy chỉnh ngữ điệu sâu.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 pt-0">
              <ol className="list-decimal pl-4 space-y-1.5">
                <li>Truy cập và đăng nhập vào <strong>elevenlabs.io</strong>.</li>
                <li>Nhấn vào ảnh hồ sơ của bạn ở góc dưới bên trái &gt; <strong>Profile + API Key</strong>.</li>
                <li>Nhấn biểu tượng mắt để xem và sao chép API Key cá nhân.</li>
              </ol>
            </CardContent>
          </Card>

          {/* Google Cloud / Gemini */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Badge variant="outline" className="text-[10px]">Google Speech</Badge>
                <a
                  href="https://aistudio.google.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline flex items-center gap-1 font-semibold"
                >
                  <span>Google AI Studio</span>
                  <ExternalLink className="size-3" />
                </a>
              </div>
              <CardTitle className="text-base font-bold mt-2">Google Cloud / Gemini</CardTitle>
              <CardDescription className="text-xs">
                Giọng đọc đa ngôn ngữ đa dạng và công cụ AI tổng hợp tiên tiến.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-2 pt-0">
              <ol className="list-decimal pl-4 space-y-1.5">
                <li>Truy cập <strong>aistudio.google.com</strong> hoặc Google Cloud Console.</li>
                <li>Nhấn <strong>Get API key</strong> &gt; Chọn <strong>Create API key</strong>.</li>
                <li>Sao chép mã Key và lưu lại để sử dụng.</li>
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Security & FAQ Section */}
      <Card className="bg-muted/30">
        <CardHeader>
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <ShieldCheck className="size-5 text-emerald-500" />
            <span>Câu hỏi thường gặp &amp; Bảo mật API Key</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-xs text-muted-foreground leading-relaxed">
          <div className="space-y-1">
            <h5 className="font-semibold text-foreground text-sm flex items-center gap-1.5">
              <HelpCircle className="size-4 text-primary shrink-0" />
              <span>API Key của tôi có được bảo mật trên Flama không?</span>
            </h5>
            <p className="pl-5">
              Có. Trên hệ thống Flama, mọi API Key do bạn cung cấp đều được mã hóa chuẩn quân sự (Fernet / AES-256)
              trước khi lưu trữ và chỉ được dùng để gửi yêu cầu phát âm theo đúng thao tác của bạn.
            </p>
          </div>

          <div className="space-y-1">
            <h5 className="font-semibold text-foreground text-sm flex items-center gap-1.5">
              <HelpCircle className="size-4 text-primary shrink-0" />
              <span>Tôi có bắt buộc phải nhập API Key không?</span>
            </h5>
            <p className="pl-5">
              Nếu bạn chỉ nghe âm thanh có sẵn trong bài học thì không cần.
              Tuy nhiên khi bạn muốn sử dụng tính năng <strong>Tạo âm thanh VoiceVox hàng loạt</strong> cho từ vựng riêng trong phần Duyệt thẻ,
              nhập API Key cá nhân sẽ giúp quá trình tạo audio diễn ra mượt mà và không gặp gián đoạn.
            </p>
          </div>
        </CardContent>
      </Card>
    </Page>
  )
}
