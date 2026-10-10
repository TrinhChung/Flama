import '@/shared/config/i18n'
import { useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cardTemplateQueryKeys, fetchTemplateLibrary, type TemplateLibraryGroup, type TemplateLibraryParams } from '@/entities/card-template'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { SearchInput, FilterPillGroup } from '@/shared/ui'
import { CreateTemplateDialog } from '../components/CreateTemplateDialog'

export function TemplateLibraryPage() {
  const { t } = useTranslation('card_templates')
  const { t: commonT } = useTranslation('common')
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [composing, setComposing] = useState(false)
  const [group, setGroup] = useState<TemplateLibraryGroup>('all')
  const [createOpen, setCreateOpen] = useState(false)
  const [includeArchived, setIncludeArchived] = useState(false)
  const filters = useMemo<{ value: TemplateLibraryGroup; label: string }[]>(() => [
    { value: 'all', label: t('library.filter_all') },
    { value: 'mine', label: t('library.filter_mine') },
    { value: 'market', label: t('library.filter_market') },
    { value: 'standalone', label: t('library.filter_standalone') },
    { value: 'in_use', label: t('library.filter_in_use') },
  ], [t])
  useEffect(() => {
    if (composing) return
    const timer = setTimeout(() => setQuery(search), 300)
    return () => clearTimeout(timer)
  }, [search, composing])
  const params = useMemo<TemplateLibraryParams>(() => ({ compact: true, page_size: 24, ...(query ? { q: query } : {}), ...(group !== 'all' ? { group } : {}), ...(includeArchived ? { include_archived: true } : {}) }), [query, group, includeArchived])
  const library = useInfiniteQuery({
    queryKey: [...cardTemplateQueryKeys.library(params), 'infinite'],
    initialPageParam: 1,
    queryFn: ({ signal, pageParam }) => fetchTemplateLibrary({ ...params, page: pageParam }, signal),
    getNextPageParam: (last) => last.pagination?.has_more ? last.pagination.page + 1 : undefined,
  })
  const items = library.data?.pages.flatMap((page) => page.items) ?? []
  return <Page size="wide" className="px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
    <PageHeader title={t('library.title')} description={t('library.description')} actions={<Button className="rounded-xl gap-2" onClick={() => setCreateOpen(true)}><Plus className="size-4" />{t('library.create_button')}</Button>} />
    <div className="space-y-3"><SearchInput aria-label={t('library.search_aria')} placeholder={t('library.search_placeholder')} value={search} onChange={(event) => setSearch(event.target.value)} onCompositionStart={() => setComposing(true)} onCompositionEnd={(event) => { setSearch(event.currentTarget.value); setComposing(false) }} /><FilterPillGroup options={filters} value={group} onChange={setGroup} aria-label={t('library.group_aria')} /><label className="flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />{t('library.show_archived')}</label></div>
    {library.isPending ? <PageLoading label={t('library.loading')} /> : library.error && !items.length ? <div className="space-y-3"><PageError error={library.error} /><Button variant="outline" onClick={() => void library.refetch()}>{t('library.retry')}</Button></div> : !items.length ? <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">{t('library.empty')}</p> :
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 3xl:grid-cols-5">{items.map((template) => <Link key={template.id} to={`/card-templates/${encodeURIComponent(template.id)}`} className="rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
        <Card className="h-full p-4 space-y-3 rounded-2xl border-border/80 hover:border-primary/40 transition-colors">
          <div className="space-y-1"><h2 className="font-semibold line-clamp-2 break-words">{template.name}</h2>{template.description && <p className="text-sm text-muted-foreground line-clamp-2 break-words">{template.description}</p>}</div>
          <Badge variant="secondary">{template.origin === 'market_copy' ? t('library.badge_received') : t('library.badge_mine')}</Badge>
          {template.archived_at && <Badge variant="outline">{t('library.badge_archived')}</Badge>}
          <p className="text-xs text-muted-foreground">{template.note_type_count ? t('library.usage_note_types', { count: template.note_type_count }) : t('library.usage_unused')}{template.application_count > template.note_type_count && t('library.usage_attachments', { count: template.application_count })}</p>
          <div className="flex flex-wrap gap-1.5">{template.input_schema.slice(0, 4).map((input) => <code key={input.key} className="rounded-md bg-muted px-1.5 py-0.5 text-xs break-all">{`{{${input.key}}}`}</code>)}{template.input_schema.length > 4 && <span className="text-xs text-muted-foreground">+{template.input_schema.length - 4}</span>}</div>
        </Card>
      </Link>)}</div>}
    {library.isFetchNextPageError && <PageError error={library.error} />}
    {library.hasNextPage && <div className="flex justify-center"><Button variant="outline" disabled={library.isFetchingNextPage} onClick={() => void library.fetchNextPage()}>{commonT(library.isFetchingNextPage ? 'pagination_loading' : 'pagination_load_more')}</Button></div>}
    <CreateTemplateDialog open={createOpen} onOpenChange={setCreateOpen} />
  </Page>
}
