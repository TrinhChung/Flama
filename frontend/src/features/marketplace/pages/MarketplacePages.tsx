import { useEffect, useMemo, useState } from 'react'
import { Search, Star } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import {
  EmptyState,
  PageError,
  PageLoading,
} from '@/shared/components/PageState'

type MarketplaceItem = {
  id: string
  title?: string
  name?: string
  description: string | null
  primary_category: string | null
  rating_avg: number
  install_count: number
  price_display: string
  pricing_mode: string
  is_installed: boolean
  installed_deck_id?: number | null
  author: {
    username?: string
    account_name?: string
  } | null
}

type SortView = 'recommended' | 'newest' | 'popular'

function MarketplacePage({ mode }: { mode: 'decks' | 'note-types' }) {
  const [view, setView] = useState<SortView>('recommended')
  const [queryText, setQueryText] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [category, setCategory] = useState('')
  const endpoint =
    mode === 'decks' ? '/api/shared/decks' : '/api/shared/note-types'
  const sort =
    view === 'recommended' ? 'top_rated' : view === 'newest' ? 'newest' : 'popular'

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(queryText.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [queryText])

  const marketQuery = useQuery({
    queryKey: ['marketplace', mode, debouncedQuery, category, sort],
    queryFn: () =>
      appApi.get<{ items: MarketplaceItem[] }>(endpoint, {
        q: debouncedQuery,
        category,
        sort,
      }),
  })

  const categories = useMemo(
    () =>
      Array.from(
        new Set(
          (marketQuery.data?.items || [])
            .map((item) => item.primary_category)
            .filter((item): item is string => Boolean(item)),
        ),
      ).sort(),
    [marketQuery.data?.items],
  )

  const title = mode === 'decks' ? 'Shared Decks' : 'Shared NoteTypes'

  return (
    <Page>
      <PageHeader
        title={title}
        description="Khám phá học liệu từ cộng đồng và cài bằng logical overlay."
        actions={
          <Button asChild>
            <Link to={mode === 'decks' ? '/installed-decks' : '/note-types'}>
              {mode === 'decks' ? 'Deck đã cài' : 'Loại thẻ của tôi'}
            </Link>
          </Button>
        }
      />

      <Card>
        <CardContent className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_200px_auto] lg:items-end">
          <div className="space-y-2">
            <Label htmlFor="marketplace-search">Tìm trong marketplace</Label>
            <div className="relative">
              <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="marketplace-search"
                className="pl-8"
                placeholder="Tên, tác giả hoặc tag…"
                value={queryText}
                onChange={(event) => setQueryText(event.currentTarget.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="marketplace-category">Danh mục</Label>
            <NativeSelect
              id="marketplace-category"
              className="w-full"
              value={category}
              onChange={(event) => setCategory(event.currentTarget.value)}
            >
              <NativeSelectOption value="">Tất cả</NativeSelectOption>
              {categories.map((item) => (
                <NativeSelectOption key={item} value={item}>{item}</NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <Tabs value={view} onValueChange={(value) => setView(value as SortView)}>
            <TabsList className="w-full lg:w-auto">
              <TabsTrigger value="recommended">Đề xuất</TabsTrigger>
              <TabsTrigger value="newest">Mới nhất</TabsTrigger>
              <TabsTrigger value="popular">Phổ biến</TabsTrigger>
            </TabsList>
          </Tabs>
        </CardContent>
      </Card>

      {marketQuery.isPending ? <PageLoading label="Đang tải marketplace…" /> : null}
      {marketQuery.error ? <PageError error={marketQuery.error} /> : null}
      {marketQuery.data && !marketQuery.data.items.length ? (
        <EmptyState
          title="Không có học liệu phù hợp"
          description="Thử đổi từ khóa, danh mục hoặc cách sắp xếp."
        />
      ) : null}

      {marketQuery.data?.items.length ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {marketQuery.data.items.map((item) => {
            const itemTitle = item.title || item.name || 'Không có tiêu đề'
            const detailUrl =
              mode === 'decks'
                ? `/marketplace/decks/${item.id}`
                : `/marketplace/note-types/${item.id}`
            return (
              <Card className="flex flex-col" key={item.id}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <Badge variant="secondary">
                      {item.primary_category || 'Khác'}
                    </Badge>
                    <span className={item.pricing_mode === 'free'
                      ? 'font-semibold text-emerald-700'
                      : 'font-semibold'}>
                      {item.price_display}
                    </span>
                  </div>
                  <CardTitle>{itemTitle}</CardTitle>
                  <CardDescription>
                    bởi {item.author?.account_name || item.author?.username || 'Cộng đồng'}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex-1 space-y-4">
                  <p className="line-clamp-3 text-sm leading-6 text-muted-foreground">
                    {item.description || 'Chưa có mô tả.'}
                  </p>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="inline-flex items-center gap-1 font-medium">
                      <Star className="size-4 fill-amber-400 text-amber-500" />
                      {item.rating_avg.toFixed(1)}
                    </span>
                    <span className="text-muted-foreground">
                      {item.install_count.toLocaleString('vi-VN')} lượt cài
                    </span>
                  </div>
                </CardContent>
                <CardFooter>
                  {mode === 'decks' && item.installed_deck_id ? (
                    <Button className="w-full" variant="outline" asChild>
                      <Link to={`/study?deck_id=${item.installed_deck_id}`}>
                        Bắt đầu học
                      </Link>
                    </Button>
                  ) : (
                    <Button className="w-full" variant="outline" asChild>
                      <Link to={detailUrl}>
                        {item.is_installed ? 'Xem học liệu đã cài' : 'Xem chi tiết'}
                      </Link>
                    </Button>
                  )}
                </CardFooter>
              </Card>
            )
          })}
        </div>
      ) : null}
    </Page>
  )
}

export function SharedDecksPage() {
  return <MarketplacePage mode="decks" />
}

export function SharedNoteTypesPage() {
  return <MarketplacePage mode="note-types" />
}

export { SharedDeckDetailPage } from './SharedDeckDetailPage'
export { SharedNoteTypeDetailPage } from './SharedNoteTypeDetailPage'

