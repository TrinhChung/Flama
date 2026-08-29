import { useState } from 'react'
import {
  BookOpen,
  Bot,
  Cpu,
  Flame,
  KeyRound,
  Wrench,
  Zap,
} from 'lucide-react'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'

import { useMcpTokenCRUD } from '../hooks/useMcpTokenCRUD'
import { McpAboutTab } from '../components/McpAboutTab'
import { McpTokensTab } from '../components/McpTokensTab'
import { McpGuideTab } from '../components/McpGuideTab'
import { McpToolsTab } from '../components/McpToolsTab'
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
              label="Hướng dẫn kết nối"
            />
          }
        />

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
              <div className="text-[11px] sm:text-xs font-semibold truncate">8 Flashcard Tools</div>
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
            <div className="p-2 sm:p-2.5 rounded-lg bg-muted text-muted-foreground shrink-0">
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
        {/* Responsive Horizontal Scroll Tab Bar */}
        <div className="overflow-x-auto pb-1 -mx-1 px-1 no-scrollbar">
          <TabsList className="inline-flex w-full sm:w-auto p-1 bg-muted/60 backdrop-blur-md rounded-2xl gap-1">
            <TabsTrigger
              value="tokens"
              className="flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all"
            >
              <KeyRound className="size-4 shrink-0" />
              <span className="hidden sm:inline">Quản lý Token (Claude / Cursor)</span>
              <span className="sm:hidden">Token</span>
            </TabsTrigger>
            <TabsTrigger
              value="oauth"
              className="flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all"
            >
              <Bot className="size-4 shrink-0" />
              <span className="hidden sm:inline">ChatGPT & OAuth 2.1 (Mới)</span>
              <span className="sm:hidden">ChatGPT</span>
            </TabsTrigger>
            <TabsTrigger
              value="about"
              className="flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all"
            >
              <Cpu className="size-4 shrink-0" />
              <span className="hidden sm:inline">MCP là gì?</span>
              <span className="sm:hidden">Tổng quan</span>
            </TabsTrigger>
            <TabsTrigger
              value="guide"
              className="flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all"
            >
              <BookOpen className="size-4 shrink-0" />
              <span className="hidden sm:inline">Hướng dẫn Cài đặt</span>
              <span className="sm:hidden">Hướng dẫn</span>
            </TabsTrigger>
            <TabsTrigger
              value="tools"
              className="flex-1 sm:flex-none px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-xl gap-1.5 transition-all"
            >
              <Wrench className="size-4 shrink-0" />
              <span className="hidden sm:inline">Danh mục 8 Công cụ & Prompts</span>
              <span className="sm:hidden">Công cụ</span>
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Tab Contents */}
        <McpTokensTab hookResult={hookResult} />
        <McpOAuthTab />
        <McpAboutTab />
        <McpGuideTab />
        <McpToolsTab />
      </Tabs>
    </Page>
  )
}

