import { useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowRight,
  faArrowUpRightFromSquare,
  faBolt,
  faCircleCheck,
  faCircleQuestion,
  faCircleXmark,
  faDesktop,
  faDownload,
  faRotateRight,
  faShieldHalved,
  faSliders,
  faTriangleExclamation,
  faVolumeHigh,
} from '@fortawesome/free-solid-svg-icons'
import { LoaderCircle } from 'lucide-react'
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
  const checksumUrl = resolveBackendUrl('/api/download/flama-audio.sha256')

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
    <Page className="max-w-5xl space-y-7">
      <PageHeader
        title="Hướng dẫn sử dụng & Tải Flama Audio Desktop"
        description="Ứng dụng Windows Desktop cung cấp dịch vụ tổng hợp phát âm (VOICEVOX & Kokoro Engine) chạy cục bộ không giới hạn cho Flama."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button asChild variant="default" size="sm" className="gap-2 font-bold rounded-xl shadow-xs">
              <a href={downloadUrl} target="_blank" rel="noopener noreferrer" download>
                <FontAwesomeIcon icon={faDownload} className="text-xs" />
                <span>Tải Flama Audio (FlamaAudio-Portable.exe)</span>
              </a>
            </Button>
            <Button asChild variant="outline" size="sm" className="gap-2 font-semibold rounded-xl">
              <a href={checksumUrl} target="_blank" rel="noopener noreferrer" download>
                <FontAwesomeIcon icon={faShieldHalved} className="text-xs" />
                <span>SHA-256</span>
              </a>
            </Button>
          </div>
        }
      />

      {/* Download Warning Alert */}
      <div className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-900 dark:text-amber-200">
        <FontAwesomeIcon icon={faTriangleExclamation} className="size-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div className="space-y-1 text-xs leading-relaxed">
          <h4 className="font-bold text-sm text-amber-800 dark:text-amber-300">
            Lưu ý khi tải xuống trên Windows (Bỏ qua cảnh báo SmartScreen)
          </h4>
          <p className="text-amber-800/90 dark:text-amber-200/90">
            Do tệp <code className="font-mono font-bold bg-amber-500/20 px-1 py-0.5 rounded">FlamaAudio-Portable.exe</code> tự biên dịch nội bộ, trình duyệt hoặc Windows SmartScreen có thể hiển thị cảnh báo bảo mật. Để mở tệp:
          </p>
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5 text-[11px] font-medium text-amber-900 dark:text-amber-100">
            <span className="px-2 py-0.5 rounded-md bg-amber-500/20">1. Bấm dấu ba chấm (...)</span>
            <span>&rarr;</span>
            <span className="px-2 py-0.5 rounded-md bg-amber-500/20">2. Chọn Giữ lại (Keep)</span>
            <span>&rarr;</span>
            <span className="px-2 py-0.5 rounded-md bg-amber-500/20">3. Bấm mở rộng cạnh nút Xóa</span>
            <span>&rarr;</span>
            <span className="px-2 py-0.5 rounded-md bg-amber-500/20">4. Chọn Vẫn giữ (Keep anyway)</span>
          </div>
        </div>
      </div>

      {/* Connection Test Banner */}
      <Card className="rounded-2xl border border-border/80 bg-card shadow-xs overflow-hidden">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-4 sm:p-5">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary shrink-0">
              <FontAwesomeIcon icon={faDesktop} className="text-base" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-sm sm:text-base text-foreground">
                  Trạng thái Flama Audio Service
                </h3>
                {serviceStatus === 'online' && (
                  <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30 text-[11px] font-semibold gap-1">
                    <FontAwesomeIcon icon={faCircleCheck} className="text-[10px]" />
                    Đã kết nối (127.0.0.1:4791)
                  </Badge>
                )}
                {serviceStatus === 'offline' && (
                  <Badge variant="outline" className="bg-rose-500/10 text-rose-600 border-rose-500/30 text-[11px] font-semibold gap-1">
                    <FontAwesomeIcon icon={faCircleXmark} className="text-[10px]" />
                    Chưa chạy (Offline)
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Cổng dịch vụ máy trạm: <code className="text-primary font-mono font-bold">127.0.0.1:4791</code>
              </p>
            </div>
          </div>

          <Button
            size="sm"
            variant="outline"
            onClick={handleCheckConnection}
            disabled={serviceStatus === 'checking'}
            className="gap-2 text-xs rounded-xl font-semibold shrink-0"
          >
            {serviceStatus === 'checking' ? (
              <LoaderCircle className="size-3.5 animate-spin text-primary" />
            ) : (
              <FontAwesomeIcon icon={faRotateRight} className="text-xs text-primary" />
            )}
            <span>Kiểm tra kết nối</span>
          </Button>
        </CardContent>
      </Card>

      {/* Feature Highlights Grid */}
      <div className="grid gap-4 sm:gap-5 md:grid-cols-3">
        <Card className="rounded-2xl border border-border/80 bg-card hover:border-primary/50 hover:shadow-md transition-all">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <div className="size-9 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center mb-2">
              <FontAwesomeIcon icon={faBolt} className="text-sm" />
            </div>
            <CardTitle className="text-sm sm:text-base font-bold text-foreground">Không giới hạn &amp; Miễn phí</CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              Tổng hợp âm thanh phát âm trực tiếp trên phần cứng PC mà không tốn chi phí API hay giới hạn băng thông.
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="rounded-2xl border border-border/80 bg-card hover:border-primary/50 hover:shadow-md transition-all">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <div className="size-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-2">
              <FontAwesomeIcon icon={faShieldHalved} className="text-sm" />
            </div>
            <CardTitle className="text-sm sm:text-base font-bold text-foreground">Ghép nối an toàn (PNA Token)</CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              Bảo mật Private Network Access với cơ chế phê duyệt Pair Code, bảo vệ thiết bị an toàn tuyệt đối.
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="rounded-2xl border border-border/80 bg-card hover:border-primary/50 hover:shadow-md transition-all">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <div className="size-9 rounded-xl bg-amber-500/10 text-amber-600 flex items-center justify-center mb-2">
              <FontAwesomeIcon icon={faSliders} className="text-sm" />
            </div>
            <CardTitle className="text-sm sm:text-base font-bold text-foreground">VOICEVOX &amp; Kokoro Offline</CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              Tích hợp sẵn bộ giọng đọc tiếng Nhật tự nhiên cùng mô hình Kokoro đa ngôn ngữ với bộ tinh chỉnh cao độ &amp; tốc độ.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>

      {/* Step by Step Setup Guide */}
      <Card className="rounded-2xl border border-border/80 bg-card shadow-xs overflow-hidden">
        <CardHeader className="bg-muted/30 p-4 sm:p-5 border-b border-border/70">
          <CardTitle className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
            <FontAwesomeIcon icon={faVolumeHigh} className="text-primary text-sm" />
            <span>Quy trình khởi chạy &amp; Sử dụng Flama Audio</span>
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            Chỉ mất chưa đầy 1 phút để thiết lập hệ thống phát âm local trên máy tính Windows.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 space-y-5">
          <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
            {/* Step 1 */}
            <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  1
                </span>
                <h4 className="font-bold text-xs sm:text-sm text-foreground">Tải &amp; Khởi chạy</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Tải <code className="text-foreground font-mono text-[11px] font-semibold">FlamaAudio-Portable.exe</code> và chạy trực tiếp, ứng dụng tự khởi tạo service ở cổng 4791.
              </p>
            </div>

            {/* Step 2 */}
            <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  2
                </span>
                <h4 className="font-bold text-xs sm:text-sm text-foreground">Yêu cầu ghép nối</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Vào <Link to="/audio/deck-generator" className="text-primary font-semibold hover:underline">Studio Tạo Âm</Link> hoặc trang <Link to="/browse" className="text-primary font-semibold hover:underline">Duyệt thẻ</Link>, bấm yêu cầu kết nối thiết bị.
              </p>
            </div>

            {/* Step 3 */}
            <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  3
                </span>
                <h4 className="font-bold text-xs sm:text-sm text-foreground">Phê duyệt trên App</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Cửa sổ Flama Audio Desktop hiển thị thông báo. Nhấn nút <strong>Đồng ý (Approve)</strong> để lưu token xác thực an toàn.
              </p>
            </div>

            {/* Step 4 */}
            <div className="rounded-xl border border-border/60 bg-muted/20 p-3.5 space-y-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  4
                </span>
                <h4 className="font-bold text-xs sm:text-sm text-foreground">Tạo âm thanh hàng loạt</h4>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Chọn giọng đọc nhân vật mong muốn, tùy chỉnh thông số và kích hoạt tạo phát âm tự động cho hàng nghìn thẻ.
              </p>
            </div>
          </div>

          {/* Action Navigation Banner */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3.5 rounded-2xl border border-primary/30 bg-primary/5 p-4 sm:p-5">
            <div className="space-y-0.5 text-center sm:text-left">
              <h4 className="font-bold text-sm text-foreground flex items-center justify-center sm:justify-start gap-2">
                <FontAwesomeIcon icon={faDesktop} className="text-primary text-xs" />
                <span>Trải nghiệm tạo phát âm từ vựng ngay bây giờ</span>
              </h4>
              <p className="text-xs text-muted-foreground">
                Tự động quét bộ thẻ và tạo hàng loạt âm thanh cho toàn bộ deck chỉ với 1 cú nhấp.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-center">
              <Button asChild size="sm" className="gap-2 font-bold rounded-xl shadow-xs">
                <Link to="/audio/deck-generator">
                  <span>Mở Studio Tạo Âm Deck</span>
                  <FontAwesomeIcon icon={faArrowRight} className="text-xs" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="sm" className="gap-1.5 font-semibold rounded-xl">
                <Link to="/browse">
                  <span>Duyệt thẻ</span>
                  <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="text-[10px] opacity-70" />
                </Link>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Troubleshooting & FAQ */}
      <Card className="rounded-2xl border border-border/80 bg-card shadow-xs overflow-hidden">
        <CardHeader className="bg-muted/30 p-4 sm:p-5 border-b border-border/70">
          <CardTitle className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
            <FontAwesomeIcon icon={faCircleQuestion} className="text-primary text-sm" />
            <span>Câu hỏi thường gặp &amp; Xử lý sự cố</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 space-y-4 text-xs text-muted-foreground leading-relaxed">
          <div className="space-y-1">
            <h5 className="font-bold text-foreground text-xs sm:text-sm flex items-center gap-2">
              <FontAwesomeIcon icon={faCircleCheck} className="text-emerald-500 text-xs shrink-0" />
              <span>Ứng dụng báo lỗi "Không thể kết nối Flama Audio Service (port 4791)"?</span>
            </h5>
            <p className="pl-5 text-muted-foreground">
              Hãy đảm bảo bạn đã mở ứng dụng <strong>Flama Audio Desktop</strong> (<code className="font-mono text-[11px] font-semibold text-foreground">FlamaAudio-Portable.exe</code>). Nếu bị Windows Firewall chặn, hãy chọn "Allow access" cho mạng Private.
            </p>
          </div>

          <div className="space-y-1">
            <h5 className="font-bold text-foreground text-xs sm:text-sm flex items-center gap-2">
              <FontAwesomeIcon icon={faCircleCheck} className="text-emerald-500 text-xs shrink-0" />
              <span>Cần cài đặt VOICEVOX Engine như thế nào?</span>
            </h5>
            <p className="pl-5 text-muted-foreground">
              Flama Audio Desktop đã tích hợp sẵn cơ chế tải và quản lý VOICEVOX Engine tự động. Bạn chỉ cần nhấn nút <strong>"Tải &amp; Cài Engine"</strong> trực tiếp ngay trên giao diện ứng dụng Desktop khi được nhắc.
            </p>
          </div>
        </CardContent>
      </Card>
    </Page>
  )
}

