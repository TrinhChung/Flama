import '@/shared/config/i18n'
import { ArrowLeft, FileCode2, Info, Pin } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { TemplateDistributionPanel } from '@/features/template-distribution'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'
import { useInstalledDeckTemplates } from '../hooks/useInstalledDeckTemplates'

export function InstallTemplatesPage() {
  const { t } = useTranslation('library')
  const { query, items, selected, selectTemplate, requestedMissing } = useInstalledDeckTemplates()

  return (
    <Page>
      <Button asChild variant="ghost" size="sm">
        <Link to="/installed-decks"><ArrowLeft className="size-4" />{t('install_templates.back')}</Link>
      </Button>
      <PageHeader title={t('install_templates.title')} description={t('install_templates.description')} />

      {query.isPending ? <PageLoading label={t('install_templates.loading')} /> : query.error ? (
        <div className="space-y-3">
          <PageError error={query.error} />
          <Button variant="outline" onClick={() => void query.refetch()}>{t('install_templates.retry')}</Button>
        </div>
      ) : (
        <>
          {query.data?.legacy_template_fallback && (
            <Alert className="border-amber-500/30 bg-amber-500/5">
              <Info aria-hidden="true" />
              <AlertDescription>{t('install_templates.legacy')}</AlertDescription>
            </Alert>
          )}
          {items.length === 0 ? (
            <EmptyState title={t('install_templates.empty_title')} description={t('install_templates.empty_description')}
              action={<Button asChild variant="outline"><Link to="/card-templates">{t('install_templates.open_library')}</Link></Button>} />
          ) : selected ? (
            <>
              {requestedMissing && <p role="status" className="text-sm text-muted-foreground">{t('install_templates.selection_missing')}</p>}
              <div className="grid items-start gap-6 lg:grid-cols-[minmax(14rem,19rem)_minmax(0,1fr)]">
                <nav aria-label={t('install_templates.list_label')} className="min-w-0 rounded-2xl border bg-card p-2 shadow-sm">
                  <ul className="space-y-1">
                    {items.map((item) => (
                      <li key={item.source_template_id}>
                        <button type="button" aria-current={item.source_template_id === selected.source_template_id ? 'true' : undefined}
                          onClick={() => selectTemplate(item.source_template_id)}
                          className="flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition-colors hover:bg-muted/60 aria-[current=true]:bg-primary/10 aria-[current=true]:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                          <FileCode2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                          <span className="min-w-0 space-y-1">
                            <span className="block break-words text-sm font-semibold">{item.template.name}</span>
                            <span className="block text-xs text-muted-foreground">{t('install_templates.local_copy')}</span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </nav>

                <section aria-label={selected.template.name} className="min-w-0 space-y-5">
                  <div className="rounded-2xl border bg-card p-4 sm:p-5 space-y-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 space-y-1">
                        <h2 className="break-words text-lg font-semibold">{selected.template.name}</h2>
                        <p className="text-sm text-muted-foreground">{t('install_templates.local_copy')}</p>
                      </div>
                      <Button asChild variant="outline" size="sm">
                        <Link to={`/card-templates/${encodeURIComponent(selected.local_template_id)}`}>{t('install_templates.edit_local')}</Link>
                      </Button>
                    </div>
                    {selected.template.description && <p className="break-words text-sm text-muted-foreground">{selected.template.description}</p>}
                    <div className="flex flex-wrap items-center gap-2 rounded-xl bg-muted/35 px-3 py-2.5 text-sm">
                      <Pin className="size-4 text-primary" aria-hidden="true" />
                      <span>{t('install_templates.pinned_release')}</span>
                      <Badge variant="outline">{selected.pinned_release?.version_label || t('install_templates.pin_unavailable')}</Badge>
                    </div>
                    <p className="text-sm leading-relaxed text-muted-foreground">{t('install_templates.copy_impact')}</p>
                  </div>
                  <TemplateDistributionPanel key={selected.local_template_id} templateId={selected.local_template_id} origin="market_copy"
                    currentVersionId={selected.current_version_id} onSourceChanged={() => { void query.refetch() }} />
                </section>
              </div>
            </>
          ) : null}
        </>
      )}
    </Page>
  )
}
