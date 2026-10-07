import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Check,
  CheckCircle2,
  Code,
  Copy,
  HelpCircle,
  Info,
  ShieldAlert,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function AnkiCorsGuideTab() {
  const { t } = useTranslation('import')
  const [copiedUrl, setCopiedUrl] = useState(false)
  const [copiedConfig, setCopiedConfig] = useState(false)

  const currentOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:5173'
  const recommendedCorsSetting = `"webCorsOriginList": [
    "http://localhost",
    "${currentOrigin}"
]`

  const handleCopyUrl = async () => {
    await navigator.clipboard.writeText(`"${currentOrigin}"`)
    setCopiedUrl(true)
    setTimeout(() => setCopiedUrl(false), 2000)
    toast.success(t('anki_sync.cors_guide.toast_copied_origin', {
      origin: currentOrigin,
      defaultValue: `Đã sao chép địa chỉ: "${currentOrigin}" (kèm dấu ngoặc kép)!`,
    }))
  }

  const handleCopyConfig = async () => {
    await navigator.clipboard.writeText(recommendedCorsSetting)
    setCopiedConfig(true)
    setTimeout(() => setCopiedConfig(false), 2000)
    toast.success(t('anki_sync.cors_guide.toast_copied_config', {
      defaultValue: 'Đã sao chép đoạn cấu hình mẫu vào bộ nhớ tạm!',
    }))
  }

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <Card className="border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-background to-primary/5 shadow-xs rounded-2xl overflow-hidden">
        <CardHeader className="p-4 sm:p-6 space-y-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="bg-amber-500 hover:bg-amber-600 text-white font-bold px-2.5 py-0.5 text-[11px] gap-1.5 shadow-2xs">
              <ShieldAlert className="size-3.5" /> Hướng dẫn quan trọng
            </Badge>
            <Badge variant="outline" className="text-[11px] border-amber-500/40 text-amber-700 dark:text-amber-300">
              Khắc phục lỗi không kết nối được Anki Desktop
            </Badge>
          </div>
          <CardTitle className="text-lg sm:text-xl font-bold tracking-tight flex items-center gap-2">
            <HelpCircle className="size-5 text-amber-500 shrink-0" />
            <span>Cách cho phép Flama kết nối với Anki Desktop của bạn</span>
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-3xl">
            Để đảm bảo an toàn cho máy tính, phần mềm Anki Desktop sẽ chặn các trang web lạ kết nối vào dữ liệu của bạn.
            Vì vậy, bạn cần thêm địa chỉ trang web hiện tại là{' '}
            <code className="font-mono text-foreground font-semibold bg-muted px-1.5 py-0.5 rounded">{currentOrigin}</code>{' '}
            vào danh sách cho phép của Anki theo hướng dẫn đơn giản dưới đây.
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Step-by-Step Guide Grid */}
      <div className="grid gap-6 md:grid-cols-3">
        {/* Step 1 */}
        <Card className="border-border/80 shadow-2xs rounded-2xl flex flex-col justify-between">
          <CardHeader className="p-5 pb-3 space-y-2">
            <div className="size-8 rounded-xl bg-primary/10 text-primary font-bold flex items-center justify-center text-sm shrink-0">
              1
            </div>
            <CardTitle className="text-base font-bold">Mở cài đặt Add-on trên Anki</CardTitle>
            <CardDescription className="text-xs leading-relaxed">
              Mở phần mềm <strong>Anki Desktop</strong> trên máy tính của bạn:
              <br />
              Vào menu <strong className="text-foreground">Tools (Công cụ)</strong> ở phía trên cùng &rarr; chọn <strong className="text-foreground">Add-ons</strong> (hoặc bấm tổ hợp phím <kbd className="px-1.5 py-0.5 bg-muted rounded font-mono text-[10px]">Ctrl + Shift + A</kbd>).
            </CardDescription>
          </CardHeader>
          <CardContent className="p-5 pt-0 text-xs text-muted-foreground space-y-2">
            <div className="p-3 rounded-xl bg-muted/40 border text-[11px] space-y-1">
              <div className="font-semibold text-foreground flex items-center gap-1.5">
                <Info className="size-3.5 text-sky-500 shrink-0" /> Chưa có AnkiConnect?
              </div>
              <p>
                Nếu chưa có add-on này, hãy bấm <strong>Get Add-ons...</strong> ở góc phải và nhập mã số: <code className="font-mono text-primary font-bold">2055492159</code> để cài đặt tự động.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Step 2 */}
        <Card className="border-border/80 shadow-2xs rounded-2xl flex flex-col justify-between">
          <CardHeader className="p-5 pb-3 space-y-2">
            <div className="size-8 rounded-xl bg-primary/10 text-primary font-bold flex items-center justify-center text-sm shrink-0">
              2
            </div>
            <CardTitle className="text-base font-bold">Thêm trang web vào cấu hình</CardTitle>
            <CardDescription className="text-xs leading-relaxed">
              Nhấp chuột chọn dòng <strong>AnkiConnect</strong> trong danh sách &rarr; Bấm nút <strong className="text-foreground">Config (Cấu hình)</strong> ở góc dưới bên phải.
              <br />
              Thêm địa chỉ trang web của chúng ta vào danh sách bên dưới.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-5 pt-0 space-y-2">
            <Button
              variant="default"
              size="sm"
              className="w-full text-xs font-semibold h-9 gap-1.5"
              onClick={handleCopyUrl}
            >
              {copiedUrl ? <Check className="size-3.5 text-emerald-300" /> : <Copy className="size-3.5" />}
              {copiedUrl ? 'Đã sao chép địa chỉ' : '1. Sao chép địa chỉ trang web'}
            </Button>
            <p className="text-[10px] text-muted-foreground text-center">
              Sao chép để tự dán vào cấu hình Anki của bạn.
            </p>
          </CardContent>
        </Card>

        {/* Step 3 */}
        <Card className="border-border/80 shadow-2xs rounded-2xl flex flex-col justify-between">
          <CardHeader className="p-5 pb-3 space-y-2">
            <div className="size-8 rounded-xl bg-emerald-500/10 text-emerald-600 font-bold flex items-center justify-center text-sm shrink-0">
              3
            </div>
            <CardTitle className="text-base font-bold">Khởi động lại Anki Desktop</CardTitle>
            <CardDescription className="text-xs leading-relaxed">
              Bấm nút <strong className="text-foreground">OK</strong> để lưu lại thay đổi.
              <br />
              <strong className="text-amber-600 dark:text-amber-400">Rất quan trọng:</strong> Bạn cần phải <strong>Tắt hẳn và mở lại (khởi động lại) phần mềm Anki Desktop</strong> để thiết lập mới được áp dụng!
            </CardDescription>
          </CardHeader>
          <CardContent className="p-5 pt-0">
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-xs font-medium flex items-center gap-2">
              <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
              <span>Hoàn tất! Flama sẽ kết nối trực tiếp với Anki.</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Visual Comparison / Before & After */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="border-border/80 shadow-2xs rounded-2xl">
          <CardHeader className="p-4 sm:p-5 border-b bg-muted/20">
            <CardTitle className="text-sm font-bold text-muted-foreground flex items-center gap-2">
              <span>Cấu hình mặc định (Trước khi sửa)</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <pre className="p-4 bg-slate-950 text-slate-400 text-xs font-mono overflow-x-auto leading-relaxed select-none">
{`{
    "apiKey": null,
    "apiPort": 8765,
    "webCorsOriginList": [
        "http://localhost"
    ]
}`}
            </pre>
          </CardContent>
        </Card>

        <Card className="border-border/80 shadow-2xs rounded-2xl border-emerald-500/20">
          <CardHeader className="p-4 sm:p-5 border-b bg-emerald-500/5">
            <CardTitle className="text-sm font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
              <span>Cấu hình chính xác (Sau khi sửa)</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <pre className="p-4 bg-slate-950 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed select-all">
{`{
    "apiKey": null,
    "apiPort": 8765,
    "webCorsOriginList": [
        "http://localhost",
        "${currentOrigin}"
    ]
}`}
            </pre>
          </CardContent>
        </Card>
      </div>

      {/* Code Snippet Box */}
      <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
        <CardHeader className="p-4 sm:p-5 border-b bg-card/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Code className="size-4 text-primary" />
              Đoạn cấu hình mẫu cho thuộc tính danh sách cho phép (CORS)
            </CardTitle>
            <CardDescription className="text-xs">
              Mẹo nhanh: Bạn có thể copy toàn bộ đoạn này để thay thế mục <code className="font-mono">webCorsOriginList</code> trong cài đặt Anki.
            </CardDescription>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-8 font-semibold text-xs shrink-0 gap-1.5"
            onClick={handleCopyConfig}
          >
            {copiedConfig ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
            {copiedConfig ? 'Đã sao chép JSON' : '2. Sao chép đoạn cấu hình mẫu'}
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <pre className="p-4 bg-slate-950 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed select-all">
            {recommendedCorsSetting}
          </pre>
        </CardContent>
      </Card>
    </div>
  )
}
