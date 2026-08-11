import { useState } from 'react'
import {
  AlertCircle,
  AudioLines,
  Check,
  CheckCircle2,
  Download,
  ExternalLink,
  HelpCircle,
  RefreshCw,
  ShieldCheck,
  Sliders,
  Sparkles,
  Volume2,
  Zap,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import { resolveBackendUrl } from '@/config/env'
import { flamaAudioClient } from '@/lib/flamaAudioClient'

export function FlamaAudioGuidePage() {
  const [serviceStatus, setServiceStatus] = useState<'unchecked' | 'checking' | 'online' | 'offline'>('unchecked')
  const downloadUrl = resolveBackendUrl('/api/download/flama-audio')

  const handleCheckConnection = async () => {
    setServiceStatus('checking')
    try {
      await flamaAudioClient.getHealth()
      setServiceStatus('online')
      toast.success('Đã kết nối thành công với Flama Audio Desktop (127.0.0.1:4791)!')
    } catch {
      setServiceStatus('offline')
      toast.error('Chưa tìm thấy Flama Audio Desktop đang chạy tại port 4791.')
    }
  }

  return (
    <Page className="max-w-5xl space-y-8">
      <PageHeader
        title="Hướng dẫn sử dụng & Tải Flama Audio Desktop"
        description="Ứng dụng Windows Desktop cung cấp dịch vụ tổng hợp âm thanh giọng đọc tiếng Nhật (VOICEVOX Engine) chạy cục bộ không giới hạn cho Flama."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button asChild variant="default" size="sm" className="gap-2 font-semibold">
              <a href={downloadUrl} target="_blank" rel="noopener noreferrer" download>
                <Download className="size-4" />
                <span>Tải Flama Audio (FlamaAudio-Portable.exe)</span>
              </a>
            </Button>
          </div>
        }
      />

      {/* Connection Test Banner */}
      <Card className="border-2 border-primary/20 bg-muted/20">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary shrink-0">
              <Volume2 className="size-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
                Trạng thái Flama Audio Service trên máy bạn
                {serviceStatus === 'online' && (
                  <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30 text-[10px]">
                    <CheckCircle2 className="size-3 mr-1" /> Đã kết nối (Online)
                  </Badge>
                )}
                {serviceStatus === 'offline' && (
                  <Badge variant="destructive" className="text-[10px]">
                    <AlertCircle className="size-3 mr-1" /> Chưa chạy (Offline)
                  </Badge>
                )}
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Local Endpoint: <code className="text-primary font-mono font-semibold">http://127.0.0.1:4791</code>
              </p>
            </div>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={handleCheckConnection}
            disabled={serviceStatus === 'checking'}
            className="gap-2 text-xs"
          >
            {serviceStatus === 'checking' ? (
              <RefreshCw className="size-3.5 animate-spin" />
            ) : (
              <RefreshCw className="size-3.5" />
            )}
            <span>Kiểm tra kết nối</span>
          </Button>
        </CardContent>
      </Card>

      {/* Feature Highlights Grid */}
      <div className="grid gap-6 md:grid-cols-3">
        <Card className="hover:border-primary/40 transition-colors">
          <CardHeader className="pb-2">
            <div className="size-9 rounded-lg bg-emerald-500/10 text-emerald-600 flex items-center justify-center mb-2">
              <Zap className="size-5" />
            </div>
            <CardTitle className="text-base font-bold">Không Giới Hạn &amp; Miễn Phí</CardTitle>
            <CardDescription className="text-xs">
              Tạo âm thanh từ vựng trực tiếp trên phần cứng máy tính của bạn mà không tốn chi phí API hay giới hạn băng thông.
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="hover:border-primary/40 transition-colors">
          <CardHeader className="pb-2">
            <div className="size-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center mb-2">
              <ShieldCheck className="size-5" />
            </div>
            <CardTitle className="text-base font-bold">Ghép Nối An Toàn (PNA Token)</CardTitle>
            <CardDescription className="text-xs">
              Bảo mật Private Network Access với cơ chế Challenge-Response. Web app chỉ được phép giao tiếp khi bạn phê duyệt.
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="hover:border-primary/40 transition-colors">
          <CardHeader className="pb-2">
            <div className="size-9 rounded-lg bg-amber-500/10 text-amber-600 flex items-center justify-center mb-2">
              <Sliders className="size-5" />
            </div>
            <CardTitle className="text-base font-bold">Tùy Chỉnh Giọng Đọc Đa Dạng</CardTitle>
            <CardDescription className="text-xs">
              Tích hợp sẵn bộ giọng đọc VOICEVOX (Zundamon, Shikikoin Metan, Kasukabe Tsumugi...) với khả năng chỉnh Tốc độ, Ngữ điệu &amp; Pitch.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>

      {/* Step by Step Setup Guide */}
      <Card className="border-2 border-primary/30 shadow-md">
        <CardHeader className="bg-gradient-to-r from-primary/10 via-amber-500/10 to-transparent pb-4">
          <CardTitle className="text-xl font-bold flex items-center gap-2">
            <Sparkles className="size-5 text-primary" />
            <span>Các bước khởi chạy &amp; Ghép nối Flama Audio</span>
          </CardTitle>
          <CardDescription className="text-xs">
            Chỉ mất chưa đầy 1 phút để thiết lập hệ thống phát âm local trên máy tính Windows của bạn.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 pt-6">
          <div className="grid gap-4 md:grid-cols-4">
            {/* Step 1 */}
            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  1
                </span>
                <h4 className="font-semibold text-sm">Tải &amp; Khởi chạy</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Tải <code className="text-foreground font-mono">FlamaAudio-Portable.exe</code> và chạy trực tiếp, không cần cài đặt. Cửa sổ ứng dụng sẽ hiển thị trạng thái endpoint <code className="text-primary font-mono">127.0.0.1:4791</code>.
              </p>
            </div>

            {/* Step 2 */}
            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  2
                </span>
                <h4 className="font-semibold text-sm">Yêu cầu ghép nối</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Trên trang <Link to="/browse" className="text-primary font-semibold hover:underline">Duyệt thẻ (Browse)</Link>, chọn các thẻ từ vựng &gt; Bấm menu <strong>Tạo âm thanh &gt; VoiceVox Local</strong> &gt; Nhấn <strong>Yêu cầu ghép nối</strong>.
              </p>
            </div>

            {/* Step 3 */}
            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  3
                </span>
                <h4 className="font-semibold text-sm">Phê duyệt trên Desktop</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Ứng dụng <strong>Flama Audio Desktop</strong> sẽ tự động bật lên màn hình. Nhấn nút <strong>Phê duyệt (Approve)</strong> bên cạnh yêu cầu ghép nối của Web.
              </p>
            </div>

            {/* Step 4 */}
            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  4
                </span>
                <h4 className="font-semibold text-sm">Tạo âm thanh hàng loạt</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Giao diện Web sẽ tự động nhận giọng đọc. Lựa chọn nhân vật, điều chỉnh tốc độ/ngữ điệu và bấm <strong>Bắt đầu tạo audio hàng loạt</strong>!
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border bg-primary/5 p-4">
            <div className="space-y-1">
              <h4 className="font-bold text-sm text-foreground flex items-center gap-2">
                <AudioLines className="size-4 text-primary" />
                Sẵn sàng thử nghiệm tính năng phát âm local?
              </h4>
              <p className="text-xs text-muted-foreground">
                Mở trang Duyệt thẻ để trải nghiệm tạo phát âm từ vựng với tốc độ cực nhanh.
              </p>
            </div>
            <Button asChild className="gap-2">
              <Link to="/browse">
                <span>Đến trang Duyệt thẻ</span>
                <ExternalLink className="size-3.5" />
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Troubleshooting & FAQ */}
      <Card className="bg-muted/30">
        <CardHeader>
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <HelpCircle className="size-5 text-primary" />
            <span>Câu hỏi thường gặp &amp; Xử lý sự cố</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-xs text-muted-foreground leading-relaxed">
          <div className="space-y-1">
            <h5 className="font-semibold text-foreground text-sm flex items-center gap-1.5">
              <Check className="size-4 text-emerald-500 shrink-0" />
              <span>Ứng dụng báo lỗi "Không thể kết nối Flama Audio Service (port 4791)"?</span>
            </h5>
            <p className="pl-5">
              Hãy đảm bảo bạn đã mở ứng dụng <strong>Flama Audio Desktop</strong> (`Flama.Audio.App.exe`). Nếu ứng dụng bị chặn bởi Firewall, hãy cho phép phần mềm giao tiếp qua cổng Private Network.
            </p>
          </div>

          <div className="space-y-1">
            <h5 className="font-semibold text-foreground text-sm flex items-center gap-1.5">
              <Check className="size-4 text-emerald-500 shrink-0" />
              <span>Ứng dụng báo lỗi "VOICEVOX Engine chưa bật (port 50021)"?</span>
            </h5>
            <p className="pl-5">
              Bạn có thể nhấn nút <strong>"Tải &amp; Tự động cài VOICEVOX Engine"</strong> ngay trên cửa sổ ghép nối của Web. Flama Audio Desktop sẽ tự động tải gói Engine VOICEVOX chuẩn về máy của bạn mà không cần cài thủ công.
            </p>
          </div>
        </CardContent>
      </Card>
    </Page>
  )
}
