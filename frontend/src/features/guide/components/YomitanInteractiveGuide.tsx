import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  ArrowRight,
  CheckCircle2,
  Code,
  Download,
  ExternalLink,
  Globe,
  Heart,
  Info,
  KeyRound,
  MousePointerClick,
  Smartphone,
  Zap,
} from 'lucide-react'

export function YomitanInteractiveGuide() {
  return (
    <div className="space-y-8 w-full min-w-0">
      {/* Overview & Feature Highlights */}
      <Card className="overflow-hidden border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-background to-primary/5 shadow-2xs">
        <CardHeader className="p-4 sm:p-6 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="default" className="bg-amber-500 hover:bg-amber-600 text-white font-semibold px-2.5 sm:px-3 py-1 text-xs gap-1.5 shadow-2xs">
              <Heart className="size-3.5 fill-current" /> Highly Recommended (おすすめ - Khuyên dùng)
            </Badge>
            <Badge variant="outline" className="text-xs border-amber-500/40 text-amber-700 dark:text-amber-300">
              Must-have extension cho người học tiếng Nhật
            </Badge>
          </div>
          <div className="space-y-1.5">
            <CardTitle className="text-lg sm:text-xl font-bold tracking-tight flex items-center gap-2 text-foreground">
              <Zap className="size-5 text-amber-500 shrink-0" />
              <span>Tại sao bạn RẤT NÊN DÙNG Yomitan khi học tiếng Nhật?</span>
            </CardTitle>
            <CardDescription className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
              Yomitan là tiện ích mở rộng (browser extension) tra từ pop-up tốc độ cao trên trình duyệt web, kế thừa và nâng cấp toàn diện từ <strong>Yomichan</strong> huyền thoại.
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="p-4 sm:p-6 pt-0 space-y-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="group rounded-2xl border bg-card/90 p-4 space-y-2.5 shadow-2xs hover:shadow-md hover:border-amber-500/40 transition-all">
              <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 w-fit group-hover:scale-105 transition-transform">
                <MousePointerClick className="size-5" />
              </div>
              <div className="font-bold text-xs sm:text-sm text-foreground">Tra từ siêu tốc 0.1s</div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Rê chuột hoặc chạm lên từ tiếng Nhật trên bất kỳ trang web nào (báo chí NHK, manga, sub anime, blog), popup hiện ngay Furigana, nghĩa Hán Việt/Anh, phiên âm và audio MP3.
              </p>
            </div>

            <div className="group rounded-2xl border bg-card/90 p-4 space-y-2.5 shadow-2xs hover:shadow-md hover:border-emerald-500/40 transition-all">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 w-fit group-hover:scale-105 transition-transform">
                <CheckCircle2 className="size-5" />
              </div>
              <div className="font-bold text-xs sm:text-sm text-foreground">Tạo Flashcard 1-Click</div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Nhấp nút <strong>+</strong> trong cửa sổ tra từ, toàn bộ Kanji, Kana, nghĩa, phát âm audio MP3 và câu ví dụ trên trang web tự động gửi thẳng vào Deck Flama qua Flama Connect.
              </p>
            </div>

            <div className="group rounded-2xl border bg-card/90 p-4 space-y-2.5 shadow-2xs hover:shadow-md hover:border-sky-500/40 transition-all">
              <div className="p-2.5 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400 w-fit group-hover:scale-105 transition-transform">
                <Globe className="size-5" />
              </div>
              <div className="font-bold text-xs sm:text-sm text-foreground">Học Đắm Mình (Immersion)</div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Không còn ngắt quãng tư duy do gõ tay từng từ vào app từ điển. Tự tin đọc và thưởng thức nội dung tiếng Nhật thực tế trên cả máy tính lẫn điện thoại di động.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Official Download Links Section */}
      <Card className="rounded-2xl border shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-2">
          <div className="space-y-1">
            <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
              <Download className="size-4.5 text-primary" />
              <span>Link Tải Tiện Ích Yomitan Chính Thức</span>
            </CardTitle>
            <CardDescription className="text-xs">
              Chọn trình duyệt bạn đang sử dụng để cài đặt extension Yomitan:
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-1">
          <div className="grid gap-3 sm:grid-cols-3">
            <a
              href="https://chromewebstore.google.com/detail/yomitan/gkgemgainhhaloainhgfppmadnhpikan"
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between rounded-xl border p-3.5 bg-background hover:border-primary hover:bg-primary/5 hover:shadow-xs transition-all group"
            >
              <div className="space-y-0.5">
                <div className="font-semibold text-xs sm:text-sm group-hover:text-primary transition-colors">
                  Chrome / Edge / Brave / Kiwi Mobile
                </div>
                <div className="text-[11px] text-muted-foreground">Chrome Web Store</div>
              </div>
              <ExternalLink className="size-3.5 text-muted-foreground group-hover:text-primary transition-colors shrink-0 ml-2" />
            </a>

            <a
              href="https://addons.mozilla.org/en-US/firefox/addon/yomitan/"
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between rounded-xl border p-3.5 bg-background hover:border-primary hover:bg-primary/5 hover:shadow-xs transition-all group"
            >
              <div className="space-y-0.5">
                <div className="font-semibold text-xs sm:text-sm group-hover:text-primary transition-colors">
                  Firefox (PC & Android)
                </div>
                <div className="text-[11px] text-muted-foreground">Firefox Add-ons</div>
              </div>
              <ExternalLink className="size-3.5 text-muted-foreground group-hover:text-primary transition-colors shrink-0 ml-2" />
            </a>

            <a
              href="https://github.com/yomitan-dev/yomitan"
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between rounded-xl border p-3.5 bg-background hover:border-primary hover:bg-primary/5 hover:shadow-xs transition-all group"
            >
              <div className="space-y-0.5">
                <div className="font-semibold text-xs sm:text-sm group-hover:text-primary transition-colors">
                  Mã Nguồn GitHub
                </div>
                <div className="text-[11px] text-muted-foreground">yomitan-dev/yomitan</div>
              </div>
              <ExternalLink className="size-3.5 text-muted-foreground group-hover:text-primary transition-colors shrink-0 ml-2" />
            </a>
          </div>
        </CardContent>
      </Card>

      {/* Mobile Android Guide */}
      <div className="rounded-2xl border border-purple-500/30 bg-purple-500/5 p-4 sm:p-5 space-y-3 shadow-2xs">
        <h4 className="font-bold text-xs sm:text-sm flex items-center gap-2 text-purple-900 dark:text-purple-200">
          <Smartphone className="size-4.5 text-purple-600 dark:text-purple-400 shrink-0" />
          <span>Sử Dụng Yomitan Trên Điện Thoại Android (Kiwi Browser / Firefox Android)</span>
        </h4>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Bạn hoàn toàn có thể tra từ & bắn Flashcard sang Flama ngay trên điện thoại Android bằng cách sử dụng trình duyệt di động hỗ trợ Extensions:
        </p>
        <ol className="text-xs text-muted-foreground space-y-1.5 list-decimal list-inside leading-relaxed font-medium">
          <li>Tải ứng dụng <strong>Kiwi Browser</strong> hoặc <strong>Firefox</strong> từ Google Play Store trên điện thoại.</li>
          <li>Mở cửa hàng tiện ích (Chrome Web Store hoặc Firefox Add-ons) trong trình duyệt di động và cài đặt <strong>Yomitan</strong>.</li>
          <li>Vào Cài đặt Yomitan ➔ phần <strong>Integration / Connect</strong> ➔ dán <strong>Server URL</strong> Flama Connect đã tạo.</li>
          <li>Bắt đầu đọc báo tiếng Nhật, manga hay light novel trên di động và chạm từ vựng để tạo thẻ Flama tức thì!</li>
        </ol>
      </div>

      {/* Unique First Field Rule Alert */}
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

      {/* Quick Action Navigation Strip */}
      <div className="grid gap-3 sm:grid-cols-2 pt-2">
        <Link
          to="/guide/integrations/yomitan-markers"
          className="group flex items-center justify-between p-4 rounded-2xl border bg-card hover:border-purple-500/50 hover:bg-muted/20 transition-all shadow-2xs"
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 shrink-0 group-hover:scale-105 transition-transform">
              <Code className="size-5" />
            </div>
            <div className="space-y-0.5">
              <div className="font-bold text-xs sm:text-sm text-foreground group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                Bảng Tra Cứu 55 Field Markers
              </div>
              <p className="text-[11px] text-muted-foreground">
                Xem toàn bộ mã ánh xạ và sao chép 1-click
              </p>
            </div>
          </div>
          <ArrowRight className="size-4 text-muted-foreground group-hover:text-purple-500 group-hover:translate-x-0.5 transition-all" />
        </Link>

        <Link
          to="/settings/yomitan"
          className="group flex items-center justify-between p-4 rounded-2xl border bg-card hover:border-primary hover:bg-muted/20 transition-all shadow-2xs"
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-primary/10 text-primary shrink-0 group-hover:scale-105 transition-transform">
              <KeyRound className="size-5" />
            </div>
            <div className="space-y-0.5">
              <div className="font-bold text-xs sm:text-sm text-foreground group-hover:text-primary transition-colors">
                Trang Quản Lý Token Flama Connect
              </div>
              <p className="text-[11px] text-muted-foreground">
                Tạo Token mới và lấy Server URL để kết nối
              </p>
            </div>
          </div>
          <ArrowRight className="size-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
        </Link>
      </div>
    </div>
  )
}
