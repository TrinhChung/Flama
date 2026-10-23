import { useEffect, useMemo, useRef, useState } from 'react'
import { keepPreviousData, useInfiniteQuery } from '@tanstack/react-query'
import { Plus, RotateCcw, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Skeleton } from '@/components/ui/skeleton'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError } from '@/shared/components/PageState'
import { FilterPillGroup, SearchInput } from '@/shared/ui'
import { MarketplaceModeSwitcher } from '@/features/marketplace/components/MarketplaceModeSwitcher'
import { fetchMarketTemplates, templateMarketQueryKeys } from '../api/templateMarketApi'
import { MarketTemplateCard } from '../components/MarketTemplateCard'
import { PublishTemplateDialog } from '../components/PublishTemplateDialog'
import type { MarketTemplateParams, MarketTemplateSort } from '../model/types'

type PricingFilter = 'all' | 'free' | 'paid'
const PAGE_SIZE = 24

function TemplateSkeletonGrid() {
  return (
    <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 8 }).map((_, index) => (
        <Card key={index} className="flex flex-col justify-between overflow-hidden border-border/70 bg-card p-4 sm:p-5 rounded-xl space-y-4 shadow-xs">
          <div className="space-y-3">
            <div className="flex items-center justify-between"><Skeleton className="h-5 w-20 rounded-md" /><Skeleton className="h-5 w-16 rounded-md" /></div>
            <Skeleton className="h-6 w-4/5 rounded-md" />
            <Skeleton className="h-10 w-full rounded-md" />
          </div>
          <Skeleton className="h-9 w-full rounded-lg" />
        </Card>
      ))}
    </div>
  )
}

