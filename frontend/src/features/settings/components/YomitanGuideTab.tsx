import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TabsContent } from '@/components/ui/tabs'
import {
  HelpCircle,
  Info,
  Smartphone,
  Sparkles,
} from 'lucide-react'

export function YomitanGuideTab() {
  return (
    <TabsContent value="guide" className="space-y-6">
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6">
          <CardTitle className="text-lg sm:text-xl font-bold flex items-center gap-2">
            <Sparkles className="size-5 text-primary shrink-0" /> Hướng dẫn kết nối Yomitan với Flama Connect
          </CardTitle>
          <CardDescription className="text-xs md:text-sm">
            Flama Connect cho phép tự động gửi từ vựng, Kana, nghĩa, âm thanh MP3 và câu ví dụ từ tiện ích Yomitan trực tiếp vào bộ thẻ Flama của bạn.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0 space-y-6 sm:space-y-8">
          {/* Step Flow */}
          <div className="grid gap-3 sm:gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-2.5 sm:space-y-3 relative">
              <div className="flex items-center gap-3">
                <span className="flex size-7 sm:size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground text-xs sm:text-sm font-bold shadow-2xs shrink-0">1</span>
                <span className="font-bold text-xs sm:text-sm">Tạo API Token</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Vào tab <strong>Quản lý Token</strong>, nhập tên thiết bị (vd: <em>Chrome PC / Kiwi Mobile</em>), bấm <strong>Tạo token mới</strong> và sao chép đường dẫn Server URL.
              </p>
            </div>

            <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-2.5 sm:space-y-3 relative">
              <div className="flex items-center gap-3">
                <span className="flex size-7 sm:size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground text-xs sm:text-sm font-bold shadow-2xs shrink-0">2</span>
                <span className="font-bold text-xs sm:text-sm">Cài đặt Yomitan</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Mở tiện ích Yomitan trên thanh công cụ trình duyệt &rarr; bấm <strong>Settings</strong> (Cài đặt) &rarr; cuộn xuống phần <strong>Integration / Connect</strong>.
              </p>
            </div>

            <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-2.5 sm:space-y-3 relative">
              <div className="flex items-center gap-3">
                <span className="flex size-7 sm:size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground text-xs sm:text-sm font-bold shadow-2xs shrink-0">3</span>
                <span className="font-bold text-xs sm:text-sm">Dán Server URL</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Bật công tắc <strong>Enable integration / Custom server</strong>. Tại ô <strong>Server URL</strong>, dán URL đã copy ở Bước 1. *(Không cần nhập API key riêng)*.
              </p>
            </div>

            <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-2.5 sm:space-y-3 relative">
              <div className="flex items-center gap-3">
                <span className="flex size-7 sm:size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground text-xs sm:text-sm font-bold shadow-2xs shrink-0">4</span>
                <span className="font-bold text-xs sm:text-sm">Cấu hình & Tạo thẻ</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Mở <strong>Configure card templates...</strong> để gán các Field Markers vào các trường của Deck. Khi tra từ, bấm <strong>+</strong> để tạo thẻ lập tức!
              </p>
            </div>
          </div>

          {/* Mobile Browser Yomitan Guide */}
          <div className="rounded-2xl border border-purple-500/30 bg-purple-500/5 p-4 sm:p-5 space-y-3">
            <h4 className="font-bold text-xs sm:text-sm flex items-center gap-2 text-purple-900 dark:text-purple-200">
              <Smartphone className="size-4.5 sm:size-5 text-purple-600 dark:text-purple-400 shrink-0" />
              <span>Sử dụng Yomitan trên Điện thoại Android (Kiwi Browser / Firefox Android)</span>
            </h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Bạn hoàn toàn có thể tra từ & bắn Flashcard sang Flama ngay trên điện thoại Android bằng cách sử dụng trình duyệt di động hỗ trợ Extensions như <strong>Kiwi Browser</strong> hoặc <strong>Firefox Android</strong>:
            </p>
            <ol className="text-xs text-muted-foreground space-y-1.5 list-decimal list-inside leading-relaxed font-medium">
              <li>Tải ứng dụng <strong>Kiwi Browser</strong> hoặc <strong>Firefox</strong> từ Google Play Store trên điện thoại.</li>
              <li>Mở cửa hàng tiện ích (Chrome Web Store hoặc Firefox Add-ons) trong trình duyệt di động và cài đặt <strong>Yomitan</strong>.</li>
              <li>Vào Cài đặt Yomitan &rarr; phần <strong>Integration / Connect</strong> &rarr; dán <strong>Server URL</strong> Flama Connect đã tạo.</li>
              <li>Bắt đầu đọc báo tiếng Nhật, manga hay light novel trên di động và chạm từ vựng để tạo thẻ Flama tức thì!</li>
            </ol>
          </div>

          {/* Unique first field rule */}
          <Alert className="border-blue-500/30 bg-blue-50/50 dark:bg-blue-950/20 p-4 sm:p-5 rounded-2xl">
            <Info className="size-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <div className="space-y-2 min-w-0">
              <AlertTitle className="text-blue-900 dark:text-blue-200 font-bold text-xs sm:text-sm">
                Quy tắc trường đầu tiên (Unique First Field Requirement)
              </AlertTitle>
              <AlertDescription className="text-xs text-blue-800 dark:text-blue-300 leading-relaxed">
                Hệ thống yêu cầu <strong>trường đầu tiên (first field)</strong> của mẫu thẻ phải chứa giá trị duy nhất để phòng tránh tạo các thẻ ghi nhớ trùng lặp:
                <ul className="mt-2 list-disc list-inside space-y-1 font-medium">
                  <li>Đối với thẻ từ vựng (Terms): Khuyên dùng marker <code className="bg-background px-1.5 py-0.5 rounded text-foreground font-mono">{'{expression}'}</code> cho trường đầu tiên.</li>
                  <li>Đối với thẻ chữ Hán (Kanji): Khuyên dùng marker <code className="bg-background px-1.5 py-0.5 rounded text-foreground font-mono">{'{character}'}</code> cho trường đầu tiên.</li>
                </ul>
              </AlertDescription>
            </div>
          </Alert>

          {/* Media Constraints & Security */}
          <div className="rounded-2xl border p-4 sm:p-5 space-y-3 bg-card">
            <h4 className="font-bold text-xs sm:text-sm flex items-center gap-2">
              <HelpCircle className="size-4 text-muted-foreground shrink-0" /> Lưu ý về Media & Bảo mật
            </h4>
            <ul className="text-xs text-muted-foreground space-y-2 list-disc list-inside leading-relaxed">
              <li>
                <strong>Âm thanh phát âm (Audio):</strong> Flama Connect tự động tiếp nhận file MP3 phát âm dung lượng tối đa <strong>1 MB</strong> gửi từ Yomitan.
              </li>
              <li>
                <strong>Hình ảnh & Video:</strong> Hiện chưa hỗ trợ nhúng tự động ảnh chụp/video qua Flama Connect.
              </li>
              <li>
                <strong>Bảo mật Token:</strong> Server URL chứa token riêng tư của bạn. Hãy bảo vệ URL và thu hồi ngay nếu nghi ngờ lộ URL.
              </li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </TabsContent>
  )
}
