import '@/shared/config/i18n'
import { useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Store } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cardTemplateQueryKeys, fetchTemplateLibrary, type TemplateLibraryGroup, type TemplateLibraryParams } from '@/entities/card-template'
import { Button } from '@/components/ui/button'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { SearchInput, FilterPillGroup } from '@/shared/ui'
import { CreateTemplateDialog } from '../components/CreateTemplateDialog'
import { TemplateCard } from '../components/TemplateCard'

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
    <PageHeader
      title={t('library.title')}
      description={t('library.description')}
      actions={
        <div className="flex items-center gap-2">
          <Button variant="outline" className="rounded-xl gap-2" asChild>
            <Link to="/marketplace/templates">
              <Store className="size-4" />
              {t('library.btn_explore_market')}
            </Link>
          </Button>
          <Button className="rounded-xl gap-2" onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" />
            {t('library.create_button')}
          </Button>
        </div>
      }
    />
    <div className="space-y-3"><SearchInput aria-label={t('library.search_aria')} placeholder={t('library.search_placeholder')} value={search} onChange={(event) => setSearch(event.target.value)} onCompositionStart={() => setComposing(true)} onCompositionEnd={(event) => { setSearch(event.currentTarget.value); setComposing(false) }} /><FilterPillGroup options={filters} value={group} onChange={setGroup} aria-label={t('library.group_aria')} /><label className="flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />{t('library.show_archived')}</label></div>
    {library.isPending ? <PageLoading label={t('library.loading')} /> : library.error && !items.length ? <div className="space-y-3"><PageError error={library.error} /><Button variant="outline" onClick={() => void library.refetch()}>{t('library.retry')}</Button></div> : !items.length ? <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">{t('library.empty')}</p> :
      <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 3xl:grid-cols-5">
        {items.map((template) => (
          <TemplateCard key={template.id} template={template} />
        ))}
      </div>}
    {library.isFetchNextPageError && <PageError error={library.error} />}
    {library.hasNextPage && <div className="flex justify-center"><Button variant="outline" disabled={library.isFetchingNextPage} onClick={() => void library.fetchNextPage()}>{commonT(library.isFetchingNextPage ? 'pagination_loading' : 'pagination_load_more')}</Button></div>}
    <CreateTemplateDialog open={createOpen} onOpenChange={setCreateOpen} />
  </Page>
}
