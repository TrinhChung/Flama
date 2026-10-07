import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import {
  ArrowRight,
  BookOpen,
  Bot,
  HelpCircle,
  KeyRound,
  MousePointerClick,
  Wrench,
} from 'lucide-react'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'

import { useMcpTokenCRUD } from '../hooks/useMcpTokenCRUD'
import { McpTokensTab } from '../components/McpTokensTab'
import { McpOAuthTab } from '../components/McpOAuthTab'

export function McpTokensPage() {
  const { t } = useTranslation('mcp')
  const [activeTab, setActiveTab] = useState('chatgpt')
  const hookResult = useMcpTokenCRUD()
  const { query } = hookResult

  if (query.isPending) return <PageLoading label={t('page.loading')} />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-6 sm:space-y-8 pb-12 px-3 sm:px-6">
      {/* Header & Feature Navigation */}
      <div className="space-y-4">
        <PageHeader
          title={t('page.title')}
          description={t('page.description')}
          actions={
            <ContextHelpButton
              guidePath="/guide/integrations/mcp-ai"
              guideTitle={t('page.connect_guide_title')}
              troubleshootPath="/guide/troubleshooting/mcp"
              troubleshootTitle={t('page.troubleshoot_title')}
              label={t('page.connect_guide_btn')}
            />
          }
        />

        {/* Top Quick Explanatory Links - Swipeable on mobile */}
        <div className="flex items-center gap-2 pt-0.5 text-xs overflow-x-auto no-scrollbar pb-1 -mx-1 px-1 sm:mx-0 sm:px-0 sm:flex-wrap">
          <span className="text-muted-foreground font-medium text-[11px] shrink-0">{t('page.quick_links_label')}</span>
          <Link
            to="/guide/integrations/mcp-ai"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-purple-500/10 hover:border-purple-500/40 hover:text-purple-600 dark:hover:text-purple-400 transition-all font-medium text-[11px] shrink-0 whitespace-nowrap"
          >
            <Bot className="size-3 text-purple-500" />
            <span>{t('page.quick_guide_ai')}</span>
          </Link>
          <Link
            to="/guide/integrations/mcp-tools"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-amber-500/10 hover:border-amber-500/40 hover:text-amber-600 dark:hover:text-amber-400 transition-all font-medium text-[11px] shrink-0 whitespace-nowrap"
          >
            <Wrench className="size-3 text-amber-500" />
            <span>{t('page.quick_tools_prompts')}</span>
          </Link>
          <Link
            to="/guide/troubleshooting/mcp"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-sky-500/10 hover:border-sky-500/40 hover:text-sky-600 dark:hover:text-sky-400 transition-all font-medium text-[11px] shrink-0 whitespace-nowrap"
          >
            <HelpCircle className="size-3 text-sky-500" />
            <span>{t('page.quick_troubleshooting')}</span>
          </Link>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full space-y-6">
        {/* Prominent, Card-Style High-Visibility Tabs */}
        <TabsList
          style={{ height: 'auto' }}
          className="grid w-full grid-cols-1 lg:grid-cols-2 p-1.5 bg-muted/50 rounded-2xl border gap-2 shadow-2xs"
        >
          {/* Tab 1: ChatGPT (Primary) */}
          <TabsTrigger
            value="chatgpt"
            style={{ height: 'auto' }}
            className="flex items-start sm:items-center justify-between gap-3 p-3 sm:p-4 text-left rounded-xl data-[state=active]:bg-card data-[state=active]:shadow-xs data-[state=active]:border-emerald-500/40 dark:data-[state=active]:border-emerald-500/50 data-[state=active]:ring-1 data-[state=active]:ring-emerald-500/20 border border-transparent transition-all whitespace-normal after:hidden"
          >
            <div className="flex items-center gap-3 min-w-0 w-full">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                <Bot className="size-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground truncate">{t('page.tabs.chatgpt.title')}</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25 shrink-0">
                    {t('page.tabs.chatgpt.badge')}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 sm:line-clamp-1">
                  {t('page.tabs.chatgpt.desc')}
                </p>
              </div>
            </div>
          </TabsTrigger>

          {/* Tab 2: Tokens & Permissions (Developer / IDE) */}
          <TabsTrigger
            value="tokens"
            style={{ height: 'auto' }}
            className="flex items-start sm:items-center justify-between gap-3 p-3 sm:p-4 text-left rounded-xl data-[state=active]:bg-card data-[state=active]:shadow-xs data-[state=active]:border-sky-500/40 dark:data-[state=active]:border-sky-500/50 data-[state=active]:ring-1 data-[state=active]:ring-sky-500/20 border border-transparent transition-all whitespace-normal after:hidden"
          >
            <div className="flex items-center gap-3 min-w-0 w-full">
              <div className="p-2.5 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400 shrink-0">
                <KeyRound className="size-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground truncate">{t('page.tabs.tokens.title')}</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground border shrink-0">
                    {t('page.tabs.tokens.badge')}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 sm:line-clamp-1">
                  {t('page.tabs.tokens.desc')}
                </p>
              </div>
            </div>
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: ChatGPT Onboarding & OAuth 2.1 */}
        <McpOAuthTab tabValue="chatgpt" />

        {/* Tab 2: Token Management & Permissions */}
        <McpTokensTab hookResult={hookResult} onSwitchToChatGPT={() => setActiveTab('chatgpt')} />
      </Tabs>

      {/* Contextual Reference / Documentation Strip */}
      <div className="rounded-2xl border bg-card/60 p-4 sm:p-5 space-y-3 shadow-2xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            <BookOpen className="size-3.5 text-primary" />
            <span>{t('page.docs_strip.title')}</span>
          </div>
          <Link
            to="/guide/integrations/mcp-ai"
            className="text-xs text-primary hover:underline font-medium flex items-center gap-1"
          >
            <span>{t('page.docs_strip.view_all')}</span>
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
                <span>{t('page.docs_strip.card_ai.title')}</span>
                <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-purple-500" />
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('page.docs_strip.card_ai.desc')}
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
                <span>{t('page.docs_strip.card_tools.title')}</span>
                <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-amber-500" />
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('page.docs_strip.card_tools.desc')}
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
                <span>{t('page.docs_strip.card_yomitan.title')}</span>
                <ArrowRight className="size-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-primary" />
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('page.docs_strip.card_yomitan.desc')}
              </p>
            </div>
          </Link>
        </div>
      </div>
    </Page>
  )
}
