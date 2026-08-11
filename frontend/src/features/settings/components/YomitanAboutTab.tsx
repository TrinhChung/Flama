import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TabsContent } from '@/components/ui/tabs'
import {
  BookOpen,
  CheckCircle2,
  Compass,
  Download,
  ExternalLink,
  Globe,
  Heart,
  KeyRound,
  MousePointerClick,
  Zap,
} from 'lucide-react'

interface YomitanAboutTabProps {
  onNavigateToTokens: () => void
}

export function YomitanAboutTab({ onNavigateToTokens }: YomitanAboutTabProps) {
  return (
    <TabsContent value="about" className="space-y-6">
      <Card className="overflow-hidden border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-background to-primary/5 shadow-md">
        <CardHeader className="p-4 sm:p-6 md:p-8 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="default" className="bg-amber-500 hover:bg-amber-600 text-white font-semibold px-2.5 sm:px-3 py-1 text-xs gap-1.5 shadow-2xs">
              <Heart className="size-3.5 fill-current" /> Highly Recommended (おすすめ - Khuyên dùng)
            </Badge>
            <Badge variant="outline" className="text-xs border-amber-500/40 text-amber-700 dark:text-amber-300">
              Must-have extension cho người học tiếng Nhật
            </Badge>
          </div>
          <div className="space-y-2">
            <CardTitle className="text-xl sm:text-2xl md:text-3xl font-bold tracking-tight flex items-center gap-2.5 sm:gap-3">
              <Compass className="size-6 sm:size-8 text-primary shrink-0" />
              <span>Tiện ích Yomitan & Công cụ đắm mình tiếng Nhật</span>
            </CardTitle>
            <CardDescription className="text-xs sm:text-sm md:text-base leading-relaxed max-w-4xl text-muted-foreground">
              Yomitan là tiện ích mở rộng (browser extension) tra từ pop-up tốc độ cao trên trình duyệt web, là phiên bản kế thừa nâng cấp và duy trì tích cực của <strong>Yomichan</strong> huyền thoại.
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="p-4 sm:p-6 md:p-8 pt-0 space-y-6 sm:space-y-8">
          {/* Feature Cards Grid */}
          <div className="space-y-4">
            <h3 className="font-bold text-sm sm:text-base md:text-lg flex items-center gap-2 text-foreground">
              <Zap className="size-4.5 sm:size-5 text-amber-500" /> Tại sao bạn RẤT NÊN DÙNG Yomitan khi học tiếng Nhật?
            </h3>

            <div className="grid gap-4 sm:gap-5 md:grid-cols-3">
              <div className="group rounded-2xl border bg-card/90 p-4 sm:p-5 space-y-2.5 sm:space-y-3 shadow-2xs hover:shadow-md hover:border-amber-500/40 transition-all">
                <div className="p-2.5 sm:p-3 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 w-fit group-hover:scale-105 transition-transform">
                  <MousePointerClick className="size-5 sm:size-6" />
                </div>
                <div className="font-bold text-sm sm:text-base">Tra từ siêu tốc 0.1s</div>
                <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                  Rê chuột hoặc chạm lên từ tiếng Nhật trên bất kỳ trang web nào (báo chí NHK, manga, sub anime web, blog), cửa sổ popup sẽ hiện ngay Furigana, nghĩa Hán Việt/Anh, phiên âm và âm thanh MP3.
                </p>
              </div>

              <div className="group rounded-2xl border bg-card/90 p-4 sm:p-5 space-y-2.5 sm:space-y-3 shadow-2xs hover:shadow-md hover:border-emerald-500/40 transition-all">
                <div className="p-2.5 sm:p-3 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 w-fit group-hover:scale-105 transition-transform">
                  <CheckCircle2 className="size-5 sm:size-6" />
                </div>
                <div className="font-bold text-sm sm:text-base">Tạo Flashcard 1-Click</div>
                <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                  Nhấp nút <strong>+</strong> trong cửa sổ tra từ, toàn bộ từ vựng, Kana, nghĩa, phát âm audio MP3 và câu ví dụ trên trang web tự động gửi thẳng vào Deck Flama của bạn qua Flama Connect.
                </p>
              </div>

              <div className="group rounded-2xl border bg-card/90 p-4 sm:p-5 space-y-2.5 sm:space-y-3 shadow-2xs hover:shadow-md hover:border-sky-500/40 transition-all">
                <div className="p-2.5 sm:p-3 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400 w-fit group-hover:scale-105 transition-transform">
                  <Globe className="size-5 sm:size-6" />
                </div>
                <div className="font-bold text-sm sm:text-base">Học Đắm mình (Immersion)</div>
                <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                  Không còn ngắt quãng tư duy do gõ tay từng từ vào ứng dụng tra từ điển. Giúp bạn tự tin đọc và thưởng thức nội dung tiếng Nhật thực tế trên cả máy tính lẫn điện thoại di động.
                </p>
              </div>
            </div>
          </div>

          {/* Download Buttons Section */}
          <div className="rounded-2xl border bg-card p-4 sm:p-6 space-y-4 shadow-2xs">
            <div className="space-y-1">
              <h4 className="font-bold text-sm sm:text-base flex items-center gap-2">
                <Download className="size-4.5 sm:size-5 text-primary" /> Hướng dẫn Tải & Cài đặt Yomitan
              </h4>
              <p className="text-xs text-muted-foreground">Chọn trình duyệt bạn đang sử dụng để cài đặt extension Yomitan chính thức:</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <a
                href="https://chromewebstore.google.com/detail/yomitan/gkgemgainhhaloainhgfppmadnhpikan"
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between rounded-xl border p-3.5 sm:p-4 bg-background hover:border-primary hover:bg-primary/5 hover:shadow-xs transition-all group"
              >
                <div className="space-y-0.5">
                  <div className="font-semibold text-sm group-hover:text-primary transition-colors">Chrome / Edge / Brave / Kiwi Mobile</div>
                  <div className="text-xs text-muted-foreground">Chrome Web Store</div>
                </div>
                <ExternalLink className="size-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0 ml-2" />
              </a>

              <a
                href="https://addons.mozilla.org/en-US/firefox/addon/yomitan/"
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between rounded-xl border p-3.5 sm:p-4 bg-background hover:border-primary hover:bg-primary/5 hover:shadow-xs transition-all group"
              >
                <div className="space-y-0.5">
                  <div className="font-semibold text-sm group-hover:text-primary transition-colors">Firefox (PC & Android)</div>
                  <div className="text-xs text-muted-foreground">Firefox Add-ons</div>
                </div>
                <ExternalLink className="size-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0 ml-2" />
              </a>

              <a
                href="https://github.com/yomitan-dev/yomitan"
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between rounded-xl border p-3.5 sm:p-4 bg-background hover:border-primary hover:bg-primary/5 hover:shadow-xs transition-all group"
              >
                <div className="space-y-0.5">
                  <div className="font-semibold text-sm group-hover:text-primary transition-colors">Mã nguồn GitHub</div>
                  <div className="text-xs text-muted-foreground">yomitan-dev/yomitan</div>
                </div>
                <ExternalLink className="size-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0 ml-2" />
              </a>
            </div>
          </div>

          {/* Next Steps CTA */}
          <div className="rounded-2xl border bg-muted/30 p-4 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <h4 className="font-bold text-sm sm:text-base flex items-center gap-2">
                <BookOpen className="size-4.5 sm:size-5 text-primary" /> Bạn đã tải Yomitan thành công?
              </h4>
              <p className="text-xs sm:text-sm text-muted-foreground">
                Bước tiếp theo là tạo API Token và cấu hình Server URL trong Yomitan để bắt đầu bắn từ vựng sang Flama.
              </p>
            </div>
            <Button size="lg" className="w-full sm:w-auto shrink-0 font-semibold shadow-2xs" onClick={onNavigateToTokens}>
              <KeyRound className="mr-2 size-4.5" /> Sang Quản lý Token ngay
            </Button>
          </div>
        </CardContent>
      </Card>
    </TabsContent>
  )
}
