import { useState } from 'react'
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
  const [copied, setCopied] = useState(false)
  const currentOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:5173'
  const recommendedCorsSetting = `"webCorsOriginList": [
    "${currentOrigin}"
]`

  const handleCopyConfig = async () => {
    await navigator.clipboard.writeText(recommendedCorsSetting)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    toast.success('Đã sao chép cấu hình JSON của AnkiConnect vào bộ nhớ tạm!')
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header Banner */}
      <Card className="border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-background to-primary/5 shadow-xs rounded-2xl overflow-hidden">
        <CardHeader className="p-4 sm:p-6 space-y-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="bg-amber-500 hover:bg-amber-600 text-white font-bold px-2.5 py-0.5 text-[11px] gap-1.5 shadow-2xs">
              <ShieldAlert className="size-3.5" /> Hướng dẫn quan trọng
            </Badge>
            <Badge variant="outline" className="text-[11px] border-amber-500/40 text-amber-700 dark:text-amber-300">
              Khắc phục lỗi CORS &amp; Kết nối Anki Desktop
            </Badge>
          </div>
          <CardTitle className="text-lg sm:text-xl font-bold tracking-tight flex items-center gap-2">
            <HelpCircle className="size-5 text-amber-500 shrink-0" />
            <span>Cách khắc phục lỗi CORS khi đồng bộ Anki Desktop</span>
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-3xl">
            Khi truy cập Flama ở cổng <code className="font-mono text-foreground font-semibold">http://localhost:5173</code> hoặc <code className="font-mono text-foreground font-semibold">http://127.0.0.1:5173</code>, trình duyệt sẽ chặn yêu cầu kết nối tới Anki Desktop (port 8765) nếu địa chỉ này chưa được thêm vào danh sách cho phép (CORS Whitelist) của AnkiConnect.
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Step-by-Step Guide Grid */}
      <div className="grid gap-4 md:grid-cols-3">
        {/* Step 1 */}
        <Card className="border-border/80 shadow-2xs rounded-2xl flex flex-col justify-between">
          <CardHeader className="p-5 pb-3 space-y-2">
            <div className="size-8 rounded-xl bg-primary/10 text-primary font-bold flex items-center justify-center text-sm shrink-0">
              1
            </div>
            <CardTitle className="text-base font-bold">Mở cấu hình AnkiConnect</CardTitle>
            <CardDescription className="text-xs leading-relaxed">
              Mở phần mềm <strong>Anki Desktop</strong> trên máy tính của bạn:
              <br />
              Vào menu <strong className="text-foreground">Tools (Công cụ)</strong> &rarr; <strong className="text-foreground">Add-ons</strong> (hoặc nhấn <kbd className="px-1.5 py-0.5 bg-muted rounded font-mono text-[10px]">Ctrl + Shift + A</kbd>).
            </CardDescription>
          </CardHeader>
          <CardContent className="p-5 pt-0 text-xs text-muted-foreground space-y-2">
            <div className="p-3 rounded-xl bg-muted/40 border text-[11px] space-y-1">
              <div className="font-semibold text-foreground flex items-center gap-1.5">
                <Info className="size-3.5 text-sky-500 shrink-0" /> Chưa có Add-on AnkiConnect?
              </div>
              <p>
                Nếu chưa cài, hãy bấm <strong>Get Add-ons...</strong> và nhập mã add-on: <code className="font-mono text-primary font-bold">2055492159</code> để cài đặt.
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
            <CardTitle className="text-base font-bold">Thêm CORS Whitelist</CardTitle>
            <CardDescription className="text-xs leading-relaxed">
              Chọn add-on <strong>AnkiConnect</strong> và bấm nút <strong className="text-foreground">Config (Cấu hình)</strong> ở góc dưới bên phải.
              <br />
              Hợp nhất origin bên dưới vào mục <code className="font-mono text-primary font-bold">webCorsOriginList</code>. Giữ nguyên các khóa khác, đặc biệt là <code className="font-mono">apiKey</code>.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-5 pt-0 space-y-2">
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs font-semibold h-8"
              onClick={handleCopyConfig}
            >
              {copied ? <Check className="size-3.5 mr-1 text-emerald-500" /> : <Copy className="size-3.5 mr-1" />}
              {copied ? 'Đã sao chép Config' : 'Sao chép cấu hình mẫu'}
            </Button>
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
              Bấm <strong className="text-foreground">OK</strong> để lưu cấu hình JSON.
              <br />
              <strong className="text-amber-600 dark:text-amber-400">Quan trọng:</strong> Bạn cần <strong>Tắt hẳn và khởi động lại phần mềm Anki Desktop</strong> để AnkiConnect nạp lại cấu hình CORS mới!
            </CardDescription>
          </CardHeader>
          <CardContent className="p-5 pt-0">
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-xs font-medium flex items-center gap-2">
              <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
              <span>Hoàn tất! Trình duyệt sẽ hết bị lỗi CORS khi đồng bộ.</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Code Snippet Box */}
      <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
        <CardHeader className="p-4 sm:p-5 border-b bg-card/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Code className="size-4 text-primary" />
              Thuộc tính CORS cần hợp nhất vào AnkiConnect Config
            </CardTitle>
            <CardDescription className="text-xs">
              Không thay toàn bộ config. Chỉ cập nhật thuộc tính này và không dùng wildcard <code className="font-mono">*</code>.
            </CardDescription>
          </div>
          <Button
            size="sm"
            className="h-8 font-semibold text-xs shrink-0"
            onClick={handleCopyConfig}
          >
            {copied ? <Check className="size-3.5 mr-1" /> : <Copy className="size-3.5 mr-1" />}
            {copied ? 'Đã sao chép' : 'Sao chép JSON'}
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
