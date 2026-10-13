import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  ArrowRight,
  BookOpen,
  Check,
  Copy,
  HelpCircle,
  Laptop,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { McpToolsExplorer } from '@/features/guide/components/McpToolsExplorer'

export function McpGuideTab() {
  const { t } = useTranslation('mcp')
  const [copiedClaude, setCopiedClaude] = useState(false)
  const [copiedCursor, setCopiedCursor] = useState(false)
  const [copiedCurl, setCopiedCurl] = useState(false)

  const claudeConfigSnippet = JSON.stringify(
    {
      mcpServers: {
        flama: {
          command: 'npx',
          args: [
            '-y',
            'mcp-remote',
            'http://localhost:4790/v1/mcp',
            '--header',
            'Authorization: Bearer <YOUR_MCP_TOKEN>',
          ],
        },
      },
    },
    null,
    2
  )

  const cursorConfigSnippet = JSON.stringify(
    {
      mcpServers: {
        flama: {
          url: 'http://localhost:4790/v1/mcp',
          headers: {
            Authorization: 'Bearer <YOUR_MCP_TOKEN>',
          },
        },
      },
    },
    null,
    2
  )

  const curlTestSnippet = `curl -X POST http://localhost:4790/v1/mcp \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer <YOUR_MCP_TOKEN>" \\
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'`

  const copyToClipboard = async (text: string, type: 'claude' | 'cursor' | 'curl') => {
    try {
      await navigator.clipboard.writeText(text)
      if (type === 'claude') {
        setCopiedClaude(true)
        setTimeout(() => setCopiedClaude(false), 2000)
      } else if (type === 'cursor') {
        setCopiedCursor(true)
        setTimeout(() => setCopiedCursor(false), 2000)
      } else {
        setCopiedCurl(true)
        setTimeout(() => setCopiedCurl(false), 2000)
      }
      toast.success(t('docs_tab.copy_success'))
    } catch {
      toast.error(t('docs_tab.copy_error'))
    }
  }

  return (
    <div className="space-y-8">
      {/* 1. Client Configuration Snippets */}
      <Card className="border-border/60 shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0">
              <Laptop className="size-4 sm:size-4.5" />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg font-bold">
                {t('docs_tab.clients.title', 'Cấu hình Ứng dụng & IDE')}
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                {t('docs_tab.clients.subtitle', 'Chọn ứng dụng AI bạn sử dụng để lấy cấu hình kết nối chuẩn')}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0">
          <Tabs defaultValue="claude" className="w-full space-y-4">
            <TabsList className="grid grid-cols-3 max-w-md p-1 bg-muted/60 rounded-xl border">
              <TabsTrigger value="claude" className="text-xs font-semibold py-1.5">
                Claude Desktop
              </TabsTrigger>
              <TabsTrigger value="cursor" className="text-xs font-semibold py-1.5">
                Cursor & Windsurf
              </TabsTrigger>
              <TabsTrigger value="curl" className="text-xs font-semibold py-1.5">
                {t('docs_tab.clients.tabs.curl')}
              </TabsTrigger>
            </TabsList>

            {/* Claude Desktop Config */}
            <TabsContent value="claude" className="space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <span className="text-xs font-semibold text-foreground">
                  {t('docs_tab.clients.claude_desktop.config_label', 'Cấu hình claude_desktop_config.json:')}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(claudeConfigSnippet, 'claude')}
                  className="h-7 text-xs gap-1.5 self-start sm:self-center"
                >
                  {copiedClaude ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                  <span>{copiedClaude ? t('docs_tab.clients.copied') : t('docs_tab.clients.copy_json')}</span>
                </Button>
              </div>

              <div className="relative rounded-xl border border-border/60 bg-muted/40 p-3.5 font-mono text-xs overflow-x-auto text-foreground">
                <pre>{claudeConfigSnippet}</pre>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-muted-foreground pt-1">
                <div className="p-2.5 rounded-lg border border-border/40 bg-card">
                  <span className="font-semibold text-foreground block mb-0.5">Windows:</span>
                  <code className="text-[11px] text-primary break-all">
                    %APPDATA%\Claude\claude_desktop_config.json
                  </code>
                </div>
                <div className="p-2.5 rounded-lg border border-border/40 bg-card">
                  <span className="font-semibold text-foreground block mb-0.5">macOS:</span>
                  <code className="text-[11px] text-primary break-all">
                    ~/Library/Application Support/Claude/claude_desktop_config.json
                  </code>
                </div>
              </div>
            </TabsContent>

            {/* Cursor IDE Config */}
            <TabsContent value="cursor" className="space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <span className="text-xs font-semibold text-foreground">
                  {t('docs_tab.clients.cursor.config_label', 'Cấu hình Cursor mcpServers:')}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(cursorConfigSnippet, 'cursor')}
                  className="h-7 text-xs gap-1.5 self-start sm:self-center"
                >
                  {copiedCursor ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                  <span>{copiedCursor ? t('docs_tab.clients.copied') : t('docs_tab.clients.copy_json')}</span>
                </Button>
              </div>

              <div className="relative rounded-xl border border-border/60 bg-muted/40 p-3.5 font-mono text-xs overflow-x-auto text-foreground">
                <pre>{cursorConfigSnippet}</pre>
              </div>

              <div className="p-3 rounded-lg border border-border/40 bg-card space-y-1 text-xs text-muted-foreground">
                <span className="font-semibold text-foreground block">
                  {t('docs_tab.clients.cursor.guide_title')}
                </span>
                <p>
                  {t('docs_tab.clients.cursor.step1')}
                </p>
                <p>
                  {t('docs_tab.clients.cursor.step2')}
                </p>
              </div>
            </TabsContent>

            {/* cURL Test */}
            <TabsContent value="curl" className="space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <span className="text-xs font-semibold text-foreground">
                  {t('docs_tab.clients.curl.command_label')}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(curlTestSnippet, 'curl')}
                  className="h-7 text-xs gap-1.5 self-start sm:self-center"
                >
                  {copiedCurl ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                  <span>{copiedCurl ? t('docs_tab.clients.copied') : t('docs_tab.clients.copy_curl')}</span>
                </Button>
              </div>

              <div className="relative rounded-xl border border-border/60 bg-muted/40 p-3.5 font-mono text-xs overflow-x-auto text-foreground">
                <pre>{curlTestSnippet}</pre>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* 2. Embedded 19 Tools Catalog Explorer */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-base sm:text-lg font-bold text-foreground">
              {t('docs_tab.tools.title', 'Danh mục Công cụ & Prompts')}
            </h3>
            <p className="text-xs sm:text-sm text-muted-foreground">
              {t('docs_tab.tools.desc', 'Tra cứu danh mục công cụ Flashcard và các mẫu câu lệnh ra lệnh cho AI.')}
            </p>
          </div>
          <Link
            to="/guide/integrations/mcp-tools"
            className="text-xs text-primary hover:underline font-medium inline-flex items-center gap-1 shrink-0"
          >
            <span>{t('docs_tab.tools.view_catalog', 'Xem danh mục công cụ →')}</span>
          </Link>
        </div>

        {/* Embedded McpToolsExplorer */}
        <McpToolsExplorer />
      </div>

      {/* 3. Troubleshooting & Security Guardrails */}
      <Card className="border-border/60 shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0">
              <HelpCircle className="size-4 sm:size-4.5" />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg font-bold">
                {t('docs_tab.troubleshooting.title', 'Khắc phục Sự cố MCP')}
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm">
                {t('docs_tab.troubleshooting.desc', 'Xử lý các lỗi kết nối thường gặp, chứng chỉ SSL và kiểm tra kết nối.')}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-3.5 rounded-xl border border-border/60 bg-muted/20 space-y-1.5">
              <span className="text-xs font-bold text-foreground block">
                {t('docs_tab.guardrails.process_title')}
              </span>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('docs_tab.guardrails.process_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-border/60 bg-muted/20 space-y-1.5">
              <span className="text-xs font-bold text-foreground block">
                {t('docs_tab.guardrails.anti_scraping_title')}
              </span>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('docs_tab.guardrails.anti_scraping_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl border border-border/60 bg-muted/20 space-y-1.5">
              <span className="text-xs font-bold text-foreground block">
                {t('docs_tab.guardrails.privacy_title')}
              </span>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('docs_tab.guardrails.privacy_desc')}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <Link
              to="/guide/integrations/mcp-ai"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0 group-hover:scale-105 transition-transform">
                <BookOpen className="size-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    {t('page.docs_strip.card_ai.title', 'Cẩm nang kết nối MCP')}
                  </span>
                  <ArrowRight className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('page.docs_strip.card_ai.desc', 'Cấu hình Claude Desktop, Cursor IDE, Antigravity và kiểm tra lệnh cURL.')}
                </p>
              </div>
            </Link>

            <Link
              to="/guide/troubleshooting/mcp"
              className="group flex items-start gap-3 p-3.5 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/50 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0 group-hover:scale-105 transition-transform">
                <HelpCircle className="size-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                    {t('page.quick_troubleshooting', 'Khắc phục sự cố MCP')}
                  </span>
                  <ArrowRight className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('docs_tab.troubleshooting.desc', 'Xử lý các lỗi kết nối thường gặp, chứng chỉ SSL và kiểm tra kết nối.')}
                </p>
              </div>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
