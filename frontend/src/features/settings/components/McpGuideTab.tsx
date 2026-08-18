import { useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TabsContent } from '@/components/ui/tabs'
import { toast } from 'sonner'
import {
  BookOpen,
  Check,
  Copy,
  Info,
  Terminal,
} from 'lucide-react'

export function McpGuideTab() {
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
    <TabsContent value="guide" className="space-y-6">
      {/* Overview Card */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
            <BookOpen className="size-5 text-primary shrink-0" />
            Hướng dẫn kết nối AI Client qua MCP
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm">
            Flama Connect chạy trên cổng <strong>4790</strong> (mặc định) và phục vụ endpoint giao thức MCP JSON-RPC 2.0 tại <code>/v1/mcp</code>.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0 space-y-6">
          {/* Step flow */}
          <div className="grid gap-3 sm:gap-4 md:grid-cols-3">
            <div className="rounded-2xl border bg-card p-4 space-y-2 relative">
              <div className="flex items-center gap-2.5">
                <span className="flex size-7 items-center justify-center rounded-xl bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  1
                </span>
                <span className="font-bold text-xs sm:text-sm">Tạo Token tại Flama</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Vào tab <strong>Quản lý Token</strong>, nhập tên thiết bị và tạo 1 token dài hạn. Sao chép chuỗi token được cấp.
              </p>
            </div>

            <div className="rounded-2xl border bg-card p-4 space-y-2 relative">
              <div className="flex items-center gap-2.5">
                <span className="flex size-7 items-center justify-center rounded-xl bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  2
                </span>
                <span className="font-bold text-xs sm:text-sm">Dán vào File Cấu hình</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Mở cấu hình MCP của ứng dụng AI bạn sử dụng (Claude Desktop, Cursor, Antigravity) và dán snippet cấu hình tương ứng bên dưới.
              </p>
            </div>

            <div className="rounded-2xl border bg-card p-4 space-y-2 relative">
              <div className="flex items-center gap-2.5">
                <span className="flex size-7 items-center justify-center rounded-xl bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  3
                </span>
                <span className="font-bold text-xs sm:text-sm">Khởi động & Trò chuyện</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Khởi động lại AI Client hoặc reload MCP Server. AI sẽ lập tức nhận diện 8 công cụ Flashcard của Flama!
              </p>
            </div>
          </div>

          {/* Guide 1: Claude Desktop */}
          <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex size-8 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 font-bold text-sm">
                  C
                </div>
                <div>
                  <h3 className="text-sm font-bold text-foreground">1. Cấu hình cho Claude Desktop</h3>
                  <p className="text-xs text-muted-foreground">Ứng dụng Claude chính thức trên macOS và Windows</p>
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

            <div className="space-y-2 text-xs text-muted-foreground">
              <div>Vị trí file cấu hình:</div>
              <ul className="list-disc list-inside space-y-1 font-mono text-[11px] bg-muted/30 p-2.5 rounded-lg border">
                <li><strong>Windows:</strong> <code>%APPDATA%\Claude\claude_desktop_config.json</code></li>
                <li><strong>macOS:</strong> <code>~/Library/Application Support/Claude/claude_desktop_config.json</code></li>
              </ul>
            </div>

            <div className="relative">
              <pre className="overflow-x-auto rounded-xl bg-zinc-950 p-3.5 font-mono text-xs text-zinc-100 dark:bg-zinc-900 leading-relaxed">
                {claudeDesktopConfig}
              </pre>
            </div>
          </div>

          {/* Guide 2: Cursor IDE */}
          <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex size-8 items-center justify-center rounded-lg bg-blue-500/10 text-blue-600 font-bold text-sm">
                  Cu
                </div>
                <div>
                  <h3 className="text-sm font-bold text-foreground">2. Cấu hình cho Cursor IDE</h3>
                  <p className="text-xs text-muted-foreground">Cấu hình MCP Server trực tiếp trong Cursor Settings</p>
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
              <li>Mở <strong>Cursor Settings</strong> (Ctrl + Shift + J hoặc Cmd + Shift + J) &rarr; chọn mục <strong>Features</strong> &rarr; <strong>MCP</strong>.</li>
              <li>Bấm nút <strong>+ Add New MCP Server</strong>.</li>
              <li>Đặt <strong>Name:</strong> <code>flama</code> | <strong>Type:</strong> <code>sse</code> hoặc <code>http</code>.</li>
              <li>Dán Server URL: <code>http://localhost:4790/v1/mcp/&lt;YOUR_MCP_TOKEN&gt;</code>.</li>
              <li>Nhấn <strong>Save</strong> để kết nối hoàn tất.</li>
            </ol>

            <pre className="overflow-x-auto rounded-xl bg-zinc-950 p-3.5 font-mono text-xs text-zinc-100 dark:bg-zinc-900 leading-relaxed">
              {cursorMcpConfig}
            </pre>
          </div>

          {/* Guide 3: Terminal / Curl */}
          <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex size-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 font-bold text-sm">
                  <Terminal className="size-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-foreground">3. Kiểm tra bằng Curl / Terminal</h3>
                  <p className="text-xs text-muted-foreground">Thử nghiệm gửi request JSON-RPC 2.0 trực tiếp từ command line</p>
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

          {/* Security Alert */}
          <Alert className="border-sky-500/30 bg-sky-50/50 dark:bg-sky-950/20 p-4 sm:p-5 rounded-2xl">
            <Info className="size-5 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
            <div className="space-y-1.5 min-w-0">
              <AlertTitle className="text-sky-900 dark:text-sky-200 font-bold text-xs sm:text-sm">
                Lưu ý về Dịch vụ Flama Connect (Port 4790)
              </AlertTitle>
              <AlertDescription className="text-xs text-sky-800 dark:text-sky-300 leading-relaxed">
                Đảm bảo tiến trình <strong>Flama Connect</strong> (chạy trên cổng <code>4790</code> qua file <code>connect_wsgi.py</code>) đang hoạt động song song với ứng dụng chính. Nếu bạn chạy trên môi trường production, Nginx sẽ tự động định tuyến các request <code>/v1/mcp</code> đến cổng 4790 với độ trễ thấp nhất.
              </AlertDescription>
            </div>
          </Alert>
        </CardContent>
      </Card>
    </TabsContent>
  )
}
