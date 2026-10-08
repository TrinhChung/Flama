import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { BookOpen, Code, HelpCircle } from 'lucide-react'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'

import { useYomitanTokenCRUD } from '../hooks/useYomitanTokenCRUD'
import { YomitanTokensTab } from '../components/YomitanTokensTab'
import { YomitanFeatureHighlights } from '../components/yomitan/YomitanFeatureHighlights'
import { YomitanDocumentationSection } from '../components/yomitan/YomitanDocumentationSection'

export function YomitanTokensPage() {
  const { t } = useTranslation('settings')
  const hookResult = useYomitanTokenCRUD()
  const { query } = hookResult

  if (query.isPending) return <PageLoading label={t('yomitan.loading')} />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-6 sm:space-y-8 pb-12 px-3 sm:px-6">
      {/* Header & Feature Highlights Bar */}
      <div className="space-y-4 sm:space-y-6">
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

        {/* Top Quick Explanatory Links */}
        <div className="flex flex-wrap items-center gap-2 pt-0.5 text-xs">
          <span className="text-muted-foreground font-medium text-[11px]">{t('yomitan.quick_links.label')}</span>
          <Link
            to="/guide/integrations/yomitan"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-sky-500/10 hover:border-sky-500/40 hover:text-sky-600 dark:hover:text-sky-400 transition-all font-medium text-[11px]"
          >
            <BookOpen className="size-3 text-sky-500" />
            <span>{t('yomitan.quick_links.install')}</span>
          </Link>
          <Link
            to="/guide/integrations/yomitan-markers"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-purple-500/10 hover:border-purple-500/40 hover:text-purple-600 dark:hover:text-purple-400 transition-all font-medium text-[11px]"
          >
            <Code className="size-3 text-purple-500" />
            <span>{t('yomitan.quick_links.markers')}</span>
          </Link>
          <Link
            to="/guide/troubleshooting/yomitan"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-amber-500/10 hover:border-amber-500/40 hover:text-amber-600 dark:hover:text-amber-400 transition-all font-medium text-[11px]"
          >
            <HelpCircle className="size-3 text-amber-500" />
            <span>{t('yomitan.quick_links.mobile')}</span>
          </Link>
        </div>

        {/* Quick Highlights Bar */}
        <YomitanFeatureHighlights />
      </div>

      {/* Main Token Management Component */}
      <YomitanTokensTab hookResult={hookResult} />

      {/* Contextual Reference / Documentation Strip */}
      <YomitanDocumentationSection />
    </Page>
  )
}
