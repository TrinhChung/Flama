import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from 'sonner'
import {
  ArrowRight,
  Bot,
  Check,
  Code,
  Copy,
  Cpu,
  Info,
  KeyRound,
  Search,
  ShieldCheck,
  Terminal,
  Wrench,
  Zap,
} from 'lucide-react'

export function McpInteractiveGuide() {
  const [copiedKey, setCopiedKey] = useState<string | null>(null)

  const copySnippet = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedKey(key)
      window.setTimeout(() => setCopiedKey(null), 2000)
      toast.success('Đã sao chép cấu hình vào bộ nhớ tạm.')
    } catch {
      toast.error('Không thể sao chép.')
    }
  }

  const claudeDesktopConfig = `{
  "mcpServers": {
    "flama": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://localhost:4790/v1/mcp",
        "--header",
        "Authorization: Bearer <YOUR_MCP_TOKEN>"
      ]
    }
  }
}`

  const cursorMcpConfig = `{
  "mcpServers": {
    "flama": {
      "url": "http://localhost:4790/v1/mcp/<YOUR_MCP_TOKEN>"
    }
  }
}`

  const curlTestCommand = `curl -X POST http://localhost:4790/v1/mcp \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer <YOUR_MCP_TOKEN>" \\
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_my_decks",
      "arguments": {}
    }
  }'`

  return (
    <div className="space-y-8 w-full min-w-0">
      {/* Hero Overview Card */}
      <Card className="border-purple-500/30 bg-gradient-to-br from-purple-500/10 via-background to-primary/5 shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-2 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="default" className="bg-purple-600 hover:bg-purple-700 text-white font-semibold px-2.5 sm:px-3 py-1 text-xs gap-1.5 shadow-2xs">
              <Cpu className="size-3.5" /> Model Context Protocol (MCP)
            </Badge>
            <Badge variant="outline" className="text-xs border-purple-500/40 text-purple-700 dark:text-purple-300">
              JSON-RPC 2.0 Standard
            </Badge>
          </div>
          <div className="space-y-1.5">
            <CardTitle className="text-lg sm:text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Bot className="size-5 text-purple-600 dark:text-purple-400 shrink-0" />
              <span>Kết Nối Trợ Lý Trí Tuệ Nhân Tạo (AI) Với Flama</span>
            </CardTitle>
            <CardDescription className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-3xl">
              <strong>Model Context Protocol (MCP)</strong> là tiêu chuẩn giao tiếp mở do Anthropic khởi xướng, cho phép các ứng dụng AI như <strong>Claude Desktop, Cursor IDE, Antigravity, Roo Code, Cline</strong> kết nối trực tiếp và thao tác an toàn trên kho thẻ Flashcard Flama.
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="p-4 sm:p-6 pt-2 space-y-6">
          {/* 4 Core Pillars */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border bg-card/90 p-4 space-y-2 shadow-2xs hover:border-amber-500/40 transition-all">
              <div className="flex size-9 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
                <Bot className="size-5" />
              </div>
              <h3 className="font-semibold text-xs sm:text-sm text-foreground">Hỏi Đáp & Tra Cứu</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                AI có thể đọc danh sách deck, cấu trúc cây thư mục và tra cứu thẻ học để trả lời hoặc gợi ý từ vựng.
              </p>
            </div>

            <div className="rounded-2xl border bg-card/90 p-4 space-y-2 shadow-2xs hover:border-emerald-500/40 transition-all">
              <div className="flex size-9 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                <Zap className="size-5" />
              </div>
              <h3 className="font-semibold text-xs sm:text-sm text-foreground">Tạo Thẻ Tự Động</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Ra lệnh tự nhiên cho AI: <em>"Tạo 10 thẻ từ vựng JLPT N2 về môi trường"</em> — thẻ được tạo ngay vào bộ Flama.
              </p>
            </div>

            <div className="rounded-2xl border bg-card/90 p-4 space-y-2 shadow-2xs hover:border-sky-500/40 transition-all">
              <div className="flex size-9 items-center justify-center rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400">
                <Search className="size-5" />
              </div>
              <h3 className="font-semibold text-xs sm:text-sm text-foreground">Tránh Trùng Lặp</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Công cụ tự động kiểm tra trùng lặp từ vựng và tự động cập nhật trường nghĩa bổ sung thay vì tạo thẻ rác.
              </p>
            </div>

            <div className="rounded-2xl border bg-card/90 p-4 space-y-2 shadow-2xs hover:border-purple-500/40 transition-all">
              <div className="flex size-9 items-center justify-center rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
                <ShieldCheck className="size-5" />
              </div>
              <h3 className="font-semibold text-xs sm:text-sm text-foreground">Bảo Mật & Tự Chủ</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Xác thực bằng Token bảo mật theo Scope, chạy trực tiếp trên Flama Connect riêng tư của bạn.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Supported Clients Grid */}
      <Card className="rounded-2xl border shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-2">
          <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2 text-foreground">
            <Cpu className="size-4.5 text-primary shrink-0" />
            <span>Các Ứng Dụng AI Tương Thích Chuẩn MCP</span>
          </CardTitle>
          <CardDescription className="text-xs">
            Flama MCP hỗ trợ tất cả các phần mềm và IDE tích hợp giao thức Model Context Protocol chuẩn:
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-2">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="flex items-start gap-3 rounded-xl border p-3.5 bg-muted/20">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 font-bold text-xs">
                C
              </div>
              <div className="min-w-0 space-y-1">
                <div className="text-xs font-bold text-foreground">Claude Desktop</div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Trợ lý Claude trên macOS / Windows qua file cấu hình <code className="font-mono text-[10px]">claude_desktop_config.json</code>.
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
                  Lập trình & học tập cùng lúc. Thêm MCP Server trong Settings ➔ Features ➔ MCP.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-xl border p-3.5 bg-muted/20">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 font-bold text-xs">
                AG
              </div>
              <div className="min-w-0 space-y-1">
                <div className="text-xs font-bold text-foreground">Antigravity / Roo Code</div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Các AI coding agent trên VS Code và Antigravity qua remote HTTP endpoint.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-xl border p-3.5 bg-muted/20">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-purple-500/10 text-purple-600 font-bold text-xs">
                GPT
              </div>
              <div className="min-w-0 space-y-1">
                <div className="text-xs font-bold text-foreground">ChatGPT Connectors</div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Kết nối với tài khoản ChatGPT Plus/Team thông qua chuẩn bảo mật OAuth 2.1 PKCE.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Interactive Config Snippets Section */}
      <div className="space-y-4">
        <h3 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
          <Code className="size-4.5 text-primary" />
          <span>Mẫu Cấu Hình Cho Từng Client AI</span>
        </h3>

        {/* 1. Claude Desktop */}
        <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-4 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="flex size-8 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 font-bold text-sm">
                C
              </div>
              <div>
                <h4 className="text-xs sm:text-sm font-bold text-foreground">1. Cấu hình cho Claude Desktop</h4>
                <p className="text-[11px] text-muted-foreground">Ứng dụng Claude chính thức trên macOS và Windows</p>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5 text-xs font-semibold h-8"
              onClick={() => copySnippet('claude', claudeDesktopConfig)}
            >
              {copiedKey === 'claude' ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
              {copiedKey === 'claude' ? 'Đã sao chép' : 'Sao chép cấu hình JSON'}
            </Button>
          </div>

          <div className="space-y-1.5 text-xs text-muted-foreground">
            <div>Vị trí file cấu hình:</div>
            <ul className="list-disc list-inside space-y-1 font-mono text-[11px] bg-muted/30 p-2.5 rounded-lg border">
              <li><strong>Windows:</strong> <code>%APPDATA%\Claude\claude_desktop_config.json</code></li>
              <li><strong>macOS:</strong> <code>~/Library/Application Support/Claude/claude_desktop_config.json</code></li>
            </ul>
          </div>

          <pre className="overflow-x-auto rounded-xl bg-zinc-950 p-3.5 font-mono text-xs text-zinc-100 dark:bg-zinc-900 leading-relaxed">
            {claudeDesktopConfig}
          </pre>
        </div>

        {/* 2. Cursor IDE */}
        <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-4 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="flex size-8 items-center justify-center rounded-lg bg-blue-500/10 text-blue-600 font-bold text-sm">
                Cu
              </div>
              <div>
                <h4 className="text-xs sm:text-sm font-bold text-foreground">2. Cấu hình cho Cursor IDE</h4>
                <p className="text-[11px] text-muted-foreground">Cấu hình MCP Server trực tiếp trong Cursor Settings</p>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5 text-xs font-semibold h-8"
              onClick={() => copySnippet('cursor', cursorMcpConfig)}
            >
              {copiedKey === 'cursor' ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
              {copiedKey === 'cursor' ? 'Đã sao chép' : 'Sao chép cấu hình Cursor'}
            </Button>
          </div>

          <ol className="text-xs text-muted-foreground space-y-1.5 list-decimal list-inside leading-relaxed font-medium">
            <li>Mở <strong>Cursor Settings</strong> (Ctrl + Shift + J hoặc Cmd + Shift + J) ➔ mục <strong>Features</strong> ➔ <strong>MCP</strong>.</li>
            <li>Bấm nút <strong>+ Add New MCP Server</strong>.</li>
            <li>Đặt <strong>Name:</strong> <code>flama</code> | <strong>Type:</strong> <code>sse</code> hoặc <code>http</code>.</li>
            <li>Dán Server URL: <code>http://localhost:4790/v1/mcp/&lt;YOUR_MCP_TOKEN&gt;</code>.</li>
            <li>Nhấn <strong>Save</strong> để kết nối hoàn tất.</li>
          </ol>

          <pre className="overflow-x-auto rounded-xl bg-zinc-950 p-3.5 font-mono text-xs text-zinc-100 dark:bg-zinc-900 leading-relaxed">
            {cursorMcpConfig}
          </pre>
        </div>

        {/* 3. Terminal / Curl */}
        <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-4 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="flex size-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 font-bold text-sm">
                <Terminal className="size-4" />
              </div>
              <div>
                <h4 className="text-xs sm:text-sm font-bold text-foreground">3. Kiểm tra kết nối bằng Curl / Terminal</h4>
                <p className="text-[11px] text-muted-foreground">Thử nghiệm gửi request JSON-RPC 2.0 trực tiếp từ command line</p>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5 text-xs font-semibold h-8"
              onClick={() => copySnippet('curl', curlTestCommand)}
            >
              {copiedKey === 'curl' ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
              {copiedKey === 'curl' ? 'Đã sao chép' : 'Sao chép lệnh cURL'}
            </Button>
          </div>

          <pre className="overflow-x-auto rounded-xl bg-zinc-950 p-3.5 font-mono text-xs text-zinc-100 dark:bg-zinc-900 leading-relaxed">
            {curlTestCommand}
          </pre>
        </div>
      </div>

      {/* Flama Connect Service Alert */}
      <Alert className="border-sky-500/30 bg-sky-50/50 dark:bg-sky-950/20 p-4 sm:p-5 rounded-2xl">
        <Info className="size-5 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
        <div className="space-y-1.5 min-w-0">
          <AlertTitle className="text-sky-900 dark:text-sky-200 font-bold text-xs sm:text-sm">
            Lưu ý về Dịch vụ Flama Connect (Cổng 4790)
          </AlertTitle>
          <AlertDescription className="text-xs text-sky-800 dark:text-sky-300 leading-relaxed">
            Đảm bảo tiến trình <strong>Flama Connect</strong> (chạy trên cổng <code>4790</code> qua file <code>connect_wsgi.py</code>) đang hoạt động song song với ứng dụng chính. Nếu bạn chạy trên môi trường production, Nginx sẽ tự động định tuyến các request <code>/v1/mcp</code> đến cổng 4790 với độ trễ thấp nhất.
          </AlertDescription>
        </div>
      </Alert>

      {/* Quick Action Navigation Strip */}
      <div className="grid gap-3 sm:grid-cols-2 pt-2">
        <Link
          to="/guide/integrations/mcp-tools"
          className="group flex items-center justify-between p-4 rounded-2xl border bg-card hover:border-purple-500/50 hover:bg-muted/20 transition-all shadow-2xs"
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 shrink-0 group-hover:scale-105 transition-transform">
              <Wrench className="size-5" />
            </div>
            <div className="space-y-0.5">
              <div className="font-bold text-xs sm:text-sm text-foreground group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                Danh Mục Toàn Bộ Công Cụ & Prompts
              </div>
              <p className="text-[11px] text-muted-foreground">
                Xem tất cả các tools MCP và câu lệnh mẫu cho AI
              </p>
            </div>
          </div>
          <ArrowRight className="size-4 text-muted-foreground group-hover:text-purple-500 group-hover:translate-x-0.5 transition-all" />
        </Link>

        <Link
          to="/settings/mcp-tokens"
          className="group flex items-center justify-between p-4 rounded-2xl border bg-card hover:border-primary hover:bg-muted/20 transition-all shadow-2xs"
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-primary/10 text-primary shrink-0 group-hover:scale-105 transition-transform">
              <KeyRound className="size-5" />
            </div>
            <div className="space-y-0.5">
              <div className="font-bold text-xs sm:text-sm text-foreground group-hover:text-primary transition-colors">
                Trang Quản Lý Token MCP
              </div>
              <p className="text-[11px] text-muted-foreground">
                Tạo Token mới và cấu hình OAuth 2.1 ChatGPT
              </p>
            </div>
          </div>
          <ArrowRight className="size-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
        </Link>
      </div>
    </div>
  )
}
