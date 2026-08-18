import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TabsContent } from '@/components/ui/tabs'
import {
  Bot,
  Cpu,
  Layers,
  Search,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react'

export function McpAboutTab() {
  return (
    <TabsContent value="about" className="space-y-6">
      {/* Hero Overview */}
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-card to-card shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-2">
          <div className="flex items-center gap-2">
            <Badge variant="default" className="gap-1 px-2.5 py-0.5 text-xs font-semibold">
              <Sparkles className="size-3" /> Model Context Protocol
            </Badge>
            <Badge variant="outline" className="text-xs">
              JSON-RPC 2.0
            </Badge>
          </div>
          <CardTitle className="text-xl sm:text-2xl font-bold mt-2">
            Kết nối Trợ lý Trí tuệ Nhân tạo (AI) với Flama
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm leading-relaxed max-w-3xl">
            <strong>Model Context Protocol (MCP)</strong> là tiêu chuẩn giao tiếp mã nguồn mở do Anthropic phát triển,
            cho phép các ứng dụng AI như <strong>Claude Desktop, Cursor IDE, Antigravity, Roo Code, Cline</strong> kết nối
            trực tiếp và thao tác an toàn trên kho thẻ Flashcard của bạn.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-2 space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border bg-card/60 p-4 space-y-2 backdrop-blur-xs">
              <div className="flex size-9 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
                <Bot className="size-5" />
              </div>
              <h3 className="font-semibold text-sm">Hỏi đáp & Tra cứu</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                AI có thể đọc danh sách deck, cấu trúc cây thư mục và tra cứu thẻ học để trả lời hoặc gợi ý từ vựng.
              </p>
            </div>

            <div className="rounded-2xl border bg-card/60 p-4 space-y-2 backdrop-blur-xs">
              <div className="flex size-9 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                <Zap className="size-5" />
              </div>
              <h3 className="font-semibold text-sm">Tạo thẻ Tự động</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Ra lệnh cho AI: <em>"Tạo 10 thẻ từ vựng JLPT N2 về chủ đề môi trường"</em> — thẻ được tạo ngay vào bộ Flama của bạn.
              </p>
            </div>

            <div className="rounded-2xl border bg-card/60 p-4 space-y-2 backdrop-blur-xs">
              <div className="flex size-9 items-center justify-center rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400">
                <Search className="size-5" />
              </div>
              <h3 className="font-semibold text-sm">Tránh trùng lặp</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Tool tự động kiểm tra trùng lặp từ vựng và tự động cập nhật trường nghĩa bổ sung thay vì tạo thẻ rác.
              </p>
            </div>

            <div className="rounded-2xl border bg-card/60 p-4 space-y-2 backdrop-blur-xs">
              <div className="flex size-9 items-center justify-center rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
                <ShieldCheck className="size-5" />
              </div>
              <h3 className="font-semibold text-sm">Bảo mật & Tự chủ</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Xác thực bằng Token bảo mật theo Scope, chạy trực tiếp trên Flama Connect riêng tư của bạn.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Supported Clients Grid */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-2">
          <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
            <Cpu className="size-5 text-primary shrink-0" />
            Các AI Client tương thích
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm">
            Flama MCP hỗ trợ tất cả các phần mềm và IDE tích hợp giao thức Model Context Protocol chuẩn.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-2">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="flex items-start gap-3 rounded-xl border p-3.5 bg-muted/20">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 font-bold text-xs">
                C
              </div>
              <div className="min-w-0 space-y-1">
                <div className="text-xs font-bold text-foreground">Claude Desktop</div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Trợ lý Claude trên máy tính cá nhân (macOS / Windows), kết nối qua file <code className="text-xs font-mono">claude_desktop_config.json</code>.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-xl border p-3.5 bg-muted/20">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-blue-500/10 text-blue-600 font-bold text-xs">
                Cu
              </div>
              <div className="min-w-0 space-y-1">
                <div className="text-xs font-bold text-foreground">Cursor IDE</div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Lập trình & học tập cùng lúc. Thêm MCP Server trực tiếp trong Cursor Settings &rarr; Features &rarr; MCP.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-xl border p-3.5 bg-muted/20">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 font-bold text-xs">
                AG
              </div>
              <div className="min-w-0 space-y-1">
                <div className="text-xs font-bold text-foreground">Antigravity & Roo Code</div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Các AI coding agent trên VS Code và Antigravity IDE thông qua remote HTTP JSON-RPC endpoint.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Workflow steps */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-2">
          <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
            <Layers className="size-5 text-primary shrink-0" />
            Quy trình sử dụng trong 3 bước
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-2">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl border p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className="flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">1</span>
                <span className="font-semibold text-xs sm:text-sm">Tạo Token MCP</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Vào tab <strong>Quản lý Token</strong>, đặt tên và chọn thời hạn phù hợp (mặc định dài hạn 180 ngày hoặc Vĩnh viễn).
              </p>
            </div>

            <div className="rounded-xl border p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className="flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">2</span>
                <span className="font-semibold text-xs sm:text-sm">Cấu hình Client</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Vào tab <strong>Hướng dẫn Cài đặt</strong>, sao chép cấu hình mẫu JSON cho Claude Desktop hoặc Cursor và lưu lại.
              </p>
            </div>

            <div className="rounded-xl border p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className="flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">3</span>
                <span className="font-semibold text-xs sm:text-sm">Trò chuyện & Tạo thẻ</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Mở AI chat và yêu cầu tra cứu hoặc tạo Flashcard tiếng Nhật. Xem các câu lệnh mẫu tại tab <strong>Danh mục Công cụ</strong>.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </TabsContent>
  )
}
