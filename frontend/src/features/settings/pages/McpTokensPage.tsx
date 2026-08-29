import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  Bot,
  Flame,
  KeyRound,
  MousePointerClick,
  Wrench,
  Zap,
} from 'lucide-react'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'

import { useMcpTokenCRUD } from '../hooks/useMcpTokenCRUD'
import { McpTokensTab } from '../components/McpTokensTab'
import { McpOAuthTab } from '../components/McpOAuthTab'

export function McpTokensPage() {
  const [activeTab, setActiveTab] = useState('tokens')
  const hookResult = useMcpTokenCRUD()
  const { query } = hookResult

  if (query.isPending) return <PageLoading label="Đang tải MCP tokens…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-6 sm:space-y-8 pb-12 px-3 sm:px-6">
      {/* Header & Feature Highlights Bar */}
      <div className="space-y-4 sm:space-y-6">
        <PageHeader
          title="Kết nối AI qua Model Context Protocol (MCP)"
          description="Tích hợp ChatGPT, Claude Desktop, Cursor và các trợ lý AI với kho Flashcard Flama để tự động tra cứu, tạo thẻ và ôn tập."
          actions={
            <ContextHelpButton
              guidePath="/guide/integrations/mcp-ai"
              guideTitle="Hướng dẫn kết nối trợ lý AI qua MCP"
              troubleshootPath="/guide/troubleshooting/mcp"
              troubleshootTitle="Khắc phục sự cố MCP"
              label="Hướng dẫn kết nối"
            />
          }
        />

        {/* Top Quick Explanatory Links */}
        <div className="flex flex-wrap items-center gap-2 pt-0.5 text-xs">
          <span className="text-muted-foreground font-medium text-[11px]">Tra cứu nhanh:</span>
          <Link
            to="/guide/integrations/mcp-ai"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-purple-500/10 hover:border-purple-500/40 hover:text-purple-600 dark:hover:text-purple-400 transition-all font-medium text-[11px]"
          >
            <Bot className="size-3 text-purple-500" />
            <span>Cẩm nang kết nối Claude/Cursor/ChatGPT</span>
          </Link>
          <Link
            to="/guide/integrations/mcp-tools"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-amber-500/10 hover:border-amber-500/40 hover:text-amber-600 dark:hover:text-amber-400 transition-all font-medium text-[11px]"
          >
            <Wrench className="size-3 text-amber-500" />
            <span>Danh mục 20 Công cụ & Prompts AI</span>
          </Link>
          <Link
            to="/guide/troubleshooting/mcp"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-sky-500/10 hover:border-sky-500/40 hover:text-sky-600 dark:hover:text-sky-400 transition-all font-medium text-[11px]"
          >
            <Zap className="size-3 text-sky-500" />
            <span>Khắc phục sự cố MCP</span>
          </Link>
        </div>

        {/* Quick Highlights Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3">
          <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-xs shadow-2xs">
            <div className="p-2 sm:p-2.5 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 shrink-0">
              <Bot className="size-4.5 sm:size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] sm:text-xs font-semibold truncate">AI Chat 2 chiều</div>
              <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">ChatGPT, Claude, Cursor</div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-xs shadow-2xs">
            <div className="p-2 sm:p-2.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0">
              <Zap className="size-4.5 sm:size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] sm:text-xs font-semibold truncate">20 Flashcard Tools</div>
              <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">Tạo thẻ, tìm kiếm, due</div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-xs shadow-2xs">
            <div className="p-2 sm:p-2.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
              <KeyRound className="size-4.5 sm:size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] sm:text-xs font-semibold truncate">Token Dài hạn</div>
              <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">Vĩnh viễn hoặc tự chọn</div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3 p-3 sm:p-3.5 rounded-xl border bg-card/60 backdrop-blur-xs shadow-2xs">
            <div className="p-2 sm:p-2.5 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0">
              <Flame className="size-4.5 sm:size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] sm:text-xs font-semibold truncate">OAuth 2.1 PKCE</div>
              <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">ChatGPT Connectors</div>
            </div>
          </div>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full space-y-6">
        {/* Clean 2-Tab Bar */}
        <div className="overflow-x-auto pb-1 -mx-1 px-1 no-scrollbar">
          <TabsList className="inline-flex w-full sm:w-auto p-1 bg-muted/60 backdrop-blur-md rounded-2xl gap-1">
            <TabsTrigger
              value="tokens"
              className="flex-1 sm:flex-none px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all"
            >
              <KeyRound className="size-4 shrink-0" />
              <span>Quản lý Token (Claude / Cursor / Antigravity)</span>
            </TabsTrigger>
            <TabsTrigger
              value="oauth"
              className="flex-1 sm:flex-none px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all"
            >
              <Bot className="size-4 shrink-0" />
              <span>ChatGPT & OAuth 2.1 (Mới)</span>
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Operational Tab Contents */}
        <McpTokensTab hookResult={hookResult} />
        <McpOAuthTab />
      </Tabs>

      {/* Contextual Reference / Documentation Strip */}
      <div className="rounded-2xl border bg-card/60 p-4 sm:p-5 space-y-3 shadow-2xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            <BookOpen className="size-3.5 text-primary" />
            <span>Tài liệu & Hướng dẫn tham chiếu MCP</span>
          </div>
          <Link
            to="/guide/integrations/mcp-ai"
            className="text-xs text-primary hover:underline font-medium flex items-center gap-1"
          >
            <span>Xem tất cả</span>
            <ArrowRight className="size-3" />
          </Link>
        </div>

        <div className="grid gap-2 sm:grid-cols-3 pt-1">
          <Link
            to="/guide/integrations/mcp-ai"
            className="group flex items-start gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors"
          >
            <div className="p-2 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
              <Bot className="size-4" />
            </div>
            <div className="min-w-0 space-y-0.5">
              <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors flex items-center gap-1">
                <span>Cẩm nang kết nối MCP</span>
                <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-purple-500" />
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Cấu hình Claude Desktop, Cursor IDE, Antigravity và kiểm tra lệnh cURL.
              </p>
            </div>
          </Link>

          <Link
            to="/guide/integrations/mcp-tools"
            className="group flex items-start gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors"
          >
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
              <Wrench className="size-4" />
            </div>
            <div className="min-w-0 space-y-0.5">
              <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors flex items-center gap-1">
                <span>Danh mục Công cụ & Prompts</span>
                <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-amber-500" />
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Tra cứu 20 công cụ Flashcard và các câu lệnh mẫu ra lệnh cho AI.
              </p>
            </div>
          </Link>

          <Link
            to="/guide/integrations/yomitan"
            className="group flex items-start gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors"
          >
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
              <MousePointerClick className="size-4" />
            </div>
            <div className="min-w-0 space-y-0.5">
              <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                <span>Tiện ích Yomitan 1-Click</span>
                <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-primary" />
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Tự động khai thác từ vựng khi đọc báo, manga trực tiếp trên trình duyệt.
              </p>
            </div>
          </Link>
        </div>
      </div>
    </Page>
  )
}
