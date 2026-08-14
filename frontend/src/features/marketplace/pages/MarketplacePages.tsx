import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  BookOpen,
  CheckCircle,
  Download,
  Eye,
  Filter,
  Layers,
  Search,
  Star,
  X,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
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

  const isFiltered = Boolean(queryText || category)

  return (
    <Page className="space-y-6 relative px-3 sm:px-6 lg:px-8 py-4 sm:py-6">
      <AmbientBackground intensity="subtle" />

      {/* Standardized Flama PageHeader */}
      <PageHeader
        title={mode === 'decks' ? 'Kho Bộ Thẻ (Shared Decks)' : 'Kho Loại Thẻ (Note Types)'}
        description={
          mode === 'decks'
            ? 'Khám phá và cài đặt các bộ thẻ được chia sẻ từ cộng đồng học tiếng Nhật.'
            : 'Các mẫu hiển thị Flashcard chuẩn đẹp, tối ưu hóa giao diện học Kanji, Từ vựng và Ngữ pháp.'
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-xl border border-border/80 bg-muted/30 p-1 shadow-2xs">
              <Button
                variant={mode === 'decks' ? 'default' : 'ghost'}
                size="sm"
                asChild
                className="h-8 px-3 text-xs font-bold rounded-lg transition-all"
              >
                <Link to="/marketplace/decks">
                  <BookOpen className="mr-1.5 size-3.5" />
                  Bộ Thẻ
                </Link>
              </Button>
              <Button
                variant={mode === 'note-types' ? 'default' : 'ghost'}
                size="sm"
                asChild
                className="h-8 px-3 text-xs font-bold rounded-lg transition-all"
              >
                <Link to="/marketplace/note-types">
                  <Layers className="mr-1.5 size-3.5" />
                  Loại Thẻ
                </Link>
              </Button>
            </div>

            <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl">
              <Link to={mode === 'decks' ? '/installed-decks' : '/note-types'}>
                {mode === 'decks' ? 'Deck đã cài' : 'Loại thẻ của tôi'}
              </Link>
            </Button>
          </div>
        }
      />

      {/* Filter & Search Toolbar */}
      <Card className="border-border/80 bg-card shadow-xs rounded-2xl">
        <CardContent className="grid gap-3 p-3.5 sm:p-5 lg:grid-cols-[minmax(0,1fr)_220px_auto] lg:items-end">
          <div className="space-y-1.5">
            <Label htmlFor="marketplace-search" className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <Search className="size-3.5 text-primary" /> Tìm kiếm học liệu
            </Label>
            <div className="relative">
              <Input
                id="marketplace-search"
                className="pl-9 pr-9 text-xs sm:text-sm h-9 sm:h-10 rounded-xl bg-background"
                placeholder="Tên bộ thẻ, tác giả hoặc từ khóa…"
                value={queryText}
                onChange={(event) => setQueryText(event.currentTarget.value)}
              />
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              {queryText ? (
                <button
                  type="button"
                  onClick={() => setQueryText('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-muted text-muted-foreground hover:text-foreground"
                >
                  <X className="size-3.5" />
                </button>
              ) : null}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="marketplace-category" className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <Filter className="size-3.5 text-primary" /> Danh mục
            </Label>
            <NativeSelect
              id="marketplace-category"
              className="w-full text-xs sm:text-sm font-medium h-9 sm:h-10 rounded-xl bg-background"
              value={category}
              onChange={(event) => setCategory(event.currentTarget.value)}
            >
              <NativeSelectOption value="">Tất cả danh mục</NativeSelectOption>
              {categories.map((item) => (
                <NativeSelectOption key={item} value={item}>
                  {item}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Tabs value={view} onValueChange={(value) => setView(value as SortView)} className="w-full sm:w-auto">
              <TabsList className="grid grid-cols-3 w-full sm:w-auto h-9 sm:h-10 p-1 rounded-xl">
                <TabsTrigger value="recommended" className="text-xs font-semibold px-2 sm:px-3 py-1 rounded-lg">Đề xuất</TabsTrigger>
                <TabsTrigger value="newest" className="text-xs font-semibold px-2 sm:px-3 py-1 rounded-lg">Mới nhất</TabsTrigger>
                <TabsTrigger value="popular" className="text-xs font-semibold px-2 sm:px-3 py-1 rounded-lg">Phổ biến</TabsTrigger>
              </TabsList>
            </Tabs>

            {isFiltered ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-9 sm:h-10 px-2.5 text-xs text-muted-foreground hover:text-foreground rounded-xl shrink-0"
                onClick={() => {
                  setQueryText('')
                  setCategory('')
                }}
                title="Xóa bộ lọc"
              >
                <X className="size-4" />
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* States */}
      {marketQuery.isPending ? <PageLoading label="Đang tải dữ liệu marketplace…" /> : null}
      {marketQuery.error ? <PageError error={marketQuery.error} /> : null}
      {marketQuery.data && !marketQuery.data.items.length ? (
        <EmptyState
          title="Không tìm thấy học liệu phù hợp"
          description="Thử thay đổi từ khóa tìm kiếm, chọn danh mục khác hoặc sắp xếp lại danh sách."
        />
      ) : null}

      {/* Item Card Grid */}
      {marketQuery.data?.items.length ? (
        <div className="grid gap-3 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {marketQuery.data.items.map((item) => {
            const itemTitle = item.title || item.name || 'Học liệu không tên'
            const detailUrl =
              mode === 'decks'
                ? `/marketplace/decks/${item.id}`
                : `/marketplace/note-types/${item.id}`
            const authorName =
              item.author?.account_name || item.author?.username || 'Cộng đồng'
            const authorInitial = authorName.charAt(0).toUpperCase()

            return (
              <Card
                key={item.id}
                className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-md rounded-2xl"
              >
                {/* Card Main Info Block */}
                <div className="flex flex-col flex-1 space-y-2.5">
                  {/* Category & Price Badge Row */}
                  <div className="flex items-center justify-between gap-1.5">
                    <Badge variant="secondary" className="px-2 py-0.5 text-xs font-medium rounded-md truncate max-w-[65%]">
                      {item.primary_category || 'Chung'}
                    </Badge>

                    <span
                      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-bold ${
                        item.pricing_mode === 'free'
                          ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                          : 'bg-primary/10 text-primary'
                      }`}
                    >
                      {item.price_display}
                    </span>
                  </div>

                  {/* Title */}
                  <h3 className="text-sm sm:text-base font-bold tracking-tight text-foreground line-clamp-1 group-hover:text-primary transition-colors leading-snug">
                    <Link to={detailUrl} className="hover:underline">
                      {itemTitle}
                    </Link>
                  </h3>

                  {/* Author Row */}
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <div className="flex size-4 sm:size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px]">
                      {authorInitial}
                    </div>
                    <span className="font-medium text-foreground/80 truncate">
                      {authorName}
                    </span>
                  </div>

                  {/* Description */}
                  <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
                    {item.description || 'Chưa có mô tả chi tiết cho học liệu này.'}
                  </p>
                </div>

                {/* Card Bottom Block */}
                <div className="mt-4 pt-3 border-t border-border/60 space-y-3">
                  {/* Rating & Install Stats */}
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1 font-semibold text-foreground">
                      <Star className="size-3.5 fill-amber-400 text-amber-500" />
                      {item.rating_avg.toFixed(1)}
                    </span>
                    <span className="inline-flex items-center gap-1 font-medium">
                      <Download className="size-3.5 text-primary" />
                      <span>{item.install_count.toLocaleString('vi-VN')} lượt</span>
                    </span>
                  </div>

                  {/* Action Button */}
                  {mode === 'decks' && item.installed_deck_id ? (
                    <Button
                      size="sm"
                      asChild
                      className="w-full h-8 sm:h-9 text-xs font-bold rounded-xl shadow-xs"
                    >
                      <Link to={`/study?deck_id=${item.installed_deck_id}`}>
                        <BookOpen className="mr-1.5 size-3.5" />
                        Học ngay
                      </Link>
                    </Button>
                  ) : item.is_installed ? (
                    <Button
                      variant="outline"
                      size="sm"
                      asChild
                      className="w-full h-8 sm:h-9 text-xs font-semibold rounded-xl border-emerald-500/40 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10"
                    >
                      <Link to={detailUrl}>
                        <CheckCircle className="mr-1.5 size-3.5 text-emerald-500" />
                        Đã cài đặt
                      </Link>
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      asChild
                      className="w-full h-8 sm:h-9 text-xs font-semibold rounded-xl hover:bg-primary hover:text-primary-foreground hover:border-primary transition-all"
                    >
                      <Link to={detailUrl}>
                        <Eye className="mr-1.5 size-3.5" />
                        Xem chi tiết
                        <ArrowRight className="ml-1 size-3.5 transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </Button>
                  )}
                </div>
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



