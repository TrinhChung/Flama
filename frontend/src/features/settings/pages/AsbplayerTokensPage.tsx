import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { BookOpen, Layers, Zap } from 'lucide-react'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'

import { useAsbplayerTokenCRUD } from '../hooks/useAsbplayerTokenCRUD'
import { AsbplayerTokensTab } from '../components/AsbplayerTokensTab'
import { AsbplayerFeatureHighlights } from '../components/asbplayer/AsbplayerFeatureHighlights'
import { AsbplayerDocumentationSection } from '../components/asbplayer/AsbplayerDocumentationSection'

export function AsbplayerTokensPage() {
  const { t } = useTranslation('settings')
  const hookResult = useAsbplayerTokenCRUD()
  const { query } = hookResult

  if (query.isPending) return <PageLoading label={t('asbplayer.loading')} />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="max-w-7xl mx-auto space-y-6 sm:space-y-8 pb-12 px-3 sm:px-6">
      {/* Header & Feature Highlights Bar */}
      <div className="space-y-4 sm:space-y-6">
        <PageHeader
          title={t('asbplayer.header.title')}
          description={t('asbplayer.header.description')}
          actions={
            <ContextHelpButton
              guidePath="/guide/integrations/asbplayer"
              guideTitle={t('asbplayer.header.guide_title')}
              troubleshootPath="/guide/troubleshooting/asbplayer"
              troubleshootTitle={t('asbplayer.header.troubleshoot_title')}
              label={t('asbplayer.header.guide_btn')}
            />
          }
        />

        {/* Top Quick Explanatory Links */}
        <div className="flex flex-wrap items-center gap-2 pt-0.5 text-xs">
          <span className="text-muted-foreground font-medium text-[11px]">{t('asbplayer.quick_links.label')}</span>
          <Link
            to="/guide/integrations/asbplayer"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-sky-500/10 hover:border-sky-500/40 hover:text-sky-600 dark:hover:text-sky-400 transition-all font-medium text-[11px]"
          >
            <BookOpen className="size-3 text-sky-500" />
            <span>{t('asbplayer.quick_links.install')}</span>
          </Link>
          <Link
            to="/guide/integrations/asbplayer#mapping"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-purple-500/10 hover:border-purple-500/40 hover:text-purple-600 dark:hover:text-purple-400 transition-all font-medium text-[11px]"
          >
            <Layers className="size-3 text-purple-500" />
            <span>{t('asbplayer.quick_links.mapping')}</span>
          </Link>
          <Link
            to="/guide/integrations/asbplayer#shortcuts"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/40 hover:bg-amber-500/10 hover:border-amber-500/40 hover:text-amber-600 dark:hover:text-amber-400 transition-all font-medium text-[11px]"
          >
            <Zap className="size-3 text-amber-500" />
            <span>{t('asbplayer.quick_links.shortcuts')}</span>
          </Link>
        </div>

        {/* Quick Highlights Bar */}
        <AsbplayerFeatureHighlights />
      </div>

      {/* Main Token Management Component */}
      <AsbplayerTokensTab hookResult={hookResult} />

      {/* Contextual Reference / Documentation Strip */}
      <AsbplayerDocumentationSection />
    </Page>
  )
}
