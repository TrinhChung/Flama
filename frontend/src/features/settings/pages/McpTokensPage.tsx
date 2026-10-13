import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import {
  BookOpen,
  Bot,
  KeyRound,
  MessagesSquare,
  Search,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'

import { useMcpTokenCRUD } from '../hooks/useMcpTokenCRUD'
import { McpTokensTab } from '../components/McpTokensTab'
import { McpOAuthTab } from '../components/McpOAuthTab'
import { McpValueIntro } from '../components/mcp/McpValueIntro'
import { McpGuideTab } from '../components/mcp/McpGuideTab'

export function McpTokensPage() {
  const { t } = useTranslation('mcp')
  const [activeTab, setActiveTabState] = useState<'overview' | 'tokens' | 'guide'>('overview')
  const [setupMode, setSetupMode] = useState<'chatgpt' | 'tokens'>('chatgpt')
  const hookResult = useMcpTokenCRUD()
  const { query } = hookResult

  const setActiveTab = (tab: string) => {
    if (tab === 'tokens' || tab === 'setup') {
      setActiveTabState('tokens')
    } else if (tab === 'guide' || tab === 'docs') {
      setActiveTabState('guide')
    } else {
      setActiveTabState('overview')
    }
  }

  if (query.isPending) return <PageLoading label={t('page.loading')} />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-6 sm:space-y-8 pb-12 px-3 sm:px-6">
      {/* Header & Feature Help Action */}
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

      {/* 3-Tab Segmented Card System */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full space-y-6">
        <TabsList
          style={{ height: 'auto' }}
          className="grid w-full grid-cols-1 md:grid-cols-3 p-1 bg-muted/60 rounded-xl border gap-1"
        >
          {/* Tab 1: Khám phá & Công dụng (Primary / Default) */}
          <TabsTrigger
            value="overview"
            style={{ height: 'auto' }}
            className="group flex items-start sm:items-center justify-between gap-3 p-3 sm:p-4 text-left rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-xs data-[state=active]:border-primary/40 border border-transparent transition-colors whitespace-normal after:hidden"
          >
            <div className="flex items-center gap-3 min-w-0 w-full">
              <Bot className="size-5 text-muted-foreground group-data-[state=active]:text-primary shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground truncate">{t('page.tabs.overview.title')}</span>
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-primary/10 text-primary shrink-0">
                    {t('page.tabs.overview.badge')}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 sm:line-clamp-1">
                  {t('page.tabs.overview.desc')}
                </p>
              </div>
            </div>
          </TabsTrigger>

          {/* Tab 2: Cài đặt & Kết nối */}
          <TabsTrigger
            value="tokens"
            style={{ height: 'auto' }}
            className="group flex items-start sm:items-center justify-between gap-3 p-3 sm:p-4 text-left rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-xs data-[state=active]:border-primary/40 border border-transparent transition-colors whitespace-normal after:hidden"
          >
            <div className="flex items-center gap-3 min-w-0 w-full">
              <KeyRound className="size-5 text-muted-foreground group-data-[state=active]:text-primary shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground truncate">{t('page.tabs.setup.title')}</span>
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-muted text-muted-foreground shrink-0">
                    {t('page.tabs.setup.badge')}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 sm:line-clamp-1">
                  {t('page.tabs.setup.desc')}
                </p>
              </div>
            </div>
          </TabsTrigger>

          {/* Tab 3: Hướng dẫn & Tra cứu */}
          <TabsTrigger
            value="guide"
            style={{ height: 'auto' }}
            className="group flex items-start sm:items-center justify-between gap-3 p-3 sm:p-4 text-left rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-xs data-[state=active]:border-primary/40 border border-transparent transition-colors whitespace-normal after:hidden"
          >
            <div className="flex items-center gap-3 min-w-0 w-full">
              <BookOpen className="size-5 text-muted-foreground group-data-[state=active]:text-primary shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground truncate">{t('page.tabs.docs.title')}</span>
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-muted text-muted-foreground shrink-0">
                    {t('page.tabs.docs.badge')}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 sm:line-clamp-1">
                  {t('page.tabs.docs.desc')}
                </p>
              </div>
            </div>
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Khám phá & Công dụng (Overview + 3 Pillars + CTA) */}
        <TabsContent value="overview" className="space-y-6">
          <McpValueIntro onStartSetup={() => setActiveTab('tokens')} showToggle={false} />

          {/* 3 Core Value Pillar Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4">
            <div className="flex items-start gap-3 p-3.5 sm:p-4 rounded-xl border border-border/60 bg-card shadow-2xs">
              <div className="p-2 sm:p-2.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0">
                <Search className="size-4.5 sm:size-5" />
              </div>
              <div className="min-w-0 space-y-1">
                <div className="text-xs sm:text-sm font-semibold text-foreground">
                  {t('page.pillars.marketplace.title')}
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('page.pillars.marketplace.desc')}
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 sm:p-4 rounded-xl border border-border/60 bg-card shadow-2xs">
              <div className="p-2 sm:p-2.5 rounded-lg bg-primary/10 text-primary shrink-0">
                <Zap className="size-4.5 sm:size-5" />
              </div>
              <div className="min-w-0 space-y-1">
                <div className="text-xs sm:text-sm font-semibold text-foreground">
                  {t('page.pillars.one_click.title')}
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('page.pillars.one_click.desc')}
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 sm:p-4 rounded-xl border border-border/60 bg-card shadow-2xs">
              <div className="p-2 sm:p-2.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                <ShieldCheck className="size-4.5 sm:size-5" />
              </div>
              <div className="min-w-0 space-y-1">
                <div className="text-xs sm:text-sm font-semibold text-foreground">
                  {t('page.pillars.privacy.title')}
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {t('page.pillars.privacy.desc')}
                </p>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Tab 2: Cài đặt & Kết nối (Consolidating Personal Tokens & ChatGPT OAuth) */}
        <TabsContent value="tokens" className="space-y-6">
          <Tabs value={setupMode} onValueChange={(val) => setSetupMode(val as any)} className="w-full space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/60 pb-3">
              <div className="space-y-0.5">
                <h3 className="text-sm sm:text-base font-bold text-foreground">
                  {t('page.tabs.setup.mode_title')}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {t('page.tabs.setup.mode_desc')}
                </p>
              </div>

              <TabsList className="grid grid-cols-2 max-w-xs p-1 bg-muted/60 rounded-xl border shrink-0">
                <TabsTrigger value="chatgpt" className="text-xs font-semibold py-1.5 gap-1.5">
                  <MessagesSquare className="size-3.5" />
                  <span>{t('page.tabs.chatgpt.title')}</span>
                </TabsTrigger>
                <TabsTrigger value="tokens" className="text-xs font-semibold py-1.5 gap-1.5">
                  <KeyRound className="size-3.5" />
                  <span>{t('page.tabs.tokens.title')}</span>
                </TabsTrigger>
              </TabsList>
            </div>

            {/* Sub-tab 1: ChatGPT Onboarding & OAuth 2.1 */}
            <McpOAuthTab tabValue="chatgpt" />

            {/* Sub-tab 2: Token Management & Permissions */}
            <McpTokensTab hookResult={hookResult} onSwitchToChatGPT={() => setSetupMode('chatgpt')} />
          </Tabs>
        </TabsContent>

        {/* Tab 3: Hướng dẫn & Tra cứu (Config JSON, Tools Explorer, Troubleshooting) */}
        <TabsContent value="guide" className="space-y-6">
          <McpGuideTab />
        </TabsContent>
      </Tabs>
    </Page>
  )
}
