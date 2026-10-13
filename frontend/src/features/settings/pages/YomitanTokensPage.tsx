import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { BookOpen, BookOpenCheck, KeyRound } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'

import { useYomitanTokenCRUD } from '../hooks/useYomitanTokenCRUD'
import { YomitanTokensTab } from '../components/YomitanTokensTab'
import { YomitanFeatureHighlights } from '../components/yomitan/YomitanFeatureHighlights'
import { YomitanValueIntro } from '../components/yomitan/YomitanValueIntro'
import { YomitanGuideTab } from '../components/yomitan/YomitanGuideTab'

export function YomitanTokensPage() {
  const { t } = useTranslation('settings')
  const [activeTab, setActiveTab] = useState('overview')
  const hookResult = useYomitanTokenCRUD()
  const { query } = hookResult

  if (query.isPending) return <PageLoading label={t('yomitan.loading')} />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-6 sm:space-y-8 pb-12 px-3 sm:px-6">
      {/* Header & Help Action */}
      <PageHeader
        title={t('yomitan.header.title')}
        description={t('yomitan.header.description')}
        actions={
          <ContextHelpButton
            guidePath="/guide/integrations/yomitan"
            guideTitle={t('yomitan.header.guide_title')}
            troubleshootPath="/guide/troubleshooting/yomitan"
            troubleshootTitle={t('yomitan.header.troubleshoot_title')}
            label={t('yomitan.header.guide_btn')}
          />
        }
      />

      {/* Segmented Card Tabs: Khám phá vs Cài đặt vs Hướng dẫn */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full space-y-6">
        <TabsList
          style={{ height: 'auto' }}
          className="grid w-full grid-cols-1 md:grid-cols-3 p-1 bg-muted/60 rounded-xl border gap-1"
        >
          {/* Tab 1: Công dụng & Khám phá (Primary / Default) */}
          <TabsTrigger
            value="overview"
            style={{ height: 'auto' }}
            className="group flex items-start sm:items-center justify-between gap-3 p-3 sm:p-4 text-left rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-xs data-[state=active]:border-primary/40 border border-transparent transition-colors whitespace-normal after:hidden"
          >
            <div className="flex items-center gap-3 min-w-0 w-full">
              <BookOpenCheck className="size-5 text-muted-foreground group-data-[state=active]:text-primary shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground truncate">{t('yomitan.tabs.overview.title')}</span>
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-primary/10 text-primary shrink-0">
                    {t('yomitan.tabs.overview.badge')}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 sm:line-clamp-1">
                  {t('yomitan.tabs.overview.desc')}
                </p>
              </div>
            </div>
          </TabsTrigger>

          {/* Tab 2: Cài đặt & Quản lý Token */}
          <TabsTrigger
            value="tokens"
            style={{ height: 'auto' }}
            className="group flex items-start sm:items-center justify-between gap-3 p-3 sm:p-4 text-left rounded-lg data-[state=active]:bg-card data-[state=active]:shadow-xs data-[state=active]:border-primary/40 border border-transparent transition-colors whitespace-normal after:hidden"
          >
            <div className="flex items-center gap-3 min-w-0 w-full">
              <KeyRound className="size-5 text-muted-foreground group-data-[state=active]:text-primary shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground truncate">{t('yomitan.tabs.tokens.title')}</span>
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-muted text-muted-foreground shrink-0">
                    {t('yomitan.tabs.tokens.badge')}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 sm:line-clamp-1">
                  {t('yomitan.tabs.tokens.desc')}
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
                  <span className="text-sm font-bold text-foreground truncate">{t('yomitan.tabs.docs.title')}</span>
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-muted text-muted-foreground shrink-0">
                    {t('yomitan.tabs.docs.badge')}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 sm:line-clamp-1">
                  {t('yomitan.tabs.docs.desc')}
                </p>
              </div>
            </div>
          </TabsTrigger>
        </TabsList>

        {/* Tab 1 Content: Công dụng & Cách hoạt động */}
        <TabsContent value="overview" className="space-y-6">
          <YomitanValueIntro onStartSetup={() => setActiveTab('tokens')} showToggle={false} />
          <YomitanFeatureHighlights />
        </TabsContent>

        {/* Tab 2 Content: Cài đặt & Quản lý Token */}
        <TabsContent value="tokens" className="space-y-6">
          <YomitanTokensTab hookResult={hookResult} />
        </TabsContent>

        {/* Tab 3 Content: Hướng dẫn & Tra cứu */}
        <TabsContent value="guide" className="space-y-6">
          <YomitanGuideTab />
        </TabsContent>
      </Tabs>
    </Page>
  )
}