export function TemplateMarketplacePage() {
  const { t } = useTranslation('marketplace')
  const [queryText, setQueryText] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [category, setCategory] = useState('')
  const [pricing, setPricing] = useState<PricingFilter>('all')
  const [sort, setSort] = useState<MarketTemplateSort>('newest')
  const [publishOpen, setPublishOpen] = useState(false)
  const searchInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(queryText.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [queryText])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const tag = document.activeElement?.tagName
      if (event.key === '/' && tag !== 'INPUT' && tag !== 'TEXTAREA') {
        event.preventDefault()
        searchInputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const params = useMemo<MarketTemplateParams>(() => ({
    q: debouncedQuery || undefined,
    category: category || undefined,
    pricing_mode: pricing === 'all' ? undefined : pricing,
    sort,
  }), [debouncedQuery, category, pricing, sort])

  const catalog = useInfiniteQuery({
    queryKey: templateMarketQueryKeys.catalog(params),
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) => fetchMarketTemplates({ ...params, page: pageParam, page_size: PAGE_SIZE }, signal),
    getNextPageParam: (last) => (last.pagination.has_more ? last.pagination.page + 1 : undefined),
    // Keep results and category pills on screen while new filters load.
    placeholderData: keepPreviousData,
  })
  const items = useMemo(() => catalog.data?.pages.flatMap((page) => page.items) ?? [], [catalog.data])
  const total = catalog.data?.pages[0]?.pagination.total ?? 0
  // Categories always cover the whole listed catalog, independent of filters.
  const categories = catalog.data?.pages[0]?.categories
  const isFiltered = Boolean(debouncedQuery || category || pricing !== 'all')

  const categoryOptions = useMemo(() => [
    { value: '', label: t('templates.filter_all_categories') },
    ...(categories ?? []).map((item) => ({ value: item.name, label: item.name, count: item.count })),
  ], [t, categories])

  const resetFilters = () => {
    setQueryText('')
    setCategory('')
    setPricing('all')
  }

  return (
    <Page size="wide" className="space-y-6 relative px-3 sm:px-6 lg:px-8 py-4 sm:py-6">
      <AmbientBackground intensity="subtle" />
      <PageHeader
        title={t('templates.title')}
        description={t('templates.description')}
        actions={
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-start sm:justify-end">
            <MarketplaceModeSwitcher mode="templates" />
            <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-2.5 sm:px-3 text-xs font-semibold rounded-lg shrink-0">
              <Link to="/card-templates">{t('templates.my_templates')}</Link>
            </Button>
            <Button variant="default" size="sm" onClick={() => setPublishOpen(true)} className="h-8 sm:h-9 px-3 sm:px-3.5 text-xs font-bold rounded-lg shadow-xs shrink-0">
              <Plus className="mr-1 sm:mr-1.5 size-3.5 shrink-0" />
              {t('templates.btn_publish')}
            </Button>
          </div>
        }
      />

      <div className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <SearchInput
            ref={searchInputRef}
            containerClassName="flex-1"
            value={queryText}
            onChange={(event) => setQueryText(event.target.value)}
            isLoading={catalog.isFetching && !catalog.isFetchingNextPage}
            shortcut="/"
            placeholder={t('templates.search_placeholder')}
            aria-label={t('templates.search_placeholder')}
          />
          <div className="flex items-center gap-2">
            <FilterPillGroup<PricingFilter>
              aria-label={t('templates.filter_pricing')}
              value={pricing}
              onChange={setPricing}
              scrollable={false}
              options={[
                { value: 'all', label: t('templates.filter_all') },
                { value: 'free', label: t('card.free', { defaultValue: 'Miễn phí' }) },
                { value: 'paid', label: t('templates.filter_paid') },
              ]}
            />
            <NativeSelect aria-label={t('templates.sort_label')} value={sort} onChange={(event) => setSort(event.target.value as MarketTemplateSort)} className="shrink-0">
              <NativeSelectOption value="newest">{t('templates.sort_newest')}</NativeSelectOption>
              <NativeSelectOption value="popular">{t('templates.sort_popular')}</NativeSelectOption>
              <NativeSelectOption value="price_asc">{t('templates.sort_price_asc')}</NativeSelectOption>
              <NativeSelectOption value="price_desc">{t('templates.sort_price_desc')}</NativeSelectOption>
              <NativeSelectOption value="name">{t('templates.sort_name')}</NativeSelectOption>
            </NativeSelect>
          </div>
        </div>
        {categoryOptions.length > 1 ? (
          <FilterPillGroup<string> aria-label={t('templates.filter_category')} value={category} onChange={setCategory} options={categoryOptions} />
        ) : null}
      </div>

      {!catalog.isPending && items.length ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
          <span className="font-medium">
            {t(isFiltered ? 'templates.results_filtered' : 'templates.results', { count: total })}
          </span>
        </div>
      ) : null}

      {catalog.isPending ? <TemplateSkeletonGrid /> : null}
      {catalog.error && !items.length ? (
        <div className="space-y-3 py-4">
          <PageError error={catalog.error} />
          <div className="flex justify-center">
            <Button variant="outline" size="sm" onClick={() => void catalog.refetch()} className="rounded-lg text-xs font-semibold">
              <RotateCcw className="mr-1.5 size-3.5" /> {t('templates.retry')}
            </Button>
          </div>
        </div>
      ) : null}

      {catalog.data && !items.length ? (
        <div className="py-8">
          <EmptyState
            title={isFiltered ? t('templates.empty_filtered_title') : t('templates.empty_title')}
            description={isFiltered ? t('templates.empty_filtered_desc') : t('templates.empty_desc')}
          />
          <div className="flex justify-center mt-4">
            {isFiltered ? (
              <Button variant="outline" size="sm" onClick={resetFilters} className="rounded-lg text-xs font-semibold">
                <X className="mr-1.5 size-3.5" /> {t('templates.btn_reset')}
              </Button>
            ) : (
              <Button size="sm" onClick={() => setPublishOpen(true)} className="rounded-lg text-xs font-bold shadow-xs">
                <Plus className="mr-1.5 size-3.5" /> {t('templates.btn_publish')}
              </Button>
            )}
          </div>
        </div>
      ) : null}

      {items.length ? (
        <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {items.map((item) => <MarketTemplateCard key={item.id} item={item} />)}
        </div>
      ) : null}

      {catalog.isFetchNextPageError ? <PageError error={catalog.error} /> : null}
      {catalog.hasNextPage ? (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" disabled={catalog.isFetchingNextPage} onClick={() => void catalog.fetchNextPage()} className="rounded-lg text-xs font-semibold">
            {catalog.isFetchingNextPage
              ? t('common:pagination_loading', { defaultValue: 'Đang tải...' })
              : t('common:pagination_load_more', { defaultValue: 'Xem thêm' })}
          </Button>
        </div>
      ) : null}

      <PublishTemplateDialog open={publishOpen} onOpenChange={setPublishOpen} />
    </Page>
  )
}
