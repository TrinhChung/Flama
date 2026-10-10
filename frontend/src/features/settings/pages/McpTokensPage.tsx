import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import {
  ArrowRight,
  BookOpen,
  KeyRound,
  LifeBuoy,
  MessagesSquare,
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
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border bg-card text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors font-medium text-[11px] shrink-0 whitespace-nowrap"
          >
            <BookOpen className="size-3" />
            <span>{t('page.quick_guide_ai')}</span>
          </Link>
          <Link
            to="/guide/integrations/mcp-tools"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border bg-card text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors font-medium text-[11px] shrink-0 whitespace-nowrap"
          >
            <Wrench className="size-3" />
            <span>{t('page.quick_tools_prompts')}</span>
          </Link>
          <Link
            to="/guide/troubleshooting/mcp"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border bg-card text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors font-medium text-[11px] shrink-0 whitespace-nowrap"
          >
            <LifeBuoy className="size-3" />
            <span>{t('page.quick_troubleshooting')}</span>
          </Link>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full space-y-6">
        <TabsList
          style={{ height: 'auto' }}
          className="grid w-full grid-cols-1 lg:grid-cols-2 p-1 bg-muted/60 rounded-xl border gap-1"
        >
          {/* Tab 1: ChatGPT (Primary) */}
          <TabsTrigger
            value="chatgpt"
            style={{ height: 'auto' }}
            className="group flex items-start sm:items-center justify-between gap-3 p-3 sm:p-4 text-left rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-xs data-[state=active]:border-primary/40 border border-transparent transition-colors whitespace-normal after:hidden"
          >
            <div className="flex items-center gap-3 min-w-0 w-full">
              <MessagesSquare className="size-5 text-muted-foreground group-data-[state=active]:text-primary shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground truncate">{t('page.tabs.chatgpt.title')}</span>
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-primary/10 text-primary shrink-0">
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
            className="group flex items-start sm:items-center justify-between gap-3 p-3 sm:p-4 text-left rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-xs data-[state=active]:border-primary/40 border border-transparent transition-colors whitespace-normal after:hidden"
          >
            <div className="flex items-center gap-3 min-w-0 w-full">
              <KeyRound className="size-5 text-muted-foreground group-data-[state=active]:text-primary shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground truncate">{t('page.tabs.tokens.title')}</span>
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-muted text-muted-foreground shrink-0">
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
      <div className="rounded-xl border bg-card p-4 sm:p-5 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            {t('page.docs_strip.title')}
          </span>
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
            className="group flex items-start gap-3 p-3 rounded-lg hover:bg-muted/60 transition-colors"
          >
            <BookOpen className="size-4 text-muted-foreground shrink-0 mt-0.5" />
            <div className="min-w-0 space-y-0.5">
              <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                {t('page.docs_strip.card_ai.title')}
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('page.docs_strip.card_ai.desc')}
              </p>
            </div>
          </Link>

          <Link
            to="/guide/integrations/mcp-tools"
            className="group flex items-start gap-3 p-3 rounded-lg hover:bg-muted/60 transition-colors"
          >
            <Wrench className="size-4 text-muted-foreground shrink-0 mt-0.5" />
            <div className="min-w-0 space-y-0.5">
              <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                {t('page.docs_strip.card_tools.title')}
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('page.docs_strip.card_tools.desc')}
              </p>
            </div>
          </Link>

          <Link
            to="/guide/integrations/yomitan"
            className="group flex items-start gap-3 p-3 rounded-lg hover:bg-muted/60 transition-colors"
          >
            <MousePointerClick className="size-4 text-muted-foreground shrink-0 mt-0.5" />
            <div className="min-w-0 space-y-0.5">
              <div className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                {t('page.docs_strip.card_yomitan.title')}
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
